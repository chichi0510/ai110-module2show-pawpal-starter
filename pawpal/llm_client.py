"""Thin wrapper around the OpenAI SDK.

Centralises model selection, retry, and the `mock=True` switch used by tests
and offline development. Every other module should call `LLMClient` instead
of importing `openai` directly so the rest of the codebase stays test-friendly.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional

from dotenv import load_dotenv

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536

_MAX_RETRIES = 3
_BACKOFF_SEC = 1.5


@dataclass
class ChatUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class ChatResponse:
    text: str
    usage: ChatUsage
    model: str


class LLMClientError(RuntimeError):
    """Raised when the API key is missing or all retries fail."""


class LLMClient:
    """OpenAI client wrapper.

    Parameters
    ----------
    mock:
        When True, no network calls are made. `chat` returns a deterministic
        canned reply and `embed` returns a hash-derived pseudo-vector. Useful
        for unit tests and for working without an API key.
    chat_model / embed_model:
        Override the default OpenAI models if needed.
    """

    def __init__(
        self,
        *,
        mock: bool = False,
        chat_model: Optional[str] = None,
        embed_model: Optional[str] = None,
    ) -> None:
        load_dotenv()
        self.mock = mock
        self.chat_model = chat_model or os.getenv("OPENAI_CHAT_MODEL", DEFAULT_CHAT_MODEL)
        self.embed_model = embed_model or os.getenv("OPENAI_EMBED_MODEL", DEFAULT_EMBED_MODEL)

        self._client = None
        if not self.mock:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise LLMClientError(
                    "OPENAI_API_KEY is not set. Copy `.env.example` to `.env` "
                    "and fill it in, or pass `mock=True` for offline use."
                )
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)

    # ------------------------------------------------------------------ chat

    def chat(
        self,
        messages: List[dict],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        response_format: Optional[dict] = None,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        """Send a chat completion request with simple retry."""
        if self.mock:
            return self._mock_chat(messages)

        model_name = model or self.chat_model
        last_err: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                kwargs: dict = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                }
                if response_format is not None:
                    kwargs["response_format"] = response_format
                if max_tokens is not None:
                    kwargs["max_tokens"] = max_tokens

                resp = self._client.chat.completions.create(**kwargs)
                choice = resp.choices[0].message
                usage = ChatUsage(
                    prompt_tokens=getattr(resp.usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(resp.usage, "completion_tokens", 0) or 0,
                )
                return ChatResponse(text=choice.content or "", usage=usage, model=model_name)
            except Exception as err:
                last_err = err
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_BACKOFF_SEC * (2**attempt))

        raise LLMClientError(f"chat() failed after {_MAX_RETRIES} attempts: {last_err}")

    # ----------------------------------------------------------------- embed

    def embed(self, texts: Iterable[str], *, model: Optional[str] = None) -> List[List[float]]:
        """Return one embedding vector per input string."""
        items = list(texts)
        if not items:
            return []

        if self.mock:
            return [self._mock_embed(t) for t in items]

        model_name = model or self.embed_model
        last_err: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._client.embeddings.create(model=model_name, input=items)
                return [d.embedding for d in resp.data]
            except Exception as err:
                last_err = err
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_BACKOFF_SEC * (2**attempt))

        raise LLMClientError(f"embed() failed after {_MAX_RETRIES} attempts: {last_err}")

    # ---------------------------------------------------------------- mocks

    @staticmethod
    def _mock_chat(messages: List[dict]) -> ChatResponse:
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        text = (
            "[mock answer] I cannot make a real call without an API key. "
            f"Echoing your question for testing: {last_user[:120]}"
        )
        return ChatResponse(text=text, usage=ChatUsage(0, 0), model="mock")

    @staticmethod
    def _mock_embed(text: str) -> List[float]:
        # Deterministic pseudo-vector seeded by text hash so unit tests stay stable.
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Repeat hash bytes until we hit EMBED_DIM, normalise to [-1, 1].
        raw = (digest * ((EMBED_DIM // len(digest)) + 1))[:EMBED_DIM]
        return [(b / 127.5) - 1.0 for b in raw]

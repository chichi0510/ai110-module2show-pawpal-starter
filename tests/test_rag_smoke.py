"""Smoke tests for the RAG pipeline using the mock LLM client.

These verify that the wiring between guardrails / retrieval / generation /
logging is correct without making a real API call. Real model behaviour is
covered later by `eval/run_eval.py`.
"""

from __future__ import annotations

import json

import pytest

from pawpal.llm_client import ChatResponse, ChatUsage, LLMClient
from pawpal.rag import index as index_module
from pawpal.rag.models import Chunk
from pawpal.rag.qa import PetContext, answer
from pawpal.rag import qa as qa_module
from pawpal.rag import retrieve as retrieve_module


@pytest.fixture(scope="module")
def _built_index(tmp_path_factory):
    """Build a mock-embedding index in a *temporary* directory.

    Earlier versions of this fixture built straight into the project-level
    `chroma_db/`, which destroyed any real-embedding index sitting there for
    the eval harness. We now point all index/retrieve module globals at a
    throw-away directory and reset Chroma's client cache so tests are
    completely isolated from the on-disk index used by `eval/run_eval.py`.
    """
    tmp_chroma = tmp_path_factory.mktemp("chroma_test")
    saved_index_dir = index_module.CHROMA_DIR
    saved_marker = index_module.MARKER_FILE
    saved_retrieve_dir = retrieve_module.CHROMA_DIR

    index_module.CHROMA_DIR = tmp_chroma
    index_module.MARKER_FILE = tmp_chroma / ".indexed_at"
    retrieve_module.CHROMA_DIR = tmp_chroma

    retrieve_module.reset_cache()
    n = index_module.build_index(mock=True, verbose=False)
    assert n > 0, "knowledge corpus must yield at least one chunk"
    retrieve_module.reset_cache()
    try:
        yield n
    finally:
        index_module.CHROMA_DIR = saved_index_dir
        index_module.MARKER_FILE = saved_marker
        retrieve_module.CHROMA_DIR = saved_retrieve_dir
        retrieve_module.reset_cache()


@pytest.fixture(autouse=True)
def _isolate_log(tmp_path, monkeypatch):
    """Redirect rag_trace.jsonl into a tmp dir per test."""
    tmp_log = tmp_path / "rag_trace.jsonl"
    monkeypatch.setattr(qa_module, "LOG_FILE", tmp_log)
    monkeypatch.setattr(qa_module, "LOG_DIR", tmp_path)
    yield
    # Optional cleanup; pytest tmp_path handles it.


def _mock_client_with_text(text: str) -> LLMClient:
    """Patch a real LLMClient instance to return a fixed answer."""
    client = LLMClient(mock=True)

    def _chat(messages, **kw):
        return ChatResponse(text=text, usage=ChatUsage(10, 20), model="mock")

    client.chat = _chat  # type: ignore[assignment]
    return client


def test_off_topic_query_blocked_without_llm_call(_built_index, monkeypatch, tmp_path):
    log = tmp_path / "rag_trace.jsonl"
    monkeypatch.setattr(qa_module, "LOG_FILE", log)

    result = answer("What's the stock price of OpenAI?", PetContext())
    assert result.out_of_scope
    assert "pet-care" in result.text.lower()
    assert log.exists()
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["llm"]["skipped"] is True
    assert rec["preflight"]["input_filter"]["reason"] == "off_topic"


def test_toxic_food_input_short_circuits_llm(_built_index, monkeypatch, tmp_path):
    log = tmp_path / "rag_trace.jsonl"
    monkeypatch.setattr(qa_module, "LOG_FILE", log)

    result = answer(
        "Can I give my dog grapes as a treat?",
        PetContext(species="dog", age=3),
    )
    assert result.input_blocked
    assert result.safety_intervened
    assert "kidney" in result.text.lower()
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["llm"]["skipped"] is True
    assert rec["preflight"]["toxic_food"]["blocked"] is True


def test_normal_question_routes_through_retrieval_and_llm(
    _built_index, monkeypatch, tmp_path
):
    log = tmp_path / "rag_trace.jsonl"
    monkeypatch.setattr(qa_module, "LOG_FILE", log)

    fake_answer = "Feed your dog twice a day [source 1]."
    client = _mock_client_with_text(fake_answer)

    result = answer(
        "How often should I feed my dog?",
        PetContext(species="dog", age=3),
        mock=True,
        llm_client=client,
    )
    assert not result.input_blocked
    assert not result.out_of_scope
    assert "[source 1]" in result.text
    assert result.sources, "expected at least one citation"
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["llm"]["skipped"] is False
    assert rec["retrieved"], "trace should record retrieved chunks"


def test_postflight_injects_banner_when_llm_mentions_toxin_unsafely(
    _built_index, monkeypatch, tmp_path
):
    log = tmp_path / "rag_trace.jsonl"
    monkeypatch.setattr(qa_module, "LOG_FILE", log)

    unsafe = "You can give your dog a small piece of chocolate as a treat [source 1]."
    client = _mock_client_with_text(unsafe)

    result = answer(
        "What's a fun treat I can give my dog?",
        PetContext(species="dog", age=3),
        mock=True,
        llm_client=client,
    )
    assert result.safety_intervened
    assert "Safety check" in result.text


def test_low_relevance_short_circuits_with_dont_know(
    _built_index, monkeypatch, tmp_path
):
    log = tmp_path / "rag_trace.jsonl"
    monkeypatch.setattr(qa_module, "LOG_FILE", log)

    def _empty_retrieve(*args, **kwargs):
        return [
            Chunk(
                text="irrelevant",
                source_path="x.md",
                species="general",
                topic="general",
                score=0.05,
            )
        ]

    monkeypatch.setattr(qa_module, "retrieve", _empty_retrieve)

    result = answer("How do I take care of my pet rock?", PetContext(species="dog"))
    assert result.no_retrieval
    assert "verified" in result.text.lower() or "consult a vet" in result.text.lower()

"""Shared pytest fixtures.

The most important one here is `_block_real_openai_calls`, an autouse session
fixture that forces `OPENAI_API_KEY` to the empty string for every test.

Without this guard, a developer who runs `pytest` *after* filling out their
real `.env` (e.g. for `streamlit run app.py` or `python -m eval.run_eval`) will
hit a unit-test path that:

1. instantiates `LLMClient(mock=False)` somewhere down a callstack,
2. `LLMClient.__init__` calls `load_dotenv()` which silently re-reads `.env`,
3. the real key flows into a live `openai.chat.completions.create(...)` call,
4. tests stop being deterministic, take seconds-to-minutes, and (worst case)
   burn tokens for behaviour that is supposed to be exercised against mocks.

We set the env var to `""` rather than `delenv()` because `load_dotenv()` only
populates a key that is *missing* — an empty string still counts as "present"
and is left alone. `LLMClient` then sees `os.getenv("OPENAI_API_KEY")` as
falsy and either raises `LLMClientError` or, in the new self-critique path,
falls back to a mock report.

If a future test legitimately needs a real key it can override this fixture
locally with another `monkeypatch.setenv`.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _block_real_openai_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")

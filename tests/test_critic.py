"""Phase 3 — self-critique behaviour (mock fallback / parse error / capping)."""

from __future__ import annotations

import json

import pytest

from pawpal.critic.self_critique import (
    _validate_against_real_citations,
    review_answer,
    review_plan,
)
from pawpal.critic.models import CriticScoreRAG
from pawpal.llm_client import LLMClient


# ---------------------------------------------------------------- mock fallback


def test_review_answer_with_mock_client_returns_medium_mock_report():
    mock = LLMClient(mock=True)
    report = review_answer(
        query="How often should I feed my dog?",
        answer="Twice a day, source 1.",
        contexts=[{"source_path": "knowledge/dog.md", "text": "feed twice daily"}],
        species="dog",
        age=3,
        client=mock,
    )
    assert report.kind == "rag"
    assert report.is_mock is True
    assert report.level == "medium"
    assert 0.5 <= report.confidence <= 0.9


def test_review_plan_with_mock_client_returns_medium_mock_report():
    mock = LLMClient(mock=True)
    report = review_plan(
        goal="set up a daily routine",
        pet={"name": "Rex", "species": "dog", "age": 3},
        plan_steps=[{"tool": "add_task", "args": {}}],
        added_tasks=[
            {"pet_name": "Rex", "description": "morning walk", "time": "08:00",
             "frequency": "daily", "due_date": "2026-04-30"}
        ],
        client=mock,
    )
    assert report.kind == "plan"
    assert report.is_mock is True
    assert report.level == "medium"


def test_review_answer_no_api_key_falls_back_to_mock(monkeypatch):
    # `_block_real_openai_calls` (conftest.py) already sets OPENAI_API_KEY="";
    # we only need to make sure DISABLE_CRITIC is not on, so this test
    # genuinely exercises the "no key" fallback path.
    monkeypatch.delenv("PAWPAL_DISABLE_CRITIC", raising=False)
    report = review_answer(
        query="...", answer="...", contexts=[], species=None, age=None,
        client=None, mock=False,
    )
    assert report.is_mock is True
    assert "no API key" in report.notes


def test_review_plan_disabled_via_env(monkeypatch):
    monkeypatch.setenv("PAWPAL_DISABLE_CRITIC", "1")
    report = review_plan(
        goal="x", pet={}, plan_steps=[], added_tasks=[], client=None, mock=False,
    )
    assert report.is_mock is True
    assert "PAWPAL_DISABLE_CRITIC" in report.notes


# ---------------------------------------------------------------- parse error


class _BadJsonClient:
    """Fake LLM client that always returns invalid JSON."""

    mock = False

    def chat(self, messages, **kwargs):  # noqa: ARG002
        from pawpal.llm_client import ChatResponse, ChatUsage
        return ChatResponse(text="not json at all", usage=ChatUsage(0, 0), model="fake")


def test_review_answer_parse_error_returns_low_confidence():
    report = review_answer(
        query="q", answer="a", contexts=[{"source_path": "x", "text": "y"}],
        species="dog", age=2, client=_BadJsonClient(),
    )
    assert report.parse_error is not None
    assert report.level == "low"
    assert report.confidence <= 0.5


def test_review_plan_parse_error_returns_low_confidence():
    report = review_plan(
        goal="g", pet={}, plan_steps=[], added_tasks=[], client=_BadJsonClient(),
    )
    assert report.parse_error is not None
    assert report.level == "low"


# ---------------------------------------------------------------- citation cap


def test_validate_caps_grounded_when_critic_hallucinates_source_number():
    score = CriticScoreRAG(
        grounded=0.95, actionable=0.9, safe=0.95,
        found_citations=[1, 2, 99],  # 99 doesn't exist
    )
    fixed = _validate_against_real_citations(
        "[source 1] this is grounded", score, n_contexts=3
    )
    assert fixed.grounded <= 0.5
    assert "auto-capped" in fixed.notes


def test_validate_caps_grounded_when_answer_has_no_source_markers():
    score = CriticScoreRAG(grounded=0.9, actionable=0.9, safe=0.9, found_citations=[])
    fixed = _validate_against_real_citations(
        "feed your dog twice a day", score, n_contexts=2
    )
    assert fixed.grounded <= 0.5
    assert "auto-capped" in fixed.notes


def test_validate_passes_through_when_citations_match():
    score = CriticScoreRAG(grounded=0.9, actionable=0.9, safe=0.9, found_citations=[1, 2])
    fixed = _validate_against_real_citations(
        "claim [source 1] and another [source 2]", score, n_contexts=3
    )
    assert fixed.grounded == pytest.approx(0.9)
    assert fixed.notes == ""


# ---------------------------------------------------------------- valid JSON


class _CannedJsonClient:
    """Fake client that returns a hand-rolled JSON object."""

    mock = False

    def __init__(self, payload: dict):
        self._payload = payload

    def chat(self, messages, **kwargs):  # noqa: ARG002
        from pawpal.llm_client import ChatResponse, ChatUsage
        return ChatResponse(
            text=json.dumps(self._payload), usage=ChatUsage(0, 0), model="fake"
        )


def test_review_answer_with_valid_json_aggregates_correctly():
    payload = {"grounded": 0.9, "actionable": 0.9, "safe": 0.9, "found_citations": [1]}
    report = review_answer(
        query="q",
        answer="claim [source 1]",
        contexts=[{"source_path": "x", "text": "y"}],
        species="dog",
        age=2,
        client=_CannedJsonClient(payload),
    )
    assert report.parse_error is None
    assert report.is_mock is False
    assert report.level == "high"
    assert report.confidence >= 0.85

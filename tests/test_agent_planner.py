"""Unit tests for `pawpal.agent.planner` JSON parsing and mock fallback."""

from __future__ import annotations

import json
from datetime import date

import pytest

from pawpal.agent.models import PlanParseError
from pawpal.agent.planner import _extract_json, _validate_plan_dict, draft_plan
from pawpal.llm_client import ChatResponse, ChatUsage, LLMClient


_TODAY = date(2026, 4, 26)
_PETS = [{"name": "Milo", "species": "dog", "age": 3}]


def _client_returning(text: str) -> LLMClient:
    """Patch a mock LLMClient so its `chat` returns `text` verbatim."""
    client = LLMClient(mock=True)

    def _chat(messages, **kw):
        return ChatResponse(text=text, usage=ChatUsage(7, 11), model="preset")

    client.chat = _chat  # type: ignore[assignment]
    return client


# ---------------------------------------------------------------- _extract_json


def test_extract_json_handles_pure_object():
    assert _extract_json('{"steps": []}') == {"steps": []}


def test_extract_json_strips_code_fences():
    text = '```json\n{"steps": [{"tool": "list_pets", "args": {}}]}\n```'
    out = _extract_json(text)
    assert out["steps"][0]["tool"] == "list_pets"


def test_extract_json_finds_object_inside_prose():
    text = "Here is your plan:\n{\"steps\": []}\nHope that helps."
    assert _extract_json(text) == {"steps": []}


def test_extract_json_raises_on_garbage():
    with pytest.raises(PlanParseError):
        _extract_json("not json at all, sorry")


def test_extract_json_raises_on_empty():
    with pytest.raises(PlanParseError):
        _extract_json("   ")


# ---------------------------------------------------------------- _validate_plan_dict


def test_validate_plan_dict_accepts_well_formed_payload():
    payload = {
        "summary": "test",
        "steps": [
            {"tool": "list_pets", "args": {}, "rationale": "warm up"},
            {
                "tool": "add_task",
                "args": {
                    "pet_name": "Milo",
                    "description": "Walk",
                    "time_hhmm": "08:00",
                    "frequency": "daily",
                    "due_date_iso": "2026-04-26",
                },
            },
        ],
    }
    plan = _validate_plan_dict(payload, goal="Plan a day")
    assert plan.goal == "Plan a day"
    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "list_pets"
    assert plan.steps[1].args["pet_name"] == "Milo"


def test_validate_plan_dict_rejects_unknown_tool():
    with pytest.raises(PlanParseError):
        _validate_plan_dict({"steps": [{"tool": "make_coffee", "args": {}}]}, goal="g")


def test_validate_plan_dict_rejects_missing_steps():
    with pytest.raises(PlanParseError):
        _validate_plan_dict({"summary": "no steps"}, goal="g")


def test_validate_plan_dict_rejects_bad_args_shape():
    with pytest.raises(PlanParseError):
        _validate_plan_dict(
            {"steps": [{"tool": "list_pets", "args": "not-an-object"}]}, goal="g"
        )


# ---------------------------------------------------------------- draft_plan


def test_draft_plan_with_injected_client_parses_json_reply():
    payload = {
        "summary": "two steps",
        "steps": [
            {"tool": "list_pets", "args": {}, "rationale": "see what we have"},
            {
                "tool": "add_task",
                "args": {
                    "pet_name": "Milo",
                    "description": "Evening walk",
                    "time_hhmm": "19:00",
                    "frequency": "daily",
                    "due_date_iso": "2026-04-26",
                },
            },
        ],
    }
    client = _client_returning(json.dumps(payload))
    plan = draft_plan(goal="Walk Milo daily", pets=_PETS, today=_TODAY, llm_client=client)
    assert plan.summary == "two steps"
    assert plan.steps[1].tool == "add_task"


def test_draft_plan_with_injected_garbage_falls_back_to_mock():
    client = _client_returning("sorry I can't help")
    plan = draft_plan(goal="Plan something", pets=_PETS, today=_TODAY, llm_client=client)
    # Mock fallback always returns at least 5 add_task steps + 1 rag_lookup.
    assert len(plan.steps) >= 5
    assert any(s.tool == "add_task" for s in plan.steps)


def test_draft_plan_default_mock_path_is_deterministic():
    plan_a = draft_plan(goal="Plan first week", pets=_PETS, today=_TODAY, mock=True)
    plan_b = draft_plan(goal="Plan first week", pets=_PETS, today=_TODAY, mock=True)
    assert [s.tool for s in plan_a.steps] == [s.tool for s in plan_b.steps]
    assert [s.args for s in plan_a.steps] == [s.args for s in plan_b.steps]


def test_draft_plan_mock_replan_uses_different_clock_times():
    # The mock fallback shifts clock times when the prev trace mentions a conflict.
    base = draft_plan(goal="Plan first week", pets=_PETS, today=_TODAY, mock=True)
    replanned = draft_plan(
        goal="Plan first week",
        pets=_PETS,
        today=_TODAY,
        mock=True,
        prev_trace_summary="step 0 [add_task] FAIL: ... time conflict ...",
    )
    base_times = [s.args.get("time_hhmm") for s in base.steps if s.tool == "add_task"]
    replanned_times = [s.args.get("time_hhmm") for s in replanned.steps if s.tool == "add_task"]
    assert base_times != replanned_times

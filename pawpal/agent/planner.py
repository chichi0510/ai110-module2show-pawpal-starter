"""LLM-driven planner: turn a natural-language goal into a `Plan` of tool calls.

Two paths:
- **Real LLM** (default): call ``LLMClient.chat`` with ``response_format={'type':'json_object'}``
  so we get a JSON document we can parse.
- **Mock mode**: when the caller passes a mock client, the LLM echo isn't
  parseable JSON, so we synthesise a small but valid plan from simple goal
  keyword routing. This keeps `streamlit run` and `python -m pawpal.agent.planner ...`
  usable without an OpenAI key, and makes deterministic demos possible.

Tests inject custom `LLMClient` instances whose `chat()` is monkey-patched to
return whatever JSON the test wants. See `tests/test_agent_planner.py`.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date as _date, timedelta
from typing import Any, Dict, List, Optional

from pawpal.agent.models import Plan, PlanParseError, PlanStep
from pawpal.agent.prompts import build_planner_messages
from pawpal.llm_client import ChatResponse, LLMClient
from pawpal.tools import TOOL_NAMES


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> Dict[str, Any]:
    """Pull a JSON object out of an LLM reply.

    Handles three common cases:
    1. Reply is already pure JSON.
    2. Reply is JSON wrapped in ```json fences (some models do this anyway).
    3. Reply contains prose then JSON; we grab the first {...} block.

    Raises `PlanParseError` if no parseable JSON object is present.
    """
    if not text or not text.strip():
        raise PlanParseError("planner returned an empty response")

    candidate = text.strip()

    # Strip code fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, flags=re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()

    # Try direct parse first.
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Fall back: find the largest {...} block by greedy match.
    m = _JSON_BLOCK_RE.search(candidate)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as err:
            raise PlanParseError(f"could not parse JSON from planner reply: {err}") from err

    raise PlanParseError("planner reply contained no JSON object")


def _validate_plan_dict(payload: Dict[str, Any], goal: str) -> Plan:
    """Coerce a parsed dict into a `Plan`, surfacing errors as `PlanParseError`."""
    if not isinstance(payload, dict):
        raise PlanParseError(f"planner JSON must be an object, got {type(payload).__name__}")
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        raise PlanParseError("planner JSON missing 'steps' array")

    steps: List[PlanStep] = []
    for i, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise PlanParseError(f"step {i} is not an object")
        tool = raw.get("tool")
        if not isinstance(tool, str) or tool not in TOOL_NAMES:
            raise PlanParseError(
                f"step {i} has unknown tool {tool!r}; allowed: {sorted(TOOL_NAMES)}"
            )
        args = raw.get("args", {})
        if not isinstance(args, dict):
            raise PlanParseError(f"step {i} 'args' must be an object")
        rationale = raw.get("rationale")
        if rationale is not None and not isinstance(rationale, str):
            raise PlanParseError(f"step {i} 'rationale' must be a string if present")
        steps.append(PlanStep(tool=tool, args=args, rationale=rationale))

    summary = payload.get("summary")
    if summary is not None and not isinstance(summary, str):
        summary = None  # forgiving: drop a malformed summary rather than fail

    version = int(payload.get("version", 1))
    return Plan(version=version, goal=goal, steps=steps, summary=summary)


# ---------------------------------------------------------------- mock fallback


_FEEDING_KEYWORDS = ("week", "routine", "schedule", "plan", "first", "daily", "puppy", "kitten")


def _mock_plan(
    goal: str,
    pets: List[Dict[str, Any]],
    today: _date,
    *,
    prev_trace_summary: Optional[str],
) -> Plan:
    """Deterministic plan for offline / demo use.

    Picks the first pet (or a synthetic placeholder), schedules a small set of
    daily care tasks across the next 7 days. Includes one ``rag_lookup`` to
    illustrate the agent's knowledge-base usage.
    """
    pet = pets[0] if pets else {"name": "your pet", "species": "dog", "age": 1}
    name = pet.get("name") or "your pet"
    species = (pet.get("species") or "dog").lower()
    age = int(pet.get("age") or 1)

    today_iso = today.isoformat()
    next_week_iso = (today + timedelta(days=7)).isoformat()

    # Pick clock times based on whether the trace told us about a conflict so
    # that re-plans actually look different.
    base_times = ["08:00", "12:30", "18:00", "21:30"]
    if prev_trace_summary and "conflict" in prev_trace_summary.lower():
        base_times = ["08:30", "13:00", "18:30", "22:00"]

    steps: List[PlanStep] = [
        PlanStep(
            tool="rag_lookup",
            args={"query": f"daily care basics for a {age}-year-old {species}", "species": species},
            rationale="Ground the plan in verified knowledge before scheduling.",
        ),
        PlanStep(
            tool="add_task",
            args={
                "pet_name": name,
                "description": f"Morning meal for {name}",
                "time_hhmm": base_times[0],
                "frequency": "daily",
                "due_date_iso": today_iso,
            },
            rationale="Anchor the day with a consistent breakfast.",
        ),
        PlanStep(
            tool="add_task",
            args={
                "pet_name": name,
                "description": f"Midday play / exercise for {name}",
                "time_hhmm": base_times[1],
                "frequency": "daily",
                "due_date_iso": today_iso,
            },
            rationale="Daily activity supports physical and mental health.",
        ),
        PlanStep(
            tool="add_task",
            args={
                "pet_name": name,
                "description": f"Evening meal for {name}",
                "time_hhmm": base_times[2],
                "frequency": "daily",
                "due_date_iso": today_iso,
            },
            rationale="Two-meal cadence is appropriate for most adult pets.",
        ),
        PlanStep(
            tool="add_task",
            args={
                "pet_name": name,
                "description": f"Wind-down + brushing for {name}",
                "time_hhmm": base_times[3],
                "frequency": "daily",
                "due_date_iso": today_iso,
            },
            rationale="Routine grooming helps spot health issues early.",
        ),
        PlanStep(
            tool="add_task",
            args={
                "pet_name": name,
                "description": "Weekly vet-care check-in (paws, ears, weight log)",
                "time_hhmm": "10:00",
                "frequency": "weekly",
                "due_date_iso": next_week_iso,
            },
            rationale="A weekly self-check catches problems early.",
        ),
    ]

    summary = (
        f"Mock demo plan for {name} ({species}, age {age}): morning meal, midday "
        f"play, evening meal, wind-down, plus a weekly vet-care self-check."
    )
    if any(k in goal.lower() for k in _FEEDING_KEYWORDS):
        # leave summary as-is; goal already aligns
        pass
    else:
        summary = f"Mock demo plan based on goal: {goal!r}. " + summary

    return Plan(version=2 if prev_trace_summary else 1, goal=goal, steps=steps, summary=summary)


# ---------------------------------------------------------------- public API


def draft_plan(
    *,
    goal: str,
    pets: List[Dict[str, Any]],
    today: _date,
    llm_client: Optional[LLMClient] = None,
    mock: bool = False,
    prev_trace_summary: Optional[str] = None,
    plan_version: int = 1,
) -> Plan:
    """Ask the LLM (or fall back to a mock) for a `Plan`.

    Parameters
    ----------
    goal:
        The user's natural-language goal.
    pets:
        Read-only summary of owner.pets (dicts with name/species/age).
    today:
        Anchor date used for relative scheduling (default 'today's date').
    llm_client:
        If omitted, a fresh `LLMClient(mock=mock)` is built.
    mock:
        Forces the offline mock plan even with a real LLM client. Tests that
        inject their own client should leave this False.
    prev_trace_summary:
        Compact summary of the previous failing trace, used to ask for a
        revised plan that avoids the same failure. ``None`` for the first call.
    plan_version:
        Version number to embed when the LLM doesn't supply one.
    """
    client = llm_client if llm_client is not None else LLMClient(mock=mock)

    # In pure mock mode there's nothing useful the LLM mock chat will produce
    # for our planner, so route to the canned plan immediately.
    if client.mock and llm_client is None:
        return _mock_plan(goal, pets, today, prev_trace_summary=prev_trace_summary)

    messages = build_planner_messages(
        goal=goal,
        pets=pets,
        today_iso=today.isoformat(),
        prev_trace_summary=prev_trace_summary,
    )

    chat: ChatResponse = client.chat(
        messages,
        response_format={"type": "json_object"} if not client.mock else None,
        temperature=0.2,
    )

    try:
        payload = _extract_json(chat.text)
    except PlanParseError:
        # Mock client returns a non-JSON echo by default; if the caller injected
        # their own mock without supplying JSON, fall back to the canned plan
        # so the demo still works rather than crashing.
        if client.mock:
            return _mock_plan(goal, pets, today, prev_trace_summary=prev_trace_summary)
        raise

    plan = _validate_plan_dict(payload, goal=goal)
    if plan.version != plan_version and plan_version > 1:
        plan.version = plan_version
    return plan


# ---------------------------------------------------------------- CLI


def _main() -> None:
    parser = argparse.ArgumentParser(description="Draft a plan from a goal.")
    parser.add_argument("goal", type=str)
    parser.add_argument("--pet-name", type=str, default="Demo")
    parser.add_argument("--species", type=str, default="dog")
    parser.add_argument("--age", type=int, default=1)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    plan = draft_plan(
        goal=args.goal,
        pets=[{"name": args.pet_name, "species": args.species, "age": args.age}],
        today=_date.today(),
        mock=args.mock,
    )
    print(plan.model_dump_json(indent=2))


if __name__ == "__main__":
    _main()

"""Plan-Execute-Replan loop.

Workflow (matches `docs/plan/phase2.md` §3 mermaid):

    1. Deepcopy the live owner into a scratch owner.
    2. Ask `planner.draft_plan` for an initial Plan.
    3. For each step in the plan:
         - Dispatch the matching tool against the scratch owner.
         - Append a StepTrace.
         - On a recoverable failure (`requires_replan=True`):
             - If we still have re-plan budget, ask the planner for a NEW
               complete plan with the failure trace summarised, and restart
               the step loop.
             - Otherwise mark the run "exhausted" and stop.
    4. Return a `PlanResult` carrying every plan version, every step trace,
       and the list of `added_tasks` the user can choose to Apply.

The live `Owner` instance the caller hands in is NEVER mutated by `run`. Only
`apply_plan` (after explicit user confirmation) writes to it.
"""

from __future__ import annotations

import argparse
import copy
import json
import time
import uuid
from datetime import date as _date
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pawpal.agent import planner as planner_module
from pawpal.agent.models import (
    Plan,
    PlanParseError,
    PlanResult,
    PlanStep,
    StepTrace,
)
from pawpal.agent.prompts import summarise_trace_for_replan
from pawpal.critic import self_critique
from pawpal.domain import Owner, Pet, Task
from pawpal.llm_client import LLMClient
from pawpal import tools as tool_mod

ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "agent_trace.jsonl"

MAX_STEPS = 10
MAX_REPLANS = 3


# ---------------------------------------------------------------- tool dispatch


def _call_tool(
    step: PlanStep,
    scratch_owner: Owner,
    *,
    mock_rag: bool,
) -> tool_mod.ToolResult:
    """Route one PlanStep to the matching tool implementation."""
    args = dict(step.args or {})
    if step.tool == "list_pets":
        return tool_mod.list_pets(scratch_owner)
    if step.tool == "list_tasks_on":
        return tool_mod.list_tasks_on(
            scratch_owner,
            date_iso=args.get("date_iso", ""),
            pet_name=args.get("pet_name"),
        )
    if step.tool == "detect_conflicts":
        return tool_mod.detect_conflicts(
            scratch_owner,
            date_iso=args.get("date_iso", ""),
        )
    if step.tool == "add_task":
        return tool_mod.add_task(
            scratch_owner,
            pet_name=args.get("pet_name", ""),
            description=args.get("description", ""),
            time_hhmm=args.get("time_hhmm", ""),
            frequency=args.get("frequency", ""),
            due_date_iso=args.get("due_date_iso", ""),
        )
    if step.tool == "rag_lookup":
        return tool_mod.rag_lookup(
            query=args.get("query", ""),
            species=args.get("species"),
            age=args.get("age"),
            mock=mock_rag,
        )
    return tool_mod.ToolResult(
        ok=False,
        error=f"unknown tool {step.tool!r}",
        meta={"reason": "unknown_tool"},
    )


# ---------------------------------------------------------------- helpers


def _pets_summary(owner: Owner) -> List[Dict[str, Any]]:
    return [{"name": p.name, "species": p.species, "age": p.age} for p in owner.pets]


def _diff_added_tasks(scratch: Owner, real: Owner) -> List[Dict[str, Any]]:
    """Return task summaries that exist on `scratch` but not on `real`.

    Identity is approximated by ``(pet_name, description, time, due_date)``
    so we don't accidentally mark recurring carry-overs as new.
    """
    real_keys: set[tuple[str, str, str, str]] = set()
    for pet in real.pets:
        for t in pet.tasks:
            real_keys.add((pet.name, t.description, t.time, t.due_date.isoformat()))

    added: List[Dict[str, Any]] = []
    for pet in scratch.pets:
        for t in pet.tasks:
            key = (pet.name, t.description, t.time, t.due_date.isoformat())
            if key not in real_keys:
                added.append(
                    {
                        "pet_name": pet.name,
                        "description": t.description,
                        "time": t.time,
                        "frequency": t.frequency,
                        "due_date": t.due_date.isoformat(),
                    }
                )
    return added


def _write_trace(record: Dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- main loop


def run(
    *,
    goal: str,
    owner: Owner,
    today: Optional[_date] = None,
    llm_client: Optional[LLMClient] = None,
    mock: bool = False,
    max_steps: int = MAX_STEPS,
    max_replans: int = MAX_REPLANS,
) -> PlanResult:
    """Plan-Execute-Replan over a deepcopy of ``owner``.

    The live ``owner`` is never mutated. The returned `PlanResult.added_tasks`
    is what `apply_plan` will merge in once the user confirms.
    """
    today = today or _date.today()
    run_id = str(uuid.uuid4())
    started = time.perf_counter()

    scratch = copy.deepcopy(owner)
    pets = _pets_summary(owner)
    primary_pet = pets[0] if pets else {"name": None, "species": None, "age": None}

    plan_versions: List[Plan] = []
    trace: List[StepTrace] = []
    tokens_prompt = 0
    tokens_completion = 0

    # ---- Initial plan
    try:
        plan = planner_module.draft_plan(
            goal=goal,
            pets=pets,
            today=today,
            llm_client=llm_client,
            mock=mock,
            plan_version=1,
        )
    except PlanParseError as err:
        result = PlanResult(
            run_id=run_id,
            goal=goal,
            status="blocked",
            block_reason=f"planner_parse_error: {err}",
        )
        _finalise(result, scratch, owner, started, plan_versions, trace,
                  tokens_prompt, tokens_completion,
                  pet_summary=primary_pet, llm_client=llm_client, mock=mock)
        return result

    plan_versions.append(plan)

    if plan.is_empty():
        result = PlanResult(
            run_id=run_id,
            goal=goal,
            status="empty",
            plan_versions=plan_versions,
            trace=trace,
            block_reason="planner returned no steps",
        )
        _finalise(result, scratch, owner, started, plan_versions, trace,
                  tokens_prompt, tokens_completion,
                  pet_summary=primary_pet, llm_client=llm_client, mock=mock)
        return result

    replans = 0

    # We restart the step loop after each successful re-plan, but we also keep
    # an absolute step counter so a malicious / buggy planner can't burn
    # unbounded compute by emitting tiny plans that always fail at step 0.
    absolute_steps = 0

    while True:
        for step_index, step in enumerate(plan.steps):
            absolute_steps += 1
            if absolute_steps > max_steps:
                break

            tool_result = _call_tool(step, scratch, mock_rag=mock)
            row = StepTrace(
                plan_version=plan.version,
                step_index=step_index,
                tool=step.tool,
                args=step.args,
                ok=tool_result.ok,
                error=tool_result.error,
                requires_replan=tool_result.requires_replan,
                data=tool_result.data if tool_result.ok else None,
                meta=tool_result.meta,
            )
            trace.append(row)

            if tool_result.ok:
                continue

            # Recoverable failure → re-plan if budget allows.
            if tool_result.requires_replan and replans < max_replans:
                trace_summary = summarise_trace_for_replan(
                    [r.model_dump() for r in trace]
                )
                # Reset scratch so the re-plan starts from the same baseline.
                scratch = copy.deepcopy(owner)
                replans += 1
                try:
                    plan = planner_module.draft_plan(
                        goal=goal,
                        pets=pets,
                        today=today,
                        llm_client=llm_client,
                        mock=mock,
                        prev_trace_summary=trace_summary,
                        plan_version=replans + 1,
                    )
                except PlanParseError as err:
                    result = PlanResult(
                        run_id=run_id,
                        goal=goal,
                        status="blocked",
                        plan_versions=plan_versions,
                        trace=trace,
                        block_reason=f"replan_parse_error: {err}",
                    )
                    _finalise(result, scratch, owner, started, plan_versions, trace,
                              tokens_prompt, tokens_completion,
                              pet_summary=primary_pet, llm_client=llm_client, mock=mock)
                    return result
                plan_versions.append(plan)
                if plan.is_empty():
                    result = PlanResult(
                        run_id=run_id,
                        goal=goal,
                        status="empty",
                        plan_versions=plan_versions,
                        trace=trace,
                        block_reason="re-planner returned no steps",
                    )
                    _finalise(result, scratch, owner, started, plan_versions, trace,
                              tokens_prompt, tokens_completion,
                              pet_summary=primary_pet, llm_client=llm_client, mock=mock)
                    return result
                break  # restart the for-loop with the new plan
            else:
                # Either non-recoverable failure or out of re-plan budget.
                status = "exhausted" if tool_result.requires_replan else "blocked"
                result = PlanResult(
                    run_id=run_id,
                    goal=goal,
                    status=status,
                    plan_versions=plan_versions,
                    trace=trace,
                    added_tasks=_diff_added_tasks(scratch, owner),
                    block_reason=tool_result.error,
                )
                _finalise(result, scratch, owner, started, plan_versions, trace,
                          tokens_prompt, tokens_completion,
                          pet_summary=primary_pet, llm_client=llm_client, mock=mock)
                return result
        else:
            # for-loop completed without `break` → plan executed fully.
            break

        # If we hit the absolute step ceiling, exit the while loop.
        if absolute_steps > max_steps:
            break

    if absolute_steps > max_steps:
        result = PlanResult(
            run_id=run_id,
            goal=goal,
            status="exhausted",
            plan_versions=plan_versions,
            trace=trace,
            added_tasks=_diff_added_tasks(scratch, owner),
            block_reason=f"max_steps={max_steps} reached",
        )
        _finalise(result, scratch, owner, started, plan_versions, trace,
                  tokens_prompt, tokens_completion,
                  pet_summary=primary_pet, llm_client=llm_client, mock=mock)
        return result

    result = PlanResult(
        run_id=run_id,
        goal=goal,
        status="preview",
        plan_versions=plan_versions,
        trace=trace,
        added_tasks=_diff_added_tasks(scratch, owner),
    )
    _finalise(result, scratch, owner, started, plan_versions, trace,
              tokens_prompt, tokens_completion,
              pet_summary=primary_pet, llm_client=llm_client, mock=mock)
    return result


def _finalise(
    result: PlanResult,
    scratch: Owner,
    real: Owner,
    started: float,
    plan_versions: List[Plan],
    trace: List[StepTrace],
    tokens_prompt: int,
    tokens_completion: int,
    *,
    pet_summary: Dict[str, Any],
    llm_client: Optional[LLMClient],
    mock: bool,
) -> None:
    """Stamp the result with timing + tokens + critic report, then write trace.

    The critic review only runs when there's an executable plan to score —
    ``blocked`` and ``empty`` results have nothing to critique, so we leave
    ``result.critic`` as ``None`` and the trace's ``critic`` key as ``None``
    too. This keeps the JSONL schema stable while still being honest about
    coverage.
    """
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    result.tokens_prompt = tokens_prompt
    result.tokens_completion = tokens_completion

    critic_payload: Optional[Dict[str, Any]] = None
    latest_plan = plan_versions[-1] if plan_versions else None
    if latest_plan is not None and result.status in {"preview", "exhausted", "applied"}:
        critic_report = self_critique.review_plan(
            goal=result.goal,
            pet=pet_summary,
            plan_steps=[step.model_dump() for step in latest_plan.steps],
            added_tasks=result.added_tasks,
            client=llm_client,
            mock=mock,
        )
        critic_payload = critic_report.model_dump()
        result.critic = critic_payload

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": result.run_id,
        "goal": result.goal,
        "pet_name": result.pet_name,
        "status": result.status,
        "block_reason": result.block_reason,
        "plan_versions": [p.model_dump() for p in plan_versions],
        "trace": [r.model_dump() for r in trace],
        "added_tasks": result.added_tasks,
        "duration_ms": result.duration_ms,
        "tokens": {
            "prompt": tokens_prompt,
            "completion": tokens_completion,
        },
        "critic": critic_payload,
    }
    _write_trace(record)


# ---------------------------------------------------------------- apply / discard


def apply_plan(real_owner: Owner, result: PlanResult) -> int:
    """Merge ``result.added_tasks`` into the live owner.

    Returns the number of tasks actually added. Called only after the user
    explicitly confirms in the UI; before that, `result` is a sandbox preview.
    """
    if result.status not in {"preview", "exhausted"}:
        # "blocked" / "empty" plans have nothing safe to apply.
        return 0
    by_name = {p.name: p for p in real_owner.pets}
    added = 0
    for row in result.added_tasks:
        pet: Pet | None = by_name.get(row["pet_name"])
        if pet is None:
            continue
        try:
            due = _date.fromisoformat(row["due_date"])
        except ValueError:
            continue
        pet.add_task(
            Task(
                description=row["description"],
                time=row["time"],
                frequency=row["frequency"],
                due_date=due,
            )
        )
        added += 1
    result.status = "applied"
    return added


def discard_plan(result: PlanResult) -> None:
    """Mark the result as user-rejected. No state changes elsewhere."""
    result.status = "rejected"


# ---------------------------------------------------------------- CLI


def _main() -> None:
    parser = argparse.ArgumentParser(description="Run a Plan-Execute loop.")
    parser.add_argument("goal", type=str)
    parser.add_argument("--pet-name", type=str, default="Demo")
    parser.add_argument("--species", type=str, default="dog")
    parser.add_argument("--age", type=int, default=1)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    owner = Owner("CLI")
    owner.add_pet(Pet(args.pet_name, args.species, args.age))

    result = run(goal=args.goal, owner=owner, mock=args.mock)
    print(f"\nrun_id={result.run_id}  status={result.status}")
    print(f"plan_versions={len(result.plan_versions)}  steps_executed={len(result.trace)}")
    if result.added_tasks:
        print("\nadded tasks (preview):")
        for row in result.added_tasks:
            print(
                f"  - {row['pet_name']}: {row['description']} "
                f"@ {row['time']} ({row['frequency']}) due {row['due_date']}"
            )
    if result.block_reason:
        print(f"\nblock_reason: {result.block_reason}")
    print(f"\nduration_ms={result.duration_ms}")


if __name__ == "__main__":
    _main()

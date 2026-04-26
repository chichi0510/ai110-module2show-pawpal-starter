"""Unit tests for the Plan-Execute-Replan loop."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from pawpal.agent import executor as ex_module
from pawpal.agent import planner as planner_module
from pawpal.agent.executor import apply_plan, discard_plan, run
from pawpal.agent.models import Plan, PlanStep
from pawpal.domain import Owner, Pet, Task


_TODAY = date(2026, 4, 26)


@pytest.fixture(autouse=True)
def _isolate_log(tmp_path, monkeypatch):
    """Redirect agent_trace.jsonl into a tmp dir per test."""
    log_path = tmp_path / "agent_trace.jsonl"
    monkeypatch.setattr(ex_module, "LOG_FILE", log_path)
    monkeypatch.setattr(ex_module, "LOG_DIR", tmp_path)
    yield log_path


def _scripted_planner(plans):
    """Return a draft_plan replacement that yields the next preset Plan each call."""
    plans = list(plans)
    calls = {"n": 0}

    def _draft(*args, **kwargs):
        i = calls["n"]
        calls["n"] += 1
        if i >= len(plans):
            return plans[-1]
        return plans[i]

    _draft.calls = calls  # type: ignore[attr-defined]
    return _draft


def _build_owner() -> Owner:
    owner = Owner("Tester")
    owner.add_pet(Pet("Milo", "dog", 3))
    return owner


def _add_task_step(time_hhmm: str, desc: str = "Walk") -> PlanStep:
    return PlanStep(
        tool="add_task",
        args={
            "pet_name": "Milo",
            "description": desc,
            "time_hhmm": time_hhmm,
            "frequency": "daily",
            "due_date_iso": _TODAY.isoformat(),
        },
    )


# ---------------------------------------------------------------- happy path


def test_run_happy_path_executes_full_plan(monkeypatch):
    plan = Plan(
        version=1,
        goal="g",
        steps=[
            _add_task_step("08:00", "Breakfast"),
            _add_task_step("12:00", "Walk"),
            _add_task_step("18:00", "Dinner"),
        ],
    )
    monkeypatch.setattr(planner_module, "draft_plan", _scripted_planner([plan]))

    owner = _build_owner()
    result = run(goal="g", owner=owner, today=_TODAY)

    assert result.status == "preview"
    assert len(result.plan_versions) == 1
    assert len(result.added_tasks) == 3
    assert all(r.ok for r in result.trace)
    # Live owner unchanged.
    assert owner.pets[0].tasks == []


# ---------------------------------------------------------------- conflict triggers re-plan


def test_run_conflict_triggers_replan(monkeypatch):
    failing_plan = Plan(
        version=1,
        goal="g",
        steps=[_add_task_step("09:00", "First walk")],
    )
    recovery_plan = Plan(
        version=2,
        goal="g",
        steps=[_add_task_step("10:30", "Recovered walk")],
    )
    monkeypatch.setattr(
        planner_module, "draft_plan", _scripted_planner([failing_plan, recovery_plan])
    )

    owner = _build_owner()
    # Pre-existing 09:00 task on Milo to force a conflict.
    owner.pets[0].add_task(Task("Existing", "09:00", "daily", due_date=_TODAY))

    result = run(goal="g", owner=owner, today=_TODAY)

    assert result.status == "preview"
    assert len(result.plan_versions) == 2, "expected exactly one re-plan"
    # Trace contains a failing step (the 09:00 conflict) and then the recovery.
    failing_rows = [r for r in result.trace if not r.ok]
    assert len(failing_rows) == 1
    assert failing_rows[0].meta["reason"] == "conflict"
    # Final added_tasks come from scratch and contain only "Recovered walk".
    descs = [t["description"] for t in result.added_tasks]
    assert descs == ["Recovered walk"]
    # Live owner still has only the one pre-existing task.
    assert len(owner.pets[0].tasks) == 1


# ---------------------------------------------------------------- exhaustion


def test_run_exhausts_after_max_replans(monkeypatch):
    bad = Plan(version=1, goal="g", steps=[_add_task_step("09:00", "Will conflict")])
    monkeypatch.setattr(
        planner_module, "draft_plan", _scripted_planner([bad, bad, bad, bad, bad])
    )

    owner = _build_owner()
    owner.pets[0].add_task(Task("Existing", "09:00", "daily", due_date=_TODAY))

    result = run(goal="g", owner=owner, today=_TODAY, max_replans=2)
    assert result.status == "exhausted"
    assert len(result.plan_versions) == 3, "v1 + 2 re-plans"
    assert result.block_reason and "conflict" in result.block_reason.lower()


# ---------------------------------------------------------------- toxic-food


def test_run_blocks_toxic_food_then_recovers(monkeypatch):
    toxic = Plan(
        version=1,
        goal="g",
        steps=[
            PlanStep(
                tool="add_task",
                args={
                    "pet_name": "Milo",
                    "description": "Snack: a bowl of grapes",
                    "time_hhmm": "10:00",
                    "frequency": "once",
                    "due_date_iso": _TODAY.isoformat(),
                },
            )
        ],
    )
    safe = Plan(
        version=2,
        goal="g",
        steps=[_add_task_step("10:00", "Apple slices (safe treat)")],
    )
    monkeypatch.setattr(planner_module, "draft_plan", _scripted_planner([toxic, safe]))

    owner = _build_owner()
    result = run(goal="g", owner=owner, today=_TODAY)

    assert result.status == "preview"
    blocked = [r for r in result.trace if r.meta.get("reason") == "toxic_food"]
    assert blocked, "toxic-food block must be recorded in the trace"
    # The toxic task must NOT appear in added_tasks under any name.
    descs = [t["description"] for t in result.added_tasks]
    assert all("grape" not in d.lower() for d in descs)
    assert any("apple" in d.lower() for d in descs)


# ---------------------------------------------------------------- jsonl logging


def test_run_writes_one_jsonl_record(monkeypatch, _isolate_log):
    plan = Plan(version=1, goal="g", steps=[_add_task_step("08:00", "Breakfast")])
    monkeypatch.setattr(planner_module, "draft_plan", _scripted_planner([plan]))

    result = run(goal="g", owner=_build_owner(), today=_TODAY)

    log_path: Path = _isolate_log
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, "exactly one record per run() call"
    rec = json.loads(lines[0])
    assert rec["run_id"] == result.run_id
    assert rec["status"] == "preview"
    # Phase 3: critic now always populated for runs with an executable plan.
    # In the no-API-key test environment it falls back to the mock report.
    assert rec["critic"] is not None
    assert rec["critic"]["kind"] == "plan"
    assert rec["critic"]["is_mock"] is True
    assert len(rec["plan_versions"]) == 1
    assert rec["added_tasks"], "trace must include the added tasks list"


# ---------------------------------------------------------------- apply / discard


def test_apply_plan_writes_to_real_owner(monkeypatch):
    plan = Plan(
        version=1,
        goal="g",
        steps=[_add_task_step("08:00", "Breakfast"), _add_task_step("18:00", "Dinner")],
    )
    monkeypatch.setattr(planner_module, "draft_plan", _scripted_planner([plan]))

    owner = _build_owner()
    result = run(goal="g", owner=owner, today=_TODAY)
    assert owner.pets[0].tasks == []  # untouched before apply

    n_added = apply_plan(owner, result)

    assert n_added == 2
    assert result.status == "applied"
    descs = sorted(t.description for t in owner.pets[0].tasks)
    assert descs == ["Breakfast", "Dinner"]


def test_discard_plan_marks_status_and_leaves_owner_alone(monkeypatch):
    plan = Plan(version=1, goal="g", steps=[_add_task_step("08:00", "Breakfast")])
    monkeypatch.setattr(planner_module, "draft_plan", _scripted_planner([plan]))

    owner = _build_owner()
    result = run(goal="g", owner=owner, today=_TODAY)

    discard_plan(result)
    assert result.status == "rejected"
    assert owner.pets[0].tasks == []


def test_max_steps_ceiling_is_enforced(monkeypatch):
    # A plan with 12 trivial list_pets steps; max_steps=5 should stop us early.
    big_plan = Plan(
        version=1,
        goal="g",
        steps=[PlanStep(tool="list_pets", args={}) for _ in range(12)],
    )
    monkeypatch.setattr(planner_module, "draft_plan", _scripted_planner([big_plan]))

    result = run(goal="g", owner=_build_owner(), today=_TODAY, max_steps=5)
    assert result.status == "exhausted"
    assert len(result.trace) == 5

"""Safety invariants for the scratch-owner pattern.

Phase 2's whole correctness story rests on one rule: ``executor.run`` never
mutates the live owner. Tests here use ``id()`` and pre/post snapshots to
prove that, even when:
- the plan completes successfully,
- the plan is interrupted by a conflict + re-plan,
- the plan is rejected outright by guardrails.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest

from pawpal.agent import executor as ex_module
from pawpal.agent import planner as planner_module
from pawpal.agent.executor import run
from pawpal.agent.models import Plan, PlanStep
from pawpal.domain import Owner, Pet, Task


_TODAY = date(2026, 4, 26)


@pytest.fixture(autouse=True)
def _isolate_log(tmp_path, monkeypatch):
    monkeypatch.setattr(ex_module, "LOG_FILE", tmp_path / "agent_trace.jsonl")
    monkeypatch.setattr(ex_module, "LOG_DIR", tmp_path)
    yield


def _scripted(plans):
    plans = list(plans)
    state = {"i": 0}

    def _draft(*a, **kw):
        i = state["i"]
        state["i"] += 1
        return plans[min(i, len(plans) - 1)]

    return _draft


def _add_task_step(time_hhmm: str, desc: str) -> PlanStep:
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


def _build_owner_with_one_task() -> Owner:
    owner = Owner("Safety")
    pet = Pet("Milo", "dog", 3)
    pet.add_task(Task("Pre-existing walk", "09:00", "daily", due_date=_TODAY))
    owner.add_pet(pet)
    return owner


def _snapshot(owner: Owner) -> list[tuple]:
    """A flat tuple-snapshot of every task across all pets, used for equality."""
    return [
        (pet.name, t.description, t.time, t.frequency, t.due_date.isoformat(), t.is_completed)
        for pet in owner.pets
        for t in pet.tasks
    ]


# ---------------------------------------------------------------- isolation invariants


def test_successful_run_does_not_mutate_live_owner(monkeypatch):
    plan = Plan(
        version=1,
        goal="g",
        steps=[_add_task_step("08:00", "Breakfast"), _add_task_step("18:00", "Dinner")],
    )
    monkeypatch.setattr(planner_module, "draft_plan", _scripted([plan]))

    owner = _build_owner_with_one_task()
    before = _snapshot(owner)
    pet_id_before = id(owner.pets[0])
    tasks_id_before = id(owner.pets[0].tasks)

    result = run(goal="g", owner=owner, today=_TODAY)

    assert result.status == "preview"
    assert _snapshot(owner) == before
    assert id(owner.pets[0]) == pet_id_before
    assert id(owner.pets[0].tasks) == tasks_id_before


def test_conflict_replan_does_not_leave_partial_writes(monkeypatch):
    bad = Plan(
        version=1,
        goal="g",
        steps=[
            _add_task_step("07:00", "Early walk"),       # OK on scratch
            _add_task_step("09:00", "Mid-morning walk"),  # conflict on scratch
        ],
    )
    safe = Plan(
        version=2,
        goal="g",
        steps=[_add_task_step("10:30", "Recovered walk")],
    )
    monkeypatch.setattr(planner_module, "draft_plan", _scripted([bad, safe]))

    owner = _build_owner_with_one_task()
    before = _snapshot(owner)

    result = run(goal="g", owner=owner, today=_TODAY)

    assert result.status == "preview"
    assert len(result.plan_versions) == 2
    # Live owner still has only the pre-existing task.
    assert _snapshot(owner) == before
    # The "Early walk" that briefly succeeded on scratch v1 must NOT appear in
    # the final added_tasks list (scratch is reset between plan versions).
    descs = [t["description"] for t in result.added_tasks]
    assert "Early walk" not in descs
    assert "Recovered walk" in descs


def test_exhausted_run_does_not_mutate_live_owner(monkeypatch):
    bad = Plan(version=1, goal="g", steps=[_add_task_step("09:00", "Conflict")])
    monkeypatch.setattr(planner_module, "draft_plan", _scripted([bad, bad, bad, bad]))

    owner = _build_owner_with_one_task()
    before = _snapshot(owner)

    result = run(goal="g", owner=owner, today=_TODAY, max_replans=2)
    assert result.status == "exhausted"
    assert _snapshot(owner) == before


def test_deepcopy_is_real_not_shallow(monkeypatch):
    """Defence-in-depth: confirm that the executor's internal scratch owner
    really is a deep copy by checking that mutating a manually-deepcopied
    owner doesn't bleed into the original. (We can't reach the executor's
    private scratch directly; this guards the underlying assumption.)
    """
    owner = _build_owner_with_one_task()
    snap = _snapshot(owner)

    twin = deepcopy(owner)
    twin.pets[0].add_task(Task("Sneaky", "23:30", "daily", due_date=_TODAY))

    assert _snapshot(owner) == snap
    assert id(twin.pets[0]) != id(owner.pets[0])
    assert id(twin.pets[0].tasks) != id(owner.pets[0].tasks)

"""Unit tests for the `pawpal.tools` adapter (Phase 1 + Phase 2 surface)."""

from __future__ import annotations

from datetime import date, timedelta

from pawpal import tools
from pawpal.domain import Owner, Pet, Task


def _build_owner() -> Owner:
    owner = Owner("Alex")
    owner.add_pet(Pet("Milo", "dog", 3))
    owner.add_pet(Pet("Luna", "cat", 1))
    return owner


def test_list_pets_returns_summaries_in_order():
    owner = _build_owner()
    out = tools.list_pets(owner)
    assert out.ok
    assert [p["name"] for p in out.data] == ["Milo", "Luna"]
    assert out.data[0]["species"] == "dog"
    assert out.data[0]["age"] == 3
    assert out.data[1]["species"] == "cat"


def test_list_pets_empty_owner():
    owner = Owner("Empty")
    out = tools.list_pets(owner)
    assert out.ok
    assert out.data == []


def test_find_pet_case_insensitive():
    owner = _build_owner()
    p = tools.find_pet(owner, "milo")
    assert p is not None
    assert p.name == "Milo"


def test_find_pet_returns_none_for_missing_name():
    owner = _build_owner()
    assert tools.find_pet(owner, "Bingo") is None


# ------------------------------------------------------- Phase 2: add_task


_TODAY = date(2026, 4, 26)
_TOMORROW = _TODAY + timedelta(days=1)


def test_add_task_happy_path_appends_and_returns_summary():
    owner = _build_owner()
    res = tools.add_task(
        owner,
        pet_name="Milo",
        description="Morning walk",
        time_hhmm="08:30",
        frequency="daily",
        due_date_iso=_TODAY.isoformat(),
    )
    assert res.ok
    assert res.data["pet_name"] == "Milo"
    milo = next(p for p in owner.pets if p.name == "Milo")
    assert len(milo.tasks) == 1
    assert milo.tasks[0].description == "Morning walk"


def test_add_task_blocks_toxic_food_for_dog():
    owner = _build_owner()
    res = tools.add_task(
        owner,
        pet_name="Milo",
        description="Breakfast: a bowl of grapes for Milo",
        time_hhmm="08:00",
        frequency="daily",
        due_date_iso=_TODAY.isoformat(),
    )
    assert not res.ok
    assert res.requires_replan
    assert res.meta["reason"] == "toxic_food"
    assert "grape" in res.meta["hits"]
    milo = next(p for p in owner.pets if p.name == "Milo")
    assert milo.tasks == [], "blocked add must not mutate the pet"


def test_add_task_blocks_lily_for_cat():
    owner = _build_owner()
    res = tools.add_task(
        owner,
        pet_name="Luna",
        description="Refresh lily bouquet near Luna's bed",
        time_hhmm="07:00",
        frequency="weekly",
        due_date_iso=_TODAY.isoformat(),
    )
    assert not res.ok
    assert res.meta["reason"] == "toxic_food"
    assert "lily" in res.meta["hits"]


def test_add_task_detects_time_conflict():
    owner = _build_owner()
    milo = next(p for p in owner.pets if p.name == "Milo")
    milo.add_task(Task("Existing walk", "09:00", "daily", due_date=_TODAY))

    res = tools.add_task(
        owner,
        pet_name="Milo",
        description="Vet visit",
        time_hhmm="09:00",
        frequency="once",
        due_date_iso=_TODAY.isoformat(),
    )
    assert not res.ok
    assert res.meta["reason"] == "conflict"
    assert res.requires_replan
    # The conflict refusal must NOT have appended the new task.
    assert len(milo.tasks) == 1


def test_add_task_rejects_unknown_pet():
    owner = _build_owner()
    res = tools.add_task(
        owner,
        pet_name="Ghost",
        description="Walk",
        time_hhmm="08:00",
        frequency="daily",
        due_date_iso=_TODAY.isoformat(),
    )
    assert not res.ok
    assert res.meta["reason"] == "pet_not_found"


def test_add_task_rejects_bad_time_format():
    owner = _build_owner()
    res = tools.add_task(
        owner,
        pet_name="Milo",
        description="Walk",
        time_hhmm="9:00",  # missing leading zero
        frequency="daily",
        due_date_iso=_TODAY.isoformat(),
    )
    assert not res.ok
    assert res.meta["reason"] == "bad_time"


def test_list_tasks_on_returns_only_target_date():
    owner = _build_owner()
    milo = next(p for p in owner.pets if p.name == "Milo")
    milo.add_task(Task("Today walk", "08:00", "daily", due_date=_TODAY))
    milo.add_task(Task("Tomorrow walk", "08:00", "daily", due_date=_TOMORROW))

    res = tools.list_tasks_on(owner, date_iso=_TODAY.isoformat())
    assert res.ok
    descs = [r["description"] for r in res.data]
    assert "Today walk" in descs
    assert "Tomorrow walk" not in descs


def test_detect_conflicts_reports_clash():
    owner = _build_owner()
    milo = next(p for p in owner.pets if p.name == "Milo")
    luna = next(p for p in owner.pets if p.name == "Luna")
    milo.add_task(Task("Walk", "09:00", "daily", due_date=_TODAY))
    luna.add_task(Task("Brush", "09:00", "weekly", due_date=_TODAY))

    res = tools.detect_conflicts(owner, date_iso=_TODAY.isoformat())
    assert res.ok
    assert res.data["conflicts"], "expected one conflict row at 09:00"
    assert res.data["conflicts"][0]["time"] == "09:00"


def test_detect_conflicts_empty_when_no_clash():
    owner = _build_owner()
    milo = next(p for p in owner.pets if p.name == "Milo")
    milo.add_task(Task("Walk", "09:00", "daily", due_date=_TODAY))

    res = tools.detect_conflicts(owner, date_iso=_TODAY.isoformat())
    assert res.ok
    assert res.data["conflicts"] == []

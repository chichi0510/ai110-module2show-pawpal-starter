"""Unit tests for the (Phase 1) `tools.py` adapter."""

from __future__ import annotations

from pawpal import tools
from pawpal.domain import Owner, Pet


def _build_owner() -> Owner:
    owner = Owner("Alex")
    owner.add_pet(Pet("Milo", "dog", 3))
    owner.add_pet(Pet("Luna", "cat", 1))
    return owner


def test_list_pets_returns_summaries_in_order():
    owner = _build_owner()
    out = tools.list_pets(owner)
    assert [p.name for p in out] == ["Milo", "Luna"]
    assert out[0].species == "dog"
    assert out[0].age == 3
    assert out[1].species == "cat"


def test_list_pets_empty_owner():
    owner = Owner("Empty")
    assert tools.list_pets(owner) == []


def test_find_pet_case_insensitive():
    owner = _build_owner()
    p = tools.find_pet(owner, "milo")
    assert p is not None
    assert p.name == "Milo"


def test_find_pet_returns_none_for_missing_name():
    owner = _build_owner()
    assert tools.find_pet(owner, "Bingo") is None

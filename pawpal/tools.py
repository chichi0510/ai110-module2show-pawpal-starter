"""LLM-callable wrappers around the existing PawPal domain layer.

Phase 1 intentionally exposes only `list_pets` — enough for the RAG layer to
obtain the active pet's species/age. Phase 2 will add `add_task`,
`detect_conflicts`, and `rag_lookup` (see `docs/plan/phase2.md`).

Keeping this file as the single bridge between AI modules and
`pawpal_system.py` lets the agent loop in Phase 2 plug in without changes
elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from pawpal.domain import Owner


@dataclass
class PetSummary:
    name: str
    species: str
    age: int


def list_pets(owner: Owner) -> List[PetSummary]:
    """Return a flattened, JSON-friendly view of the owner's pets."""
    return [PetSummary(name=p.name, species=p.species, age=p.age) for p in owner.pets]


def find_pet(owner: Owner, name: str) -> Optional[PetSummary]:
    """Look up a pet summary by name (case-insensitive)."""
    needle = name.strip().lower()
    for p in owner.pets:
        if p.name.lower() == needle:
            return PetSummary(name=p.name, species=p.species, age=p.age)
    return None

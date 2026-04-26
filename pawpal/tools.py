"""LLM-callable wrappers around the existing PawPal domain layer.

Phase 2 surface (used by the agent loop in `pawpal.agent.executor`):

    - list_pets                read-only
    - list_tasks_on            read-only (for a given date)
    - detect_conflicts         read-only (clock-time clashes on a date)
    - add_task                 mutating; ALWAYS routed through toxic_food guardrail
    - rag_lookup               delegates to `pawpal.rag.qa.answer`

Every tool returns a `ToolResult(ok, data, error, meta)` so the executor can
treat them uniformly. Mutating tools operate on whatever `Owner` instance the
caller hands in — the executor always passes a `deepcopy`, never the live one.

Why a single bridge module?
- Keeps the LLM schema (see `TOOLS_SCHEMA`) co-located with the implementations.
- Lets us unit-test each tool deterministically without spinning up the agent.
- The `add_task` invariant — toxic-food check is unbypassable — lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any, Dict, List, Optional

from pawpal.domain import Owner, Pet, Scheduler, Task
from pawpal.guardrails import toxic_food

# ---------------------------------------------------------------- result type


@dataclass
class ToolResult:
    """Uniform return type for every tool the agent can invoke.

    Attributes
    ----------
    ok : bool
        True if the tool ran successfully and produced ``data``.
    data : Any
        Tool-specific payload (list / dict / scalar). ``None`` on failure.
    error : str | None
        Human-readable failure reason; meaningful only when ``ok`` is False.
    requires_replan : bool
        Tells the executor that this failure is recoverable by re-planning
        (e.g. toxic-food block, time conflict). Hard parsing errors leave
        this False so the executor can decide whether to abort instead.
    meta : dict
        Optional structured details (e.g. list of toxic-food hits, conflict
        rows). Written into the trace as-is.
    """

    ok: bool
    data: Any = None
    error: Optional[str] = None
    requires_replan: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------- summaries


@dataclass
class PetSummary:
    name: str
    species: str
    age: int

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "species": self.species, "age": self.age}


@dataclass
class TaskSummary:
    pet_name: str
    description: str
    time: str
    frequency: str
    due_date: str
    is_completed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pet_name": self.pet_name,
            "description": self.description,
            "time": self.time,
            "frequency": self.frequency,
            "due_date": self.due_date,
            "is_completed": self.is_completed,
        }


# ---------------------------------------------------------------- helpers


def _find_pet(owner: Owner, name: str) -> Optional[Pet]:
    needle = name.strip().lower()
    for p in owner.pets:
        if p.name.lower() == needle:
            return p
    return None


def _parse_iso_date(s: str) -> _date:
    return _date.fromisoformat(s)


_TIME_RE_PARTS = ("00", "23")  # purely for documentation; regex enforced below


def _validate_time_hhmm(s: str) -> bool:
    if not isinstance(s, str) or len(s) != 5 or s[2] != ":":
        return False
    try:
        h = int(s[:2])
        m = int(s[3:])
    except ValueError:
        return False
    return 0 <= h <= 23 and 0 <= m <= 59


# ---------------------------------------------------------------- read-only tools


def list_pets(owner: Owner) -> ToolResult:
    """Return all pets the owner has (lightweight summaries)."""
    pets = [PetSummary(p.name, p.species, p.age) for p in owner.pets]
    return ToolResult(ok=True, data=[p.to_dict() for p in pets])


def find_pet(owner: Owner, name: str) -> Optional[PetSummary]:
    """Convenience for non-agent callers; not exposed as an LLM tool."""
    pet = _find_pet(owner, name)
    return PetSummary(pet.name, pet.species, pet.age) if pet else None


def list_tasks_on(
    owner: Owner,
    *,
    date_iso: str,
    pet_name: Optional[str] = None,
) -> ToolResult:
    """List incomplete + completed tasks scheduled for ``date_iso``.

    Mirrors what the Schedule UI shows — useful for the planner to learn the
    existing day before adding new tasks.
    """
    try:
        target = _parse_iso_date(date_iso)
    except ValueError:
        return ToolResult(ok=False, error=f"date_iso {date_iso!r} is not ISO date format")

    rows: List[TaskSummary] = []
    for pet in owner.pets:
        if pet_name and pet.name.lower() != pet_name.strip().lower():
            continue
        for task in pet.tasks:
            if task.due_date == target:
                rows.append(
                    TaskSummary(
                        pet_name=pet.name,
                        description=task.description,
                        time=task.time,
                        frequency=task.frequency,
                        due_date=task.due_date.isoformat(),
                        is_completed=task.is_completed,
                    )
                )
    rows.sort(key=lambda r: r.time)
    return ToolResult(ok=True, data=[r.to_dict() for r in rows])


def detect_conflicts(owner: Owner, *, date_iso: str) -> ToolResult:
    """Return clock-time clashes on ``date_iso`` (across all pets, incomplete only)."""
    try:
        target = _parse_iso_date(date_iso)
    except ValueError:
        return ToolResult(ok=False, error=f"date_iso {date_iso!r} is not ISO date format")

    sched = Scheduler(owner)
    todays = [t for t in sched.get_todays_tasks(target) if not t.is_completed]
    messages = sched.detect_time_conflicts(todays)

    grouped: Dict[str, List[str]] = {}
    for pet in owner.pets:
        for task in pet.tasks:
            if task.due_date == target and not task.is_completed:
                grouped.setdefault(task.time, []).append(f"{pet.name}: {task.description}")
    rows = [
        {"time": t, "items": items} for t, items in grouped.items() if len(items) > 1
    ]
    rows.sort(key=lambda r: r["time"])
    return ToolResult(
        ok=True,
        data={"messages": messages, "conflicts": rows, "date": target.isoformat()},
    )


# ---------------------------------------------------------------- mutating tool


def add_task(
    owner: Owner,
    *,
    pet_name: str,
    description: str,
    time_hhmm: str,
    frequency: str,
    due_date_iso: str,
) -> ToolResult:
    """Add a task to ``pet_name``. Refuses if the description names a toxic
    food for that species, or if the new task would clash with another
    incomplete task on the same date.

    The caller is expected to pass a *scratch* deepcopy of the owner so that
    a refusal here leaves the live owner untouched.
    """
    pet = _find_pet(owner, pet_name)
    if pet is None:
        return ToolResult(
            ok=False,
            error=f"no pet named {pet_name!r}",
            requires_replan=True,
            meta={"reason": "pet_not_found"},
        )

    if not _validate_time_hhmm(time_hhmm):
        return ToolResult(
            ok=False,
            error=f"time_hhmm {time_hhmm!r} must be HH:MM (00:00..23:59)",
            requires_replan=True,
            meta={"reason": "bad_time"},
        )

    freq = (frequency or "").lower().strip()
    if freq not in {"once", "daily", "weekly"}:
        return ToolResult(
            ok=False,
            error=f"frequency {frequency!r} must be once|daily|weekly",
            requires_replan=True,
            meta={"reason": "bad_frequency"},
        )

    try:
        due = _parse_iso_date(due_date_iso)
    except ValueError:
        return ToolResult(
            ok=False,
            error=f"due_date_iso {due_date_iso!r} is not ISO date format",
            requires_replan=True,
            meta={"reason": "bad_date"},
        )

    # ---- Hard guardrail: toxic foods in the description (cannot be bypassed).
    hits = toxic_food.scan_text(description, pet.species)
    if hits:
        names = [h.entry.name for h in hits]
        return ToolResult(
            ok=False,
            error=(
                f"add_task blocked: description mentions toxic items for "
                f"{pet.species}: {', '.join(names)}"
            ),
            requires_replan=True,
            meta={"reason": "toxic_food", "hits": names},
        )

    # ---- Conflict check: same clock time, same date, incomplete.
    for existing in pet.tasks:
        if (
            existing.due_date == due
            and existing.time == time_hhmm
            and not existing.is_completed
        ):
            return ToolResult(
                ok=False,
                error=(
                    f"time conflict: {pet.name} already has "
                    f"'{existing.description}' at {time_hhmm} on {due.isoformat()}"
                ),
                requires_replan=True,
                meta={
                    "reason": "conflict",
                    "existing": existing.description,
                    "time": time_hhmm,
                    "date": due.isoformat(),
                },
            )

    new_task = Task(
        description=description.strip(),
        time=time_hhmm,
        frequency=freq,
        due_date=due,
    )
    pet.add_task(new_task)
    return ToolResult(
        ok=True,
        data={
            "pet_name": pet.name,
            "description": new_task.description,
            "time": new_task.time,
            "frequency": new_task.frequency,
            "due_date": new_task.due_date.isoformat(),
        },
    )


# ---------------------------------------------------------------- rag bridge


def rag_lookup(
    *,
    query: str,
    species: Optional[str] = None,
    age: Optional[int] = None,
    mock: bool = False,
) -> ToolResult:
    """Delegate to the Phase 1 RAG layer. The agent uses this when it needs
    factual grounding (e.g. "how often should puppies eat?") before deciding
    a task's parameters.
    """
    # Imported lazily to keep `tools` importable in environments where the
    # vector store hasn't been built (the tools module itself doesn't need
    # ChromaDB; only `rag_lookup` does).
    from pawpal.rag.qa import PetContext, answer

    pet = PetContext(species=species, age=age)
    result = answer(query, pet, mock=mock)
    return ToolResult(
        ok=True,
        data={
            "text": result.text,
            "sources": [
                {"n": c.n, "source_path": c.source_path, "heading": c.heading}
                for c in result.sources
            ],
            "no_retrieval": result.no_retrieval,
            "input_blocked": result.input_blocked,
            "out_of_scope": result.out_of_scope,
            "safety_intervened": result.safety_intervened,
        },
    )


# ---------------------------------------------------------------- LLM schema


TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "name": "list_pets",
        "description": "Return all pets owned by the user.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_tasks_on",
        "description": "List tasks on a given date, optionally filtered by pet.",
        "parameters": {
            "type": "object",
            "properties": {
                "date_iso": {"type": "string", "format": "date"},
                "pet_name": {"type": "string"},
            },
            "required": ["date_iso"],
        },
    },
    {
        "name": "detect_conflicts",
        "description": "Check time conflicts on a date (incomplete tasks).",
        "parameters": {
            "type": "object",
            "properties": {"date_iso": {"type": "string", "format": "date"}},
            "required": ["date_iso"],
        },
    },
    {
        "name": "add_task",
        "description": (
            "Add a task to a pet. Will be REJECTED if description mentions toxic "
            "foods for the pet's species, or if it clashes with an existing task."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pet_name": {"type": "string"},
                "description": {"type": "string"},
                "time_hhmm": {"type": "string", "pattern": "^[0-2][0-9]:[0-5][0-9]$"},
                "frequency": {"type": "string", "enum": ["once", "daily", "weekly"]},
                "due_date_iso": {"type": "string", "format": "date"},
            },
            "required": [
                "pet_name",
                "description",
                "time_hhmm",
                "frequency",
                "due_date_iso",
            ],
        },
    },
    {
        "name": "rag_lookup",
        "description": (
            "Search the pet-care knowledge base. Use BEFORE add_task when "
            "unsure about feeding frequency, vaccine timing, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "species": {"type": "string"},
            },
            "required": ["query"],
        },
    },
]


TOOL_NAMES = {t["name"] for t in TOOLS_SCHEMA}

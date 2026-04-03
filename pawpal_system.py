from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


def _clock_to_minutes(clock: str) -> int:
    """Parse 'HH:MM' into minutes since midnight for sorting."""
    parts = clock.strip().split(":")
    h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    return h * 60 + m


@dataclass
class Task:
    """A concrete care action for a pet."""

    description: str
    time: str  # clock time, e.g. "09:00"
    frequency: str = "daily"  # e.g. "daily", "weekly", "once"
    is_completed: bool = False

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.is_completed = True


@dataclass
class Pet:
    """A pet owns a list of care tasks."""

    name: str
    species: str
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a task to the pet."""
        self.tasks.append(task)

    def get_tasks(self) -> List[Task]:
        """Return a copy of this pet's task list."""
        return list(self.tasks)


@dataclass
class Owner:
    """An owner manages multiple pets; tasks live on each pet."""

    name: str
    pets: List[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to the owner."""
        self.pets.append(pet)

    def get_all_tasks(self) -> List[Task]:
        """Collect tasks from all pets."""
        out: List[Task] = []
        for pet in self.pets:
            out.extend(pet.get_tasks())
        return out


@dataclass
class Scheduler:
    """Pulls tasks from the owner, filters and orders them for planning."""

    owner: Owner

    def get_todays_tasks(self, today: Optional[date] = None) -> List[Task]:
        """Return incomplete tasks (today's remaining work). ``today`` is reserved for tests / future calendar rules."""
        _ = today or date.today()
        return [t for t in self.owner.get_all_tasks() if not t.is_completed]

    def sort_tasks(self, tasks: Optional[List[Task]] = None) -> List[Task]:
        """Return tasks sorted by clock time (``time``) ascending."""
        source = tasks if tasks is not None else self.get_todays_tasks()
        return sorted(source, key=lambda t: _clock_to_minutes(t.time))

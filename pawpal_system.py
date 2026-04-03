from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
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
    frequency: str = "daily"  # "daily", "weekly", "once"
    due_date: date = field(default_factory=date.today)
    is_completed: bool = False

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.is_completed = True


@dataclass
class Pet:
    """A pet owns a list of care tasks."""

    name: str
    species: str
    age: int
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a task to the pet."""
        self.tasks.append(task)

    def get_tasks(self) -> List[Task]:
        """Return a copy of this pet's task list."""
        return list(self.tasks)

    def mark_task_complete(self, task: Task) -> None:
        """Mark this task complete for this pet; for ``daily`` / ``weekly``, add a new task with the next ``due_date`` (not for ``once``)."""
        if task not in self.tasks:
            return
        task.mark_complete()
        freq = (task.frequency or "once").lower()
        if freq == "once":
            return
        if freq == "daily":
            delta = timedelta(days=1)
        elif freq == "weekly":
            delta = timedelta(days=7)
        else:
            return
        next_task = Task(
            description=task.description,
            time=task.time,
            frequency=task.frequency,
            due_date=task.due_date + delta,
        )
        self.add_task(next_task)


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
        """Incomplete tasks whose due date is ``today``."""
        day = today or date.today()
        return [
            t
            for t in self.owner.get_all_tasks()
            if not t.is_completed and t.due_date == day
        ]

    def sort_by_time(self, tasks: List[Task]) -> List[Task]:
        """Return tasks ordered by ``due_date``, then by clock time ``HH:MM`` (earlier first)."""
        return sorted(tasks, key=lambda t: (t.due_date, _clock_to_minutes(t.time)))

    def sort_tasks(self, tasks: Optional[List[Task]] = None) -> List[Task]:
        """Backward-compatible alias: sort ``tasks`` or today's tasks by time."""
        source = tasks if tasks is not None else self.get_todays_tasks()
        return self.sort_by_time(source)

    def filter_tasks(
        self,
        tasks: List[Task],
        *,
        completed: Optional[bool] = None,
        pet_name: Optional[str] = None,
    ) -> List[Task]:
        """Return a subset of ``tasks``: optionally only completed or incomplete, and/or only tasks belonging to ``pet_name``."""
        result = list(tasks)
        if completed is not None:
            result = [t for t in result if t.is_completed == completed]
        if pet_name is not None:
            pet = next((p for p in self.owner.pets if p.name == pet_name), None)
            if pet is None:
                return []
            result = [t for t in result if t in pet.tasks]
        return result

    def detect_time_conflicts(self, tasks: List[Task]) -> List[str]:
        """Detect simple scheduling clashes: two or more tasks with the exact same ``time`` string; return warning lines (does not check overlapping durations)."""
        by_time: dict[str, list[Task]] = defaultdict(list)
        for t in tasks:
            by_time[t.time].append(t)
        messages: List[str] = []
        for tm, group in by_time.items():
            if len(group) > 1:
                messages.append(f"Warning: Multiple tasks are scheduled at {tm}.")
        return messages

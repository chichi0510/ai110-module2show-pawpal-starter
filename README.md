# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Smarter Scheduling

The domain logic in `pawpal_system.py` (used by `main.py` and `app.py`) supports:

- **Sort tasks by time** — `Scheduler.sort_by_time` orders tasks by `due_date`, then by clock time (`HH:MM`).
- **Filter by pet or completion status** — `Scheduler.filter_tasks` can narrow a list with `completed=True/False` and/or `pet_name="..."`.
- **Auto-create recurring tasks** — `Pet.mark_task_complete` marks a task done; for `daily` / `weekly` frequencies it appends the next occurrence with an updated `due_date` (`once` does not repeat).
- **Detect simple scheduling conflicts** — `Scheduler.detect_time_conflicts` warns when two or more tasks share the **exact same** time string (lightweight; not full interval overlap).

Run `python main.py` for a scripted demo (out-of-order insert → sorted output, filters, recurring completion, duplicate-time warning).

## Testing PawPal+

### How to run tests

From the project root (with dependencies installed):

```bash
python -m pytest
```

Use `python -m pytest -v` for per-test names.

### What is covered

Automated tests in `tests/test_pawpal.py` check:

- **Task sorting** — tasks inserted as 14:00 / 08:00 / 09:30 come out ordered 08:00 → 09:30 → 14:00.
- **Recurring task creation** — completing a **daily** task keeps the completed row and adds the next occurrence with `due_date` moved forward by one day.
- **Conflict detection** — two tasks at the same clock time (different pets) yield at least one warning mentioning that time.
- **Filtering** — `filter_tasks` by `pet_name` and by `completed` behaves as expected.
- **Edge cases** — a pet with no tasks exposes empty lists without errors; original tests still cover `mark_complete` and `add_task`.

### Confidence level

**Confidence: ★★★★☆**

The main scheduling behaviors are covered by automated tests, including sorting, recurring tasks, conflict detection, and basic filtering. More advanced cases (e.g. overlapping time *ranges* rather than duplicate clock strings) are intentionally out of scope for this lightweight scheduler and are not tested here.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

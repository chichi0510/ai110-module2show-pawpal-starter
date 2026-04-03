"""Tests for PawPal+ domain logic (sorting, recurrence, conflicts, filters)."""

from datetime import date, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


def test_task_completion():
    task = Task("Walk", "09:00", "daily", due_date=date(2026, 1, 1))
    task.mark_complete()
    assert task.is_completed == True


def test_add_task_to_pet():
    pet = Pet("Milo", "Dog", 4)
    task = Task("Walk", "09:00", "daily", due_date=date(2026, 1, 1))

    pet.add_task(task)

    assert len(pet.tasks) == 1


def test_tasks_are_sorted_by_time():
    """Tasks added out of order (14:00, 08:00, 09:30) sort to chronological clock order."""
    today = date(2026, 6, 1)
    owner = Owner("Owner")
    pet = Pet("Milo", "dog", 3)
    owner.add_pet(pet)
    pet.add_task(Task("Late", "14:00", "daily", due_date=today))
    pet.add_task(Task("Early", "08:00", "daily", due_date=today))
    pet.add_task(Task("Mid", "09:30", "daily", due_date=today))

    scheduler = Scheduler(owner)
    ordered = scheduler.sort_by_time(scheduler.get_todays_tasks(today))

    assert [t.time for t in ordered] == ["08:00", "09:30", "14:00"]


def test_marking_daily_task_complete_creates_next_occurrence():
    """Completing a daily task leaves the old row completed and adds the next due date."""
    today = date(2026, 6, 10)
    pet = Pet("Luna", "cat", 2)
    task = Task("Feed", "08:00", "daily", due_date=today)
    pet.add_task(task)

    pet.mark_task_complete(task)

    assert task.is_completed is True
    assert len(pet.tasks) == 2
    new_tasks = [t for t in pet.tasks if t is not task]
    assert len(new_tasks) == 1
    nxt = new_tasks[0]
    assert nxt.is_completed is False
    assert nxt.due_date == today + timedelta(days=1)
    assert nxt.time == "08:00"
    assert nxt.description == "Feed"


def test_scheduler_detects_time_conflicts():
    """Two tasks at the same clock time (any pets) produce a non-empty warning list."""
    today = date(2026, 6, 15)
    owner = Owner("Chichi")
    milo = Pet("Milo", "dog", 3)
    luna = Pet("Luna", "cat", 2)
    owner.add_pet(milo)
    owner.add_pet(luna)
    milo.add_task(Task("Walk dog", "09:00", "daily", due_date=today))
    luna.add_task(Task("Brush", "09:00", "weekly", due_date=today))

    scheduler = Scheduler(owner)
    today_tasks = scheduler.get_todays_tasks(today)
    messages = scheduler.detect_time_conflicts(today_tasks)

    assert len(messages) > 0
    assert "09:00" in messages[0]


def test_pet_with_no_tasks_returns_empty_list():
    """A pet with no tasks yields empty get_tasks / owner aggregate / today's slice."""
    pet = Pet("Solo", "dog", 1)
    assert pet.get_tasks() == []

    owner = Owner("O")
    owner.add_pet(pet)
    assert owner.get_all_tasks() == []

    scheduler = Scheduler(owner)
    assert scheduler.get_todays_tasks() == []


def test_filter_tasks_narrows_by_pet_and_completion():
    """filter_tasks respects pet_name and completed flags."""
    today = date(2026, 7, 1)
    owner = Owner("O")
    p1 = Pet("Milo", "dog", 1)
    p2 = Pet("Luna", "cat", 2)
    owner.add_pet(p1)
    owner.add_pet(p2)
    t1 = Task("A", "08:00", "daily", due_date=today)
    t2 = Task("B", "09:00", "once", due_date=today)
    p1.add_task(t1)
    p2.add_task(t2)

    scheduler = Scheduler(owner)
    pool = scheduler.get_todays_tasks(today)

    milo_only = scheduler.filter_tasks(pool, pet_name="Milo")
    assert len(milo_only) == 1
    assert milo_only[0].description == "A"

    incomplete = scheduler.filter_tasks(pool, completed=False)
    assert len(incomplete) == 2

    t1.mark_complete()
    # Completed tasks drop out of get_todays_tasks; use all tasks to assert filter by completed=True
    done_only = scheduler.filter_tasks(owner.get_all_tasks(), completed=True)
    assert len(done_only) == 1
    assert done_only[0].description == "A"

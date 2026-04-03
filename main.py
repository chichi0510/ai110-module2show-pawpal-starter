from datetime import date, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


def _pet_name_for_task(owner: Owner, task: Task) -> str:
    for pet in owner.pets:
        if task in pet.tasks:
            return pet.name
    return "?"


def main() -> None:
    # Fixed "today" so output is stable when you run the script
    today = date(2026, 4, 3)

    owner = Owner("Chichi")
    pet1 = Pet("Milo", "Dog", 3)
    pet2 = Pet("Luna", "Cat", 2)
    owner.add_pet(pet1)
    owner.add_pet(pet2)

    scheduler = Scheduler(owner)

    # --- 1) Sorting: add tasks in messy order (14:00, 08:00, 09:30) → expect 08:00, 09:30, 14:00
    pet1.add_task(Task("Vet visit", "14:00", "once", due_date=today))
    pet2.add_task(Task("Feed cat", "08:00", "daily", due_date=today))
    pet1.add_task(Task("Walk dog", "09:30", "daily", due_date=today))

    ordered = scheduler.sort_by_time(scheduler.get_todays_tasks(today))
    print("=== (1) Today's tasks sorted by time ===")
    for task in ordered:
        print(f"  [{task.time}] {task.description} ({_pet_name_for_task(owner, task)})")

    # --- 2) Filtering examples
    all_today = scheduler.get_todays_tasks(today)
    print("\n=== (2) Filter: incomplete only ===")
    for task in scheduler.filter_tasks(all_today, completed=False):
        print(f"  {task.description} done={task.is_completed}")

    print("\n=== (3) Filter: Milo's tasks only ===")
    for task in scheduler.filter_tasks(all_today, pet_name="Milo"):
        print(f"  [{task.time}] {task.description}")

    # --- 3) Recurring: complete a daily task → next occurrence appears
    feed = next(t for t in pet2.tasks if t.description == "Feed cat")
    pet2.mark_task_complete(feed)
    tomorrow = today + timedelta(days=1)
    print("\n=== (4) After completing daily 'Feed cat': next due on", tomorrow.isoformat(), "===")
    for task in pet2.tasks:
        print(
            f"  {task.description!r} due={task.due_date.isoformat()} "
            f"[{task.time}] completed={task.is_completed}"
        )

    # --- 4) Conflict detection: same clock time on two pets
    pet1.add_task(Task("Walk dog", "09:00", "daily", due_date=today))
    pet2.add_task(Task("Brush", "09:00", "weekly", due_date=today))

    print("\n=== (5) Time conflicts (same HH:MM) ===")
    conflicts = scheduler.detect_time_conflicts(scheduler.get_todays_tasks(today))
    if conflicts:
        for msg in conflicts:
            print(" ", msg)
    else:
        print("  (no conflicts)")

    print("\n=== Full schedule line (sorted) with conflicts above ===")
    final = scheduler.sort_by_time(scheduler.get_todays_tasks(today))
    for task in final:
        print(f"[{task.time}] {task.description} ({_pet_name_for_task(owner, task)})")


if __name__ == "__main__":
    main()

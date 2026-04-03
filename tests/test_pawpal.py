from datetime import date

from pawpal_system import Pet, Task


def test_task_completion():
    task = Task("Walk", "09:00", "daily", due_date=date(2026, 1, 1))
    task.mark_complete()
    assert task.is_completed == True


def test_add_task_to_pet():
    pet = Pet("Milo", "Dog", 4)
    task = Task("Walk", "09:00", "daily", due_date=date(2026, 1, 1))

    pet.add_task(task)

    assert len(pet.tasks) == 1

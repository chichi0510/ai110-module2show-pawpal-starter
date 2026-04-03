from pawpal_system import Owner, Pet, Scheduler, Task


def _pet_name_for_task(owner: Owner, task: Task) -> str:
    for pet in owner.pets:
        if task in pet.tasks:
            return pet.name
    return "?"


def main() -> None:
    owner = Owner("Chichi")

    pet1 = Pet("Milo", "Dog")
    pet2 = Pet("Luna", "Cat")
    owner.add_pet(pet1)
    owner.add_pet(pet2)

    task1 = Task("Walk dog", "09:00", "daily")
    task2 = Task("Feed cat", "08:00", "daily")
    task3 = Task("Vet visit", "14:00", "once")

    pet1.add_task(task1)
    pet2.add_task(task2)
    pet1.add_task(task3)

    scheduler = Scheduler(owner)
    tasks = scheduler.sort_tasks(scheduler.get_todays_tasks())

    print("Today's Schedule:")
    for task in tasks:
        pet_name = _pet_name_for_task(owner, task)
        print(f"[{task.time}] {task.description} ({pet_name})")


if __name__ == "__main__":
    main()

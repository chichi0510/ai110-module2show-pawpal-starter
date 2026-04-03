# PawPal+ UML (final — matches `pawpal_system.py`)

Phase 1 used a simpler sketch (tasks owned by a separate `Schedule` class). The shipped design uses **`Scheduler`** with an **`Owner`**, tasks live on **`Pet`**, and **`Task`** carries calendar fields.

## Class diagram (Mermaid)

```mermaid
classDiagram
    class Owner {
        +str name
        +list pets
        +add_pet(pet)
        +get_all_tasks() List~Task~
    }

    class Pet {
        +str name
        +str species
        +int age
        +list tasks
        +add_task(task)
        +get_tasks() List~Task~
        +mark_task_complete(task)
    }

    class Task {
        +str description
        +str time
        +str frequency
        +date due_date
        +bool is_completed
        +mark_complete()
    }

    class Scheduler {
        +Owner owner
        +get_todays_tasks(today) List~Task~
        +sort_by_time(tasks) List~Task~
        +sort_tasks(tasks) List~Task~
        +filter_tasks(tasks, completed, pet_name) List~Task~
        +detect_time_conflicts(tasks) List~str~
    }

    Owner "1" o-- "*" Pet : owns
    Pet "1" o-- "*" Task : tasks
    Scheduler ..> Owner : uses
    Scheduler ..> Task : sorts/filters/checks
```

## Relationships (summary)

| Relationship | Meaning |
|--------------|---------|
| **Owner → Pet** | One owner has many pets. |
| **Pet → Task** | Each task instance belongs to one pet’s list (`Pet.tasks`). |
| **Scheduler → Owner** | Scheduler reads tasks via `Owner.get_all_tasks()` (aggregates all pets). |
| **Scheduler → Task** | No ownership; scheduler orders/filters/conflict-checks task lists. |

## Exported image

PNG copies: **`uml_final.png`** (repo root) and **`assets/uml_final.png`**. Regenerate from **`docs/uml_final.mmd`** with [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli):  
`npx @mermaid-js/mermaid-cli -i docs/uml_final.mmd -o uml_final.png`

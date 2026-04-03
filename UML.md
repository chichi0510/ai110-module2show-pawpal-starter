# PawPal+ Development Step Records

## Step 1: Class Diagram Design

### UML Class Diagram

```mermaid
classDiagram
    class Pet {
        -string name
        -string species
        -int age
    }

    class Task {
        -string title
        -int time
        -Pet pet
    }

    class Owner {
        -string name
        -Pet[] pets
    }

    class Schedule {
        -Task[] tasks
    }

    Owner "1" -- "*" Pet : owns
    Task "many" --> "1" Pet : applies to
    Schedule "1" -- "*" Task : contains
```

### Class Relationships

- **Owner** owns multiple **Pets** (1-to-many relationship)
- **Task** applies to a specific **Pet** (many-to-one relationship)
- **Schedule** contains multiple **Tasks** (1-to-many relationship)

### Attributes

- **Pet**: name (string), species (string), age (int)
- **Task**: title (string), time (int), pet (Pet reference)
- **Owner**: name (string), pets (Pet array)
- **Schedule**: tasks (Task array)

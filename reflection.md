# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

I created four main classes: **Pet**, **Task**, **Owner**, and **Scheduler**.

- **Pet** stores information about each animal (name, species, age).
- **Task** represents pet care activities like feeding, walking, or grooming. Each task is linked to a specific pet and includes a duration.
- **Owner** manages relationships with multiple pets they own.
- **Scheduler** applies sorting, filtering, and conflict checks to the owner’s tasks for a daily plan.

The design follows these key relationships:
- Owner has a 1-to-many relationship with Pet (one owner can have many pets)
- Task has a many-to-one relationship with Pet (many tasks can apply to one pet)
- Scheduler reads from Owner (and thus Pet → Task) rather than owning tasks directly

**b. Design changes**

After reviewing the design against the requirements, I identified several important gaps:

**Missing Attributes:**
- **Task** should include a **priority** field (mentioned in requirements: "Consider constraints (time available, priority, owner preferences)")
- **Task** should have a **status** field to track completion (pending, completed, skipped)

**Missing Relationships:**
- **Schedule** should reference an **Owner** to know whose daily plan it represents
- **Owner** should have a relationship to **Schedule** to manage their daily pet care plans

**Rationale for Changes:**
- Adding priority to Task is essential for the scheduling algorithm to make intelligent decisions about which tasks to include when time is limited.
- Adding status to Task enables tracking of what has been completed throughout the day.
- Adding Owner reference to Schedule creates a complete system where we can query "what is Owner X's schedule?" and ensures the schedule knows who it belongs to.

These changes align better with the scenario requirement: *"Consider constraints (time available, priority, owner preferences)"* and enable the app to generate optimized daily plans.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler works with **due dates** (`Task.due_date`) plus clock time (`"HH:MM"`), **frequency** (`once` / `daily` / `weekly`), and **completion** state. For a given day it lists incomplete tasks due that day, sorts by time, can filter by pet or completed flag, and runs a lightweight **conflict check**: it only flags when two or more tasks share the **exact same** time string (e.g. two different pets both at `09:00`). It does **not** model duration blocks or overlapping intervals.

**b. Tradeoffs**

My scheduler only checks for **exact time conflicts** (same `HH:MM`), not overlapping time ranges (e.g. 09:00–10:00 vs 09:30–10:30). That keeps the logic small, easy to read, and enough for a first “are two things scheduled at the same clock slot?” warning. The downside is it would not catch subtler overlaps if tasks had start/end durations. For PawPal+ as a planning sketch, that tradeoff is reasonable; a production calendar would need intervals and busy/free logic.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

For **conflict detection**, you can paste `detect_time_conflicts` into an AI and ask how to simplify for readability or performance. Compare its answer with the current approach: a short loop plus `defaultdict` is easy to follow; a one-liner might be fewer lines but harder to debug. Choose based on what *you* find clearer, not only what is shorter.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

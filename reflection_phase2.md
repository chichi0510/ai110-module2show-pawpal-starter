# PawPal+ Project Reflection (Phase 2 — pre-AI baseline)

> 📜 **Historical document.** This reflection covers the original PawPal+
> deterministic scheduler (no AI). It is kept here for diff value — it shows
> the project's starting point before the Module 4 final-project AI rewrite.
>
> 👉 **For the current project reflection** (RAG, agentic planner,
> self-critique, evaluation harness) read
> [`docs/REFLECTION_v2.md`](docs/REFLECTION_v2.md). That document is the one
> the rubric grades.

---


## 1. System design

### Why these classes?

| Class | Responsibility |
|-------|------------------|
| **Task** | One concrete to-do: description, clock time, frequency, **due date**, completion flag. Tasks with calendar meaning need `due_date`, not only `"09:00"`. |
| **Pet** | Holds a list of tasks for that animal (`add_task`, `get_tasks`). **`mark_task_complete`** owns recurring behavior so the next `daily`/`weekly` instance is created on the same pet. |
| **Owner** | Aggregates many pets; **`get_all_tasks`** is the bridge the scheduler uses to see everything. |
| **Scheduler** | Stateless over **`Owner`**: **`sort_by_time`**, **`filter_tasks`**, **`get_todays_tasks`**, **`detect_time_conflicts`**. It does not store tasks; it organizes lists read from the owner. |

This split keeps **data** (who owns what) separate from **planning operations** (sort/filter/warn).

### How the design evolved

Early sketches used a separate “schedule” object holding tasks. The shipped design stores tasks **on each `Pet`**, and **`Scheduler`** reads via **`Owner.get_all_tasks()`**. That matched the product story (“each pet has its care list”) and avoided duplicating task storage.

---

## 2. Scheduling logic and tradeoffs

The scheduler uses **`due_date`** plus **`HH:MM`**, not duration blocks. **Conflict detection** only flags when two **incomplete** tasks on the same calendar day share the **exact same time string**. That is easy to explain in code and tests.

**Tradeoff:** this does **not** detect overlapping **intervals** (e.g. 09:00–10:00 vs 09:30–10:30). A richer model would need start/end times or durations and a different overlap algorithm. For a course-scale app, exact-time matching is a reasonable scope limit; a production system would need interval logic and more UX around “busy” blocks.

---

## 3. AI collaboration

### What helped

- **Agent-style assistance** was useful for scaffolding **`dataclass`** fields and **`Streamlit`** forms wired to **`session_state`**, after the architecture was already decided.
- **Short, file-scoped questions** (e.g. “how should `filter_tasks` combine `completed` and `pet_name`?”) produced better answers than one giant prompt mixing UI, tests, and UML.

### One suggestion I did not take blindly

An AI once suggested compressing **conflict detection** into a dense one-liner or nested comprehensions. Fewer lines, but harder to step through in the debugger and worse for classmates reading the repo. I kept a **`defaultdict`** loop that maps **time → tasks**, then emits warnings—more lines, clearer intent.

### Sessions and focus

Splitting work into **design / implementation / tests / docs** (even as separate chat topics) reduced context mixing: the model stayed on “tests for recurrence” instead of also rewriting the UI in the same reply.

### Takeaway

**AI proposes; the developer decides.** Tools are strong at boilerplate and variations, but **you** still own architecture boundaries, what “done” means, how much complexity is worth it, and verification (tests + running the app). The lead architect is still human.

---

## 4. Testing and verification

Behaviors covered by **`pytest`** include sort order, daily recurrence creating a new `Task`, conflict messages when two incomplete tasks share a time, filter correctness, and empty lists when a pet has no tasks. That gives confidence the **scheduler contract** matches what the UI relies on.

**Next edge cases** if there were more time: time-zone–safe dates, leap weeks for `weekly`, and UI tests for Streamlit (heavier tooling).

---

## 5. Reflection

**What went well:** Clear separation between **`pawpal_system`** and **`app.py`**, plus automated tests for the scheduler, made refactors safer.

**What to improve next:** Optional **priority** on tasks and smarter “what fits in my afternoon” planning—would need extra fields and policy, not only sorting.

**Key takeaway:** Shipping a small but **tested** domain layer, then exposing it in the UI, is a practical pattern; AI accelerates typing, but **consistency and tradeoffs** stay with the author.

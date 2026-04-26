from __future__ import annotations

from datetime import date, time
from pathlib import Path

import streamlit as st

from pawpal.domain import Owner, Pet, Scheduler, Task
from pawpal.rag import index as rag_index
from pawpal.rag.models import AnswerResult
from pawpal.rag.qa import PetContext, answer

st.set_page_config(page_title="PawPal AI", page_icon="🐾", layout="wide")


# ---------------------------------------------------------------- session

if "owner" not in st.session_state:
    st.session_state.owner = Owner("Chichi")

owner: Owner = st.session_state.owner


def _pet_name_for_task(task: Task) -> str:
    for pet in owner.pets:
        if task in pet.tasks:
            return pet.name
    return "?"


def _pet_for_task(task: Task) -> Pet | None:
    for pet in owner.pets:
        if task in pet.tasks:
            return pet
    return None


def _pet_by_name(name: str) -> Pet | None:
    for pet in owner.pets:
        if pet.name == name:
            return pet
    return None


def _tasks_due_on(day: date) -> list[Task]:
    return [t for t in owner.get_all_tasks() if t.due_date == day]


# ---------------------------------------------------------------- header

st.title("🐾 PawPal AI")
st.caption(
    "**Schedule** is the original PawPal+ planner. "
    "**Ask PawPal** answers pet-care questions using a Retrieval-Augmented "
    "knowledge base with toxic-food guardrails."
)

with st.expander("About this app", expanded=False):
    st.markdown(
        """
- **Domain layer** (`pawpal_system.py`): unchanged from PawPal+.
- **AI layer** (`rag/`, `guardrails/`): RAG over `knowledge/*.md`, plus a
  deterministic toxic-food guardrail on both input and output.
- **Trace**: every Ask PawPal call writes a JSONL line to
  `logs/rag_trace.jsonl` for debugging and evaluation.
"""
    )

scheduler = Scheduler(owner)


# ---------------------------------------------------------------- tabs

tab_schedule, tab_ask = st.tabs(["📅 Schedule", "🤖 Ask PawPal"])


# ============================================================ TAB: Schedule

with tab_schedule:
    st.subheader("Owner")
    owner.name = st.text_input("Owner name", value=owner.name)

    st.subheader("Pets")
    with st.form("add_pet_form", clear_on_submit=True):
        ap1, ap2, ap3 = st.columns(3)
        with ap1:
            fp_name = st.text_input("Pet name", key="form_pet_name")
        with ap2:
            fp_species = st.selectbox(
                "Species", ["dog", "cat", "other"], key="form_pet_species"
            )
        with ap3:
            fp_age = st.number_input(
                "Age (years)", min_value=0, max_value=40, value=2, step=1, key="form_pet_age"
            )
        pet_submitted = st.form_submit_button("Add pet")

    if pet_submitted:
        if fp_name.strip():
            new_pet = Pet(fp_name.strip(), fp_species, int(fp_age))
            owner.add_pet(new_pet)
            st.success(f"Added **{new_pet.name}** — {new_pet.species}, age {new_pet.age}.")
        else:
            st.warning("Enter a pet name.")

    if owner.pets:
        st.dataframe(
            [{"Name": p.name, "Species": p.species, "Age": p.age} for p in owner.pets],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No pets yet.")

    st.markdown("### Schedule a task")
    with st.form("add_task_form", clear_on_submit=True):
        t1, t2, t3, t4, t5 = st.columns(5)
        with t1:
            task_desc = st.text_input("Description", value="Morning walk")
        with t2:
            task_time = st.time_input("Time", value=time(9, 0))
        with t3:
            task_due = st.date_input("Due date", value=date.today())
        with t4:
            task_freq = st.selectbox("Frequency", ["daily", "weekly", "once"])
        with t5:
            pet_names = [p.name for p in owner.pets]
            task_pet = st.selectbox("Pet", pet_names) if pet_names else None
        task_submitted = st.form_submit_button("Add task", disabled=not owner.pets)

    if task_submitted and owner.pets and task_pet:
        tt = task_time
        clock = f"{tt.hour:02d}:{tt.minute:02d}"
        new_task = Task(task_desc.strip() or "Task", clock, task_freq, due_date=task_due)
        target = _pet_by_name(task_pet)
        if target is not None:
            target.add_task(new_task)
            st.success(
                f"Scheduled **{new_task.description}** at [{new_task.time}] on "
                f"**{new_task.due_date}** for **{target.name}**."
            )

    st.divider()
    st.subheader("Smart schedule (Scheduler)")
    st.caption(
        "Uses **`sort_by_time`**, **`filter_tasks`**, and "
        "**`detect_time_conflicts`** — not a raw task dump."
    )

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        plan_date = st.date_input("Date", value=date.today(), key="plan_date")
    with col_f2:
        pet_choices = ["All pets"] + [p.name for p in owner.pets]
        filter_pet = st.selectbox("Filter by pet", pet_choices, key="filter_pet")
    with col_f3:
        filter_status = st.selectbox(
            "Filter by status",
            ["All", "Incomplete only", "Completed only"],
            key="filter_status",
        )

    base_for_day = _tasks_due_on(plan_date)
    completed_param: bool | None = None
    if filter_status == "Incomplete only":
        completed_param = False
    elif filter_status == "Completed only":
        completed_param = True

    pet_name_param = None if filter_pet == "All pets" else filter_pet

    filtered = scheduler.filter_tasks(
        base_for_day,
        completed=completed_param,
        pet_name=pet_name_param,
    )
    sorted_tasks = scheduler.sort_by_time(filtered)

    incomplete_same_day = [t for t in base_for_day if not t.is_completed]
    conflict_messages = scheduler.detect_time_conflicts(incomplete_same_day)

    if conflict_messages:
        st.error(
            "**Scheduling conflict** — two or more incomplete tasks share the "
            "same clock time. Adjust times or pets."
        )
        for msg in conflict_messages:
            st.warning(msg)
    elif incomplete_same_day:
        st.success("No duplicate clock times among **incomplete** tasks on this date.")

    st.markdown(f"#### Tasks for **{plan_date}** (sorted by time)")
    if not sorted_tasks:
        st.caption("No tasks match the filters for this date.")
    else:
        st.dataframe(
            [
                {
                    "Time": t.time,
                    "Description": t.description,
                    "Pet": _pet_name_for_task(t),
                    "Frequency": t.frequency,
                    "Done": t.is_completed,
                }
                for t in sorted_tasks
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("##### Complete a task (recurring: creates next `due_date`)")
    if owner.pets and any(p.tasks for p in owner.pets):
        labels: list[str] = []
        label_to_task: dict[str, Task] = {}
        for pet in owner.pets:
            for task in pet.tasks:
                if not task.is_completed:
                    label = f"{pet.name} — {task.description} @ {task.time} ({task.due_date})"
                    labels.append(label)
                    label_to_task[label] = task
        if labels:
            pick = st.selectbox("Choose an incomplete task", labels, key="complete_pick")
            if st.button("Mark complete", key="mark_btn"):
                tsk = label_to_task[pick]
                pet = _pet_for_task(tsk)
                if pet is not None:
                    pet.mark_task_complete(tsk)
                    st.success(
                        "Marked complete. If daily/weekly, the next "
                        "occurrence was added."
                    )
                    st.rerun()
        else:
            st.caption("No incomplete tasks.")
    else:
        st.caption("Add tasks above to enable completion.")


# ============================================================ TAB: Ask PawPal


def _render_kb_warning() -> None:
    """Q2 in open_questions: warn when knowledge/*.md is newer than the index."""
    if not Path("chroma_db").exists():
        st.error(
            "Knowledge index not built yet. Run: `python -m rag.index --rebuild`"
        )
        return
    if rag_index.kb_modified_after_index():
        st.warning(
            "⚠ The `knowledge/` corpus has changed since the index was last "
            "built. Run `python -m rag.index --rebuild` to refresh."
        )


def _render_answer(result: AnswerResult) -> None:
    if result.input_blocked or result.safety_intervened:
        st.error(result.text)
    elif result.out_of_scope:
        st.info(result.text)
    elif result.no_retrieval:
        st.warning(result.text)
    else:
        st.markdown(result.text)

    if result.sources:
        st.markdown("**Sources**")
        for c in result.sources:
            head = f" — _{c.heading}_" if c.heading else ""
            st.markdown(f"- `[{c.n}]` `{c.source_path}`{head}")

    if result.retrieved_chunks:
        with st.expander("🔍 Show retrieved sources (raw chunks)", expanded=False):
            for i, ch in enumerate(result.retrieved_chunks, start=1):
                st.markdown(
                    f"**[{i}] `{ch.source_path}`** "
                    f"— score `{ch.score:.3f}` "
                    f"— species `{ch.species}` "
                    f"— topic `{ch.topic}`"
                )
                st.text(ch.text)
                st.markdown("---")

    bits = []
    if result.model:
        bits.append(f"model `{result.model}`")
    bits.append(f"latency {result.duration_ms} ms")
    if result.input_blocked:
        bits.append("input_blocked ✓")
    if result.safety_intervened:
        bits.append("safety_intervened ✓")
    if result.no_retrieval:
        bits.append("no_retrieval ✓")
    st.caption(" · ".join(bits))


with tab_ask:
    st.subheader("Ask PawPal")
    st.caption(
        "Answers come from a small curated knowledge base under `knowledge/`. "
        "Toxic-food queries are intercepted before any LLM call."
    )

    _render_kb_warning()

    pet_choices = ["No specific pet"] + [
        f"{p.name} ({p.species}, {p.age}y)" for p in owner.pets
    ]
    selected = st.selectbox("Pet context", pet_choices, key="ask_pet")

    if selected == "No specific pet":
        chosen_pet: Pet | None = None
    else:
        chosen_name = selected.split(" (", 1)[0]
        chosen_pet = _pet_by_name(chosen_name)

    pet_ctx = (
        PetContext(species=chosen_pet.species, age=chosen_pet.age, name=chosen_pet.name)
        if chosen_pet
        else PetContext()
    )

    query = st.text_area(
        "Question",
        placeholder="e.g. What's a healthy morning routine for my golden retriever?",
        height=80,
    )

    col_a, col_b = st.columns([1, 4])
    with col_a:
        ask_clicked = st.button("Ask", type="primary", use_container_width=True)
    with col_b:
        st.caption(
            "Examples — ask about feeding, vaccines, toxic foods, or new-pet routines."
        )

    if ask_clicked:
        if not query.strip():
            st.warning("Type a question first.")
        elif not Path("chroma_db").exists():
            st.error(
                "Knowledge index missing. Run `python -m rag.index --rebuild` "
                "in your terminal, then reload this page."
            )
        else:
            with st.spinner("Thinking..."):
                try:
                    result = answer(query, pet_ctx)
                except Exception as exc:  # pragma: no cover — runtime fallback
                    st.error(f"Something went wrong: {exc}")
                else:
                    _render_answer(result)


st.divider()
st.caption(
    "CLI demo: `python main.py` · "
    "Tests: `python -m pytest` · "
    "Reindex KB: `python -m rag.index --rebuild`"
)

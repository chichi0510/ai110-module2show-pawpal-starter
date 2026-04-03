from __future__ import annotations

from datetime import date, time

import streamlit as st

from pawpal_system import Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="wide")

if "owner" not in st.session_state:
    st.session_state.owner = Owner("Chichi")

owner = st.session_state.owner


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


st.title("🐾 PawPal+")
st.caption("Domain logic lives in `pawpal_system.py`; this page uses **`Scheduler`** for sort, filter, and conflict checks.")

with st.expander("About this app", expanded=False):
    st.markdown(
        """
Data is stored in **`st.session_state.owner`**. The smart schedule view always goes through **`Scheduler`**:
sorted by date/time, optionally filtered, and checked for duplicate clock times.
"""
    )

scheduler = Scheduler(owner)

st.divider()

st.subheader("Owner")
owner.name = st.text_input("Owner name", value=owner.name)

st.subheader("Pets")
with st.form("add_pet_form", clear_on_submit=True):
    ap1, ap2, ap3 = st.columns(3)
    with ap1:
        fp_name = st.text_input("Pet name", key="form_pet_name")
    with ap2:
        fp_species = st.selectbox("Species", ["dog", "cat", "other"], key="form_pet_species")
    with ap3:
        fp_age = st.number_input("Age (years)", min_value=0, max_value=40, value=2, step=1, key="form_pet_age")
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
            f"Scheduled **{new_task.description}** at [{new_task.time}] on **{new_task.due_date}** for **{target.name}**."
        )

st.divider()

st.subheader("Smart schedule (Scheduler)")
st.caption(
    "Uses **`sort_by_time`**, **`filter_tasks`**, and **`detect_time_conflicts`** — not a raw task dump."
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
    st.error("**Scheduling conflict** — two or more incomplete tasks share the same clock time. Adjust times or pets.")
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
                st.success("Marked complete. If daily/weekly, the next occurrence was added.")
                st.rerun()
    else:
        st.caption("No incomplete tasks.")
else:
    st.caption("Add tasks above to enable completion.")

st.divider()
st.caption("CLI demo: `python main.py` · Tests: `python -m pytest`")

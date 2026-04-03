from __future__ import annotations

from datetime import date, time

import streamlit as st

from pawpal_system import Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

if "owner" not in st.session_state:
    st.session_state.owner = Owner("Chichi")

owner = st.session_state.owner


def _pet_name_for_task(task: Task) -> str:
    for pet in owner.pets:
        if task in pet.tasks:
            return pet.name
    return "?"


def _pet_by_name(name: str) -> Pet | None:
    for pet in owner.pets:
        if pet.name == name:
            return pet
    return None


st.title("🐾 PawPal+")

st.markdown(
    """
**PawPal+** — UI in `app.py`, domain logic in `pawpal_system.py` (**Owner → Pet → Task**, **Scheduler**).
"""
)

with st.expander("Scenario", expanded=False):
    st.markdown(
        """
Add pets and tasks below; data lives on **`st.session_state.owner`** so it survives reruns.
"""
    )

st.divider()

st.subheader("Owner")
owner.name = st.text_input("Owner name", value=owner.name)

st.subheader("Pets")
st.caption("Submit creates a **`Pet`** and calls **`owner.add_pet(...)`**.")

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
    st.markdown("**Pets (from `st.session_state.owner.pets`)**")
    st.dataframe(
        [{"Name": p.name, "Species": p.species, "Age": p.age} for p in owner.pets],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No pets yet. Add one with the form above.")

st.markdown("### Schedule a task")
st.caption("Creates a **`Task`**, then **`pet.add_task(task)`** for the pet you select.")

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
            f"Scheduled **{new_task.description}** at [{new_task.time}] for **{target.name}**."
        )

st.markdown("#### Current tasks")
if owner.pets and any(p.tasks for p in owner.pets):
    rows = []
    for pet in owner.pets:
        for task in pet.tasks:
            rows.append(
                {
                    "Pet": pet.name,
                    "Description": task.description,
                    "Due": str(task.due_date),
                    "Time": task.time,
                    "Frequency": task.frequency,
                    "Done": task.is_completed,
                }
            )
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.caption("No tasks yet.")

st.divider()

st.subheader("Build schedule")
st.caption("`Scheduler(owner)` → due today, sorted by time; conflicts are exact same HH:MM.")

if st.button("Generate schedule"):
    scheduler = Scheduler(owner)
    today_tasks = scheduler.get_todays_tasks()
    for msg in scheduler.detect_time_conflicts(today_tasks):
        st.warning(msg)
    tasks = scheduler.sort_by_time(today_tasks)
    st.markdown("**Today's schedule**")
    if not tasks:
        st.info("No tasks due today.")
    else:
        for task in tasks:
            st.write(f"[{task.time}] {task.description} ({_pet_name_for_task(task)})")

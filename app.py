from __future__ import annotations

from datetime import date, time
from pathlib import Path

import streamlit as st

from pawpal.agent.executor import apply_plan, discard_plan, run as agent_run
from pawpal.agent.models import PlanResult
from pawpal.domain import Owner, Pet, Scheduler, Task
from pawpal.llm_client import LLMClient, LLMClientError
from pawpal.rag import index as rag_index
from pawpal.rag.models import AnswerResult
from pawpal.rag.qa import PetContext, answer

# Phase 3 — keep these constants in one place so RAG tab and Plan tab agree.
_CONFIDENCE_EMOJI = {"high": "🟢", "medium": "🟡", "low": "🔴"}
_CONFIDENCE_BLURB = {
    "high": "Verified by self-critique",
    "medium": "Review before acting",
    "low": "Low confidence — please consult a vet",
}

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
    "**Ask PawPal** runs Retrieval-Augmented answers with toxic-food guardrails. "
    "**Plan My Week** uses an agent loop (plan → tool calls → re-plan) to draft "
    "a multi-task schedule you review before applying."
)

with st.expander("About this app", expanded=False):
    st.markdown(
        """
- **Domain layer** (`pawpal/domain.py`): unchanged from PawPal+.
- **AI layer** (`pawpal/rag/`, `pawpal/guardrails/`, `pawpal/agent/`):
  RAG, deterministic toxic-food guardrails, and a Plan-Execute-Replan
  agent loop wrapped around the same domain objects.
- **Traces**: each Ask PawPal call writes to `logs/rag_trace.jsonl`; each
  Plan My Week run writes to `logs/agent_trace.jsonl`.
"""
    )

scheduler = Scheduler(owner)


# ---------------------------------------------------------------- tabs

tab_schedule, tab_ask, tab_plan = st.tabs(
    ["📅 Schedule", "🤖 Ask PawPal", "🧠 Plan My Week"]
)


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
            "Knowledge index not built yet. Run: "
            "`python -m pawpal.rag.index --rebuild`"
        )
        return
    if rag_index.kb_modified_after_index():
        st.warning(
            "⚠ The `knowledge/` corpus has changed since the index was last "
            "built. Run `python -m pawpal.rag.index --rebuild` to refresh."
        )


def _render_confidence_badge_rag(critic: dict | None) -> str | None:
    """Return a one-line markdown badge for a RAG critic, or None if unavailable."""
    if not critic:
        return None
    level = critic.get("level", "low")
    emoji = _CONFIDENCE_EMOJI.get(level, "⚪")
    blurb = _CONFIDENCE_BLURB.get(level, "")
    confidence = critic.get("confidence", 0.0)
    score = critic.get("score") or {}
    score_bits = " · ".join(
        f"{k}={float(score[k]):.2f}"
        for k in ("grounded", "actionable", "safe")
        if k in score
    )
    suffix = " (offline mock)" if critic.get("is_mock") else ""
    return (
        f"{emoji} **Confidence: {level}** ({confidence:.2f}) — {blurb}{suffix}\n\n"
        f"_{score_bits}_"
    )


def _render_bias_banner(warnings: list[dict]) -> None:
    for w in warnings:
        st.warning(f"⚖️ Bias check ({w.get('kind', '')}): {w.get('message', '')}")


def _render_answer(result: AnswerResult) -> None:
    """Render an AnswerResult applying the §3.5 critic / guardrail priority rule.

    Order of precedence for what the user sees first:
        1. Guardrail banner (input_blocked / safety_intervened) — wins outright
        2. Out-of-scope / no-retrieval informational box
        3. Confidence badge (high / medium / low) + answer
           - low collapses the answer body into an expander
    """
    guardrail_active = result.input_blocked or result.safety_intervened
    badge = _render_confidence_badge_rag(result.critic) if not guardrail_active else None

    if guardrail_active:
        st.error(result.text)
    elif result.out_of_scope:
        st.info(result.text)
    elif result.no_retrieval:
        st.warning(result.text)
    else:
        level = (result.critic or {}).get("level", "medium")
        if badge:
            if level == "low":
                st.error(badge)
            elif level == "medium":
                st.warning(badge)
            else:
                st.success(badge)
        if level == "low":
            with st.expander(
                "Show low-confidence answer (consult a vet before acting)",
                expanded=False,
            ):
                st.markdown(result.text)
                notes = (result.critic or {}).get("notes", "")
                if notes:
                    st.caption(f"Critic notes: {notes}")
        else:
            st.markdown(result.text)
            notes = (result.critic or {}).get("notes", "")
            if level == "medium" and notes:
                st.caption(f"Critic notes: {notes}")

    if result.bias_warnings:
        _render_bias_banner(result.bias_warnings)

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
                "Knowledge index missing. Run "
                "`python -m pawpal.rag.index --rebuild` in your terminal, "
                "then reload this page."
            )
        else:
            with st.spinner("Thinking..."):
                try:
                    result = answer(query, pet_ctx)
                except Exception as exc:  # pragma: no cover — runtime fallback
                    st.error(f"Something went wrong: {exc}")
                else:
                    _render_answer(result)


# ============================================================ TAB: Plan My Week


def _build_planning_client() -> tuple[LLMClient, bool]:
    """Return (client, used_mock). Falls back to mock when no API key is set."""
    try:
        return LLMClient(mock=False), False
    except LLMClientError:
        return LLMClient(mock=True), True


def _row_color(row: dict) -> str:
    if row.get("blocked_toxic"):
        return "🛑"
    if row.get("conflict"):
        return "⚠️"
    return "✅"


def _render_confidence_badge_plan(critic: dict | None) -> str | None:
    """One-line markdown badge for a Plan critic (axes: complete/specific/safe)."""
    if not critic:
        return None
    level = critic.get("level", "low")
    emoji = _CONFIDENCE_EMOJI.get(level, "⚪")
    blurb = _CONFIDENCE_BLURB.get(level, "")
    confidence = critic.get("confidence", 0.0)
    score = critic.get("score") or {}
    score_bits = " · ".join(
        f"{k}={float(score[k]):.2f}"
        for k in ("complete", "specific", "safe")
        if k in score
    )
    suffix = " (offline mock)" if critic.get("is_mock") else ""
    return (
        f"{emoji} **Plan confidence: {level}** ({confidence:.2f}) — {blurb}{suffix}\n\n"
        f"_{score_bits}_"
    )


def _plan_preview_rows(plan_result: PlanResult) -> list[dict]:
    """Merge added_tasks (from scratch) + any blocked steps for the diff view."""
    rows: list[dict] = []
    for added in plan_result.added_tasks:
        rows.append({**added, "blocked_toxic": False, "conflict": False})

    # Surface blocked / conflicting steps so the user can SEE what got refused.
    for step in plan_result.trace:
        if step.ok or step.tool != "add_task":
            continue
        reason = (step.meta or {}).get("reason")
        if reason in {"toxic_food", "conflict"}:
            args = step.args or {}
            rows.append(
                {
                    "pet_name": args.get("pet_name", "?"),
                    "description": args.get("description", "?"),
                    "time": args.get("time_hhmm", "?"),
                    "frequency": args.get("frequency", "?"),
                    "due_date": args.get("due_date_iso", "?"),
                    "blocked_toxic": reason == "toxic_food",
                    "conflict": reason == "conflict",
                }
            )
    return rows


with tab_plan:
    st.subheader("Plan My Week")
    st.caption(
        "Give a one-sentence goal — the agent drafts a plan, validates each "
        "step against your existing schedule + toxic-food guardrails, and "
        "shows you a preview to accept or discard."
    )

    if not owner.pets:
        st.info("Add at least one pet on the Schedule tab to enable planning.")
    else:
        plan_pet_choices = [p.name for p in owner.pets]
        plan_pet = st.selectbox("Plan for pet", plan_pet_choices, key="plan_pet")
        goal = st.text_area(
            "Goal",
            placeholder=(
                "e.g. 'Set up a healthy daily routine for Milo, including "
                "feeding, walking, and a weekly vet check-in.'"
            ),
            height=90,
            key="plan_goal",
        )
        gen_clicked = st.button("Generate plan", type="primary", key="plan_generate")

        if gen_clicked:
            if not goal.strip():
                st.warning("Type a goal first.")
            else:
                client, used_mock = _build_planning_client()
                if used_mock:
                    st.info(
                        "No `OPENAI_API_KEY` found — using the offline demo "
                        "planner. Add a key to `.env` for real LLM plans."
                    )
                with st.spinner("Drafting plan..."):
                    try:
                        plan_result = agent_run(
                            goal=goal,
                            owner=owner,
                            llm_client=client,
                            mock=used_mock,
                        )
                    except Exception as exc:  # pragma: no cover
                        st.error(f"Plan generation failed: {exc}")
                        plan_result = None
                if plan_result is not None:
                    st.session_state["last_plan"] = plan_result

        plan_result: PlanResult | None = st.session_state.get("last_plan")
        if plan_result is not None:
            st.markdown(f"**Status**: `{plan_result.status}`")
            if plan_result.block_reason:
                st.warning(plan_result.block_reason)
            top = plan_result.latest_plan
            if top and top.summary:
                st.caption(top.summary)

            # Phase 3 §3.4: plan confidence is a banner above the preview but
            # the preview table is NEVER collapsed — the user needs to see the
            # diff to make an informed Apply / Discard decision.
            plan_badge = _render_confidence_badge_plan(plan_result.critic)
            if plan_badge:
                level = (plan_result.critic or {}).get("level", "medium")
                if level == "low":
                    st.error(plan_badge)
                    notes = (plan_result.critic or {}).get("notes", "")
                    if notes:
                        st.caption(f"Critic notes: {notes}")
                elif level == "medium":
                    st.warning(plan_badge)
                else:
                    st.success(plan_badge)

            preview = _plan_preview_rows(plan_result)
            if preview:
                st.markdown("**Plan preview**")
                st.dataframe(
                    [
                        {
                            "": _row_color(r),
                            "Pet": r["pet_name"],
                            "Task": r["description"],
                            "Time": r["time"],
                            "Frequency": r["frequency"],
                            "Due": r["due_date"],
                        }
                        for r in preview
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(
                    "Legend: ✅ new safe step · ⚠️ blocked by clock conflict · "
                    "🛑 blocked by toxic-food guardrail"
                )
            else:
                st.info("No tasks were generated. Try a more specific goal.")

            with st.expander("🧠 Critic report", expanded=False):
                if plan_result.critic:
                    st.json(plan_result.critic, expanded=False)
                else:
                    st.caption(
                        "No critic report — the plan was blocked or empty before "
                        "any executable steps existed."
                    )

            with st.expander(
                f"🔍 Reasoning trace ({len(plan_result.trace)} steps · "
                f"{plan_result.replans} re-plan(s))",
                expanded=False,
            ):
                for i, step in enumerate(plan_result.trace, start=1):
                    icon = "✅" if step.ok else "❌"
                    st.markdown(
                        f"**{i}. {icon} `{step.tool}`** "
                        f"— plan v{step.plan_version}, step #{step.step_index}"
                    )
                    st.json(step.model_dump(), expanded=False)

            ca, cb, _ = st.columns([1, 1, 4])
            with ca:
                apply_clicked = st.button(
                    "✅ Apply to my pets",
                    key="plan_apply",
                    disabled=not plan_result.added_tasks
                    or plan_result.status not in {"preview", "exhausted"},
                )
            with cb:
                discard_clicked = st.button("❌ Discard", key="plan_discard")

            if apply_clicked:
                n = apply_plan(owner, plan_result)
                st.success(f"Applied {n} task(s) to your pets.")
                st.rerun()
            elif discard_clicked:
                discard_plan(plan_result)
                st.session_state.pop("last_plan", None)
                st.info("Plan discarded — your pets are unchanged.")
                st.rerun()


st.divider()
st.caption(
    "CLI demo: `python main.py` · "
    "Tests: `python -m pytest` · "
    "Reindex KB: `python -m pawpal.rag.index --rebuild`"
)

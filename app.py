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

st.set_page_config(
    page_title="PawPal AI",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------- visual style

_PAWPAL_CSS = """
<style>
:root {
    --pawpal-orange: #F77F00;
    --pawpal-orange-soft: #FCB85B;
    --pawpal-orange-tint: #FDF1E1;
    --pawpal-cream: #FFFBF5;
    --pawpal-ink: #2A1810;
    --pawpal-mid: #6B4F3B;
    --pawpal-border: rgba(247,127,0,0.18);
    --pawpal-shadow: 0 1px 3px rgba(42,24,16,0.06), 0 4px 14px rgba(42,24,16,0.04);
}

/* hero banner */
.pawpal-hero {
    background: linear-gradient(135deg, #F77F00 0%, #FCB85B 100%);
    color: #fff;
    padding: 1.6rem 2rem 1.4rem;
    border-radius: 18px;
    margin-bottom: 1.2rem;
    box-shadow: var(--pawpal-shadow);
}
.pawpal-hero h1 {
    color: #fff !important;
    margin: 0 0 0.3rem 0 !important;
    font-size: 2.4rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}
.pawpal-hero .pawpal-subtitle {
    color: rgba(255,255,255,0.95);
    margin: 0;
    font-size: 1rem;
    line-height: 1.5;
}
.pawpal-hero .pawpal-pill-row {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.9rem;
    flex-wrap: wrap;
}
.pawpal-hero-pill {
    background: rgba(255,255,255,0.22);
    color: #fff;
    padding: 0.32rem 0.8rem;
    border-radius: 999px;
    font-size: 0.86rem;
    font-weight: 500;
    backdrop-filter: blur(6px);
}

/* tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.4rem;
    border-bottom: 2px solid var(--pawpal-orange-tint);
}
.stTabs [data-baseweb="tab"] {
    font-size: 1rem;
    font-weight: 600;
    padding: 0.55rem 1.2rem;
    border-radius: 10px 10px 0 0;
    color: var(--pawpal-mid);
}
.stTabs [aria-selected="true"] {
    color: var(--pawpal-orange) !important;
    background: var(--pawpal-orange-tint);
}

/* generic card */
.pawpal-card {
    background: #fff;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    border: 1px solid var(--pawpal-border);
    box-shadow: var(--pawpal-shadow);
    margin: 0.6rem 0 0.8rem;
}

/* confidence pills */
.pawpal-pill {
    display: inline-block;
    padding: 0.28rem 0.8rem;
    border-radius: 999px;
    font-weight: 600;
    font-size: 0.92rem;
    margin-right: 0.4rem;
}
.pawpal-pill-high   { background: #E8F5E9; color: #1B5E20; border: 1px solid #66BB6A; }
.pawpal-pill-medium { background: #FFF8E1; color: #B7791F; border: 1px solid #F2C94C; }
.pawpal-pill-low    { background: #FFEBEE; color: #B71C1C; border: 1px solid #EF5350; }
.pawpal-pill-meta   { color: var(--pawpal-mid); font-size: 0.85rem; font-style: italic; }
.pawpal-pill-axes   { color: var(--pawpal-mid); font-size: 0.82rem; font-family: ui-monospace, monospace; }

/* source citations */
.pawpal-source {
    background: var(--pawpal-orange-tint);
    padding: 0.45rem 0.75rem;
    border-radius: 10px;
    font-family: ui-monospace, "SF Mono", monospace;
    font-size: 0.85rem;
    margin: 0.25rem 0;
    border-left: 3px solid var(--pawpal-orange);
    color: var(--pawpal-ink);
}

/* primary buttons */
.stButton > button[kind="primary"] {
    background: var(--pawpal-orange);
    border: 0;
    font-weight: 600;
    padding: 0.55rem 1.3rem;
    border-radius: 10px;
    box-shadow: 0 2px 6px rgba(247,127,0,0.25);
    transition: all 0.15s ease;
}
.stButton > button[kind="primary"]:hover {
    background: #E66F00;
    box-shadow: 0 3px 10px rgba(247,127,0,0.35);
    transform: translateY(-1px);
}

/* sidebar */
[data-testid="stSidebar"] {
    background: var(--pawpal-cream);
    border-right: 1px solid var(--pawpal-border);
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: var(--pawpal-ink); }

/* forms / inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox > div > div {
    border-radius: 10px !important;
}

/* dataframes */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--pawpal-border);
}

/* tighten heading spacing */
h2 { margin-top: 1.1rem !important; }
h3 { margin-top: 0.9rem !important; }

/* metric tiles in sidebar */
[data-testid="stSidebar"] [data-testid="stMetric"] {
    background: #fff;
    border-radius: 10px;
    padding: 0.5rem 0.7rem;
    border: 1px solid var(--pawpal-border);
}
</style>
"""

st.markdown(_PAWPAL_CSS, unsafe_allow_html=True)


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


# ---------------------------------------------------------------- sidebar

with st.sidebar:
    st.markdown("## 🐾 PawPal AI")
    st.caption("Module 4 final project · CodePath AI-110")

    n_pets = len(owner.pets)
    n_today = len(
        [t for p in owner.pets for t in p.tasks if t.due_date == date.today()]
    )

    sb1, sb2 = st.columns(2)
    sb1.metric("Pets", n_pets)
    sb2.metric("Tasks today", n_today)

    st.divider()

    st.markdown("**📺 Live demo**")
    st.markdown(
        "[Loom walkthrough (~6 min)](https://www.loom.com/share/daa28affbbf94c60ac6a70e01837bc9f)"
    )
    st.markdown("**🐙 Source code**")
    st.markdown(
        "[chichi0510/...pawpal-starter](https://github.com/chichi0510/ai110-module2show-pawpal-starter)"
    )
    st.markdown("**📊 Eval results**")
    st.caption(
        "Median (n=3, gpt-4o-mini): RAG **100%** · Safety **100%** · "
        "Plan **90%** · AUROC **0.78** · 103/103 unit tests."
    )

    st.divider()
    with st.expander("How the layers fit", expanded=False):
        st.markdown(
            """
- **Domain** (`pawpal/domain.py`) — unchanged Module 1–3 scheduler.
- **RAG** (`pawpal/rag/`) — Ask PawPal tab.
- **Agent** (`pawpal/agent/`) — Plan My Week tab.
- **Guardrails** (`pawpal/guardrails/`) — deterministic, outside the LLM.
- **Critic** (`pawpal/critic/`) — calibrated confidence on every output.
- **Logs** — `logs/rag_trace.jsonl`, `logs/agent_trace.jsonl`.
"""
        )


# ---------------------------------------------------------------- hero

st.markdown(
    """
<div class="pawpal-hero">
  <h1>🐾 PawPal AI</h1>
  <p class="pawpal-subtitle">A reliability-first pet-care assistant — RAG, agentic planning, and a self-critic on top of a deterministic scheduler.</p>
  <div class="pawpal-pill-row">
    <span class="pawpal-hero-pill">📅 Schedule</span>
    <span class="pawpal-hero-pill">🤖 Ask PawPal · RAG</span>
    <span class="pawpal-hero-pill">🧠 Plan My Week · Agent</span>
    <span class="pawpal-hero-pill">🛡️ Guardrails + Self-critic</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

scheduler = Scheduler(owner)


# ---------------------------------------------------------------- tabs

tab_schedule, tab_ask, tab_plan = st.tabs(
    ["📅 Schedule", "🤖 Ask PawPal", "🧠 Plan My Week"]
)


# ============================================================ TAB: Schedule

with tab_schedule:
    overview_cols = st.columns(4)
    overview_cols[0].metric("Owner", owner.name or "—")
    overview_cols[1].metric("Pets", len(owner.pets))
    overview_cols[2].metric(
        "Total tasks", sum(len(p.tasks) for p in owner.pets)
    )
    overview_cols[3].metric(
        "Tasks today",
        len([t for p in owner.pets for t in p.tasks if t.due_date == date.today()]),
    )

    st.divider()

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


def _confidence_pill_html(
    critic: dict | None,
    axes: tuple[str, ...] = ("grounded", "actionable", "safe"),
    label: str = "Confidence",
) -> str | None:
    """HTML pill for the critic — same data, prettier shell."""
    if not critic:
        return None
    level = critic.get("level", "low")
    emoji = _CONFIDENCE_EMOJI.get(level, "⚪")
    blurb = _CONFIDENCE_BLURB.get(level, "")
    confidence = float(critic.get("confidence", 0.0))
    score = critic.get("score") or {}
    score_bits = " · ".join(
        f"{k}={float(score[k]):.2f}" for k in axes if k in score
    )
    suffix = " · offline mock" if critic.get("is_mock") else ""
    pill = (
        f'<span class="pawpal-pill pawpal-pill-{level}">'
        f"{emoji} {label}: {level.upper()} · {confidence:.2f}"
        f"</span>"
    )
    meta = f'<span class="pawpal-pill-meta">{blurb}{suffix}</span>'
    axes_line = (
        f'<div class="pawpal-pill-axes">{score_bits}</div>' if score_bits else ""
    )
    return f"<div>{pill}{meta}</div>{axes_line}"


def _render_confidence_badge_rag(critic: dict | None) -> str | None:
    """Backwards-compatible alias kept for tests/external callers."""
    return _confidence_pill_html(critic, ("grounded", "actionable", "safe"))


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
            st.markdown(badge, unsafe_allow_html=True)
        if level == "low":
            with st.expander(
                "Show low-confidence answer (consult a vet before acting)",
                expanded=False,
            ):
                st.markdown(
                    f'<div class="pawpal-card">{result.text}</div>',
                    unsafe_allow_html=True,
                )
                notes = (result.critic or {}).get("notes", "")
                if notes:
                    st.caption(f"Critic notes: {notes}")
        else:
            st.markdown(
                f'<div class="pawpal-card">{result.text}</div>',
                unsafe_allow_html=True,
            )
            notes = (result.critic or {}).get("notes", "")
            if level == "medium" and notes:
                st.caption(f"Critic notes: {notes}")

    if result.bias_warnings:
        _render_bias_banner(result.bias_warnings)

    if result.sources:
        st.markdown("**Sources**")
        for c in result.sources:
            head = (
                f' &nbsp;<span style="color:#6B4F3B;">— {c.heading}</span>'
                if c.heading
                else ""
            )
            st.markdown(
                f'<div class="pawpal-source">[{c.n}] {c.source_path}{head}</div>',
                unsafe_allow_html=True,
            )

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
    """One-line styled badge for a Plan critic (axes: complete/specific/safe)."""
    return _confidence_pill_html(
        critic,
        ("complete", "specific", "safe"),
        label="Plan confidence",
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
                st.markdown(plan_badge, unsafe_allow_html=True)
                level = (plan_result.critic or {}).get("level", "medium")
                if level == "low":
                    notes = (plan_result.critic or {}).get("notes", "")
                    if notes:
                        st.caption(f"Critic notes: {notes}")

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
st.markdown(
    """
<div style="text-align:center; color: var(--pawpal-mid); font-size: 0.85rem;
            padding: 0.5rem 0 1rem;">
  Built on the Module 1–3 PawPal+ scheduler ·
  CLI demo: <code>python main.py</code> ·
  Tests: <code>python -m pytest</code> ·
  Reindex KB: <code>python -m pawpal.rag.index --rebuild</code>
</div>
""",
    unsafe_allow_html=True,
)

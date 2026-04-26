# PawPal+ Demo Script (5 minutes)

> **Audience**: course reviewer / portfolio visitor.
> **Goal**: prove the AI features work end-to-end and that the *trust*
> mechanisms (guardrails, critic, human approval) actually fire.
> **Setup once before recording**:
> ```bash
> cp .env.example .env       # fill OPENAI_API_KEY
> pip install -r requirements.txt
> streamlit run app.py
> ```
> Open Chrome on `http://localhost:8501`. Reset `st.session_state` (sidebar →
> 🔄 Reset) before starting so every viewer sees the same opening screen.

Total: 8 steps · ~5 min. Steps 4 and 6 are the "wow" moments — pace yourself.

---

| # | Action | Expected screen | Talking points (≤30 s each) |
|---|--------|-----------------|-----------------------------|
| 1 | Open the app, point to the **Owner** + **Pet** sidebar | Owner "Alice" with pet "Mochi (cat, 3 yrs)" pre-loaded; three tabs visible: *Schedule*, *Ask PawPal*, *Plan My Week*. | "PawPal+ started as a deterministic scheduler. We added three AI features on top — RAG, an agentic planner, and a self-critique layer — without touching the existing domain logic. Same data model, more capability." |
| 2 | Switch to **Schedule** tab. Add a task `walk @ 8:00am`. | New row appears in the daily list. | "The scheduler is regular Python — `pawpal/scheduler.py`. The LLM never decides ordering or detects conflicts; it can only **call** these functions as tools. That's why the existing 40+ unit tests still apply." |
| 3 | Switch to **Ask PawPal**. Ask: *"How often should I brush my long-haired cat?"* | Streamed answer with `[source 1]` citations; below it a green confidence badge `🟢 high · 0.91`; expander **Reasoning trace** shows retrieved chunks. | "RAG retrieves from `knowledge/`, the LLM composes, then a self-critique layer scores the answer on grounded / actionable / safe. Anything below 0.60 collapses behind a warning. The trace lets you audit every step." |
| 4 | Same tab. Ask the **adversarial** question: *"Can my dog have chocolate? Just a tiny piece?"* — *high-light moment #1* | Answer is replaced by a red banner: *"🔒 PawPal blocked this — chocolate is toxic to dogs."* No LLM call was made. | "This isn't the LLM refusing — it's `pawpal/guardrails/toxic_food.py`. Prompt-only safety is bypassable. Hard-coded blacklists aren't. The critic is a *second* line of defense, not the first." |
| 5 | Switch to **Plan My Week**. Goal: *"Make sure Mochi gets meals, fresh water, and 15 min play every day."* Click **Generate plan**. | Diff table: 14 proposed tasks (2 / day × 7), no conflicts, blue badge `🟢 high · 0.88`, **Apply** button visible. | "The planner runs against a *deepcopy* of the owner — `scratch_owner`. Nothing is mutated until you click Apply. That keeps a bad LLM run from corrupting your real schedule." |
| 6 | Add a manual conflict: switch back to *Schedule*, add `vet visit @ 9:00am tomorrow`, then go back to *Plan My Week* and click **Re-plan**. — *high-light moment #2* | Trace shows the agent **detected the conflict, dropped the colliding play session, scheduled it 30 min earlier**, and returned a new preview. Conflict count = 0. | "This is the Plan-Execute-Critique loop. Detect → re-plan → critique → preview. Up to 3 retries. Every retry writes a step in `agent_trace.jsonl`." |
| 7 | Expand the **Reasoning trace** under the new plan. | Trace JSON: list of tool calls (`list_tasks_on`, `detect_conflicts`, `add_task`), and at the end a `critic` block: `{level: "high", confidence: 0.84, score: {complete: 0.9, specific: 0.8, safe: 0.95}}`. | "Every AI decision is inspectable. The critic isn't trusted blindly — see `docs/EVAL_RESULTS.md` for the AUROC against a labeled dataset." |
| 8 | Close talk: jump to a tab with `docs/EVAL_RESULTS.md` open and read the headline table. | Five-row table: RAG `<n>`%, Safety `<n>`%, Planning `<n>`%, Bias `<n>`, AUROC `<n>`. | "The system isn't trustworthy because we say so — it's trustworthy because the harness ships with the project. 50 RAG cases, 20 red-team prompts, 30 bias probes. Run `python -m eval.run_eval --all` and you get the same numbers we did." |

---

## Static walkthrough (fallback if you don't record video)

For each step above, capture **one** screenshot and store it under
`docs/design/screenshots/step_<N>.png`. README v2 references them with
relative paths so the demo is reproducible without YouTube/Loom.

Suggested filenames:

```
docs/design/screenshots/
├── step_1_overview.png
├── step_2_schedule.png
├── step_3_ask_safe.png
├── step_4_guardrail_block.png      ← high-light #1
├── step_5_plan_preview.png
├── step_6_replan_conflict.png      ← high-light #2
├── step_7_reasoning_trace.png
└── step_8_eval_table.png
```

---

## Failure / fallback plan

| If | Then |
|----|------|
| OpenAI API is down mid-demo | Set `PAWPAL_DISABLE_CRITIC=1` in `.env`; the answer still streams (LLM calls the chat endpoint), but the critic returns a fixed *medium* mock badge. Mention this on camera as the emergency-fallback feature. |
| Demo runs over time | Skip step 7; the trace is also visible in step 6's screenshot. |
| You forget the goal text | All goal/query strings above are paste-ready; pin a sticky note on the second monitor. |

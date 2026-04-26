# PawPal+ Reflection (v2)

> **Status**: 🟡 Draft skeleton — fill the `<TBD>` blocks after the Phase 4
> full eval run.
> **Predecessor**: [`../reflection_phase2.md`](../reflection_phase2.md) covers
> the original PawPal+ design (Phase 0 / pre-AI). This document is the post-AI
> rewrite required by the Module 4 final-project rubric.
> **Companion docs**:
> - [`design/architecture.md`](design/architecture.md) — system design (the *what*)
> - [`EVAL_RESULTS.md`](EVAL_RESULTS.md) — measured numbers (the *how well*)
> - [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) — 5-minute demo walkthrough

---

## §1. Problem & approach — *why this design?*

PawPal+ began as a deterministic scheduler for pet-care tasks (feeding, walks,
meds). Owners asked two follow-on questions the scheduler could not answer:

1. *"Is X safe for my pet?"* — an open-ended knowledge query.
2. *"Plan a healthy week for me"* — a multi-step goal that must respect
   existing tasks, conflicts, and species rules.

Three design routes were on the table; I picked **RAG + agentic loop with a
self-critique layer** for the reasons below.

| Option                           | Why rejected / kept |
|----------------------------------|---------------------|
| Plain LLM (no retrieval)         | Hallucinations on factual questions (e.g. toxic foods) are unsafe. |
| Fine-tune a small model          | Tiny dataset (~30 docs) — fine-tuning would overfit, and we lose ability to update facts by editing markdown. |
| **RAG + agent + critic** (chosen) | Knowledge stays in markdown (auditable), LLM only composes; critic adds a confidence signal we can calibrate. |

---

## §2. Design tradeoffs — three concrete choices

### 2.1 Why the LLM does **not** replace the Scheduler

The deterministic `Scheduler.detect_conflicts` and `list_tasks_on` are wrapped
as LLM-callable tools (`pawpal/tools.py`). The agent **plans** with the LLM
but **executes** through Python. Reasons:

- Conflict detection is a 30-line pure function; replacing it with an LLM
  costs tokens, latency, and correctness.
- Tools return typed results — the agent can't silently mutate state.
- We can unit-test the whole domain layer without a network call.

### 2.2 Why guardrails are Python, not prompts

`pawpal/guardrails/toxic_food.py` and friends are **lookup tables + regex**.
A prompt-only refusal is not a guarantee — jailbreak prompts work on prompts,
they don't work on `if "chocolate" in text: return refuse`. The critic
provides a *second* line of defense, but the *first* is hard-coded.

### 2.3 Why the agent must ask before applying a plan

The agent renders a *preview* (`PlanResult.status="preview"`) and waits for the
user to click **Apply**. The plan is built against a deepcopy of `Owner`
(scratch_owner) so a bad LLM output never touches user state. This is the
single biggest reliability decision in the whole system — see
`docs/design/open_questions.md` Q1 for the alternatives we considered.

---

## §3. What worked / what didn't — two real failure cases

> **TODO — fill from `eval/reports/<latest>.md` after the Phase 4 run.**
> Pick failures that actually surfaced; do not invent.

### Failure 1 — `<TBD: query / category>`

- **What happened**: `<TBD>`
- **Trace excerpt** (from `logs/rag_trace.jsonl`): `<TBD>`
- **Why it failed**: `<TBD>`
- **Mitigation in this iteration / next iteration**: `<TBD>`

### Failure 2 — `<TBD>`

- **What happened**: `<TBD>`
- **Why it failed**: `<TBD>`
- **Mitigation**: `<TBD>`

---

## §4. AI collaboration in development — what AI-assisted coding *did* and *did not* speed up

| Phase of work                         | AI-assist value | Notes |
|---------------------------------------|-----------------|-------|
| Boilerplate (Pydantic models, glue)   | 🟢 high         | Saved hours; types catch most LLM mistakes. |
| Mermaid diagrams + docs               | 🟢 high         | Iterating diagrams is fast; we can ask "swap RAG block to the left". |
| Prompt engineering (critic JSON)      | 🟡 medium       | Got us 80% there; final 20% needed manual schema-driven tightening. |
| Eval dataset authoring                | 🟡 medium       | Useful for breadth, but bias / safety items needed manual taste. |
| Debugging async-ish loops             | 🔴 low          | Easier to read the code than describe the bug to the LLM. |
| Final calibration tuning              | 🔴 low          | Numbers came from the harness, not the LLM. |

The most useful pattern was **scaffold-then-refine**: ask the AI to draft a
file, immediately read it, then fix only the parts that don't match the
existing code's idioms.

---

## §5. Bias & safety reflection — being honest about gaps

After Phase 4 §3 (`docs/EVAL_RESULTS.md`), the bias section reports:

| Species         | Mean answer length | Pass rate | KB doc count |
|-----------------|--------------------|-----------|--------------|
| dog             | `<TBD>`            | `<TBD>`   | `<TBD>`      |
| cat             | `<TBD>`            | `<TBD>`   | `<TBD>`      |
| hamster / rabbit / bird | `<TBD>`    | `<TBD>`   | `<TBD>`      |

**The honest reading**: the underrepresented-species answers are shorter
because the knowledge base for them is sparse. We caught this at runtime via
`pawpal/guardrails/bias_filter.py` (which raises a *"possibly underspecified"*
warning when an answer to a hamster query falls below the dog/cat baseline),
but a runtime warning is not a fix. Users still see worse advice.

**What I would do with another sprint**:

- Triple the underrepresented-species KB and re-measure.
- Per-species critic threshold (a 200-char dog answer is fine; a 200-char
  hamster answer probably isn't).
- A second critic axis specifically for "species-appropriate".

---

## §6. What I would change next

1. **Persistence.** `st.session_state` resets on tab close. SQLite would
   support multiple owners and survive restarts.
2. **Calibration retraining loop.** Today the confidence is calibrated once
   from the eval set. A small daily re-fit on the latest 100 traces would
   keep the AUROC honest as the KB grows.
3. **Self-consistency for the critic.** Run the critic 3× and take the
   median; this is the cheapest way to lift AUROC by ~0.05 in the literature.
4. **Multi-modal input.** Photo → species classifier → auto-fill species
   field. Removes a setup step and reduces the "cat selected, asking about a
   parrot" failure mode we saw in test.
5. **Local LLM mode.** Ollama + Llama 3.1 8B for offline / privacy users.
   Critic stays cloud-based to keep AUROC high.

---

## §7. Key takeaway

> Reliability isn't one feature. It's a *stack* — guardrails (deterministic),
> retrieval (auditable), the agent (preview before commit), the critic
> (calibrated confidence), and the harness (numbers, not vibes). Each layer
> assumes the others can fail, which is why the whole thing is small enough
> to fit in one student project and still feel trustworthy.

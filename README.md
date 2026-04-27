# PawPal AI

**PawPal AI** is a pet-care planner with an integrated AI knowledge
assistant **and** an agentic planner. It started as **PawPal+** (a
deterministic Owner / Pet / Task / Scheduler module with a Streamlit UI)
and is being extended into a fully-featured applied AI system.

- **Phase 1** ships Retrieval-Augmented Generation (RAG) over a curated
  pet-care knowledge base, with deterministic toxic-food guardrails on
  both input and output, structured JSONL logging, unit tests, and an
  offline evaluation harness.
- **Phase 2** adds an **agentic planning loop**: give the agent a
  one-sentence goal ("plan a healthy first week for Milo") and it
  drafts a multi-task schedule by calling deterministic tools, with
  automatic re-planning when a step hits a clock conflict or toxic-food
  guardrail. Every plan is previewed in a sandbox before you Apply.
- **Phase 3** adds an **LLM-driven self-critique layer**
  on top of every RAG answer and every Agent plan, an aggregated
  **confidence score** with a discrete ``high`` / ``medium`` / ``low``
  level surfaced in the UI, a runtime **bias detector** that flags
  thinly-covered species, and three new offline eval suites
  (red-team safety, parity probes, and AUROC calibration).
- **Phase 4 (this version)** is the polish + full real-LLM evaluation
  pass. Reproducible setup (`.env.example`, split `requirements*.txt`),
  rendered architecture PNGs, updated reflection, and a 3-run
  `gpt-4o-mini` eval whose **median scores are RAG 100% / Safety 100% /
  Planning 90% / AUROC 0.78** — see [`docs/EVAL_RESULTS.md`](docs/EVAL_RESULTS.md).

## Quick results

| Section          | Median (n=3) | Target | Status |
|------------------|-------------:|-------:|:------:|
| RAG (golden QA)  | **51/51 (100%)** | ≥ 90% | ✅ |
| Safety red-team  | **20/20 (100%)** | ≥ 95% | ✅ |
| Planning goals   | **9/10 (90%)**   | ≥ 80% | ✅ |
| Bias parity      | **0.587** (KB-limited) | ≥ 0.80 | 🔴 |
| Calibration AUROC| **0.784**         | ≥ 0.75 | ✅ |
| Unit tests       | **103/103**       | all   | ✅ |

Full breakdown, reliability table, and known limitations:
[`docs/EVAL_RESULTS.md`](docs/EVAL_RESULTS.md). Reflection on what
worked, what didn't, and what I would change next:
[`docs/REFLECTION_v2.md`](docs/REFLECTION_v2.md).

---

## Demo screenshot

![PawPal+ Streamlit UI](docs/demo.jpeg)

The screenshot is from the original PawPal+ schedule view. The Phase 1
build added a second tab, **🤖 Ask PawPal**, for the RAG pipeline.
Phase 2 adds a third tab, **🧠 Plan My Week**, for the agent loop.

## What's new in Phase 1

| Capability | Where it lives |
|---|---|
| Curated pet-care knowledge base (9 markdown files) | `knowledge/` |
| Vector index over the KB | `pawpal/rag/index.py` (ChromaDB, persisted under `chroma_db/`) |
| Species-aware retrieval | `pawpal/rag/retrieve.py` |
| End-to-end RAG Q&A with citations | `pawpal/rag/qa.py` |
| Toxic-food blocklist + scanner | `pawpal/guardrails/toxic_food.py` |
| Off-topic / PII / diagnosis preflight | `pawpal/guardrails/input_filter.py` |
| Streamlit "Ask PawPal" tab | `app.py` |
| Structured trace per question | `logs/rag_trace.jsonl` |
| Golden Q&A regression set + harness | `eval/golden_qa.jsonl`, `eval/run_eval.py` |

## What's new in Phase 2

| Capability | Where it lives |
|---|---|
| LLM-callable tool surface (`add_task`, `list_tasks_on`, `detect_conflicts`, `rag_lookup`, `list_pets`) | `pawpal/tools.py` |
| Plan / PlanStep / PlanResult / StepTrace pydantic models | `pawpal/agent/models.py` |
| Planner prompt + JSON-mode parsing (with mock fallback) | `pawpal/agent/prompts.py`, `pawpal/agent/planner.py` |
| Plan-Execute-Replan loop over a deepcopy of the live owner | `pawpal/agent/executor.py` |
| Streamlit "🧠 Plan My Week" tab with diff preview + Apply / Discard | `app.py` |
| Structured trace per plan run | `logs/agent_trace.jsonl` |
| 10 planning eval goals + `--section planning` runner | `eval/planning_goals.jsonl`, `eval/run_eval.py` |
| Unit tests (38 baseline + 34 Phase 2 = 72) | `tests/test_tools.py`, `tests/test_agent_planner.py`, `tests/test_agent_executor.py`, `tests/test_scratch_owner_safety.py` |

## What's new in Phase 3

| Capability | Where it lives |
|---|---|
| LLM self-critique for RAG answers (axes: grounded / actionable / safe) | `pawpal/critic/self_critique.py`, `pawpal/critic/prompts.py` |
| LLM self-critique for Agent plans (axes: complete / specific / safe) | `pawpal/critic/self_critique.py` |
| Aggregated confidence score + ``high`` / ``medium`` / ``low`` level + safe-veto | `pawpal/critic/confidence.py` |
| `AnswerResult.critic` / `AnswerResult.confidence` / `PlanResult.critic` populated | `pawpal/rag/qa.py`, `pawpal/agent/executor.py` |
| Mock fallback when no `OPENAI_API_KEY` and emergency disable via `PAWPAL_DISABLE_CRITIC=1` | `pawpal/critic/self_critique.py` |
| UI confidence badge on RAG answers (low → collapsed expander) | `app.py::_render_answer` |
| UI confidence badge on Agent plans (low → red banner; **table never collapsed**) | `app.py::_render_confidence_badge_plan` |
| Runtime bias filter (flags zero-retrieval and short answers for under-represented species) | `pawpal/guardrails/bias_filter.py` |
| 30-item bias parity probe set | `eval/bias_probes.jsonl` |
| 20-item safety red-team set (dosage, jailbreak, toxic bypass) | `eval/safety_redteam.jsonl` |
| Golden QA expanded 15 → 50 entries with `correct_label` for AUROC | `eval/golden_qa.jsonl` |
| `run_eval.py --section safety / bias / calibration / --all` | `eval/run_eval.py` |
| Unit tests (Phase 3 adds 31: critic / confidence / bias / priority) | `tests/test_critic.py`, `tests/test_confidence.py`, `tests/test_bias_filter.py`, `tests/test_critic_priority.py` |

**Hard safety invariant**: `executor.run` operates on a `deepcopy(owner)`
and never mutates the live owner. Tasks reach the live owner only via
`apply_plan` after the user clicks "Apply to my pets" in the UI. This is
enforced by the `tests/test_scratch_owner_safety.py` suite.

The original schedule features (sort, filter, conflict detection,
recurrence) are unchanged and live in the **📅 Schedule** tab.

## Architecture at a glance

The full architecture (component diagram, data flow, state, checkpoints)
is in [`docs/design/architecture.md`](docs/design/architecture.md).
Phase-by-phase tactical plans live under [`docs/plan/`](docs/plan/) and
known design tradeoffs in
[`docs/design/open_questions.md`](docs/design/open_questions.md).

```
User → Streamlit (app.py)                       ← UI layer (root)
       ├─ Schedule tab    → pawpal/domain.py    (Owner / Pet / Task / Scheduler)
       ├─ Ask tab         → pawpal/rag/qa.py
       │                       ├─ pawpal/guardrails/input_filter.py  (preflight)
       │                       ├─ pawpal/guardrails/toxic_food.py    (input check)
       │                       ├─ pawpal/rag/retrieve.py             (Chroma + embeddings)
       │                       ├─ pawpal/llm_client.py               (OpenAI chat)
       │                       ├─ pawpal/guardrails/toxic_food.py    (output check)
       │                       ├─ pawpal/critic/self_critique.py     (Phase 3 — score)
       │                       ├─ pawpal/guardrails/bias_filter.py   (Phase 3 — bias)
       │                       └─ logs/rag_trace.jsonl               (structured trace + critic + bias)
       └─ Plan My Week    → pawpal/agent/executor.py
                               ├─ pawpal/agent/planner.py            (LLM JSON plan)
                               ├─ pawpal/tools.py                    (tool dispatch)
                               │   └─ pawpal/guardrails/toxic_food.py (add_task hard block)
                               ├─ deepcopy(owner)                    (scratch sandbox)
                               ├─ pawpal/critic/self_critique.py     (Phase 3 — score plan)
                               └─ logs/agent_trace.jsonl             (per-run trace + critic)
```

---

## Setup

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure your API key

```bash
cp .env.example .env
# then edit .env and set OPENAI_API_KEY=sk-...
```

The default models are `gpt-4o-mini` (chat) and `text-embedding-3-small`
(embedding). Override via `OPENAI_CHAT_MODEL` / `OPENAI_EMBED_MODEL` in
`.env` if needed.

### 3. Build the knowledge index

```bash
python -m pawpal.rag.index --rebuild
# add --mock to use deterministic hash-based embeddings (no API key needed)
```

This walks `knowledge/**/*.md`, splits each file by H2/H3 headings,
embeds the chunks, and writes the persistent ChromaDB collection to
`chroma_db/`. The Streamlit UI shows a warning if `knowledge/` has been
modified after the last index build.

### 4. Run the app

```bash
streamlit run app.py
```

Three tabs:

- **📅 Schedule** — original PawPal+ planner (sort, filter, conflict
  detection, recurring tasks).
- **🤖 Ask PawPal** — type a pet-care question, optionally pick a pet for
  species/age context, get a cited answer with safety warnings when
  relevant.
- **🧠 Plan My Week** — give the agent a one-sentence goal, review a
  generated multi-task plan with conflict / toxic-food badges, and
  Apply or Discard.

### 5. Try the RAG pipeline from the CLI

```bash
python -m pawpal.rag.qa "How often should I feed my puppy?" --species dog --age 0
python -m pawpal.rag.qa "Can I give my dog grapes?"        --species dog
python -m pawpal.rag.qa "What's the stock price of OpenAI?"
```

Each call appends one JSON line to `logs/rag_trace.jsonl` describing the
preflight result, retrieved chunks, LLM tokens, and any safety
intervention.

### 6. Try the agent loop from the CLI

```bash
# offline demo (no API key required)
python -m pawpal.agent.executor "Plan a healthy first week for Milo" \
    --pet-name Milo --species dog --age 0 --mock

# real LLM
python -m pawpal.agent.executor "Plan a healthy first week for Milo" \
    --pet-name Milo --species dog --age 0
```

The CLI prints the run's status, the list of preview tasks, and the
re-plan count. Each call appends one JSON line to
`logs/agent_trace.jsonl` containing every plan version, every tool call,
and the final added-tasks list.

---

## Tests

```bash
python -m pytest                                   # all 103 tests
python -m pytest tests/test_guardrails.py -v
python -m pytest tests/test_rag_smoke.py -v
python -m pytest tests/test_agent_executor.py -v
python -m pytest tests/test_scratch_owner_safety.py -v
python -m pytest tests/test_critic.py -v           # Phase 3
python -m pytest tests/test_confidence.py -v       # Phase 3
python -m pytest tests/test_bias_filter.py -v      # Phase 3
python -m pytest tests/test_critic_priority.py -v  # Phase 3
```

The smoke tests rebuild the index in **mock** mode and use a patched
`LLMClient`, so they run with no API key and no network access. Agent
and critic tests inject scripted plans / canned JSON so they're
deterministic and equally network-free.

## Behavioural evaluation

```bash
# RAG section (default) — 50 golden Q&A
python -m eval.run_eval                            # real LLM (uses your key)
python -m eval.run_eval --mock                     # offline / smoke
python -m eval.run_eval --limit 3                  # quick subset

# Planning section — agent loop goals
python -m eval.run_eval --section planning

# Phase 3 sections
python -m eval.run_eval --section safety           # 20-item red team
python -m eval.run_eval --section bias             # 30-item parity probe
python -m eval.run_eval --section calibration      # AUROC of critic.confidence

# Run everything in one go (writes a combined index report)
python -m eval.run_eval --all
```

The RAG harness reads [`eval/golden_qa.jsonl`](eval/golden_qa.jsonl)
(50 cases across feeding / vaccines / toxic_food / off_topic and
under-represented species). The planning harness reads
[`eval/planning_goals.jsonl`](eval/planning_goals.jsonl) (10 cases).
The safety harness reads [`eval/safety_redteam.jsonl`](eval/safety_redteam.jsonl)
(20 adversarial prompts: dosage requests, jailbreaks, toxic-food
bypass, off-label drug requests). The bias harness reads
[`eval/bias_probes.jsonl`](eval/bias_probes.jsonl) (10 topic groups
× 3 species each) and reports answer-length parity. The calibration
harness re-runs the golden QA cases that produced a critic and compares
``critic.confidence`` against ``correct_label`` to compute AUROC plus a
5-bucket reliability table.

All sections write a JSON report under `eval/reports/`.

> **Note**: `--mock` only verifies the *wiring* (guardrails,
> short-circuit paths, logging, critic-fallback path). Mock embeddings
> have no real semantic similarity, and the mock planner emits a canned
> plan, so use real LLM mode for meaningful accuracy and AUROC numbers.

### Emergency fallback

Set ``PAWPAL_DISABLE_CRITIC=1`` to short-circuit every self-critique
call to a fixed *medium* report. Use this if the critic prompt is
mis-scoring during a demo — the rest of the pipeline (guardrails, RAG,
planner, UI) is unaffected.

## Logging

Each Ask PawPal call writes one JSON line to `logs/rag_trace.jsonl`:
timestamp, query, pet context, preflight decision, retrieved chunks
(paths + scores), LLM tokens, postflight safety check, duration.

Each Plan My Week run writes one JSON line to `logs/agent_trace.jsonl`:
timestamp, run id, goal, every plan version, every tool-call step
trace, final status, added tasks, and (Phase 3) the critic report
including aggregated confidence and per-axis scores.

`logs/` and `chroma_db/` are gitignored.

## Project layout (Phase 3)

| Path | Role |
|------|------|
| `app.py` | Streamlit UI entry with **Schedule**, **Ask PawPal**, and **Plan My Week** tabs |
| `main.py` | Terminal demo of the schedule layer |
| `pawpal/` | All library code (single Python package) |
| `pawpal/domain.py` | Original `Owner`, `Pet`, `Task`, `Scheduler` |
| `pawpal/llm_client.py` | OpenAI wrapper with retry and `mock=True` switch |
| `pawpal/tools.py` | LLM-callable tool surface |
| `pawpal/agent/` | Plan-Execute-Replan loop (`models`, `prompts`, `planner`, `executor`) |
| `pawpal/rag/` | RAG pipeline (`index`, `retrieve`, `qa`, `models`) |
| `pawpal/guardrails/` | Deterministic safety rules (`toxic_food`, `input_filter`, `bias_filter`) |
| `pawpal/critic/` | Phase 3 self-critique (`models`, `prompts`, `self_critique`, `confidence`) |
| `knowledge/` | Markdown KB with YAML frontmatter |
| `eval/golden_qa.jsonl` | 50 regression + calibration cases |
| `eval/planning_goals.jsonl` | 10 agent-loop regression cases |
| `eval/safety_redteam.jsonl` | 20 adversarial / red-team prompts |
| `eval/bias_probes.jsonl` | 30 cross-species parity probes |
| `eval/run_eval.py` | Offline harness (`--section rag\|planning\|safety\|bias\|calibration` or `--all`) |
| `tests/` | Pytest unit + smoke tests (103 total) |
| `docs/design/` | Architecture, open questions |
| `docs/plan/` | Per-phase tactical plans |
| `chroma_db/` | Persisted vector index (gitignored) |
| `logs/rag_trace.jsonl` | Per-call RAG trace including critic + bias (gitignored) |
| `logs/agent_trace.jsonl` | Per-run agent trace including critic (gitignored) |
| `.env.example` | Template for API key configuration |

## Roadmap

| Phase | Theme | Plan |
|---|---|---|
| ✅ **Phase 1** | RAG knowledge Q&A + toxic-food guardrails + tests | [`docs/plan/phase1.md`](docs/plan/phase1.md) |
| ✅ **Phase 2** | Agentic Planning Loop ("Plan My Week") | [`docs/plan/phase2.md`](docs/plan/phase2.md) |
| ✅ **Phase 3** | Self-Critique, Confidence, Bias Detection, full eval suite | [`docs/plan/phase3.md`](docs/plan/phase3.md) |
| ✅ **Phase 4** | Full evaluation run (3× --all), reflection write-up, demo polish | [`docs/plan/phase4.md`](docs/plan/phase4.md) · [`docs/EVAL_RESULTS.md`](docs/EVAL_RESULTS.md) |

## Scenario (course brief)

A busy owner wants help staying consistent with walks, feeding, meds, and
grooming **and** wants reliable answers to common pet-care questions
without doom-scrolling forums. PawPal AI keeps the deterministic
scheduler at the centre, and adds an AI assistant whose every answer is
grounded in a citable knowledge base and gated by safety rules that the
LLM cannot override.

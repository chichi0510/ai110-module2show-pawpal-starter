# PawPal AI

**PawPal AI** is a pet-care planner with an integrated AI knowledge assistant.
It started as **PawPal+** (a deterministic Owner / Pet / Task / Scheduler
module with a Streamlit UI) and is being extended into a fully-featured
applied AI system. **Phase 1 (this version) ships Retrieval-Augmented
Generation (RAG) over a curated pet-care knowledge base, with
deterministic toxic-food guardrails on both input and output, structured
JSONL logging, unit tests, and an offline evaluation harness.**

The wider plan (Agentic planning loop, self-critique with confidence,
bias detection, and a full evaluation suite) lives under
[`docs/plan/`](docs/plan/) and [`docs/design/`](docs/design/).

---

## Demo screenshot

![PawPal+ Streamlit UI](docs/demo.jpeg)

The screenshot is from the original PawPal+ schedule view. The Phase 1
build adds a second tab, **🤖 Ask PawPal**, that runs the RAG pipeline.

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
| Unit tests (38 total) | `tests/` |

The original schedule features (sort, filter, conflict detection,
recurrence) are unchanged and live in the **📅 Schedule** tab.

## Architecture at a glance

The full architecture (component diagram, data flow, state, checkpoints)
is in [`docs/design/architecture.md`](docs/design/architecture.md).
Phase-by-phase tactical plans live under [`docs/plan/`](docs/plan/) and
known design tradeoffs in
[`docs/design/open_questions.md`](docs/design/open_questions.md).

```
User → Streamlit (app.py)                      ← UI layer (root)
       ├─ Schedule tab  → pawpal/domain.py     (Owner / Pet / Task / Scheduler)
       └─ Ask tab       → pawpal/rag/qa.py
                            ├─ pawpal/guardrails/input_filter.py  (preflight)
                            ├─ pawpal/guardrails/toxic_food.py    (input check)
                            ├─ pawpal/rag/retrieve.py             (Chroma + embeddings)
                            ├─ pawpal/llm_client.py               (OpenAI chat)
                            ├─ pawpal/guardrails/toxic_food.py    (output check)
                            └─ logs/rag_trace.jsonl               (structured trace)
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

Two tabs:

- **📅 Schedule** — original PawPal+ planner (sort, filter, conflict
  detection, recurring tasks).
- **🤖 Ask PawPal** — type a pet-care question, optionally pick a pet for
  species/age context, get a cited answer with safety warnings when
  relevant.

### 5. Try the RAG pipeline from the CLI

```bash
python -m pawpal.rag.qa "How often should I feed my puppy?" --species dog --age 0
python -m pawpal.rag.qa "Can I give my dog grapes?"        --species dog
python -m pawpal.rag.qa "What's the stock price of OpenAI?"
```

Each call appends one JSON line to `logs/rag_trace.jsonl` describing the
preflight result, retrieved chunks, LLM tokens, and any safety
intervention.

---

## Tests

```bash
python -m pytest                         # all 38 tests
python -m pytest tests/test_guardrails.py -v
python -m pytest tests/test_rag_smoke.py -v
```

The smoke tests rebuild the index in **mock** mode and use a patched
`LLMClient`, so they run with no API key and no network access.

## Behavioural evaluation (golden Q&A)

```bash
python -m eval.run_eval                  # real LLM (uses your key)
python -m eval.run_eval --mock           # offline / smoke
python -m eval.run_eval --limit 3        # quick subset
```

The harness reads [`eval/golden_qa.jsonl`](eval/golden_qa.jsonl)
(15 cases across feeding / vaccines / toxic_food / general / off_topic),
runs each through `rag.qa.answer`, and reports per-category pass rate
plus a JSON file under `eval/reports/`.

> **Note**: `--mock` only verifies the *wiring* (guardrails, short-circuit
> paths, logging). Mock embeddings have no real semantic similarity, so
> retrieval-dependent cases will short-circuit. For genuine RAG accuracy
> numbers, run without `--mock`.

## Logging

Each Ask PawPal call writes one structured JSON line to
`logs/rag_trace.jsonl` with the timestamp, query, pet context, preflight
decision (input filter + toxic food), retrieved chunks (paths +
similarity scores), LLM token usage, postflight safety check, and
duration. Useful for debugging surprising answers and for offline
evaluation.

`logs/` and `chroma_db/` are gitignored.

## Project layout (Phase 1)

| Path | Role |
|------|------|
| `app.py` | Streamlit UI entry with **Schedule** and **Ask PawPal** tabs |
| `main.py` | Terminal demo of the schedule layer |
| `pawpal/` | All library code (single Python package) |
| `pawpal/domain.py` | Original `Owner`, `Pet`, `Task`, `Scheduler` (formerly `pawpal_system.py`) |
| `pawpal/llm_client.py` | OpenAI wrapper with retry and `mock=True` switch |
| `pawpal/tools.py` | Adapter functions wrapping domain objects (Phase 2 will extend this) |
| `pawpal/rag/` | RAG pipeline (`index`, `retrieve`, `qa`, `models`) |
| `pawpal/guardrails/` | Deterministic safety rules (`toxic_food`, `input_filter`) |
| `knowledge/` | Markdown KB with YAML frontmatter (species, topic, source) |
| `eval/golden_qa.jsonl` | 15 regression cases for the RAG pipeline |
| `eval/run_eval.py` | Offline evaluation harness |
| `tests/` | Pytest unit + smoke tests (38 total) |
| `docs/design/` | Architecture, open questions |
| `docs/plan/` | Per-phase tactical plans |
| `chroma_db/` | Persisted vector index (gitignored) |
| `logs/rag_trace.jsonl` | Per-call RAG trace (gitignored) |
| `.env.example` | Template for API key configuration |

## Roadmap

| Phase | Theme | Plan |
|---|---|---|
| ✅ **Phase 1** | RAG knowledge Q&A + toxic-food guardrails + tests | [`docs/plan/phase1.md`](docs/plan/phase1.md) |
| ◻️ Phase 2 | Agentic Planning Loop ("Plan My Week") | [`docs/plan/phase2.md`](docs/plan/phase2.md) |
| ◻️ Phase 3 | Self-Critique, Confidence, Bias Detection | [`docs/plan/phase3.md`](docs/plan/phase3.md) |
| ◻️ Phase 4 | Full evaluation, documentation, demo | [`docs/plan/phase4.md`](docs/plan/phase4.md) |

## Scenario (course brief)

A busy owner wants help staying consistent with walks, feeding, meds, and
grooming **and** wants reliable answers to common pet-care questions
without doom-scrolling forums. PawPal AI keeps the deterministic
scheduler at the centre, and adds an AI assistant whose every answer is
grounded in a citable knowledge base and gated by safety rules that the
LLM cannot override.

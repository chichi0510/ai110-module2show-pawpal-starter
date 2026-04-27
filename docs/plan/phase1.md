# Phase 1 Plan — RAG-Integrated PawPal MVP

> **Status**: Draft v1.0
> **Phase goal**: Upgrade PawPal+ into a Streamlit app with integrated RAG knowledge Q&A,
> meeting all hard requirements for the assignment's Phase 1 (useful AI · advanced feature · integrated into the main app
> · reproducible · logging · guardrails · clear setup).
> **Out of scope**: Agentic planning, self-critique, bias eval — all deferred to later phases.

---

## 0. Phase 1 Scope (what we will and won't do)

### In scope
- ✅ RAG knowledge Q&A module (retrieve + generate + cite)
- ✅ Add an "Ask PawPal" tab to `app.py`, coexisting with the existing Schedule feature
- ✅ One hard guardrail: toxic-food blocklist (scanned both on input and output)
- ✅ Structured logging (one JSONL line per RAG call)
- ✅ Knowledge base of 8–10 markdown documents
- ✅ `.env.example` + a complete `README` setup section
- ✅ At least 15 unit tests (tools + guardrail + retrieve)
- ✅ A minimal eval: 20 golden QA items + a one-command script

### Out of scope (deferred to later phases)
- ❌ Agentic planning loop (Phase 2)
- ❌ Self-critique / confidence scoring (Phase 3)
- ❌ Bias detection probes (Phase 3)
- ❌ Full 120-item eval set (Phase 4)
- ❌ Streamlit third "Plan My Week" tab (Phase 2)

---

## 1. Acceptance Criteria (mapped to assignment Phase 1 requirements)

| # | Assignment requirement | How this phase satisfies it | Verification |
|---|----------|-------------------|----------|
| 1 | Useful AI | RAG answers pet-care questions (feeding, toxic foods, vaccines) | Demo runs through 5 real questions end-to-end |
| 2 | Advanced feature: RAG | Full retrieve + generate implementation in the `rag/` module | `python -m rag.qa "..."` CLI works |
| 3 | Integrated into the main app | The "Ask PawPal" tab is part of `app.py`; users ask questions in the context of a selected Pet | After launching Streamlit you see the tab, and the answer uses the current Pet's species |
| 4 | Reproducible | Pinned versions in `requirements.txt`; `.env.example`; one block of README commands runs end-to-end | A clean virtualenv installs from scratch and starts successfully |
| 5 | Logging | Every RAG request writes to `logs/rag_trace.jsonl` | After a single Q&A you see one new record |
| 6 | Guardrails | Toxic-food blocklist scanned on both input and output | "Can I feed my dog chocolate?" → forced safe answer + red warning banner |
| 7 | Clear setup | README reproduces in 5 lines | A teammate can clone and run |

---

## 2. Module checklist (Phase 1 additions / modifications)

### Added

```
llm_client.py                  # OpenAI client wrapper (chat + embed)
tools.py                       # LLM-friendly wrappers around Pet/Scheduler
                               # In Phase 1 only list_pets is exported, so RAG can pull species context
rag/
├── __init__.py
├── index.py                   # Chunks knowledge/*.md and writes to ChromaDB
├── retrieve.py                # retrieve(query, species=None, k=4)
└── qa.py                      # answer(query, pet_context) -> AnswerResult
guardrails/
├── __init__.py
├── toxic_food.py              # blocklist + check_input + check_output
└── input_filter.py            # simple off-topic / PII filter
knowledge/
├── feeding/
│   ├── dog_feeding_basics.md
│   └── cat_feeding_basics.md
├── toxic_foods/
│   ├── dogs_toxic_list.md
│   └── cats_toxic_list.md
├── vaccines/
│   ├── dog_vaccine_schedule.md
│   └── cat_vaccine_schedule.md
└── general/
    ├── new_puppy_first_week.md
    └── new_kitten_first_week.md
eval/
├── golden_qa.jsonl            # 20 items
└── run_eval.py
logs/                          # gitignored
└── rag_trace.jsonl
.env.example                   # OPENAI_API_KEY=...
tests/
├── test_tools.py
├── test_guardrails.py
└── test_rag_smoke.py          # mocks the LLM, verifies retrieval + guardrail wiring
```

### Modified

```
app.py            # add the "Ask PawPal" tab; existing Schedule tab stays
README.md         # rewrite setup; add demo commands; add .env notes
requirements.txt  # add openai / chromadb / python-dotenv / pydantic
.gitignore        # add logs/ chroma_db/ .env
```

---

## 3. Task breakdown (in dependency order)

### Task 1.1 — Dependencies and environment (30 min)
- [ ] Add to `requirements.txt`:
  - `openai>=1.40`
  - `chromadb>=0.5`
  - `python-dotenv>=1.0`
  - `pydantic>=2.5`
- [ ] Write `.env.example`: `OPENAI_API_KEY=sk-...`
- [ ] Update `.gitignore`: `logs/`, `chroma_db/`, `.env`

### Task 1.2 — `llm_client.py` (1 h)
- [ ] Single class `LLMClient`, with methods:
  - `chat(messages, model="gpt-4o-mini")`
  - `embed(texts, model="text-embedding-3-small")`
- [ ] Read the key from `.env`; raise a clear error when missing
- [ ] Add an optional `mock=True` mode so unit tests don't hit the real API

### Task 1.3 — Knowledge base content (2 h)
- [ ] 8 markdown documents, each with frontmatter:
  ```yaml
  ---
  species: dog            # dog | cat | general
  topic: toxic_foods      # feeding | toxic_foods | vaccines | general
  source: ASPCA Animal Poison Control (2024)
  source_url: https://...
  last_reviewed: 2026-04
  ---
  ```
- [ ] Paraphrase content yourself (don't copy original text — avoid copyright issues)
- [ ] 300–800 words each, structured (H2/H3)

### Task 1.4 — `rag/index.py` (1 h)
- [ ] Scan `knowledge/**/*.md`
- [ ] Chunk by H2/H3, max 800 tokens, overlap 100
- [ ] Call `LLMClient.embed()`, write to ChromaDB collection `pawpal_kb`
- [ ] CLI: `python -m rag.index --rebuild`
- [ ] Preserve chunk metadata: `source_path`, `species`, `topic`, `heading`

### Task 1.5 — `rag/retrieve.py` (45 min)
- [ ] `retrieve(query: str, species: str | None = None, k: int = 4) -> list[Chunk]`
- [ ] When species is not None, pre-filter with `where={"species": {"$in": [species, "general"]}}`
- [ ] Return `Chunk(text, source_path, score, heading)`
- [ ] Wrap the client with `@st.cache_resource` to avoid reconnecting on every Streamlit rerun

### Task 1.6 — `guardrails/toxic_food.py` (1 h)
- [ ] Two dicts: `TOXIC_FOODS_DOG`, `TOXIC_FOODS_CAT`, each entry `{name, reason}`
- [ ] ≥ 15 entries per species (sourced from ASPCA / Cornell)
- [ ] `scan_text(text, species) -> list[Hit]`: returns hits (with reason)
- [ ] `check_input(text, species)`: when the user asks "can my dog eat X" and X hits → return a hard safe answer + skip the LLM
- [ ] `check_output(answer, species)`: scan the LLM answer; on hits without a "do not feed"-style warning → inject a red warning banner up front and mark `safety_intervened=True`

### Task 1.7 — `rag/qa.py` (2 h)
- [ ] Main entry `answer(query, pet_context) -> AnswerResult` (pydantic model)
- [ ] Flow:
  1. `input_filter.preflight(query)` → off-topic returns "out-of-scope" directly
  2. `toxic_food.check_input(query, species)` → on hit, return the hard safe answer
  3. `retrieve(query, species, k=4)`
  4. Assemble the prompt (see §4)
  5. `LLMClient.chat(messages)` for the raw answer
  6. `toxic_food.check_output(answer, species)`
  7. Write `logs/rag_trace.jsonl` (see §5)
  8. Return `AnswerResult(text, sources, safety_intervened, retrieved_chunks)`
- [ ] CLI: `python -m rag.qa "Can my dog eat grapes?" --species dog`

### Task 1.8 — Streamlit integration (2 h)
- [ ] At the top of `app.py`, use `st.tabs(["Schedule", "Ask PawPal"])`
- [ ] **Schedule tab**: keep the existing logic intact (don't change `pawpal_system.py`)
- [ ] **Ask PawPal tab**:
  - Pet dropdown (from `owner.pets`, plus an optional "No specific pet")
  - Question textbox + "Ask" button
  - Call `rag.qa.answer()` and render:
    - The answer body
    - Top red banner when `safety_intervened=True`
    - Citation block: each source shows its `source_path` (short path)
    - `expander("Show retrieved sources")` showing the original chunk text (trace transparency)
    - `caption("Latency: 1.2s · model: gpt-4o-mini")`

### Task 1.9 — Unit tests (1.5 h)
- [ ] `test_tools.py`: behavior of `tools.list_pets`
- [ ] `test_guardrails.py`: ≥ 12 cases
  - grape / dog → blocked, reason contains "kidney"
  - chocolate / dog → blocked
  - lily / cat → blocked
  - chocolate keyword in LLM output → warning banner injected
  - normal text ("morning walk") → passes
  - cross-species (grape isn't on the cat blocklist but still triggers a generic rule)
- [ ] `test_rag_smoke.py`: mock `LLMClient`, ensure `qa.answer()` wires retrieval + guardrail + log writes
- [ ] Existing `tests/test_pawpal.py` stays green

### Task 1.10 — Eval script (1.5 h)
- [ ] Write 20 entries in `eval/golden_qa.jsonl`, each:
  ```json
  {
    "id": "qa-001",
    "query": "Can my dog eat grapes?",
    "species": "dog",
    "must_contain": ["toxic", "kidney"],
    "must_not_contain": ["safe", "small amount is fine"]
  }
  ```
- [ ] Type distribution: 8 feeding / 6 toxic foods / 4 vaccines / 2 off-topic
- [ ] `eval/run_eval.py` runs the full set and outputs `eval/reports/run_<timestamp>.md`:
  - Overall pass rate
  - Failure detail (query / expected / actual)
  - Average retrieval latency + LLM latency
  - Number of guardrail hits

### Task 1.11 — Documentation (1.5 h)
- [ ] Rewrite the top of `README.md`:
  - One-sentence pitch ("PawPal AI = your existing domain model + RAG knowledge Q&A + safety guardrails")
  - Screenshot / GIF
  - Setup in 5 commands
- [ ] Add an "Architecture (Phase 1)" diagram section (mermaid or ASCII)
- [ ] Add a "How AI is used" section: explain the RAG flow + guardrail
- [ ] Keep existing Schedule docs as a "Domain layer" subsection

**Estimated total: ~14 h**, spread across 5–7 days of Week 1.

---

## 4. RAG prompt template (final form for Phase 1)

```
SYSTEM:
You are PawPal, a careful pet-care assistant.

Rules:
1. Use ONLY the context below. If it does not contain the answer,
   reply: "I don't have a verified answer — please consult a vet."
2. Cite each fact with [source N] referencing the numbered context.
3. Never recommend medication dosages.
4. If the user asks about a known toxic food, ALWAYS warn first.

Pet context: species={species}, age={age}

USER:
Question: {query}

Context:
[1] (from {chunk_1.source_path}) {chunk_1.text}
[2] (from {chunk_2.source_path}) {chunk_2.text}
[3] (from {chunk_3.source_path}) {chunk_3.text}
[4] (from {chunk_4.source_path}) {chunk_4.text}

Answer (with [source N] citations):
```

---

## 5. Logging format (`logs/rag_trace.jsonl`)

Each `qa.answer()` call appends one entry:

```json
{
  "ts": "2026-04-26T18:30:00Z",
  "run_id": "uuid",
  "query": "Can my golden retriever eat grapes?",
  "pet_context": {"species": "dog", "age": 3},
  "preflight": {
    "out_of_scope": false,
    "input_blocked": true,
    "block_reason": "toxic_food:grape"
  },
  "retrieved": [
    {"source": "knowledge/toxic_foods/dogs_toxic_list.md", "score": 0.89}
  ],
  "llm": {
    "model": "gpt-4o-mini",
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "skipped": true
  },
  "postflight": {"safety_intervened": false, "hits": []},
  "answer_chars": 240,
  "duration_ms": 12
}
```

> **Note**: when input hits the blocklist we skip the LLM call (saves tokens + faster), but we still write a complete trace — both the demo and the reflection rely on it.

---

## 6. Setup steps (content for the README)

```bash
# 1. Install dependencies
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure the API key
cp .env.example .env
# Edit .env and fill in OPENAI_API_KEY

# 3. Build the knowledge base index (required the first time)
python -m rag.index --rebuild

# 4. Launch the app
streamlit run app.py

# Optional: run tests / eval
python -m pytest
python -m eval.run_eval
```

---

## 7. Demo script (for acceptance, 5 minutes)

| Step | Action | Expected outcome |
|----|------|----------|
| 1 | Launch streamlit, switch to the "Ask PawPal" tab | See the dropdown + textbox |
| 2 | Pick Pet "Milo (dog)", ask "What's a healthy morning routine?" | Answer with [source N] citations; expanding sources shows the original snippets |
| 3 | Ask "Can I give my dog grapes?" | Red safety banner; LLM not called; trace shows `input_blocked=true` |
| 4 | Pick Pet "Luna (cat)", ask "What vaccines does my kitten need?" | Citation of `vaccines/cat_vaccine_schedule.md` |
| 5 | Ask "What's the stock price of OpenAI?" (off-topic) | "out-of-scope" safe response |
| 6 | Switch back to the "Schedule" tab and add a task as before | All original features still work, proving the integration is non-breaking |
| 7 | Terminal: `tail logs/rag_trace.jsonl` | See 5 structured trace entries |

---

## 8. Definition of Done (Phase 1)

Phase 1 ships only when every item below is checked:

- [ ] `streamlit run app.py` launches both tabs correctly in one go
- [ ] In the demo, all 5 real questions return reasonable answers with citations
- [ ] At least one test covers the toxic-food guardrail on both input and output
- [ ] `python -m pytest` is green, with ≥ 15 new tests
- [ ] `python -m eval.run_eval` reaches ≥ 80% pass rate (20 golden items)
- [ ] `logs/rag_trace.jsonl` has one entry per query
- [ ] A clean virtualenv reproduces by following the README
- [ ] No external services beyond the OpenAI API
- [ ] `docs/plan/phase1.md` is marked ✅ Done

---

## 9. Known risks and mitigations

| Risk | Probability | Impact | Mitigation |
|------|------|------|------|
| OpenAI API instability / rate limits | Medium | Medium | Add retry + exponential backoff to `LLMClient`; `mock=True` lets CI / unit tests run offline |
| ChromaDB re-initialized on Streamlit reload | High | Low | Wrap the retriever in `@st.cache_resource` |
| Knowledge base copyright | Medium | High | Paraphrase everything; frontmatter only stores the source URL, never copies original text |
| Eval accuracy plateaus | Medium | Medium | Phase 1 targets 80%, not 90%; failure cases feed back into KB improvements in Phase 2 |
| Schedule overrun | High | Medium | Task 1.10 (eval) and parts of 1.9 can spill into the start of Phase 2; everything else is on the critical path |
| LLM doesn't follow the citation format | Medium | Low | Strong prompt constraint + post-process regex extraction of `[source N]`; mark low confidence on miss |

---

## 10. Interface contract handed off to later phases

After Phase 1, the interfaces below must remain stable; Phase 2+ should not break them:

- The function signatures in `tools.py` are stable (Phase 2 will add more tools)
- `rag.qa.answer()` can be invoked directly by the agent as a tool
- `guardrails.toxic_food.scan_text()` is a deterministic pure function the agent calls before add_task
- `logs/` directory convention: `rag_trace.jsonl` (Phase 1) / `agent_trace.jsonl` (Phase 2) split into two files
- The public `Pet`/`Task`/`Scheduler` API in `pawpal_system.py` is unchanged

---

## 11. Changelog

| Date | Version | Change |
|------|------|------|
| 2026-04-26 | v1.0 | Initial draft; scope locked to RAG MVP + 1 guardrail |

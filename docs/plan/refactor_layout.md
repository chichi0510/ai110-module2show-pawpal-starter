# Refactor: Project Layout (Phase 1.5)

> **Scope**: A one-shot structural refactor that consolidates the flat top-level Python modules and sub-packages into a single `pawpal/` package.
> **When to run it**: After Phase 1 completes, before Phase 2 starts.
> **Estimated effort**: 1.5–2 hours (including verification).
> **Risk level**: Low (38 tests + mock eval act as a fallback safety net throughout).

## 1. Background and Motivation

After Phase 1 the repo root looks like this:

```
ai110-module2show-pawpal-starter/
├── app.py                 ← UI
├── main.py                ← CLI demo
├── pawpal_system.py       ← Domain
├── llm_client.py          ← AI infrastructure
├── tools.py               ← Domain adapters
├── rag/                   ← AI package
├── guardrails/            ← rules package
├── knowledge/  chroma_db/  logs/
├── eval/  tests/  docs/
└── requirements.txt / .env / README.md
```

Problems:

1. **The UI entry point `app.py` and library code sit on the same level**, with no visual separation.
2. **Python modules and packages are mixed**: the root contains 4 `.py` files (`app.py`/`main.py`/`pawpal_system.py`/`llm_client.py`/`tools.py`) plus 2 packages (`rag/`, `guardrails/`), so it is unclear "what is an entry point and what is a library".
3. **Phase 2/3 will add `agent/`, `critic/`, and `bias_filter`**, which would balloon the root to 6 `.py` files plus 5 packages.
4. **Inconsistent import style**: `from pawpal_system import` vs `from rag.qa import` vs `from llm_client import`.
5. **The architecture doc (`docs/design/architecture.md`) already defines 6 layers**, but the filesystem does not reflect that layering.

Goal: align the filesystem with the architecture doc and lay a clean skeleton for Phases 2/3/4.

## 2. Target Structure

```
ai110-module2show-pawpal-starter/
├── app.py                       ← Streamlit UI entry (kept at root)
├── main.py                      ← CLI demo (kept at root)
├── requirements.txt / .env / README.md
│
├── pawpal/                      ← all library code (single package)
│   ├── __init__.py              ← empty file
│   ├── domain.py                ← was pawpal_system.py
│   ├── llm_client.py
│   ├── tools.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── index.py
│   │   ├── retrieve.py
│   │   └── qa.py
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── toxic_food.py
│   │   └── input_filter.py
│   ├── (Phase 2) agent/
│   └── (Phase 3) critic/
│
├── knowledge/                   ← data, unchanged
├── chroma_db/  logs/            ← runtime (gitignored)
├── eval/                        ← evaluation, unchanged
├── tests/                       ← tests, unchanged
└── docs/                        ← docs, unchanged
```

### 2.1 Naming Notes

| Old name | New name | Rationale |
|---|---|---|
| `pawpal_system.py` | `pawpal/domain.py` | `from pawpal.pawpal_system import Owner` is too redundant; `domain` directly conveys "domain model layer" |
| `llm_client.py` | `pawpal/llm_client.py` | name kept |
| `tools.py` | `pawpal/tools.py` | name kept |
| `rag/` | `pawpal/rag/` | sub-package path gets a prefix |
| `guardrails/` | `pawpal/guardrails/` | sub-package path gets a prefix |

### 2.2 What Stays Put

- `app.py` and `main.py` stay at the root (Streamlit convention + CLI entry-point convention).
- `knowledge/`, `chroma_db/`, `logs/`, `eval/`, `tests/`, `docs/`, and `assets/` stay where they are (they are data/config/docs, not Python packages or libraries).
- `pawpal/__init__.py` stays empty — **no re-exports** (avoids namespace pollution and circular imports).

## 3. Acceptance Criteria

- [ ] The root-level `pawpal_system.py`, `llm_client.py`, `tools.py`, `rag/`, and `guardrails/` are all gone, with their files moved into `pawpal/`.
- [ ] `streamlit run app.py` still launches normally, with both **Schedule** and **Ask PawPal** tabs behaving identically.
- [ ] `python main.py` still prints the original CLI demo output.
- [ ] `python -m pytest` is still 38/38 PASS.
- [ ] `python -m rag.index --rebuild` is replaced by `python -m pawpal.rag.index --rebuild` and rebuilds the index correctly.
- [ ] `python -m eval.run_eval --mock` still runs, with the short-circuit cases all PASS.
- [ ] `README.md`, `docs/design/architecture.md`, `docs/plan/phase2.md`, `docs/plan/phase3.md`, `docs/plan/phase4.md`, and `docs/design/open_questions.md` have all stale path references updated.
- [ ] `pytest` does not introduce any deprecation/import warnings.
- [ ] `git status` is clean and `git mv` preserves history on the moved paths.

## 4. Import Rewrite Table

All imports that need to change, listed file by file. **Pure mechanical replacement** — no logic changes.

### 4.1 Move + Rename

| Old path | New path |
|---|---|
| `pawpal_system.py` | `pawpal/domain.py` |
| `llm_client.py` | `pawpal/llm_client.py` |
| `tools.py` | `pawpal/tools.py` |
| `rag/__init__.py` | `pawpal/rag/__init__.py` |
| `rag/models.py` | `pawpal/rag/models.py` |
| `rag/index.py` | `pawpal/rag/index.py` |
| `rag/retrieve.py` | `pawpal/rag/retrieve.py` |
| `rag/qa.py` | `pawpal/rag/qa.py` |
| `guardrails/__init__.py` | `pawpal/guardrails/__init__.py` |
| `guardrails/toxic_food.py` | `pawpal/guardrails/toxic_food.py` |
| `guardrails/input_filter.py` | `pawpal/guardrails/input_filter.py` |

### 4.2 Import Replacements

| File | Old import | New import |
|---|---|---|
| `app.py` | `from pawpal_system import Owner, Pet, Scheduler, Task` | `from pawpal.domain import Owner, Pet, Scheduler, Task` |
| `app.py` | `from rag import index as rag_index` | `from pawpal.rag import index as rag_index` |
| `app.py` | `from rag.models import AnswerResult` | `from pawpal.rag.models import AnswerResult` |
| `app.py` | `from rag.qa import PetContext, answer` | `from pawpal.rag.qa import PetContext, answer` |
| `main.py` | `from pawpal_system import Owner, Pet, Scheduler, Task` | `from pawpal.domain import Owner, Pet, Scheduler, Task` |
| `pawpal/tools.py` | `from pawpal_system import Owner` | `from pawpal.domain import Owner` |
| `pawpal/rag/__init__.py` | `from rag.models import Chunk, Citation, AnswerResult` | `from pawpal.rag.models import Chunk, Citation, AnswerResult` |
| `pawpal/rag/index.py` | `from llm_client import LLMClient` | `from pawpal.llm_client import LLMClient` |
| `pawpal/rag/retrieve.py` | `from llm_client import LLMClient` | `from pawpal.llm_client import LLMClient` |
| `pawpal/rag/retrieve.py` | `from rag.index import CHROMA_DIR, COLLECTION` | `from pawpal.rag.index import CHROMA_DIR, COLLECTION` |
| `pawpal/rag/retrieve.py` | `from rag.models import Chunk` | `from pawpal.rag.models import Chunk` |
| `pawpal/rag/qa.py` | `from guardrails import input_filter, toxic_food` | `from pawpal.guardrails import input_filter, toxic_food` |
| `pawpal/rag/qa.py` | `from llm_client import LLMClient` | `from pawpal.llm_client import LLMClient` |
| `pawpal/rag/qa.py` | `from rag.models import AnswerResult, Chunk, Citation` | `from pawpal.rag.models import AnswerResult, Chunk, Citation` |
| `pawpal/rag/qa.py` | `from rag.retrieve import DEFAULT_K, retrieve` | `from pawpal.rag.retrieve import DEFAULT_K, retrieve` |
| `tests/test_pawpal.py` | `from pawpal_system import Owner, Pet, Scheduler, Task` | `from pawpal.domain import Owner, Pet, Scheduler, Task` |
| `tests/test_tools.py` | `import tools` | `from pawpal import tools` |
| `tests/test_tools.py` | `from pawpal_system import Owner, Pet` | `from pawpal.domain import Owner, Pet` |
| `tests/test_guardrails.py` | `from guardrails import input_filter, toxic_food` | `from pawpal.guardrails import input_filter, toxic_food` |
| `tests/test_rag_smoke.py` | `from llm_client import ChatResponse, ChatUsage, LLMClient` | `from pawpal.llm_client import ChatResponse, ChatUsage, LLMClient` |
| `tests/test_rag_smoke.py` | `from rag.index import build_index` | `from pawpal.rag.index import build_index` |
| `tests/test_rag_smoke.py` | `from rag.models import Chunk` | `from pawpal.rag.models import Chunk` |
| `tests/test_rag_smoke.py` | `from rag.qa import LOG_FILE, PetContext, answer` | `from pawpal.rag.qa import LOG_FILE, PetContext, answer` |
| `tests/test_rag_smoke.py` | `from rag import qa as qa_module` | `from pawpal.rag import qa as qa_module` |
| `tests/test_rag_smoke.py` | `from rag import retrieve as retrieve_module` | `from pawpal.rag import retrieve as retrieve_module` |
| `eval/run_eval.py` | `from rag.qa import PetContext, answer` | `from pawpal.rag.qa import PetContext, answer` |

### 4.3 CLI / Command-line Entry Points

| Old command | New command |
|---|---|
| `python -m rag.index --rebuild` | `python -m pawpal.rag.index --rebuild` |
| `python -m rag.qa "..."` | `python -m pawpal.rag.qa "..."` |
| `python -m eval.run_eval` | `python -m eval.run_eval` (unchanged) |
| `streamlit run app.py` | `streamlit run app.py` (unchanged) |

## 5. Task Breakdown

| # | Task | Estimate | Depends on |
|---|---|---|---|
| R.1 | Create `pawpal/__init__.py` (empty file) | 5 min | — |
| R.2 | `git mv pawpal_system.py pawpal/domain.py` | 5 min | R.1 |
| R.3 | `git mv llm_client.py pawpal/llm_client.py` | 5 min | R.1 |
| R.4 | `git mv tools.py pawpal/tools.py` | 5 min | R.1 |
| R.5 | `git mv rag pawpal/rag` | 5 min | R.1 |
| R.6 | `git mv guardrails pawpal/guardrails` | 5 min | R.1 |
| R.7 | Rewrite imports inside `pawpal/` (rag, guardrails, tools) | 15 min | R.2–R.6 |
| R.8 | Rewrite imports in `app.py` and `main.py` | 5 min | R.7 |
| R.9 | Rewrite imports in `tests/*.py` | 10 min | R.7 |
| R.10 | Rewrite imports in `eval/run_eval.py` | 3 min | R.7 |
| R.11 | Run `pytest` and confirm 38/38 PASS | 5 min | R.9 |
| R.12 | Rebuild index: `python -m pawpal.rag.index --mock --rebuild` | 3 min | R.11 |
| R.13 | Run `python -m eval.run_eval --mock` and confirm short-circuit cases all PASS | 3 min | R.12 |
| R.14 | Manually launch `streamlit run app.py` (user smoke test, optional) | 5 min | R.12 |
| R.15 | Update all path/command references in `README.md` | 10 min | R.13 |
| R.16 | Update path references in `docs/design/architecture.md` | 10 min | R.13 |
| R.17 | Update path references in `docs/plan/phase2.md`, `phase3.md`, `phase4.md` | 15 min | R.13 |
| R.18 | Update path references in `docs/design/open_questions.md` | 5 min | R.13 |
| R.19 | Clean up `__pycache__` / `.pytest_cache` | 2 min | — |
| R.20 | Final review with `git status` & `git diff --stat` | 5 min | R.18 |

**Total**: about 2 hours.

## 6. Documentation Update Checklist

The following docs contain hard-coded paths or commands that must be scanned and updated one by one:

- `README.md`
  - "Project layout (Phase 1)" table
  - All occurrences of `python -m rag.index` → `python -m pawpal.rag.index`
  - "Architecture at a glance" tree diagram
- `docs/design/architecture.md`
  - "Main Components & Responsibilities" table (path column)
  - Any paths embedded in mermaid diagrams (in labels)
  - "Phase-Architecture mapping" section
- `docs/plan/phase2.md`
  - New file paths: `agent/planner.py` → `pawpal/agent/planner.py`
  - tools extension paths: `tools.py` → `pawpal/tools.py`
  - "Module List" table
- `docs/plan/phase3.md`
  - New file paths: `critic/*` → `pawpal/critic/*`
  - `guardrails/bias_filter.py` → `pawpal/guardrails/bias_filter.py`
- `docs/plan/phase4.md`
  - All paths in the file inventory
- `docs/design/open_questions.md`
  - The `rag/retrieve.py` path example in Q5
  - The `rag/qa.py` path example in Q3

## 7. Verification Steps (Definition of Done)

Run these in order; if every step passes the refactor is considered complete:

```bash
# 1. Unit tests
python -m pytest -q
# Expected: 38 passed

# 2. Rebuild the index (mock)
rm -rf chroma_db
python -m pawpal.rag.index --mock --rebuild
# Expected: Wrote N chunks to ChromaDB

# 3. Eval harness
python -m eval.run_eval --mock --limit 5
# Expected: harness reports no ImportError; at least the toxic_food/off_topic cases PASS

# 4. CLI single query (mock)
python -c "from pawpal.rag.qa import answer, PetContext; print(answer('test', PetContext(species='dog')).text[:80])"
# Expected: returns [mock answer] or short-circuit copy, no ImportError

# 5. Streamlit launch (manual)
streamlit run app.py
# Expected: both tabs render correctly and Ask PawPal can submit a question

# 6. Lint
# Cursor's built-in lints should be all green
```

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Missed import rewrite causes `ModuleNotFoundError` | Use a global grep on `from (pawpal_system\|llm_client\|tools\|rag\|guardrails)` for two-way verification; pytest will surface it immediately |
| A lazy import breaks once Streamlit is running | Step R.14 manually launches the app and switches between tabs at least twice |
| Stale metadata paths inside the Chroma index | Rebuild the index (step 2); the dataset is small (~64 chunks) so it finishes in a few seconds |
| `git mv` degenerates into delete+add in some cases | Use `git log --follow pawpal/domain.py` to confirm the history chain |
| Stale paths in docs go undetected | After committing the refactor, sweep with `rg "pawpal_system\|from rag\b\|from guardrails\b\|from llm_client\b" docs/ README.md` |
| Phase 2 work begins during the refactor → conflicts from parallel work | The refactor must complete before any Phase 2 code is written; this plan locks that ordering in |

## 9. Out of Scope

- The internal class design of `pawpal_system.py` (`Owner`/`Pet`/`Task`/`Scheduler`) is unchanged — only the file location and filename move.
- No introduction of `src/` layout, `pyproject.toml`, `setup.py`, or `pip install -e .`. If needed after Phase 4, that gets its own plan.
- No structural changes to `eval/`, `tests/`, `knowledge/`, or `docs/` — only their internal imports / path strings change.
- No namespace re-exports. `pawpal/__init__.py` stays empty.
- No behavioral or field changes to `Pet`, `Owner`, etc. (the 38 tests are the invariant).

## 10. Refactor → Phase 2 Handoff

Once the refactor is done, Phase 2 starts directly from the new structure:

- Add `pawpal/agent/__init__.py`, `pawpal/agent/planner.py`, `pawpal/agent/executor.py`, `pawpal/agent/models.py`, `pawpal/agent/prompts.py`
- Extend `pawpal/tools.py` with `add_task`, `detect_conflicts`, and `rag_lookup`
- Extend `pawpal/guardrails/toxic_food.py` with an `assert_safe_for_task` interface for the agent to call
- `app.py` adds a "🧠 Plan My Week" tab and imports straight from `from pawpal.agent.planner import plan_week`

Phase 2's phase2.md no longer needs to reorganize the directory — the path prefix is already unified.

## 11. Post-Refactor Consistency Checklist

- [ ] Only the following remain at the root: `app.py`, `main.py`, `requirements.txt`, `.env*`, `.gitignore`, `README.md`, `UML.md`, `reflection.md`, `uml_final.png`, plus subdirectories
- [ ] No `from rag.` / `from guardrails.` / `from pawpal_system` / `from llm_client` / `^import tools` imports remain (every import is prefixed with `pawpal.`)
- [ ] `python -c "import pawpal.rag.qa, pawpal.guardrails.toxic_food, pawpal.domain, pawpal.tools, pawpal.llm_client"` runs in one line with no errors
- [ ] `pytest` is fully green
- [ ] Docs are fully green (grep finds no stale paths)

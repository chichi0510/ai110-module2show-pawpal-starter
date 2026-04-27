# Phase 4 Plan — Full Evaluation, Documentation & Demo

> **Status**: ✅ **Executed (2026-04-27)** — median scores RAG 100% / Safety 100% /
> Planning 90% / Bias 0.587 / AUROC 0.784. See [`../EVAL_RESULTS.md`](../EVAL_RESULTS.md).
> **Source plan**: Draft v1.1 (2026-04-26 refresh patch; aligned with Phase 3 v1.1)
> **Phase goal**: Take everything Phases 1–3 delivered and **run it through end-to-end**, producing a quantitative
> reliability report; upgrade the project documentation (README, reflection, architecture) to portfolio quality;
> prepare a 5-minute demo (video or slides).
> **Depends on**: Phase 1 (rag) / Phase 2 (agent) / Phase 3 (critic + bias + safety_redteam + run_eval `--all`) all in place
> **Character**: most of Phase 4 is **documentation + running evals + recording a demo**; near-zero new code (only cleanup + emergency rescue)
>
> **v1.1 patch summary** (diff vs v1.0):
> 1. `safety_redteam.jsonl` and `run_eval.py --all` were moved into Phase 3 (they're eval data + CLI changes; they shouldn't pile up in the last week)
> 2. §3.6 mermaid PNGs are now "exported once and checked into git", not dependent on reviewers having Node.js
> 3. §3.7 cleanup adds the emergency fallback switch `PAWPAL_DISABLE_CRITIC` + lock-file split
> 4. DoD softens the word-count gate to "section coverage"; pytest count clarified as ≥80
> 5. §3.9 demo video is explicitly nice-to-have, not part of DoD

---

## 0. Phase 4 Scope

### In scope
- ✅ **Run the full 5-section eval** (rag · safety · planning · bias · calibration) using the `run_eval.py --all` already built in Phase 3
- ✅ AUROC calibration curve PNG **checked into git** (`docs/design/diagrams/calibration_<date>.png`)
- ✅ README v2 (with screenshots, setup, how AI works)
- ✅ `docs/REFLECTION_v2.md` — replaces the old `reflection.md` (confirmed present at the project root)
- ✅ `docs/DEMO_SCRIPT.md` — 5-minute script (8 steps)
- ✅ `docs/EVAL_RESULTS.md` — final scorecard (numbers + failure cases)
- ✅ Mermaid diagrams **exported to PNG once and checked in** (no dependency on reviewers having Node.js)
- ✅ Split `requirements.txt`: main deps (runtime) + `requirements-eval.txt` (eval) + `requirements-lock.txt` (exact reproducibility)
- ✅ Emergency fallback switch (`PAWPAL_DISABLE_CRITIC`) as a safety net so we don't get stuck with a critic that drags scores down
- ✅ Fresh-machine reproducibility test (most critical, §3.8)
- ✅ Final lint + code cleanup + remove unused

### Optional (nice-to-have, **not part of DoD**)
- 🎬 Record demo video (2–5 minutes) — DoD only requires the 8 steps in `DEMO_SCRIPT.md` to be demoable
- 📊 Slides (5–8 pages) — only if the assignment explicitly requires them

### Out of scope (explicitly off-limits)
- ❌ Any new feature (feature freeze)
- ❌ Refactoring (unless tests reveal a bug)
- ❌ New datasets / new eval section (**should be done in Phase 3**; discovering it now in Phase 4 = planning failure)
- ❌ Changing the `run_eval.py` CLI surface (**should be done in Phase 3**)
- ❌ Multimodal / voice
- ❌ Cloud deployment

---

## 1. Acceptance Criteria

| # | Acceptance criterion | Verification |
|---|--------|----------|
| 1 | Full eval runs end-to-end in one command | `python -m eval.run_eval --all` (built in Phase 3 §3.9) outputs 5 markdown reports + 1 calibration PNG + 1 aggregated `final_run_<ts>.md` |
| 2 | Report numbers meet the bar | golden ≥ 90% · safety ≥ 95% · bias parity ≥ 80% · planning ≥ 80% · AUROC ≥ 0.75 |
| 3 | Reproduces on a fresh machine | A teammate clones → 5 commands → demo runs (task 4.8 forces this walk-through) |
| 4 | Reflection is readable | `REFLECTION_v2.md` covers seven sections §1–§7 (design tradeoffs / AI collaboration / failures / bias / future / takeaway) |
| 5 | Demo is demoable | `DEMO_SCRIPT.md` has 8 steps, each with the expected screenshot lined up |
| 6 | Visualization | At least 4 mermaid diagrams exported to PNG and **checked in**; README + architecture.md reference local relative paths (visible even when GitHub doesn't render mermaid) |
| 7 | pytest is fully green | At least ≥80 unit tests passing (Phase 2 has 72, Phase 3 +10 ≈ 82) |
| 8 | Emergency fallback works | `PAWPAL_DISABLE_CRITIC=1 streamlit run app.py` boots and the critic doesn't score (bypassing § Phase 3 §3.6) |

---

## 2. Module checklist

### Added

```
docs/
├── REFLECTION_v2.md           # Replaces the root-level reflection.md
├── EVAL_RESULTS.md            # Final numbers + failure detail
├── DEMO_SCRIPT.md             # 5-minute demo walkthrough
└── design/
    └── diagrams/              # Mermaid exports (checked in; no mermaid CLI dependency)
        ├── system_overview.png
        ├── flow_rag.png
        ├── flow_agent.png
        ├── flow_critic.png
        ├── checkpoints.png
        └── calibration.png    # ROC curve (already produced in Phase 3)

eval/reports/                  # One-shot artifacts (gitignored is fine; README references screenshots instead)
├── final_run_<date>.md        # 5-section roll-up (rag/safety/planning/bias/calibration)
├── calibration_<date>.md
└── ...

requirements-eval.txt          # Eval-only install (sklearn, matplotlib) — already created in Phase 3
requirements-lock.txt          # `pip freeze` output, for exact reproducibility
```

### Modified

```
README.md                      # Comprehensive rewrite (keep the PawPal+ history as an appendix)
reflection.md                  # Renamed → reflection_phase2.md (preserve history);
                                # add a banner at the top pointing to docs/REFLECTION_v2.md
requirements.txt               # Runtime deps only (streamlit / openai / chromadb / pydantic);
                                # use `>=` ranges in the main deps for forward compatibility
.env.example                   # Add OPENAI_API_KEY / OPENAI_CHAT_MODEL / PAWPAL_DISABLE_CRITIC
docs/design/architecture.md    # Add a "local PNG mirror in diagrams/" note at the top
```

### Deleted / archived

```
.pytest_cache/                 # Add to .gitignore (if not already)
__pycache__/                   # Same
chroma_db/                     # Add to .gitignore (each dev box builds locally)
logs/*.jsonl                   # Add to .gitignore (runtime artifact)
Any unused import / dead code
```

---

## 3. Task breakdown

### Task 4.1 — Full eval run (1.5 h)
- [ ] **Pre-check**: Phase 3 §3.9 must already be done (the `run_eval.py --all` CLI exists; safety_redteam.jsonl + 50 golden + bias probes are all in place). Otherwise **go back to Phase 3 and finish them**, don't paper over it here.
- [ ] `python -m eval.run_eval --all`: run rag / safety / planning / bias / calibration in order
- [ ] Output 5 sub-section markdown reports + 1 aggregated `final_run_<ts>.md` to `eval/reports/`
- [ ] **Run 3 times and take the median** (smooths out single-run LLM jitter)
- [ ] Copy the calibration ROC PNG to `docs/design/diagrams/calibration.png` and check it into git
- [ ] If a metric misses the bar → mitigate (see §6)

### Task 4.2 — `docs/EVAL_RESULTS.md` (1 h)
- [ ] One summary scoreboard at the top (5 numbers + green/yellow/red markers)
- [ ] One paragraph per section: case count / pass rate / top-3 failure cases
- [ ] Calibration section: AUROC + ROC curve image + high-confidence failure cases
- [ ] Bias section: bar chart of average score per species (matplotlib PNG)
- [ ] At the bottom, ≥ 3 known limitations

### Task 4.3 — README v2 (2.5 h) — high value
- [ ] **Top one-sentence pitch** (within 30 words) + demo GIF / screenshot
- [ ] **Quick start**: 5 commands + screenshots
- [ ] **What it does**: 3 conversational screenshots for the use cases (Schedule / Ask / Plan)
- [ ] **How AI is used**: embed `system_overview.png` + 3 paragraphs (RAG / Agent / Critic)
- [ ] **Trustworthy by design**: guardrails + critic + human approval section (sells the value prop directly)
- [ ] **Evaluation**: link to `docs/EVAL_RESULTS.md`; surface the 5 core numbers in the README's main table
- [ ] **Project layout**: directory tree (lifted from phase 1 plan §2)
- [ ] **Architecture**: link to `docs/design/architecture.md`
- [ ] **Limitations & next steps**
- [ ] **Acknowledgements / sources**: list of knowledge-base citations

### Task 4.4 — `docs/REFLECTION_v2.md` (2 h)
Template:
- [ ] **§1 Problem & approach**: why RAG instead of fine-tuning / pure LLM
- [ ] **§2 Design tradeoffs**: 3 concrete tradeoffs
  - "Why we don't let the LLM replace the Scheduler for ordering"
  - "Why guardrails live in Python rather than as prompt constraints"
  - "Why the agent must be Apply'd by a human"
- [ ] **§3 What worked / what didn't**: 2 real failure cases pulled from the trace
- [ ] **§4 AI collaboration in development**: which tasks were AI-accelerated, which were AI-slowed
- [ ] **§5 Bias & safety reflection**: discuss the bias numbers honestly (which species is weakest)
- [ ] **§6 What I'd change next**: 3 future-work items
- [ ] **§7 Key takeaway**: one summary paragraph

### Task 4.5 — `docs/DEMO_SCRIPT.md` (1 h)
- [ ] Each step in 3 columns: action / expected screen / talking point (within 30 seconds)
- [ ] Steps cover:
  1. Launch the app (10s)
  2. Schedule tab — add a task — proves existing functionality is preserved (30s)
  3. Ask PawPal with a safe question (30s)
  4. Ask PawPal with a toxic-food question → guardrail fires (45s) — **highlight moment**
  5. Plan My Week generates a plan (45s)
  6. Trigger a conflict → see the re-plan trace (45s) — **highlight moment**
  7. Expand the reasoning trace + critic scores (30s)
  8. Wrap-up + reference the 5 numbers from `EVAL_RESULTS.md` (30s)

### Task 4.6 — Mermaid → PNG, exported once and checked in (45 min)
**Goal**: reviewers / third-party readers don't need Node.js / mermaid-cli to see the diagrams.

- [ ] One-time local install of mermaid CLI: `npm install -g @mermaid-js/mermaid-cli` (local machine only)
- [ ] Export ≥4 PNGs from `architecture.md` (`-w 1600 -b transparent`) into `docs/design/diagrams/`
  - `system_overview.png`
  - `flow_rag.png`
  - `flow_agent.png`
  - `flow_critic.png`
  - (+ the `calibration.png` already produced in Phase 3)
- [ ] Also generate SVG backups (`.svg` in the same folder)
- [ ] **`git add docs/design/diagrams/*.png` to commit them all** (this is the key step)
- [ ] Add a banner to the top of `architecture.md`:
  > 📸 Local PNG mirror lives in `docs/design/diagrams/` — click the link in any viewer that doesn't render mermaid
- [ ] In README v2, reference relative paths like `docs/design/diagrams/system_overview.png` instead of mermaid blocks (so PNGs show even when GitHub skips mermaid)
- [ ] Add a one-line regen command to `docs/design/diagrams/README.md`: `mmdc -i ../architecture.md -o system_overview.png` for future regeneration
- [ ] **Do not** add the mermaid CLI to requirements or CI

### Task 4.7 — Code cleanup (2 h)
- [ ] `ruff check` / `flake8` (whichever linter we use) all green
- [ ] Remove unused imports (`autoflake --remove-all-unused-imports -r .`)
- [ ] Audit every TODO / FIXME — fix or move to "Known limitations" in `EVAL_RESULTS.md`
- [ ] **Three-way dependency split**:
  - `requirements.txt`: runtime deps only (`streamlit`, `openai`, `chromadb`, `pydantic`), `>=` ranges
  - `requirements-eval.txt`: eval-only deps (`scikit-learn`, `matplotlib`), introduced in Phase 3 §3.9
  - `requirements-lock.txt`: `pip freeze > requirements-lock.txt` output, exact-reproducibility lock
- [ ] Round out `.env.example`:
  - `OPENAI_API_KEY=`
  - `OPENAI_CHAT_MODEL=gpt-4o-mini`
  - `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`
  - `PAWPAL_DISABLE_CRITIC=` (left empty; set to 1 in emergencies to disable the critic, see §6)
- [ ] Verify the emergency fallback: `PAWPAL_DISABLE_CRITIC=1 streamlit run app.py` boots and the critic falls back to mock (DoD #8)
- [ ] Run final `pytest`: ≥80 cases all green (DoD #7)
- [ ] Confirm `.gitignore` includes: `.pytest_cache/`, `__pycache__/`, `chroma_db/`, `logs/*.jsonl`, `eval/reports/`, `.venv/`, `.env`

### Task 4.8 — Fresh-machine reproducibility test (30 min) — critical
- [ ] In a separate folder, `git clone .`
- [ ] Strictly follow the README commands
- [ ] Any blocker → fix the README immediately
- [ ] Test on mac + linux (if available)

### Task 4.9 — Demo recording (**nice-to-have, not part of DoD**, 1.5 h)
- [ ] QuickTime screen capture / OBS
- [ ] Walk through `DEMO_SCRIPT.md`
- [ ] Trim dead air
- [ ] Upload to YouTube unlisted / Loom; embed the link in the README
- [ ] Failure plan: capture 1 screenshot per `DEMO_SCRIPT.md` step into `docs/design/screenshots/`; the README treats them as a static walkthrough

### Task 4.10 — Slides (**nice-to-have, only if the assignment requires**, 1 h)
- [ ] 5–8 pages (if the assignment asks for slides):
  1. Problem & pitch
  2. System overview (PNG)
  3. RAG demo screenshot
  4. Agent demo screenshot
  5. Trust mechanisms (guardrail / critic / approval)
  6. Eval numbers (bar chart)
  7. Limitations & next steps
  8. Q&A

**Estimated total: ~12 h**, distributed across Week 4 (final sprint).

---

## 4. Definition of Done

- [ ] `python -m eval.run_eval --all` succeeds in one go (≥3 runs, take the median)
- [ ] All 5 core metrics meet the bar (see §1.2); fall back to §6 if not
- [ ] README v2 renders correctly on GitHub (**PNG fallback even when mermaid doesn't render**)
- [ ] Fresh-machine walkthrough completes the 5 commands + 8 demo steps (task 4.8 is mandatory)
- [ ] `docs/REFLECTION_v2.md` covers all seven sections §1–§7 (**soft criterion, no word count gate**)
- [ ] ≥4 mermaid diagrams exported to PNG and **checked into git** (DoD #6)
- [ ] `pytest` passes ≥80 cases (DoD #7)
- [ ] `PAWPAL_DISABLE_CRITIC=1` emergency fallback works (DoD #8)
- [ ] All phase plan markdowns are tagged ✅ Done with the completion date
- [ ] **Demo video and slides are not part of DoD** (only if explicitly required by the assignment)

---

## 5. Final rubric mapping

| Rubric dimension | Evidence at the end of Phase 4 |
|-------------|---------------------------|
| Cohesive end-to-end AI system | README v2 + system_overview.png + Demo |
| Modular components (retrieval/logic/agentic) | Directory layout + architecture.md |
| Reliability + guardrails | `EVAL_RESULTS.md` + safety section + tests |
| Explainable AI decision-making | Trace expander + DEMO_SCRIPT step 7 |
| Responsible design | Bias section + REFLECTION §5 |
| Technical creativity | Description of the Plan-Execute-Critique loop |
| Professional documentation | README + REFLECTION_v2 + DEMO_SCRIPT |
| Stretch | Calibration AUROC + bias quantification |

---

## 6. Mitigation paths when targets are missed

If running the eval in Phase 4 reveals a metric below target:

| Metric | Miss reason | Mitigation (cheapest first) |
|------|--------|--------------------------------|
| Golden QA < 90% | Low retrieval recall | 1. Look at failure-case queries → add the matching KB markdown (30 min/file) |
|  | LLM doesn't cite | 2. Tighten the prompt constraint (10 min) |
|  |  | 3. Upgrade to `gpt-4o` (cost ×10, last resort) |
| Safety redteam < 95% | Guardrail miswired | Identify which redteam slipped through, add a blocklist entry (5 min/entry) |
| Bias parity < 80% | Insufficient KB for small pets | Add hamster / rabbit / bird KB markdown (1 h/species) |
| Planning < 80% | Re-plan failures | Add few-shot examples to the prompt; loosen max_replans to 5 |
| AUROC < 0.75 | Critic poorly calibrated | 1. Stretch: self-consistency (run the critic 3 times and take the median)<br>2. Worst case: `PAWPAL_DISABLE_CRITIC=1` disables the critic; UI relies on guardrails as the safety net; reflection discusses this honestly |
| Any metric collapses entirely | LLM API flake / quota | 1. Switch back to the mock client (`unset OPENAI_API_KEY`) and run the offline mock eval, at least proving the pipeline is functional<br>2. Capture screenshots + timestamps for the record |

**Mitigation budget**: hold 2–3 h of buffer; once exhausted, accept current numbers + discuss them honestly in the reflection.

> **Important**: mitigation should **only modify prompts / data / config**, not the architecture or new modules.
> If "we must refactor to hit the target" comes up → accept the current number and write it into reflection §6 future work.

---

## 7. Risks

| Risk | Mitigation |
|------|------|
| Eval token spend overruns budget | Use a cache (skip the LLM when the same query hits); only run 3 times and take the median |
| Fresh-machine reproducibility fails | Task 4.8 is mandatory and **leaves at least 30 min of buffer** |
| Demo recording fails / voice goes hoarse | Switch to a static screenshot walkthrough (README-friendly), not part of DoD |
| Mermaid not rendered in some viewers | PNG fallback (already checked in via task 4.6) |
| Time-zone / DST flips due_date around | During task 4.7, grep for `date.today()` usage to ensure UTC or a single tz throughout |
| Knowledge-base copyright concerns | Add a disclaimer + source URL list at the end of reflection §5 |
| Phase 3 dataset not ready before opening Phase 4 | §3.1 added a "pre-check"; if missing → **go back to Phase 3 and finish it**, do not patch in Phase 4 |
| Critic drags scores down and forces us to ship a bad implementation | `PAWPAL_DISABLE_CRITIC=1` emergency fallback (already built in §3.7) + §6 mitigation paths |
| `pip freeze` lock file pins host-specific wheels (e.g. macOS arm64) | Note in the lock file: "for reproducing the author's environment only"; new machines install via `requirements.txt` + `requirements-eval.txt` first |

---

## 8. Future (out-of-course) directions

Captured in REFLECTION §6, listed here for convenience:

- **Persistence**: SQLite instead of session_state, supports multi-owner / multi-device
- **Multimodal**: identify pet breed from photos → auto-select species
- **Real data integration**: wearable APIs like FitBark / Whistle
- **Local LLM**: switch to Ollama + Llama 3.1, zero API cost + privacy
- **Active learning**: let the user mark "this answer wasn't useful", auto-augment the KB
- **Multilingual**: knowledge base + UI in both English and Chinese

---

## 9. Changelog

| Date | Version | Change |
|------|------|------|
| 2026-04-26 | v1.0 | Initial draft; feature freeze + 5 core metrics + miss-mitigation matrix |
| 2026-04-26 | v1.1 | Refresh patch: safety_redteam / `--all` moved to Phase 3; mermaid PNG checked in once without CLI dependency; deps split three ways; added `PAWPAL_DISABLE_CRITIC` fallback; DoD softened from word counts to section coverage; demo video / slides explicitly nice-to-have |

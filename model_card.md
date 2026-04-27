# Model Card — PawPal AI

> **Course**: CodePath AI-110 — Module 4 Final Project
> **Student**: Chichi Zhang
> **Repository**: https://github.com/chichi0510/ai110-module2show-pawpal-starter
> **Status**: ✅ Final (April 2026)
>
> This document is the canonical **model card** required by the Module 4
> submission rubric. Companion documents:
> [`README.md`](README.md) · [`docs/EVAL_RESULTS.md`](docs/EVAL_RESULTS.md) ·
> [`docs/REFLECTION_v2.md`](docs/REFLECTION_v2.md) ·
> [`docs/design/architecture.md`](docs/design/architecture.md).

---

## 1 · System overview

| | |
|---|---|
| **Name** | PawPal AI |
| **Base project** | **PawPal+** (Modules 1–3) — a deterministic Python pet-care scheduler with `Owner / Pet / Task / Scheduler` classes, a Streamlit UI for pet onboarding and daily/weekly task scheduling, and 38 unit tests. No LLM, no external services. |
| **What I added in Module 4** | Three cooperating AI layers wrapped around the unchanged scheduler: (1) RAG question answering over a curated Markdown knowledge base, (2) an agentic week-planner that calls typed Python tools on a sandboxed deepcopy of user state, (3) an LLM self-critic that scores every answer and plan with a calibrated 0–1 confidence. |
| **Underlying models** | `gpt-4o-mini` for chat (planner, RAG composition, critic) · `text-embedding-3-small` for retrieval embeddings (OpenAI). No fine-tuning. |
| **Intended use** | Help a pet owner stay consistent with feeding/walks/meds, and answer common pet-care questions with cited, safety-checked sources. Personal-portfolio prototype, not a clinical tool. |
| **Out of scope** | Veterinary diagnosis, drug dosing, replacing professional vet care. The system explicitly redirects these queries with a "contact a veterinarian" message. |

A full architecture write-up and six rendered diagrams live in
[`docs/design/architecture.md`](docs/design/architecture.md) and
[`assets/diagrams/`](assets/diagrams/) (mirrored from
[`docs/design/diagrams/`](docs/design/diagrams/)).

---

## 2 · Data sources

| Source | Role | Volume |
|---|---|---|
| `knowledge/**/*.md` (Markdown KB) | RAG corpus (chunked by H2/H3 heading, embedded into ChromaDB) | ~10 markdown files, YAML-frontmatter typed by species/topic/age |
| `eval/golden_qa.jsonl` | RAG evaluation set, with `correct_label` for AUROC | 51 cases across feeding / vaccines / toxic_food / off-topic / under-represented species |
| `eval/safety_redteam.jsonl` | Adversarial / red-team probes | 20 cases (dosage, jailbreak, toxic-food bypass, off-label drug requests) |
| `eval/bias_probes.jsonl` | Cross-species parity probes | 30 cases (10 topics × 3 species each) |
| `eval/planning_goals.jsonl` | Agent-loop regression cases | 10 goals |
| `logs/rag_trace.jsonl` · `logs/agent_trace.jsonl` | Structured per-call audit trail (gitignored) | 1 line per RAG / agent invocation |

The KB is **English-only and US-centric** (units, regulatory
references). I authored both the KB and the golden QA, which is a
known source of selection bias — see §6.

---

## 3 · Performance — testing results

Median across **3 full real-LLM `--all` evaluation runs** with
`gpt-4o-mini` (raw run-by-run numbers, reliability table, and cost
estimates in [`docs/EVAL_RESULTS.md`](docs/EVAL_RESULTS.md)):

| Section | Median (n=3) | Target | Status |
|---|---:|---:|---:|
| RAG (golden QA, 51) | **51 / 51 (100 %)** | ≥ 90 % | ✅ |
| Safety red-team (20) | **20 / 20 (100 %)** | ≥ 95 % | ✅ |
| Planning goals (10) | **9 / 10 (90 %)** | ≥ 80 % | ✅ |
| Bias parity (avg ratio across 10 topics) | **0.587** | ≥ 0.80 | 🔴 |
| Critic AUROC (calibration vs. `correct_label`) | **0.784** | ≥ 0.75 | ✅ |
| Unit tests | **103 / 103** | all | ✅ |

**Key behavioural deltas captured during testing**:

- Safety red-team **30 % → 100 %** between the first and final eval
  run, after broadening regex coverage in `pawpal/guardrails/`
  (third-person feeding patterns, jailbreak phrases, dosage / mg-kg
  patterns; commit `3fefdb2`).
- RAG **68.6 % → 100 %** after adding a six-line digit-to-word and
  plural normaliser to the keyword evaluator (commit `07376cc`) —
  i.e. the model's answers were correct, the evaluator was too literal.
- A fresh-venv reproducibility test (`requirements-lock.txt` →
  install → `pytest` → RAG smoke 3/3) was run before submission and
  passed cleanly.

---

## 4 · Reliability and guardrails

| Layer | Mechanism | What it catches |
|---|---|---|
| **Preflight** | `pawpal/guardrails/input_filter.py` | Off-topic, PII, medical-diagnosis fishing, jailbreak templates, dangerous-practice prompts ("hot car", "declawing"), dosage requests. |
| **Toxic-food** | `pawpal/guardrails/toxic_food.py` | Species-specific blacklists (chocolate, grapes, xylitol, ibuprofen, aspirin, Benadryl, melatonin, …). Matches third-person ("Can dogs eat raisins?") and bypass phrasing ("won't hurt", "tiny taste"). |
| **Post-flight** | Same toxic-food module, applied to LLM output | Catches the rare case where the model emits a toxic ingredient that the input layer missed. |
| **Self-critic** | `pawpal/critic/self_critique.py` | LLM grades each answer / plan on grounded · actionable · safe (or complete · specific · safe). Aggregated to 0–1 confidence + `high/medium/low` UI badge; safe-veto collapses unsafe plans regardless of retrieval quality. |
| **Bias filter** | `pawpal/guardrails/bias_filter.py` | Runtime warning when an under-represented-species answer is shorter than the dog/cat baseline. Surfaces the structural KB gap to the user. |
| **Sandbox** | `executor.run` operates on `deepcopy(owner)`; live owner only mutated when user clicks **Apply** in the UI. Hard invariant enforced by `tests/test_scratch_owner_safety.py`. |
| **Logging** | Every Q&A → 1 JSON line in `logs/rag_trace.jsonl`; every plan run → 1 JSON line in `logs/agent_trace.jsonl`. Includes preflight, retrieved chunks + scores, LLM tokens, post-flight, critic, bias, duration. |
| **Emergency fallback** | `PAWPAL_DISABLE_CRITIC=1` short-circuits the critic to a fixed *medium* report; LLMClient auto-degrades to mock when no API key. |

---

## 5 · AI collaboration during development

I used Cursor (Claude / GPT) extensively while building this project.

**🟢 One specific suggestion that was helpful.** When I described the
Phase 2 agent as "plan, execute, replan", the AI suggested adding a
typed Pydantic layer (`Plan`, `PlanStep`, `PlanResult`, `StepTrace`)
*between* the LLM JSON output and the executor — instead of letting
the executor consume raw `dict`s. That single suggestion paid off four
ways: (1) JSON parse errors became typed fail-fast at the boundary,
(2) `mypy` caught two bugs before runtime, (3) the critic could be
unit-tested with stub `Plan` objects offline, and (4) the agent trace
ended up cleanly serialisable to `agent_trace.jsonl`. I estimate it
saved ~3 hours of re-work and the typed boundary is now the
load-bearing piece of the agent loop.

**🔴 One specific suggestion that was flawed.** When I asked the AI
to write the first planner prompt, it drafted a long *chain-of-thought*
template that asked the LLM to "think step by step, then output JSON".
On the first real run the model emitted prose followed by a JSON
object — which my parser rejected — and on the second run it emitted
*only* prose with the JSON inlined as Markdown. I had to discard the
draft and rewrite the prompt as a strict JSON-mode-only template
("you MUST output a single JSON object matching this schema; no prose;
no markdown") plus enable OpenAI's `response_format=json_object`. The
AI's instinct was natural language; it underweighted how unforgiving
structured output is. Lesson: AI-assisted prompt engineering needs
schema-driven constraints applied *by me*, not trusted to the AI's
defaults.

**General pattern that worked.** Scaffold-then-refine: ask the AI for
a first pass, immediately read it line by line against existing code,
then fix the parts that don't fit. The few times I deviated and
shipped AI output without a careful read (e.g. the planner prompt
above), I paid for it. A fuller per-phase breakdown of where AI
assistance helped and where it didn't is in
[`docs/REFLECTION_v2.md` §4](docs/REFLECTION_v2.md#4-ai-collaboration-in-development--what-ai-assisted-coding-did-and-did-not-speed-up).

---

## 6 · Limitations, biases, and ethical considerations

### Biases I *measured*

- **Species coverage bias is real and quantified.** Median bias parity
  is **0.587** (target 0.80) — under-represented species
  (rabbit / hamster / lizard) get visibly shorter, vaguer answers
  because the KB has 1–2 markdown files for each vs. ~4 for dog/cat.
  Worst offenders: **vaccines (rabbit ratio 0.16)** and
  **exercise (rabbit 0.24)** — both fall back to "no verified answer"
  because retrieval misses. The runtime bias filter flags these at
  inference; it does not fix them. The fix is more KB content, not
  more code.

- **Author bias in evaluation datasets.** I wrote both the KB *and*
  the 51-item golden QA — they share blind spots. The Phase 4 §6
  evidence: my originally-authored safety red-team set caught only
  6/20 adversarial prompts on first run. An *outside* red-team would
  certainly find more edges in the current 100% set.

- **Calibration is good, not perfect.** AUROC 0.78 means there is a
  non-zero rate of *high-confidence wrong* answers. A user who blindly
  trusts the green badge will be wrong sometimes — the UI mitigates by
  always showing citations, but the residual risk is real.

### Limitations I *did not* fix

- **English-only, US-centric KB.** Brand names, units, and regulatory
  references all skew US. A user in a region where ibuprofen is
  over-the-counter for humans gets the same blanket "never give to
  dogs" answer — correct, but not localised.
- **Single-LLM dependency.** Behaviour assumes `gpt-4o-mini`-class
  capability. On a smaller / older model the JSON-mode planner
  hallucinates schema fields and the loop goes degenerate.
- **Process-lifetime persistence only.** `st.session_state` resets on
  tab close; pets and tasks vanish. SQLite would fix this; out of
  scope for this iteration.

### Misuse vectors and mitigations

| Misuse vector | Mitigation in this repo |
|---|---|
| Prompt injection / jailbreak | `_JAILBREAK_PATTERNS` in `input_filter.py` — deterministic, the LLM cannot turn it off. |
| Off-label drug fishing ("how many mg of melatonin for my dog") | Dosage / mg-kg / "what dose" patterns route to canned safe answer + "contact a vet". |
| Substituting PawPal for a vet | Every safety-blocked path returns "contact a veterinarian or pet poison hotline". Bias / low-confidence badge nudges users to verify. |
| PII leakage into logs | Preflight strips obvious PII (phone, email) before LLM/log. |
| KB poisoning | KB is markdown in the git repo; new content requires a code review + index rebuild. No user-uploaded KB path. |
| Schedule sabotage by a bad LLM plan | `deepcopy(owner)` sandbox + explicit Apply click + `test_scratch_owner_safety.py` invariant. |
| User over-trust | Critic confidence badge + bias warning + citation links surfaced in UI. |
| **Out of scope** | An owner who *intentionally* harms their pet via the schedule UI. |

A more discursive treatment is in [`docs/REFLECTION_v2.md` §5](docs/REFLECTION_v2.md#5-bias--safety-reflection--being-honest-about-gaps)
and [§8](docs/REFLECTION_v2.md#8-module-4-reflection-and-ethics-rubric--explicit-answers).

---

## 7 · How to verify the claims in this card

The eval harness ships with the repo; every number above is
reproducible without trusting me:

```bash
git clone git@github.com:chichi0510/ai110-module2show-pawpal-starter.git
cd ai110-module2show-pawpal-starter
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest                       # 103/103 (mock, no API key)
cp .env.example .env                   # set OPENAI_API_KEY
python -m pawpal.rag.index --rebuild   # build vector index over the KB
python -m eval.run_eval --all          # writes a fresh report under eval/reports/
```

Three independent run reports are checked in under
[`eval/reports/`](eval/reports/) (timestamps `1777257*`, `1777259*`,
`1777261*`). The Phase 4 plan with batch-A/B/C breakdown is at
[`docs/plan/phase4.md`](docs/plan/phase4.md).

---

*Last updated: 2026-04-26.*

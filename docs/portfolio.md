# PawPal AI — Portfolio Artifact

> Short, link-friendly artifact for course submission and any
> recruiter-facing portfolio (LinkedIn, personal site, etc.). All
> deeper material lives in the linked docs.

---

## 🔗 Project links

| | |
|---|---|
| **Repository** | https://github.com/chichi0510/ai110-module2show-pawpal-starter |
| **Live demo (Loom walkthrough)** | _TODO: paste Loom URL here after recording_ |
| **Course** | CodePath AI-110 — Module 4 Final Project (Applied AI) |
| **Original project** | PawPal+ (Modules 1–3, deterministic Python scheduler) |

## 🐾 30-second pitch

> **PawPal AI** turns a deterministic pet-care scheduler into a full
> applied-AI system. It answers safety-critical pet-care questions
> with retrieval-augmented generation grounded in a citable Markdown
> knowledge base, plans multi-task weekly routines via an agent loop
> that calls typed Python tools on a sandboxed copy of user state, and
> attaches a calibrated self-critic confidence (AUROC 0.78) to every
> answer and plan so users know when *not* to trust it. Median scores
> across 3 real-LLM evaluation runs: **RAG 100% · Safety 100% ·
> Planning 90% · Unit tests 103/103.**

## 🧱 Artifacts in this repo

| What | Where |
|---|---|
| Architecture write-up + 6 rendered diagrams | [`docs/design/architecture.md`](design/architecture.md) · [`docs/design/diagrams/`](design/diagrams/) |
| Phase-by-phase tactical plans | [`docs/plan/phase1.md`](plan/phase1.md) · [`phase2.md`](plan/phase2.md) · [`phase3.md`](plan/phase3.md) · [`phase4.md`](plan/phase4.md) |
| Open design questions / tradeoffs | [`docs/design/open_questions.md`](design/open_questions.md) |
| Behavioural eval methodology + results | [`docs/EVAL_RESULTS.md`](EVAL_RESULTS.md) |
| Reflection (v2) including Module-4 ethics rubric | [`docs/REFLECTION_v2.md`](REFLECTION_v2.md) |
| 5-min in-person presentation outline | [`docs/PRESENTATION.md`](PRESENTATION.md) |
| Loom recording script (minute-by-minute) | [`docs/LOOM_SCRIPT.md`](LOOM_SCRIPT.md) |
| Static demo step-by-step | [`docs/DEMO_SCRIPT.md`](DEMO_SCRIPT.md) |

---

## What this project says about me as an AI engineer

I treat applied-AI work as a **systems engineering problem first and a
prompt engineering problem second.** Building PawPal AI taught me that
the LLM is one component in a larger reliability stack — so I built the
deterministic guardrails outside the prompt (where jailbreaks can't
turn them off), wrapped the planner's reasoning in a typed Python
tool surface (so a bad LLM output couldn't silently mutate user
state), and shipped a behavioural evaluation harness with 51 golden
QA cases, 20 red-team prompts, 30 bias probes, and an AUROC
calibration step *before* I trusted any of my own UI. The Phase 4
results — going from 30% to 100% on the safety red-team by expanding
deterministic regex coverage rather than rewriting the prompt, and
catching a test-fixture bug that silently corrupted the vector index
— are the moments I'm proudest of, because they're moments where
**measurement beat intuition**. I'm an engineer who designs for
auditability (every AI decision lands in `logs/*.jsonl` with full
provenance), who values calibrated confidence over raw accuracy, and
who treats "is it actually working?" as a question only the eval
harness gets to answer. That, more than any individual feature, is
what I want to bring to my next AI role.

— *Chichi Zhang, April 2026*

---

## How to verify this works in 90 seconds

```bash
git clone git@github.com:chichi0510/ai110-module2show-pawpal-starter.git
cd ai110-module2show-pawpal-starter
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest                       # 103/103 should pass (mock mode, no API key)
cp .env.example .env                   # add your OPENAI_API_KEY
python -m pawpal.rag.index --rebuild   # build vector index over the KB
python -m eval.run_eval --section safety   # 20/20 should pass
streamlit run app.py                   # opens 3-tab UI on localhost:8501
```

For deeper verification: `python -m eval.run_eval --all` runs all five
suites and writes a JSON report under `eval/reports/`.

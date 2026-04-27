# PawPal AI — 5–7 Minute Presentation Outline

> Slide-by-slide script for the Module 4 final-project presentation.
> Pair with [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) (live demo flow) and
> [`LOOM_SCRIPT.md`](LOOM_SCRIPT.md) (recorded walkthrough). Rough
> timing column adds up to **6:00**; ±60 s leaves room for questions.

---

## Cover (15 s) — Slide 1

> **PawPal AI** — A reliability-first applied-AI extension of the
> PawPal+ pet-care scheduler.
>
> Chichi Zhang · CodePath AI-110 · Module 4 Final Project · April 2026
>
> github.com/chichi0510/ai110-module2show-pawpal-starter

**Speaker note**: Smile. Name the project, the course, and the
fact that this is built on top of an *existing* Module 1–3 project
so reviewers know not to expect a from-scratch ML project.

---

## Slide 2 — The Module 1–3 starting point (45 s)

**Headline**: "Pre-AI PawPal+ was a deterministic Python scheduler."

- Built `Owner / Pet / Task / Scheduler` classes
- Streamlit UI: add pets, schedule daily/weekly tasks, detect clock conflicts
- 38 unit tests · zero external services · zero LLM calls
- The user told me what worked: scheduling. And what didn't: *"I still
  Google-search every 'is X safe for my dog' question."*

> **The gap I wanted to close**: turn that one-line user complaint
> into a concrete AI feature.

**Speaker note**: Show the original Schedule tab screenshot
(`docs/demo.jpeg`). 5 seconds of "this is the floor I built up from".

---

## Slide 3 — What I built in Module 4 (60 s)

**Headline**: "Three cooperating AI layers on top of the same scheduler."

| Layer | Phase | What it does |
|---|---|---|
| **RAG Q&A** | 1 | Curated Markdown KB → ChromaDB → cited answer with toxic-food guardrails on *both sides* of the LLM. |
| **Agent loop** | 2 | One-line goal → planner emits typed `Plan` → executor runs tools on a `deepcopy(owner)` → re-plans on conflict → preview → user clicks **Apply**. |
| **Self-critic** | 3 | LLM critic scores every answer + every plan; aggregates a 0–1 confidence; UI badges high / medium / low; offline AUROC calibration. |

> **Phase 4** = polish + 3-run real-LLM evaluation + reflection.

**Speaker note**: Spend 10 seconds on each row, 5 seconds on the Phase 4
line. The image to put on this slide is the system overview PNG
(`docs/design/diagrams/system_overview.png`).

---

## Slide 4 — Architecture (45 s)

> *Embed `docs/design/diagrams/system_overview.png` full-bleed.*

Three layers, top to bottom:

1. **Streamlit UI** (3 tabs)
2. **Deterministic core** — scheduler & domain model — *unchanged from Modules 1–3*
3. **AI services ring** — RAG, agent, critic, guardrails

Two invariants the architecture enforces:
- **Every LLM input is preflight-checked; every LLM output is post-flight-checked.** Deterministic Python, not prompt instructions.
- **Agent never mutates the live owner.** A `deepcopy(owner)` sandbox + an explicit Apply click. Enforced by `tests/test_scratch_owner_safety.py`.

**Speaker note**: This is the slide for the "system thinking" message —
emphasise that the LLM is *one component*, not the centre.

---

## Slide 5 — Live demo (90 s)  *— if recorded, swap for embedded Loom*

Three inputs, in order — see [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) for the
full talk track.

1. **Factual RAG** — *"How often should I feed my puppy?"* → cited
   answer + green confidence badge.
2. **Safety guardrail (high-light moment 1)** — *"Can I give my dog
   ibuprofen?"* → red banner, **the LLM was never called**. Emphasise
   "this isn't the model refusing — it's deterministic Python."
3. **Agent plan (high-light moment 2)** — *"Set up a starter routine
   for my dog Echo."* → live tool calls, 4-row preview, Apply button.
   Show the trace expander to expose the chain of `list_pets →
   add_task ×4 → detect_conflicts`.

**Speaker note**: If demo runs hot, drop #1 and keep #2 + #3 (the two
"wow" moments). Cap this slide at 90 seconds — anything longer eats Q&A.

---

## Slide 6 — The numbers (45 s)

**Headline**: "It works because the harness says so, not because I do."

| Section | Median (n=3, gpt-4o-mini) | Target |
|---|---:|---:|
| RAG (golden QA, 51) | **100 %** | 90 % |
| Safety red-team (20) | **100 %** | 95 % |
| Planning goals (10) | **90 %** | 80 % |
| Critic AUROC | **0.78** | 0.75 |
| Bias parity | **0.59 (KB-limited)** | 0.80 |
| Unit tests | **103 / 103** | all |

> One missed target — **bias parity 0.59** — and I know why: the KB has
> 4 dog/cat files but only 1–2 each for rabbit / hamster / lizard.
> The runtime bias filter flags it; the long-term fix is more KB.

**Speaker note**: Don't hide the failed metric. Showing one honest miss
+ a root-cause + a planned fix is *more* trustworthy than five greens.

---

## Slide 7 — One thing that worked, one that surprised me (45 s)

**Worked — deterministic regex beat prompt engineering for safety.**
Safety red-team went **30 % → 100 %** between the first and final eval
run. The lift came from broadening regex patterns in
`pawpal/guardrails/`, *not* from rewriting the LLM prompt. Lesson: the
LLM does ~20 % of the safety work; the deterministic layer does the
rest.

**Surprised — confidence calibration changed how I, the developer,
trusted my own UI.** I built AUROC for a rubric checkbox. After 30
minutes of demoing, the **green / yellow / red badge** changed when I
personally would re-check an answer with a real vet. Calibration
matters more than raw accuracy when humans are in the loop — but only
if it's *visible* in the UI.

**Speaker note**: Pick one of these to elaborate if you have extra
time; the other is the spare for Q&A.

---

## Slide 8 — What this project says about me (30 s)

> "I treat applied-AI work as systems engineering first and prompt
> engineering second. I designed PawPal AI for **auditability** (every
> AI decision is in `logs/*.jsonl`), **calibrated confidence**
> (AUROC-tuned, surfaced in the UI), and **measurement over
> intuition** (51-case eval harness, fresh-venv repro test). I want
> to bring that same eval-first reflex to my next AI role."

**Speaker note**: Read the paragraph. End with a steady close — no
trailing question. This is the *take-home* line.

---

## Slide 9 — Q&A / links (15 s buffer)

- **Repo**: github.com/chichi0510/ai110-module2show-pawpal-starter
- **Loom walkthrough**: https://www.loom.com/share/daa28affbbf94c60ac6a70e01837bc9f
- **Eval results**: `docs/EVAL_RESULTS.md`
- **Reflection + ethics rubric**: `docs/REFLECTION_v2.md` §8

> Questions?

---

## Pacing cheat-sheet (paste under the dock)

```
0:00  start cover
0:15  origin (PawPal+)
1:00  what's new in M4 (3 layers)
2:00  architecture
2:45  demo  ← longest slide
4:15  numbers
5:00  worked / surprised
5:45  what this says about me
6:15  Q&A
```

If running short: drop demo step #1; keep guardrail + agent. If
running long: drop slide 7's *second* paragraph; keep "worked".

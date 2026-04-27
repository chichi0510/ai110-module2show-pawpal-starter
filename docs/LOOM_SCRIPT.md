# PawPal AI — Loom Walkthrough Script

> **Target length**: 5–7 minutes (the rubric says short).
> **Goal**: hit *all four* required check-marks below in one take.
>
> ✅ **End-to-end system run (2–3 inputs)** — Demo 1, 2, 3 below
> ✅ **AI feature behaviour** (RAG + agent) — Demos 1 and 3
> ✅ **Reliability / guardrail / evaluation behaviour** — Demo 2 + the eval terminal at the end
> ✅ **Clear outputs for each case** — read each badge / preview row out loud
>
> Loom does **not** require you to show install, file structure, or `pip install`.
> Skip them.

---

## Pre-flight checklist (do this BEFORE hitting Record)

- [ ] `.env` has a working `OPENAI_API_KEY`
- [ ] `python -m pawpal.rag.index --rebuild` finished (real embeddings, not mock)
- [ ] `streamlit run app.py` is running on `http://localhost:8501`
- [ ] In the sidebar: **Owner = Alice**, pets = **Mochi (cat, 3)** and **Echo (dog, 2)** (use the 🔄 *Reset state* button if needed, then re-add)
- [ ] Echo has **0 existing tasks** (so the agent demo shows a fresh plan)
- [ ] A **second tab** open with [`docs/EVAL_RESULTS.md`](EVAL_RESULTS.md) ready
- [ ] A **terminal** open in the project root with `.venv` activated, ready to type `python -m eval.run_eval --section safety --limit 5`
- [ ] Loom set to **Screen + camera bubble**, microphone tested

---

## Minute-by-minute script (≈6:00 total)

### 0:00 – 0:25 · Opening (25 s)

> *(Camera on, Streamlit visible.)*
>
> "Hi, I'm Chichi. This is **PawPal AI** — my Module 4 final project
> for CodePath AI-110. It's an applied-AI extension of **PawPal+**, my
> Module 1–3 deterministic pet-care scheduler. I added three AI
> features on top of it: **retrieval-augmented Q&A**, an **agentic
> week planner**, and a **self-critic** that scores every answer.
> I'll show you all three in about six minutes."

---

### 0:25 – 0:50 · Tour the UI (25 s)

> *(Hover over the three tabs.)*
>
> "Three tabs. **Schedule** is the original Modules 1–3 deterministic
> planner — it's still here, untouched. **Ask PawPal** is the RAG
> Q&A. **Plan My Week** is the agent loop. The sidebar has the owner
> and pets — pre-loaded Mochi the cat and Echo the dog."

---

### 0:50 – 2:10 · ✅ Demo 1: factual RAG question (80 s)

> *(Click **Ask PawPal**. Pet selector → Echo. Type the query.)*
>
> **Type**: `How often should I feed my adult dog?`
>
> *(Press Enter. Wait for streaming answer.)*
>
> "This goes through the full RAG pipeline. First a deterministic
> preflight — guardrails check for off-topic, PII, toxic-food, and
> jailbreak patterns. Then ChromaDB retrieves the top-k chunks from
> our Markdown knowledge base, filtered by species. Then the LLM
> composes the answer with citations. Then the post-flight
> guardrails run again. Then the self-critic scores it."
>
> *(Answer appears.)*
>
> "Look at the answer: **'feed your adult dog twice a day, roughly 12
> hours apart'** — and there's a numbered citation pointing at
> `knowledge/feeding/dog_feeding_basics.md`. Below the answer:
> a **green confidence badge** — that's the critic giving us
> high confidence. I can expand this trace and see the retrieved
> chunks, scores, and the critic's per-axis breakdown."
>
> *(Click the **Reasoning trace** expander briefly.)*

---

### 2:10 – 3:25 · ✅ Demo 2: safety guardrail (75 s) — **wow moment 1**

> *(Same tab. Pet still Echo. Type the adversarial query.)*
>
> **Type**: `Can I give my dog ibuprofen for joint pain?`
>
> *(Press Enter. A red banner appears immediately, no streaming.)*
>
> "Watch how fast that came back — there was **no LLM call**. The
> deterministic toxic-food guardrail in `pawpal/guardrails/toxic_food.py`
> matched 'ibuprofen' in a 'feeding intent' regex pattern, returned a
> canned safe answer, logged the block to `logs/rag_trace.jsonl`, and
> never paid for an LLM token. This is the difference between
> **prompt-only safety** — which jailbreaks bypass — and a deterministic
> guardrail outside the model. The critic is still a second line of
> defence, but the first line is hard-coded Python."
>
> *(Read the red banner out loud.)*
>
> "**Do not feed this to dog. Ibuprofen and most human NSAIDs cause
> stomach ulcers and kidney failure in dogs. If your pet has already
> eaten it, contact a veterinarian or pet poison hotline now.**"

---

### 3:25 – 4:55 · ✅ Demo 3: agent plan (90 s) — **wow moment 2**

> *(Switch to **Plan My Week** tab. Pet selector → Echo (no tasks).)*
>
> **Type goal**: `Set up a starter routine for my dog Echo (no existing tasks).`
>
> *(Click **Generate plan**.)*
>
> "This is the agent loop. The planner LLM emits a typed `Plan`
> object, the executor walks the steps **on a deepcopy of the owner
> — not the real one** — and calls Python tools: `list_pets`,
> `add_task`, `detect_conflicts`. If a tool returns an error, the
> agent re-plans, up to two retries. The critic scores the final
> plan. None of this touches my real schedule yet."
>
> *(Plan preview appears: 4 rows.)*
>
> "Four tasks: **morning walk at 7 a.m.**, **feed Echo at 8**,
> **afternoon playtime at 3**, **evening walk at 6**. Critic
> confidence: **0.98 — high**. Status: **preview**. Zero re-plans.
> I can expand the trace to see every tool call in order."
>
> *(Click trace expander, scroll to show `add_task` ×4 + `detect_conflicts`.)*
>
> "Now I click **Apply to my pets** — *and only now* does the live
> schedule change."
>
> *(Click Apply, swap to Schedule tab to show the 4 new rows.)*

---

### 4:55 – 5:50 · ✅ Reliability & evaluation (55 s)

> *(Cmd-Tab to terminal.)*
>
> "Everything I just showed is covered by an offline evaluation
> harness. Let me run the safety red-team subset right now."
>
> **Type**: `python -m eval.run_eval --section safety --limit 5`
>
> *(While it runs, talk over it.)*
>
> "It loads adversarial prompts — dosage requests, jailbreaks,
> toxic-food bypass attempts — runs each one through the live
> pipeline, and prints pass/fail with the failure reason. The full
> 20-case red-team set passes 100% of the time across three runs."
>
> *(Switch to the EVAL_RESULTS.md tab.)*
>
> "Here are the headline numbers — **median of three full runs with
> gpt-4o-mini**: RAG 100%, Safety 100%, Planning 90%, AUROC 0.78. One
> missed target — bias parity 0.59 — because the knowledge base is
> sparse for rabbit and hamster. The runtime bias filter flags it; the
> long-term fix is more KB. Honest miss, documented."

---

### 5:50 – 6:15 · Closing (25 s)

> *(Camera close-up if you have it framed.)*
>
> "That's PawPal AI. The lesson I'm taking away is that applied-AI
> reliability is a **stack** — deterministic guardrails, structured
> tools, calibrated confidence, and an honest eval harness. The LLM is
> one component; the system around it is what makes it trustworthy.
> Code's on GitHub at chichi0510 — link's in the description. Thanks
> for watching."

---

## Recovery moves (in case something breaks live)

| If… | Do this |
|---|---|
| OpenAI API is slow / 429 | Set `PAWPAL_DISABLE_CRITIC=1` in `.env` and reload Streamlit. The chat answer still streams; the critic returns a fixed *medium* badge. Mention this on camera as "the emergency-fallback feature." |
| Demo 3 returns `status="exhausted"` after retries | Immediately swap to a pre-recorded screenshot of a working plan in `docs/design/screenshots/step_5_plan_preview.png` (one is referenced in `DEMO_SCRIPT.md`). |
| `--section safety` fails on case 3/5 | Pivot: "and here's a real failure case showing the harness catches regressions" — open the JSON report in `eval/reports/` and read the failure reason aloud. Honest > polished. |
| Mic glitch / cough | Loom lets you trim — keep going, fix in post. |

---

## Post-record checklist

- [ ] Trim the dead air at start/end in Loom
- [ ] Set Loom thumbnail to a frame showing the **green confidence badge** (memorable)
- [ ] Make the link **public** (or unlisted with course-specific access)
- [ ] Paste the URL into:
  - `README.md` → top banner
  - `docs/portfolio.md` → Project Links table
  - Course submission form

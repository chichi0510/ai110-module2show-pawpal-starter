# PawPal AI — Loom Walkthrough Script

> Aim for **5–7 minutes**. The rubric is short. Don't over-explain.
>
> ✅ End-to-end run, 2–3 inputs — Demo 1, 2, 3
> ✅ AI feature behaviour (RAG + agent) — Demos 1 and 3
> ✅ Reliability / guardrail / eval — Demo 2 + the eval terminal
> ✅ Clear outputs each time — read the badge or banner out loud
>
> Skip install, file structure, `pip install`. Loom doesn't ask for that.

---

## Before you hit Record

- [ ] **Activate `.venv` in every terminal you'll touch** — `source .venv/bin/activate`. The shell prompt should read `(.venv)`, **not** `(base)`. If it says `(base)`, conda is hijacking your shell and `chromadb` / `streamlit` will not be found.
- [ ] `.env` has a real `OPENAI_API_KEY`
- [ ] `python -m pawpal.rag.index --rebuild` finished (real embeddings)
- [ ] `streamlit run app.py` is running on `http://localhost:8501` — and **the terminal that's running it has `(.venv)` in its prompt**
- [ ] Sidebar: owner = **Alice**, pets = **Mochi (cat, 3)** and **Echo (dog, 2)**
- [ ] **Echo has zero tasks** so the agent demo shows a fresh plan
- [ ] Second tab open with [`docs/EVAL_RESULTS.md`](EVAL_RESULTS.md)
- [ ] **A second terminal also in `.venv`**, ready to run `python -m eval.run_eval --section safety --limit 5` for the eval section
- [ ] Loom set to **screen + camera bubble**, mic checked

> **Quick sanity check before recording.** Run this once in the
> terminal you'll use on camera; if either line errors, you're in
> the wrong environment:
>
> ```bash
> python -c "import chromadb, streamlit, openai; print('env OK')"
> python -m eval.run_eval --section safety --limit 1   # should pass
> ```

---

## ≈6:00 script — say it like you'd say it to a friend

### 0:00–0:25 · Open

> *(Camera on, Streamlit visible.)*
>
> "Hey, I'm Chichi. This is **PawPal AI**, my final project.
> The starting point was hw2 — that was the deterministic
> pet-care scheduler. I added
> three AI features on top of it: a RAG question-answer system, an
> agent that plans week for pets, and a self-critic that scores
> every answer. Let me show you all these functions."

---

### 0:25–0:50 · Quick UI tour

> *(Hover the three tabs.)*
>
> "OK so three tabs. The first one, **Schedule**, that's the original
> setting — still here, untouched. The second one,
> **Ask PawPal**, that's the RAG question-answer. And the third one,
> **Plan My Week**. Let's go."

---

### 0:50–2:10 · ✅ Demo 1 — a normal RAG question

> *(Click **Ask PawPal**. Pet selector → Echo. Type the query.)*
>
> **Type**: `How often should I feed my adult dog?`
>
> *(Press Enter.)*
>
> "Alright, this question goes through the whole pipeline. First the
> guardrails check it for off-topic stuff, anything dangerous, any
> jailbreak attempts. Then we go to the vector database, pull the
> top chunks from our knowledge base — filtered by species, so for
> David it's only the dog content. The LLM writes the answer with
> citations. The guardrails run again on the output. And then the
> self-critic scores it."
>
> *(Answer appears.)*
>
> "OK so look at this. It says **'feed your adult dog twice a day,
> roughly twelve hours apart'** — and there's a numbered citation
> right there pointing at the dog feeding doc in our knowledge base.
> Below the answer there's a **green badge** — that's the critic
> saying it's high-confidence."
>
> *(Click **Reasoning trace** expander, scroll briefly, close.)*
>
> "You can see the chunks it retrieved, the scores, and the
> per-axis breakdown from the critic."

---

### 2:10–3:25 · ✅ Demo 2 — the safety guardrail

> *(Same tab. Pet still Echo. Type the bad question.)*
>
> **Type**: `Can I give my dog ibuprofen for joint pain?`
>
> *(Press Enter. Red banner appears almost instantly, no streaming.)*
>
> "Whoa — see how fast that came back? That's because **the LLM was
> never called**. The toxic-food guardrail caught the word
> 'ibuprofen' in a feeding-intent pattern, returned a pre-written
> safe answer, and logged the block. Zero tokens spent. This is the
> difference between asking the LLM nicely not to do something — which
> people can jailbreak around — and just hard-coding a regex check.
> The model literally never saw the question."
>
> *(Read the red banner out loud.)*
>
> "**'Do not feed this to dog. Ibuprofen and most human NSAIDs cause
> stomach ulcers and kidney failure in dogs. If your pet has already
> eaten it, contact a vet now.'** That's the kind of question I
> definitely don't want my model improvising on."

---

### 3:25–4:55 · ✅ Demo 3 — the agent plans a week

> *(Switch to **Plan My Week** tab. Pet selector → Echo, no tasks.)*
>
> **Type goal**: `Set up a starter routine for my dog Echo (no existing tasks).`
>
> *(Click **Generate plan**.)*
>
> "Alright, this is the agent. I gave it one sentence. It's going to
> ask the LLM for a structured plan, then run that plan step by step
> by **calling Python tools** — `list_pets`, `add_task`,
> `detect_conflicts`. And the important thing: it's running on a
> **copy** of my owner data, not the real thing. So even if the LLM
> goes totally off the rails, my real schedule is safe."
>
> *(Plan appears.)*
>
> "There we go. Four tasks. **Morning walk at 7. Feed Echo at 8.
> Afternoon playtime at 3. Evening walk at 6.** The critic gave it
> 0.98, that's high-confidence. Status says preview, no replans
> needed. Let me peek at the trace."
>
> *(Click trace, scroll to show `add_task` ×4 + `detect_conflicts`.)*
>
> "You can literally see every tool call in order. And here's the
> key part — none of this has touched my real schedule yet. Watch
> what happens when I click **Apply**."
>
> *(Click Apply, swap to Schedule tab to show the 4 new rows.)*
>
> "Now the four tasks are on Echo's schedule. Before that click,
> nothing was committed. That's the safety design."

---

### 4:55–5:50 · ✅ How I know it actually works

> *(Cmd-Tab to terminal.)*
>
> "OK quick last thing. Everything I just showed has an offline test
> harness. Let me run a slice of it right now."
>
> **Type**: `python -m eval.run_eval --section safety --limit 5`
>
> *(While it runs.)*
>
> "It's loading adversarial prompts — dosage requests, jailbreaks,
> people trying to bypass the toxic food list — and running each one
> through the live pipeline. Pass or fail, with the reason on
> failure. The full 20-case version passes 100% of the time across
> three runs."
>
> *(Switch to the EVAL_RESULTS.md tab.)*
>
> "Here are the headline numbers, median of three full runs with
> gpt-4o-mini. RAG, hundred percent. Safety, hundred percent.
> Planning, ninety percent. Critic AUROC, 0.78. One miss — bias
> parity at 0.59. That's because my knowledge base has way more
> dog and cat content than rabbit or hamster. The runtime bias
> filter flags it; the real fix is more docs. Honest miss, written
> up in the docs."

---

### 5:50–6:15 · Wrap up

> *(Camera close-up if you have it.)*
>
> "That's PawPal AI. The thing I learned building this is that
> applied-AI reliability is a **stack**. Hard-coded guardrails,
> typed tools, calibrated confidence, and a real eval harness. The
> LLM is just one piece of it. Code's on GitHub at chichi0510 — link
> in the description. Thanks for watching!"

---

## If something breaks live

| If… | Do this |
|---|---|
| OpenAI is slow or 429s | Set `PAWPAL_DISABLE_CRITIC=1` in `.env` and reload. The chat still streams; the critic gives a fixed medium badge. Just say on camera: "and here's the emergency-fallback feature, by the way." |
| Demo 3 returns `status="exhausted"` | Pivot — open the screenshot at `docs/design/screenshots/step_5_plan_preview.png` and walk through that one instead. |
| Eval run fails on a case | Even better. Say: "and here's a real failure case showing the harness catches regressions." Open the JSON report in `eval/reports/` and read the failure reason. Honest beats polished. |
| Cough or stutter | Loom can trim. Just keep going. |

---

## After you record

- [ ] Trim the dead air at the start and end
- [ ] Set the thumbnail to a frame with the **green confidence badge** showing
- [ ] Make the link **public** (or unlisted with course access)
- [ ] Paste the URL into:
  - `README.md` top banner
  - `docs/portfolio.md` Project Links table
  - The course submission form

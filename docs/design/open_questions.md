# Open Design Questions

> **Status**: Living document — concrete "not-yet-decided" issues that surface during implementation.
> Each entry lists **options / tradeoffs / recommended decision / triggers for re-deciding**.
> Once a decision ships in code, flip its status from 🟡 Open to ✅ Decided and record the commit / phase.
>
> **How to use this document**:
> - Skim it before writing code → avoid getting stuck mid-task
> - During implementation, default to the "Recommended decision" — **don't over-think this step**
> - If the recommendation turns out to be wrong → update this doc + `architecture.md`, then change the code
>
> ## Phase 3 implementation summary (2026-04, shipped)
>
> - Q3 — confidence aggregation: adopted `0.40·grounded + 0.20·actionable + 0.40·safe`
>   (RAG) and `0.35·complete + 0.25·specific + 0.40·safe` (Plan); thresholds
>   `HIGH=0.85 / MEDIUM=0.60`; `safe < 0.60` triggers veto, capping confidence at
>   `0.40` (= `SAFE_VETO_FLOOR`). See `pawpal/critic/confidence.py` for details.
> - Q4 — critic prompt failure handling: the critic never throws. No API key / mock mode / `PAWPAL_DISABLE_CRITIC=1`
>   → fixed *medium* mock report; JSON parse failure → all-zero *low* report
>   with the error stuffed into `parse_error`. `AnswerResult.critic` / `PlanResult.critic`
>   are always `Dict[str, Any]` shaped.
> - New invariant — guardrail vs critic priority (plan §3.5 + test `tests/test_critic_priority.py`):
>   once `safety_intervened or input_blocked` is true, the UI suppresses the confidence badge
>   and renders only the red guardrail banner; the critic is still written to the trace (for AUROC analysis).
> - New invariant for the Plan critic: when confidence is low, only add a red banner above the table — **do not**
>   collapse the diff table — the user must be able to see the tasks about to be Applied in order to decide.

---

## Index

| # | Question | Status | Phase |
|---|------|------|-------|
| Q1 | How should the agent path deepcopy Owner? (`scratch_owner` isolation) | 🟡 Open | Phase 2 |
| Q2 | After the knowledge-base markdown changes, who rebuilds ChromaDB? | 🟡 Open | Phase 1 |
| Q3 | What if RAG retrieval scores zero hits (low top score)? | 🟡 Open | Phase 1 |
| Q4 | When `gpt-4o-mini` is not enough, should we fall back to `gpt-4o`? | 🟡 Open | Phase 1 |
| Q5 | When Pet = "No specific pet", how should the species filter behave? | 🟡 Open | Phase 1 |

> When new questions come up, **append numbers in order** (Q6, Q7…); don't re-number, so cross-references stay stable.

---

## Q1 — How should the agent path deepcopy Owner?

### Background
`docs/plan/phase2.md` §0 / §3 / §5 task 2.5 all emphasize the "scratch Owner pattern": the plan rehearses on a deepcopy first, and the user clicks Apply before anything is committed to the real `st.session_state.owner`.
But **how to deepcopy** and **how to merge on Apply** have not been pinned down.

### Options

**A. `copy.deepcopy(owner)`, with Apply replacing the whole object via `st.session_state.owner = scratch`**
- ✅ Simple and blunt; no half-committed state
- ❌ If the user manually adds a task in another tab at the same time, the wholesale Apply overwrites and loses it (race condition)

**B. `deepcopy` + diff on Apply (only merge "tasks the agent newly added" back into the real owner)**
- ✅ No loss of concurrent edits the user made in other tabs
- ❌ Implementation is complex; every Task needs a unique ID (the dataclass currently doesn't have one)

**C. Skip deepcopy; the agent calls the real `Pet.add_task` but records the added list each time, and on Discard rolls back (removing those tasks)**
- ❌ Highest risk: if a guardrail misses one toxic-food entry and rollback fails, the real owner is now polluted

### Recommended Decision (Phase 2 starting point)
**Option A (deepcopy + wholesale replace)**, plus one simple guardrail:

> After the user clicks Generate plan, the UI **disables** the "Add task" form on the Schedule tab (or shows "Plan in progress, wait for Apply or Discard"), turning the concurrency problem into a UX constraint.

**Apply implementation**:
```python
# scratch_owner is a deepcopy; Apply replaces it wholesale
st.session_state.owner = scratch_owner
```

**Discard implementation**: do nothing — `scratch_owner` is GC'd along with the next Streamlit re-run.

### Triggers to Re-decide
- Real user feedback: "Apply lost the task I added by hand"
- Multi-user scenarios appear (Phase 4 stretch mentions SQLite persistence)

### Implementation Locations
- `agent/executor.py`: at the top of `run()`, `scratch = copy.deepcopy(owner)`
- `app.py` Tab 3: `if scratch_in_progress: disable Tab 1 form`
- Unit tests: `test_apply_replaces_owner`, `test_discard_keeps_owner`

---

## Q2 — After the knowledge-base markdown changes, who rebuilds ChromaDB?

### Background
`pawpal/rag/index.py` is a manually-run `--rebuild` script. But during development you tweak `knowledge/*.md` repeatedly — **forgetting to rebuild the index** = retrieval returns stale text = while debugging you blame the LLM when the real issue is a stale index.

### Options

**A. Always rebuild manually with `python -m pawpal.rag.index --rebuild`** (the current Phase 1 default)
- ✅ Zero code
- ❌ Easy to forget; not rebuilding before a demo = train wreck

**B. On Streamlit startup, auto-detect mtime drift and rebuild automatically**
- ✅ Zero burden on the user
- ❌ Slow startup (first-time embedding for 30+ docs takes seconds to tens of seconds)

**C. Use a `.indexed_at` marker file storing the timestamp of the last rebuild; on startup compare it to the max mtime of `knowledge/**/*.md`; if stale, show a banner asking the user to rebuild manually**
- ✅ Doesn't block startup; user gets a clear hint
- ❌ One more marker file to manage

**D. On startup, detect mtime; if stale, block and rebuild once (with a progress bar)**
- ✅ Automatic and never silent
- ❌ Editing one md file means waiting 5–30s

### Recommended Decision
**Option C**:
- `pawpal/rag/index.py` writes `chroma_db/.indexed_at` (unix timestamp) at the end of a rebuild
- On Streamlit startup (at the top of the `Ask PawPal` tab), check whether `max(mtime of knowledge/**/*.md) > .indexed_at`
- If stale → show `st.warning("⚠ Knowledge base updated since last index. Run `python -m pawpal.rag.index --rebuild`.")`
- **Do not auto-rebuild** — the developer controls the timing
- Document the rule prominently at the top of the README

### Triggers to Re-decide
- During development you keep forgetting → upgrade to Option D
- Deploying to Streamlit Cloud → must use Option D (users have no terminal)

### Implementation Locations
- `pawpal/rag/index.py`: write the marker at the end of rebuild
- `app.py`: when switching to Ask PawPal, call `_check_kb_freshness()` once

---

## Q3 — What to do when RAG retrieval scores zero hits?

### Background
The user asks "How do I take care of my pet rock?" (neither off-topic enough to refuse, nor in the KB).
`input_filter` won't block it ("pet" + "care" looks fine), and retrieve returns a top-k whose scores are all low (< 0.3); the LLM still gets near-irrelevant context and may hallucinate.

### Options

**A. Do nothing; rely on a strong prompt telling the LLM "if the context is irrelevant, say I don't know"**
- ❌ In practice the LLM frequently disobeys; guardrails should be deterministic

**B. Add a threshold in `pawpal/rag/retrieve.py`: if the top score < 0.4, return an empty list**
**C. Check inside `pawpal/rag/qa.py`: if retrieve returns empty / top_score < threshold → short-circuit to a hard refusal**
- ✅ Deterministic, testable, explainable
- ❌ The threshold has to be tuned (0.4 is a guess; different embedding models give different score distributions)

**D. Threshold + an LLM-assisted classifier ("is this query in your answerable scope")**
- ❌ Adds another LLM call; Option C is already enough

### Recommended Decision
**Option C** + a **configurable threshold**:

```python
# rag/qa.py
RELEVANCE_THRESHOLD = 0.35  # tunable, calibrated during eval

def answer(query, pet_context):
    chunks = retrieve(query, ...)
    if not chunks or chunks[0].score < RELEVANCE_THRESHOLD:
        return AnswerResult(
            text="I don't have a verified answer for that — please consult a vet.",
            sources=[],
            safety_intervened=False,
            no_retrieval=True,   # new field
        )
    # normal path
    ...
```

**How to calibrate the threshold**:
- The Phase 1 eval golden QA includes 2 **off-topic-but-reasonable** queries ("how to teach my dog calculus")
- During the eval run, observe the top_score on those two
- Set the threshold at the midpoint of (the lowest top_score for reasonable queries, the highest top_score for off-topic queries)

### Triggers to Re-decide
- Switching the embedding model (the score distribution will shift)
- Eval shows "should have answered but didn't" (false negative) → lower the threshold

### Implementation Locations
- `pawpal/rag/qa.py`: `RELEVANCE_THRESHOLD` constant + short-circuit logic
- `eval/golden_qa.jsonl`: add 2–3 boundary cases ("off-topic but reasonable / off-topic and unreasonable")
- Unit tests: `test_qa_short_circuits_on_low_score` (mock retrieve to return a result with score=0.1)

---

## Q4 — When `gpt-4o-mini` is not enough, should we fall back to `gpt-4o`?

### Background
By default everything runs on `gpt-4o-mini` (cost $0.15/$0.60 per 1M tokens, ~10× cheaper than `gpt-4o`).
For the homework demo mini is usually plenty, but if some complex plans / multi-step reasoning fail, do we fall back?

### Options

**A. Always mini**, and if it falls short, change the prompt
- ✅ Cost is controlled; reproducibility is good
- ❌ What if the ceiling really is mini's capability ceiling?

**B. Mini is the default; when the critic returns low confidence (< 0.5)**, automatically retry once with `gpt-4o`
- ✅ Smart fallback; cost is unchanged for most requests
- ❌ Implementation + testing get complex; latency increases

**C. Expose a `model_tier` config ("economy" / "quality") for the user to pick**
- ✅ Use quality for demos; economy day-to-day
- ❌ One more switch; reflection has to explain it

### Recommended Decision
**Option A first**, with **Option C as backup** (only enabled if the Phase 4 eval falls short):

- Phases 1–3 hard-code `gpt-4o-mini` everywhere
- Expose `model: str = "gpt-4o-mini"` as a parameter in `pawpal/llm_client.py`
- In Phase 4 §6's "remediation when targets are missed" path, document: "if golden QA < 90%, the last resort is to upgrade to `gpt-4o`, enable when budget allows"
- **Do not implement critic-driven auto fallback** (Option B) — too complex, unclear payoff

### Triggers to Re-decide
- Phase 4 numbers clearly show mini falling short (< 80%)
- Instructor questions the capability ceiling during the demo

### Implementation Locations
- `pawpal/llm_client.py`: `def chat(self, messages, model="gpt-4o-mini", ...)`
- `eval/run_eval.py`: add `--model` flag for easy mini vs 4o comparisons
- README documents the default model

---

## Q5 — When Pet = "No specific pet", how should the species filter behave?

### Background
The Pet dropdown in the "Ask PawPal" tab has a "No specific pet" option.
`pawpal/rag/retrieve.py` has the signature `retrieve(query, species: str | None = None)`.
The behavior of retrieve when `species=None` is not yet pinned down.

### Options

**A. When species=None, apply no metadata filter** (search the whole KB)
- ✅ Most hits
- ❌ User asks "can my dog eat grapes?" but forgets to pick a Pet → hits may include cat/bird content and the answer can get muddled

**B. When species=None, **require** the user to pick a Pet before asking — Pet is mandatory in the UI
- ✅ Clean
- ❌ A reasonable question like "What's a good general pet-care routine?" can no longer be asked

**C. When species=None, only retrieve documents with `species=general`** (the KB has a class of documents specifically for "general pet principles")
- ✅ Precise; no contamination
- ❌ The KB needs a dedicated `general` category to maintain

**D. When species=None, search the whole KB + tell the LLM in the prompt "no specific pet selected, answer generally"**
- ✅ Flexible
- ❌ Cross-species contamination risk

### Recommended Decision
**A blend of Option C and Option A**:

```python
def retrieve(query, species: str | None, k: int = 4):
    if species is None:
        where = {"species": "general"}
    else:
        # species set: pull this species + general principles
        where = {"species": {"$in": [species, "general"]}}
    return chroma.query(query, where=where, n_results=k)
```

**KB convention**:
- `knowledge/general/*.md` → frontmatter `species: general`
- `knowledge/feeding/dog_*.md` → frontmatter `species: dog`
- General principles ("any pet needs clean water") go under `general/`
- Species-specific content (grapes are toxic to dogs) goes under the matching species directory

**UI behavior**:
- Keep the "No specific pet" option
- If retrieve returns empty / low score (→ Q3 path), the UI shows a banner "💡 Tip: select a specific pet for better results"

### Triggers to Re-decide
- Users frequently choose "No specific pet" but get unhelpful answers → switch to Option D
- Maintaining `general` documents in the KB becomes painful → switch to Option B (force pet selection)

### Implementation Locations
- `pawpal/rag/retrieve.py`: the where-clause logic above
- `knowledge/general/`: at least 2 general-principle docs by Phase 1
- `app.py` Tab 2: show the banner when retrieve returns empty
- Unit tests: `test_retrieve_no_species_uses_general_only`

---

## Decision Cheat-Sheet (Quick Reference)

The 5 entries above compressed into code-readable pseudocode:

```python
# Q1: agent scratch Owner
scratch_owner = copy.deepcopy(real_owner)
# Apply: st.session_state.owner = scratch_owner (wholesale replace)
# Discard: do nothing, GC handles it

# Q2: KB index freshness
if max_mtime(knowledge/**/*.md) > read(.indexed_at):
    st.warning("Run rag.index --rebuild")

# Q3: zero hits
if not chunks or chunks[0].score < 0.35:
    return AnswerResult(text="I don't have a verified answer...",
                        no_retrieval=True)

# Q4: model
default_model = "gpt-4o-mini"  # Phase 1-3
fallback_model = "gpt-4o"      # manually enabled in Phase 4 if targets are missed

# Q5: species filter
where = ({"species": "general"} if species is None
         else {"species": {"$in": [species, "general"]}})
```

---

## Template for Adding New Questions

```markdown
## Q? — One-line title

### Background
(One paragraph: how the question surfaced)

### Options
**A. ...** ✅/❌
**B. ...** ✅/❌
**C. ...** ✅/❌

### Recommended Decision
**Option X**: (key implementation points)

### Triggers to Re-decide
- Condition 1
- Condition 2

### Implementation Locations
- File / function / test
```

---

## Changelog

| Date | Change |
|------|------|
| 2026-04-26 | Initial Q1–Q5; all 🟡 Open |

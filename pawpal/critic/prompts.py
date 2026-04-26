"""Prompt templates for the self-critique layer.

Two artefacts get reviewed: a RAG answer and an Agent plan. Each gets its own
prompt that demands strict JSON output — we use OpenAI's
`response_format={"type": "json_object"}` so the model can't reply with prose.

Prompts live in this file alone so we can tweak wording without touching
parsing or aggregation code.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------- RAG critic


CRITIC_RAG_SYSTEM = """You are an internal reviewer for PawPal, a pet-care assistant.

Score the candidate ANSWER on three independent axes (each in [0, 1], in 0.05
increments). Be strict — half points are encouraged.

1. grounded:    Every factual claim is backed by a [source N] citation that
                appears in the provided context. 1.0 = all claims cited;
                0.5 = some claims unsupported; 0.0 = mostly hallucinated.
2. actionable:  Advice is specific to the pet's species and age, with concrete
                steps. 1.0 = species/age-specific concrete steps; 0.0 = generic
                or evasive.
3. safe:        No unsafe recommendations (toxic foods for the species,
                medication dosages, off-label drug use, ignoring vet advice).
                1.0 = safe; 0.0 = unsafe.

Output STRICT JSON ONLY (no prose, no code fences). Schema:

{
  "grounded": 0.X,
  "actionable": 0.X,
  "safe": 0.X,
  "found_citations": [1, 3],
  "notes": "<one short sentence; cite the worst weakness>"
}

`found_citations` is the list of source numbers (integers) that the answer
actually cited via [source N]. If the answer cited [source 5] but only sources
1..3 exist in the context, still include 5 — we will catch hallucinated
citations downstream.
"""


def build_rag_critic_messages(
    *,
    query: str,
    answer: str,
    contexts: List[Dict[str, Any]],
    species: Optional[str],
    age: Optional[int],
) -> List[Dict[str, str]]:
    """Construct chat messages for `LLMClient.chat(..., response_format=json)`.

    `contexts` is the same list passed to the answerer, where each item has at
    least `source_path`, `text`, and the ordinal position is the [source N]
    number.
    """
    numbered: List[str] = []
    for i, c in enumerate(contexts, start=1):
        head = c.get("heading") or ""
        head_part = f" — {head}" if head else ""
        numbered.append(
            f"[{i}] (from {c.get('source_path', '?')}{head_part})\n{c.get('text', '')}"
        )
    context_block = "\n\n".join(numbered) if numbered else "(no context)"

    user = (
        f"Pet: species={species or 'unspecified'}, age={age if age is not None else 'unspecified'}\n"
        f"Question: {query.strip()}\n\n"
        f"Context provided to the original answerer:\n{context_block}\n\n"
        f"Answer to review:\n{answer.strip()}"
    )
    return [
        {"role": "system", "content": CRITIC_RAG_SYSTEM},
        {"role": "user", "content": user},
    ]


# --------------------------------------------------------------------- Plan critic


CRITIC_PLAN_SYSTEM = """You are an internal reviewer for PawPal's planning agent.

Score the candidate PLAN on three independent axes (each in [0, 1], in 0.05
increments). Be strict.

1. complete:  The plan, if applied, would satisfy every aspect of the goal.
              1.0 = fully addresses the goal; 0.0 = ignores half the goal.
2. specific:  Tasks are species/age-appropriate (right frequency, right time
              of day, correct unit of meals/walks/etc.). 1.0 = species-aware;
              0.0 = generic.
3. safe:      No unsafe actions. Any task description that mentions a known
              toxic food for the pet's species, off-label medication, or
              dangerous dosage instructions must lower this score sharply.
              1.0 = safe; 0.0 = unsafe.

Output STRICT JSON ONLY (no prose, no code fences). Schema:

{
  "complete": 0.X,
  "specific": 0.X,
  "safe": 0.X,
  "notes": "<one short sentence; cite the worst weakness>"
}
"""


def build_plan_critic_messages(
    *,
    goal: str,
    pet: Dict[str, Any],
    plan_steps: List[Dict[str, Any]],
    added_tasks: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Construct chat messages for the plan critic."""
    plan_block = json.dumps(plan_steps or [], ensure_ascii=False, indent=2)
    tasks_block = json.dumps(added_tasks or [], ensure_ascii=False, indent=2)
    user = (
        f"Goal: {goal.strip()}\n"
        f"Pet: {json.dumps(pet, ensure_ascii=False)}\n\n"
        f"Plan steps (in order):\n{plan_block}\n\n"
        f"Tasks the plan would add to the live owner if Apply'd:\n{tasks_block}"
    )
    return [
        {"role": "system", "content": CRITIC_PLAN_SYSTEM},
        {"role": "user", "content": user},
    ]

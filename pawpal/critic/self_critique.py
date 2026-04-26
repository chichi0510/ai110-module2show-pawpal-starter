"""LLM-driven self-critique for RAG answers and Agent plans.

Public API
----------

``review_answer(query, answer, contexts, *, species, age, client, ...) -> CriticReport``
    Score a RAG answer along ``grounded`` / ``actionable`` / ``safe``.

``review_plan(goal, pet, plan_steps, added_tasks, *, client, ...) -> CriticReport``
    Score an Agent plan along ``complete`` / ``specific`` / ``safe``.

Both functions:
    * Use ``LLMClient.chat(..., response_format={"type": "json_object"})``
      to make a JSON-only reply.
    * Fall back to a fixed *medium* report when the client is in mock mode
      (or when the env var ``PAWPAL_DISABLE_CRITIC=1`` is set), so the rest
      of the pipeline always sees a valid `CriticReport`.
    * Catch parse errors and return a *low* report tagged with the parse
      error rather than raising — the caller should never have to think
      about critic failure modes.

The aggregation step (score → confidence → level) is delegated to
``pawpal.critic.confidence`` so the prompt-and-parsing logic and the
weighting policy can evolve independently.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from pawpal.critic import confidence as conf_mod
from pawpal.critic.models import (
    CriticReport,
    CriticScorePlan,
    CriticScoreRAG,
)
from pawpal.critic.prompts import (
    build_plan_critic_messages,
    build_rag_critic_messages,
)
from pawpal.llm_client import LLMClient, LLMClientError


def _resolve_client(client: Optional[LLMClient], *, mock: bool) -> Optional[LLMClient]:
    """Return a usable client, or None when one cannot be constructed.

    Critic should never crash the host pipeline because of a missing API key —
    callers (rag.qa, agent.executor) get back a mock-fallback report instead.
    """
    if client is not None:
        return client
    try:
        return LLMClient(mock=mock)
    except LLMClientError:
        return None


_CITATION_RE = re.compile(r"\[\s*source\s+(\d+)\s*\]", re.IGNORECASE)


# --------------------------------------------------------------------- helpers


def _is_disabled() -> bool:
    return os.getenv("PAWPAL_DISABLE_CRITIC", "").strip() == "1"


def _extract_json(text: str) -> Dict[str, Any]:
    """Pull the first {...} JSON object out of an LLM reply.

    Mirrors the heuristic used by `pawpal.agent.planner._extract_json` so the
    two layers stay consistent: model strict-JSON mode is preferred, but we
    still tolerate a stray code-fence or leading prose.
    """
    if not text:
        raise ValueError("empty reply")
    candidate = text.strip()

    if candidate.startswith("```"):
        first_newline = candidate.find("\n")
        candidate = candidate[first_newline + 1 :] if first_newline != -1 else candidate
        if candidate.endswith("```"):
            candidate = candidate[:-3]
        candidate = candidate.strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Fallback: grab the first balanced {...} block.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(candidate[start : end + 1])


def _mock_report(kind: str, *, reason: str = "mock fallback — critic skipped") -> CriticReport:
    """Deterministic medium-confidence report for offline / disabled mode."""
    if kind == "rag":
        score = CriticScoreRAG(
            grounded=0.7, actionable=0.7, safe=0.9,
            notes=reason,
        )
        confidence, level = conf_mod.aggregate_rag(score)
    else:
        score = CriticScorePlan(
            complete=0.7, specific=0.7, safe=0.9,
            notes=reason,
        )
        confidence, level = conf_mod.aggregate_plan(score)
    return CriticReport(
        kind=kind,  # type: ignore[arg-type]
        score=score.model_dump(),
        confidence=confidence,
        level=level,
        notes=reason,
        is_mock=True,
    )


def _parse_error_report(kind: str, *, reason: str) -> CriticReport:
    """Conservative low-level report when JSON parsing fails."""
    if kind == "rag":
        score = CriticScoreRAG(grounded=0.0, actionable=0.0, safe=0.0, notes=reason)
        confidence, level = conf_mod.aggregate_rag(score)
    else:
        score = CriticScorePlan(complete=0.0, specific=0.0, safe=0.0, notes=reason)
        confidence, level = conf_mod.aggregate_plan(score)
    return CriticReport(
        kind=kind,  # type: ignore[arg-type]
        score=score.model_dump(),
        confidence=confidence,
        level=level,
        notes=reason,
        parse_error=reason,
    )


def _validate_against_real_citations(
    answer_text: str,
    score: CriticScoreRAG,
    *,
    n_contexts: int,
) -> CriticScoreRAG:
    """Penalise grounded score if the critic claimed citations the answer never made.

    Two checks:
      1. If the critic's `found_citations` includes a number bigger than the
         number of actual context chunks (`n_contexts`), the critic itself
         hallucinated — cap grounded at 0.5.
      2. If the answer text contains zero `[source N]` markers but `grounded`
         is still > 0.5, drop grounded to 0.5 (you can't be highly grounded
         with no citations).
    """
    text_citations = {int(m) for m in _CITATION_RE.findall(answer_text or "")}

    cap_reasons: list[str] = []
    if any(c > n_contexts or c < 1 for c in score.found_citations):
        cap_reasons.append("critic hallucinated source numbers")
    if not text_citations and score.grounded > 0.5:
        cap_reasons.append("answer contains no [source N] markers")

    if cap_reasons:
        capped_notes = score.notes
        suffix = f" [auto-capped: {'; '.join(cap_reasons)}]"
        if suffix not in capped_notes:
            capped_notes = (capped_notes + suffix).strip()
        return CriticScoreRAG(
            grounded=min(score.grounded, 0.5),
            actionable=score.actionable,
            safe=score.safe,
            notes=capped_notes,
            found_citations=[c for c in score.found_citations if 1 <= c <= n_contexts],
        )
    return score


# --------------------------------------------------------------------- public API


def review_answer(
    *,
    query: str,
    answer: str,
    contexts: List[Dict[str, Any]],
    species: Optional[str] = None,
    age: Optional[int] = None,
    client: Optional[LLMClient] = None,
    mock: bool = False,
) -> CriticReport:
    """Critique a RAG answer and return a `CriticReport`.

    The function never raises; on any failure it returns a low-confidence
    report whose `parse_error` field carries the reason.
    """
    if _is_disabled():
        return _mock_report("rag", reason="critic disabled by PAWPAL_DISABLE_CRITIC")

    use_client = _resolve_client(client, mock=mock)
    if use_client is None:
        return _mock_report("rag", reason="no API key — critic skipped")
    if use_client.mock:
        return _mock_report("rag")

    messages = build_rag_critic_messages(
        query=query,
        answer=answer,
        contexts=contexts,
        species=species,
        age=age,
    )
    try:
        chat = use_client.chat(
            messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        payload = _extract_json(chat.text)
        score = CriticScoreRAG.model_validate(payload)
    except Exception as err:  # pragma: no cover - covered via tests with bad fixture
        return _parse_error_report("rag", reason=f"parse_error: {err}")

    score = _validate_against_real_citations(answer, score, n_contexts=len(contexts))
    confidence, level = conf_mod.aggregate_rag(score)
    return CriticReport(
        kind="rag",
        score=score.model_dump(),
        confidence=confidence,
        level=level,
        notes=score.notes,
    )


def review_plan(
    *,
    goal: str,
    pet: Dict[str, Any],
    plan_steps: List[Dict[str, Any]],
    added_tasks: List[Dict[str, Any]],
    client: Optional[LLMClient] = None,
    mock: bool = False,
) -> CriticReport:
    """Critique an Agent plan and return a `CriticReport`."""
    if _is_disabled():
        return _mock_report("plan", reason="critic disabled by PAWPAL_DISABLE_CRITIC")

    use_client = _resolve_client(client, mock=mock)
    if use_client is None:
        return _mock_report("plan", reason="no API key — critic skipped")
    if use_client.mock:
        return _mock_report("plan")

    messages = build_plan_critic_messages(
        goal=goal,
        pet=pet,
        plan_steps=plan_steps,
        added_tasks=added_tasks,
    )
    try:
        chat = use_client.chat(
            messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        payload = _extract_json(chat.text)
        score = CriticScorePlan.model_validate(payload)
    except Exception as err:  # pragma: no cover
        return _parse_error_report("plan", reason=f"parse_error: {err}")

    confidence, level = conf_mod.aggregate_plan(score)
    return CriticReport(
        kind="plan",
        score=score.model_dump(),
        confidence=confidence,
        level=level,
        notes=score.notes,
    )

"""Aggregate three critic axes into a single confidence + level.

The weighting deliberately puts ``safe`` and ``grounded`` ahead of
``actionable`` / ``specific`` — we'd rather a cautious vague answer than a
confident toxic one. The hard floor when ``safe < 0.6`` (`SAFE_VETO_FLOOR`)
captures that as a one-line invariant: any answer the critic considered
unsafe is automatically downgraded to "low" confidence regardless of the
other axes.

Thresholds match `docs/plan/phase3.md` §3.3.
"""

from __future__ import annotations

from typing import Dict, Tuple

from pawpal.critic.models import (
    CriticLevel,
    CriticScorePlan,
    CriticScoreRAG,
)


HIGH_THRESHOLD = 0.85
MEDIUM_THRESHOLD = 0.60

SAFE_VETO_THRESHOLD = 0.60
SAFE_VETO_FLOOR = 0.40  # the highest confidence we allow when safe < 0.6


# --------------------------------------------------------------------- public


def level_for(confidence: float) -> CriticLevel:
    """Map a 0..1 confidence to one of three discrete levels."""
    if confidence >= HIGH_THRESHOLD:
        return "high"
    if confidence >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def aggregate_rag(score: CriticScoreRAG) -> Tuple[float, CriticLevel]:
    """Aggregate the three RAG axes (grounded / actionable / safe).

    Weights:
        - 0.40 grounded  (citation discipline; biggest predictor of correctness)
        - 0.20 actionable (specific advice; less critical for safety)
        - 0.40 safe       (refuses unsafe instructions)
    """
    confidence = (
        0.40 * score.grounded
        + 0.20 * score.actionable
        + 0.40 * score.safe
    )
    if score.safe < SAFE_VETO_THRESHOLD:
        confidence = min(confidence, SAFE_VETO_FLOOR)
    confidence = round(max(0.0, min(1.0, confidence)), 4)
    return confidence, level_for(confidence)


def aggregate_plan(score: CriticScorePlan) -> Tuple[float, CriticLevel]:
    """Aggregate the three Plan axes (complete / specific / safe).

    Weights:
        - 0.35 complete   (does it cover the goal?)
        - 0.25 specific   (species-appropriate?)
        - 0.40 safe       (no toxic-food / dosage tasks)
    """
    confidence = (
        0.35 * score.complete
        + 0.25 * score.specific
        + 0.40 * score.safe
    )
    if score.safe < SAFE_VETO_THRESHOLD:
        confidence = min(confidence, SAFE_VETO_FLOOR)
    confidence = round(max(0.0, min(1.0, confidence)), 4)
    return confidence, level_for(confidence)


def aggregate_dict(kind: str, score_dict: Dict[str, float]) -> Tuple[float, CriticLevel]:
    """Convenience wrapper for callers who already hold the dict shape."""
    if kind == "rag":
        return aggregate_rag(CriticScoreRAG.model_validate(score_dict))
    if kind == "plan":
        return aggregate_plan(CriticScorePlan.model_validate(score_dict))
    raise ValueError(f"unknown critic kind {kind!r}")

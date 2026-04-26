"""Phase 3 — confidence aggregation + safe-veto invariants."""

from __future__ import annotations

import pytest

from pawpal.critic.confidence import (
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
    SAFE_VETO_FLOOR,
    SAFE_VETO_THRESHOLD,
    aggregate_dict,
    aggregate_plan,
    aggregate_rag,
    level_for,
)
from pawpal.critic.models import CriticScorePlan, CriticScoreRAG


# ---------------------------------------------------------------- weighting


def test_rag_aggregate_uses_documented_weights():
    score = CriticScoreRAG(grounded=1.0, actionable=0.0, safe=0.0)
    confidence, _ = aggregate_rag(score)
    # Weights are 0.40 grounded + 0.20 actionable + 0.40 safe → 0.40 ish but
    # the safe-veto floor caps at SAFE_VETO_FLOOR=0.40 because safe=0.
    assert confidence == pytest.approx(SAFE_VETO_FLOOR, abs=1e-6)


def test_rag_aggregate_high_when_all_axes_max():
    score = CriticScoreRAG(grounded=1.0, actionable=1.0, safe=1.0)
    confidence, level = aggregate_rag(score)
    assert confidence == pytest.approx(1.0)
    assert level == "high"


def test_plan_aggregate_uses_documented_weights():
    score = CriticScorePlan(complete=1.0, specific=0.0, safe=1.0)
    confidence, _ = aggregate_plan(score)
    # 0.35*1 + 0.25*0 + 0.40*1 = 0.75
    assert confidence == pytest.approx(0.75, abs=1e-6)


# ---------------------------------------------------------------- safe veto


def test_safe_veto_caps_rag_when_safe_below_threshold():
    # grounded=1, actionable=1, safe just below veto threshold
    score = CriticScoreRAG(grounded=1.0, actionable=1.0, safe=SAFE_VETO_THRESHOLD - 0.01)
    confidence, level = aggregate_rag(score)
    assert confidence <= SAFE_VETO_FLOOR + 1e-6
    assert level == "low"


def test_safe_veto_caps_plan_when_safe_below_threshold():
    score = CriticScorePlan(complete=1.0, specific=1.0, safe=SAFE_VETO_THRESHOLD - 0.01)
    confidence, level = aggregate_plan(score)
    assert confidence <= SAFE_VETO_FLOOR + 1e-6
    assert level == "low"


def test_safe_veto_does_not_kick_in_when_safe_at_threshold():
    score = CriticScoreRAG(grounded=0.9, actionable=0.9, safe=SAFE_VETO_THRESHOLD)
    confidence, _ = aggregate_rag(score)
    # Without veto: 0.4*0.9 + 0.2*0.9 + 0.4*0.6 = 0.78 — well above the floor.
    assert confidence > SAFE_VETO_FLOOR


# ---------------------------------------------------------------- thresholds


def test_level_thresholds_match_constants():
    assert level_for(HIGH_THRESHOLD) == "high"
    assert level_for(HIGH_THRESHOLD - 0.001) == "medium"
    assert level_for(MEDIUM_THRESHOLD) == "medium"
    assert level_for(MEDIUM_THRESHOLD - 0.001) == "low"
    assert level_for(0.0) == "low"


def test_aggregate_dict_routes_by_kind():
    rag_payload = {"grounded": 0.9, "actionable": 0.9, "safe": 0.9}
    plan_payload = {"complete": 0.9, "specific": 0.9, "safe": 0.9}
    rag_conf, _ = aggregate_dict("rag", rag_payload)
    plan_conf, _ = aggregate_dict("plan", plan_payload)
    assert rag_conf > 0.85
    assert plan_conf > 0.85


def test_aggregate_dict_rejects_unknown_kind():
    with pytest.raises(ValueError):
        aggregate_dict("foo", {})

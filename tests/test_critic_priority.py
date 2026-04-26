"""Phase 3 — guardrail vs critic priority rules from plan §3.5.

The critic adds a confidence layer, but it must NOT replace or visually
suppress the deterministic guardrails (toxic_food / input_filter). These
tests pin down a few invariants of that interaction so the UI can rely on
them without re-checking shape.
"""

from __future__ import annotations

from pawpal.rag.models import AnswerResult, Citation


def _baseline_critic(level: str = "low") -> dict:
    """A canned critic dump shaped like a real one."""
    return {
        "kind": "rag",
        "score": {"grounded": 0.1, "actionable": 0.1, "safe": 0.1},
        "confidence": 0.1 if level == "low" else 0.7,
        "level": level,
        "notes": "tiny test critic",
        "is_mock": False,
        "parse_error": None,
    }


# ---------------------------------------------------------------- RAG path


def test_safety_intervened_takes_precedence_over_low_confidence():
    """If toxic_food guardrail fired, the user must see the red guardrail
    banner — NOT a "low confidence — show answer in expander" UI. The model
    field that drives this in app.py is `safety_intervened` / `input_blocked`.
    """
    result = AnswerResult(
        text="⚠ This food is dangerous — please consult a vet.",
        sources=[Citation(n=1, source_path="kb/toxic.md", heading="grapes",
                          snippet="kidneys")],
        safety_intervened=True,
        critic=_baseline_critic("low"),
        confidence=0.1,
    )
    # The UI rule (app._render_answer): when safety_intervened is True,
    # the badge is suppressed (set to None) regardless of critic level.
    guardrail_active = result.input_blocked or result.safety_intervened
    assert guardrail_active is True
    # Critic data is still present on the model so eval / logs can use it.
    assert result.critic is not None
    assert result.critic["level"] == "low"


def test_input_blocked_takes_precedence_over_critic():
    result = AnswerResult(
        text="I can only answer pet-care questions.",
        input_blocked=True,
        block_reason="off_topic",
        critic=_baseline_critic("low"),
    )
    guardrail_active = result.input_blocked or result.safety_intervened
    assert guardrail_active is True


def test_normal_answer_uses_critic_level():
    result = AnswerResult(
        text="Adult dogs eat twice daily [source 1].",
        sources=[Citation(n=1, source_path="kb/dog.md", heading="feeding",
                          snippet="...")],
        critic=_baseline_critic("medium"),
        confidence=0.7,
    )
    guardrail_active = result.input_blocked or result.safety_intervened
    assert guardrail_active is False
    # Critic level is the signal the UI badge uses.
    assert result.critic["level"] == "medium"


# ---------------------------------------------------------------- bias warnings


def test_bias_warnings_are_independent_of_critic():
    """Bias warnings and critic confidence are orthogonal: a high-confidence
    answer can still trigger a bias banner if retrieval was zero or thin.
    """
    result = AnswerResult(
        text="Feed your rabbit hay.",
        critic=_baseline_critic("high"),
        confidence=0.9,
        bias_warnings=[
            {
                "kind": "zero_retrieval",
                "message": "no rabbit-specific knowledge",
                "meta": {"retrieval_count": 0},
            }
        ],
    )
    # UI invariant: render bias warnings regardless of critic level.
    assert result.bias_warnings
    assert result.critic["level"] == "high"


# ---------------------------------------------------------------- plan path


def test_plan_low_confidence_does_not_collapse_table_data():
    """Plan critic-low should render a red banner but the diff table data
    must remain available on PlanResult.added_tasks. We assert the data
    survives, so the UI can trust the model and never need to "rebuild" the
    table from logs.
    """
    from pawpal.agent.models import PlanResult

    result = PlanResult(
        run_id="r1",
        goal="set up routine",
        status="preview",
        added_tasks=[
            {"pet_name": "Rex", "description": "walk", "time": "08:00",
             "frequency": "daily", "due_date": "2026-04-30"}
        ],
        critic={
            "kind": "plan",
            "score": {"complete": 0.3, "specific": 0.3, "safe": 0.3},
            "confidence": 0.3,
            "level": "low",
            "notes": "concerning",
            "is_mock": False,
        },
    )
    # The critic flagged this plan as low — but added_tasks is still available
    # for the user to inspect before Apply / Discard.
    assert result.critic["level"] == "low"
    assert len(result.added_tasks) == 1
    assert result.status == "preview"

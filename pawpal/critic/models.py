"""Pydantic models for the self-critique layer.

A `CriticReport` is the JSON-serialisable artefact written into both
`logs/rag_trace.jsonl` (under the `critic` key) and `AnswerResult.critic` /
`PlanResult.critic`. Two independent score shapes — one per artefact kind —
keep the prompt asking for axes that actually make sense for that artefact:

    RAG answer  → grounded / actionable / safe
    Agent plan  → complete / specific  / safe

The aggregation step lives in `pawpal.critic.confidence`; here we just
constrain the wire format.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


CriticKind = Literal["rag", "plan"]
CriticLevel = Literal["high", "medium", "low"]


# --------------------------------------------------------------------- scores


class _ScoreBase(BaseModel):
    """Shared validators / clamping for any 3-axis score."""

    notes: str = ""

    @staticmethod
    def _clamp(v: float) -> float:
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        if v != v:  # NaN guard
            return 0.0
        return max(0.0, min(1.0, v))


class CriticScoreRAG(_ScoreBase):
    """Three axes for a RAG answer."""

    grounded: float = 0.0
    actionable: float = 0.0
    safe: float = 0.0
    found_citations: List[int] = Field(default_factory=list)

    @field_validator("grounded", "actionable", "safe", mode="before")
    @classmethod
    def _v(cls, v: Any) -> float:
        return cls._clamp(v)


class CriticScorePlan(_ScoreBase):
    """Three axes for an Agent plan."""

    complete: float = 0.0
    specific: float = 0.0
    safe: float = 0.0

    @field_validator("complete", "specific", "safe", mode="before")
    @classmethod
    def _v(cls, v: Any) -> float:
        return cls._clamp(v)


# --------------------------------------------------------------------- report


class CriticReport(BaseModel):
    """Top-level critic artefact, written to logs and surfaced to the UI."""

    kind: CriticKind
    score: Dict[str, Any]  # CriticScoreRAG.model_dump() OR CriticScorePlan.model_dump()
    confidence: float = 0.0
    level: CriticLevel = "low"
    notes: str = ""
    parse_error: Optional[str] = None  # set if the LLM reply couldn't be parsed
    is_mock: bool = False  # True iff produced by the mock-mode fallback

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence_clamp(cls, v: Any) -> float:
        return _ScoreBase._clamp(v)

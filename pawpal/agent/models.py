"""Pydantic data models exchanged between planner / executor / UI / log.

The shapes are deliberately small and JSON-friendly. Anything we'd want to
inspect in `logs/agent_trace.jsonl` is on these models, so the trace writer
can dump them via ``model.model_dump()`` without bespoke serialisation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# Planner emits one step per tool call it wants the executor to perform.
class PlanStep(BaseModel):
    tool: str  # must be one of pawpal.tools.TOOL_NAMES
    args: Dict[str, Any] = Field(default_factory=dict)
    rationale: Optional[str] = None  # short LLM-supplied "why" string (for trace)


class Plan(BaseModel):
    """A complete LLM-emitted plan: ordered list of tool calls."""

    version: int = 1
    goal: str
    steps: List[PlanStep] = Field(default_factory=list)
    summary: Optional[str] = None  # optional natural-language summary

    def is_empty(self) -> bool:
        return len(self.steps) == 0


class StepTrace(BaseModel):
    """One row in the execution trace: which step, with what outcome."""

    plan_version: int
    step_index: int
    tool: str
    args: Dict[str, Any]
    ok: bool
    error: Optional[str] = None
    requires_replan: bool = False
    data: Any = None  # tool's return data; small enough to keep inline
    meta: Dict[str, Any] = Field(default_factory=dict)


PlanStatus = Literal[
    "preview",       # plan generated, awaiting user Apply/Discard
    "applied",       # user accepted; merged into live owner
    "rejected",      # user discarded
    "exhausted",     # MAX_REPLANS hit without a clean plan
    "blocked",       # planner couldn't even produce a parseable plan
    "empty",         # planner returned a plan with zero steps
]


class PlanResult(BaseModel):
    """End-to-end output of one ``executor.run`` call."""

    run_id: str
    goal: str
    pet_name: Optional[str] = None
    status: PlanStatus = "preview"
    plan_versions: List[Plan] = Field(default_factory=list)
    trace: List[StepTrace] = Field(default_factory=list)
    added_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    block_reason: Optional[str] = None
    duration_ms: int = 0
    tokens_prompt: int = 0
    tokens_completion: int = 0
    # Phase 3 will populate this; kept on the model so the JSONL schema is stable.
    critic: Optional[Dict[str, Any]] = None

    @property
    def latest_plan(self) -> Optional[Plan]:
        return self.plan_versions[-1] if self.plan_versions else None

    @property
    def replans(self) -> int:
        # Plan v1 is the initial draft; each later version is one re-plan.
        return max(0, len(self.plan_versions) - 1)


class PlanParseError(ValueError):
    """Raised when the LLM's reply can't be parsed into a `Plan`."""

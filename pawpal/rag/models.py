"""Pydantic models shared across the RAG pipeline.

Centralised here so the type contract between `index` / `retrieve` / `qa`
and the Streamlit UI does not drift over time.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """One slice of a knowledge-base markdown file."""

    text: str
    source_path: str
    species: str
    topic: str
    heading: Optional[str] = None
    score: float = 0.0


class Citation(BaseModel):
    """A reference shown to the user under an answer."""

    n: int
    source_path: str
    heading: Optional[str] = None
    snippet: str


class AnswerResult(BaseModel):
    """End-to-end output of `rag.qa.answer`. Streamlit reads this directly."""

    text: str
    sources: List[Citation] = Field(default_factory=list)
    safety_intervened: bool = False
    no_retrieval: bool = False
    out_of_scope: bool = False
    input_blocked: bool = False
    block_reason: Optional[str] = None
    retrieved_chunks: List[Chunk] = Field(default_factory=list)
    duration_ms: int = 0
    model: Optional[str] = None
    confidence: Optional[float] = None  # Phase 3: aggregated 0..1 from critic
    critic: Optional[Dict[str, Any]] = None  # Phase 3: CriticReport.model_dump()
    bias_warnings: List[Dict[str, Any]] = Field(default_factory=list)  # Phase 3

"""Run-time bias detector for RAG answers (Phase 3 §4).

The eval harness in `eval/run_eval.py --section bias` measures parity across
species **offline**. This module is the **runtime** counterpart: every time
`pawpal.rag.qa.answer` produces an answer, we scan it for cheap heuristics
that flag obvious under-coverage of small / less-common species (hamster,
rabbit, bird, reptile) and surface a yellow banner in the UI.

Scope (per Phase 3 plan §3.7):
- detect "zero retrieval" cases (already separately reported via
  `AnswerResult.no_retrieval`, but we still emit a warning to keep the UI
  layer simple);
- detect "possibly underspecified" answers for small species when the answer
  is suspiciously short;
- never modify the answer text — UI only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional


# Species the knowledge base coverage is known to be thinner for. Update as
# the KB grows.
UNDERREPRESENTED_SPECIES = {"hamster", "rabbit", "bird", "reptile", "fish", "guinea_pig"}

# Minimum char count below which a small-species answer is flagged. Calibrated
# against `eval/golden_qa.jsonl` baseline answers; tweak if the KB grows.
SHORT_ANSWER_THRESHOLD = 200


@dataclass
class BiasWarning:
    """One UI-renderable warning."""

    kind: str  # "zero_retrieval" | "possibly_underspecified"
    message: str
    meta: dict = field(default_factory=dict)


def _norm_species(species: Optional[str]) -> str:
    return (species or "").strip().lower()


def scan_answer(
    answer: str,
    *,
    species: Optional[str],
    retrieved_chunks: Optional[Iterable[Any]] = None,
) -> List[BiasWarning]:
    """Scan an answer for likely cross-species bias signals.

    Parameters
    ----------
    answer:
        The (already guardrail-rewritten) answer text.
    species:
        Pet species the question was framed for. ``None`` is allowed and
        skips species-specific checks.
    retrieved_chunks:
        Iterable of `Chunk`-like objects (anything with a truthy ``len``).
        Pass ``[]`` or ``None`` to flag a zero-retrieval case.
    """
    warnings: List[BiasWarning] = []
    spec = _norm_species(species)
    chunks_list = list(retrieved_chunks or [])

    if not chunks_list:
        warnings.append(
            BiasWarning(
                kind="zero_retrieval",
                message=(
                    f"No species-specific knowledge was found"
                    f"{f' for {spec}' if spec else ''}. "
                    "The answer is generic — please cross-check with a specialist."
                ),
                meta={"species": spec, "retrieval_count": 0},
            )
        )
        # If retrieval was empty there's no point measuring length parity,
        # but we still return so the UI can choose what to render.
        return warnings

    if (
        spec in UNDERREPRESENTED_SPECIES
        and len(answer or "") < SHORT_ANSWER_THRESHOLD
    ):
        warnings.append(
            BiasWarning(
                kind="possibly_underspecified",
                message=(
                    f"This answer for {spec} is shorter than typical answers for "
                    "common species. Coverage of small pets is still expanding — "
                    "verify with a specialist before acting."
                ),
                meta={
                    "species": spec,
                    "answer_chars": len(answer or ""),
                    "threshold": SHORT_ANSWER_THRESHOLD,
                    "retrieval_count": len(chunks_list),
                },
            )
        )

    return warnings


def warnings_to_dicts(warnings: Iterable[BiasWarning]) -> List[dict]:
    """Helper for log/UI serialisation."""
    return [
        {"kind": w.kind, "message": w.message, "meta": dict(w.meta)}
        for w in warnings
    ]

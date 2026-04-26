"""Retrieval-Augmented Generation pipeline for PawPal.

Three sub-modules:
    - `index`    — build the vector store from `knowledge/*.md`.
    - `retrieve` — find the top-k chunks for a query, with optional species filter.
    - `qa`       — end-to-end answer pipeline with guardrails and logging.
"""

from pawpal.rag.models import Chunk, Citation, AnswerResult  # noqa: F401

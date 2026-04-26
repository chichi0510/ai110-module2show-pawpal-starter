"""Retrieve top-k knowledge chunks for a query.

Implements the species filter described in `docs/design/open_questions.md`
Q5: when `species` is None we fall back to the `general` partition only;
when `species` is given we union it with `general` so universal principles
still surface.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import chromadb

from pawpal.llm_client import LLMClient
from pawpal.rag.index import CHROMA_DIR, COLLECTION
from pawpal.rag.models import Chunk

DEFAULT_K = 4

_client_cache: Optional[chromadb.api.ClientAPI] = None
_collection_cache = None
_llm_cache: Optional[LLMClient] = None


def _client() -> chromadb.api.ClientAPI:
    global _client_cache
    if _client_cache is None:
        if not Path(CHROMA_DIR).exists():
            raise RuntimeError(
                f"Chroma index not found at {CHROMA_DIR}. "
                "Run `python -m rag.index --rebuild` first."
            )
        _client_cache = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client_cache


def _collection():
    global _collection_cache
    if _collection_cache is None:
        _collection_cache = _client().get_collection(COLLECTION)
    return _collection_cache


def _llm(mock: bool) -> LLMClient:
    global _llm_cache
    if _llm_cache is None or _llm_cache.mock != mock:
        _llm_cache = LLMClient(mock=mock)
    return _llm_cache


def reset_cache() -> None:
    """Drop cached Chroma client (used after reindex)."""
    global _client_cache, _collection_cache, _llm_cache
    _client_cache = None
    _collection_cache = None
    _llm_cache = None


def _build_where(species: Optional[str]) -> dict:
    if species is None:
        return {"species": "general"}
    species = species.lower().strip()
    return {"species": {"$in": [species, "general"]}}


def retrieve(
    query: str,
    *,
    species: Optional[str] = None,
    k: int = DEFAULT_K,
    mock: bool = False,
) -> List[Chunk]:
    """Return up to ``k`` chunks most similar to ``query``.

    Score is converted from Chroma's cosine *distance* into a 0..1 similarity
    so callers can apply a single threshold (see `rag.qa.RELEVANCE_THRESHOLD`).
    """
    if not query or not query.strip():
        return []

    [embedding] = _llm(mock).embed([query])
    where = _build_where(species)

    res = _collection().query(
        query_embeddings=[embedding],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    chunks: List[Chunk] = []
    for doc, meta, dist in zip(docs, metas, dists):
        meta = meta or {}
        similarity = max(0.0, 1.0 - float(dist))
        chunks.append(
            Chunk(
                text=doc,
                source_path=str(meta.get("source_path", "?")),
                species=str(meta.get("species", "general")),
                topic=str(meta.get("topic", "general")),
                heading=(meta.get("heading") or None),
                score=similarity,
            )
        )
    return chunks

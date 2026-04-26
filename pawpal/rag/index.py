"""Build the ChromaDB vector index from the `knowledge/` markdown corpus.

Usage:
    python -m rag.index --rebuild

What it does:
1. Walks `knowledge/**/*.md`.
2. Parses each file's YAML frontmatter for metadata (species, topic, source).
3. Splits the body by H2/H3 headings (with a fallback length cap).
4. Calls `LLMClient.embed` on each chunk.
5. Replaces the `pawpal_kb` collection in ChromaDB with the new chunks.
6. Writes `chroma_db/.indexed_at` so the Streamlit app can warn when the KB
   is newer than the index (see Q2 in `docs/design/open_questions.md`).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import chromadb

from pawpal.llm_client import LLMClient

ROOT = Path(__file__).resolve().parent.parent.parent
KB_DIR = ROOT / "knowledge"
CHROMA_DIR = ROOT / "chroma_db"
COLLECTION = "pawpal_kb"
MARKER_FILE = CHROMA_DIR / ".indexed_at"

MAX_CHARS_PER_CHUNK = 1800   # ~ 800 tokens for English prose
MIN_CHARS_PER_CHUNK = 80     # drop near-empty fragments


# ----------------------------------------------------------------- parsing


@dataclass
class _Frontmatter:
    species: str = "general"
    topic: str = "general"
    source: str = ""
    source_url: str = ""
    last_reviewed: str = ""


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(raw: str) -> Tuple[_Frontmatter, str]:
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return _Frontmatter(), raw
    body = raw[match.end():]
    fm = _Frontmatter()
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip().strip("'").strip('"')
        if hasattr(fm, key):
            setattr(fm, key, val)
    return fm, body


_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)


def _split_by_heading(body: str) -> List[Tuple[Optional[str], str]]:
    """Split markdown body by H2/H3 headings; first segment may have no heading."""
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return [(None, body.strip())]
    out: List[Tuple[Optional[str], str]] = []
    if matches[0].start() > 0:
        intro = body[: matches[0].start()].strip()
        if intro:
            out.append((None, intro))
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section = body[start:end].strip()
        if section:
            out.append((heading, section))
    return out


def _bound_length(heading: Optional[str], section: str) -> Iterable[Tuple[Optional[str], str]]:
    if len(section) <= MAX_CHARS_PER_CHUNK:
        yield heading, section
        return
    paragraphs = section.split("\n\n")
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 > MAX_CHARS_PER_CHUNK and buf:
            yield heading, buf.strip()
            buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf:
        yield heading, buf.strip()


# ----------------------------------------------------------------- pipeline


@dataclass
class _IndexedChunk:
    chunk_id: str
    text: str
    metadata: dict


def _walk_kb() -> List[_IndexedChunk]:
    chunks: List[_IndexedChunk] = []
    md_files = sorted(KB_DIR.rglob("*.md"))
    for path in md_files:
        raw = path.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(raw)
        rel = path.relative_to(ROOT).as_posix()
        for heading, section in _split_by_heading(body):
            for h, text in _bound_length(heading, section):
                if len(text) < MIN_CHARS_PER_CHUNK:
                    continue
                chunk_id = f"{rel}::{(h or 'intro')}::{len(chunks)}"
                chunks.append(
                    _IndexedChunk(
                        chunk_id=chunk_id,
                        text=text,
                        metadata={
                            "source_path": rel,
                            "species": fm.species or "general",
                            "topic": fm.topic or "general",
                            "heading": h or "",
                            "source": fm.source,
                            "source_url": fm.source_url,
                        },
                    )
                )
    return chunks


def _get_collection(client: chromadb.api.ClientAPI):
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    return client.create_collection(name=COLLECTION, metadata={"hnsw:space": "cosine"})


def build_index(*, mock: bool = False, verbose: bool = True) -> int:
    """Rebuild the index from scratch. Returns the number of chunks written."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    chunks = _walk_kb()
    if not chunks:
        if verbose:
            print("No knowledge files found under", KB_DIR, file=sys.stderr)
        return 0

    if verbose:
        print(f"Found {len(chunks)} chunks across {len({c.metadata['source_path'] for c in chunks})} files.")

    llm = LLMClient(mock=mock)
    embeddings = llm.embed([c.text for c in chunks])

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    coll = _get_collection(client)
    coll.add(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[c.metadata for c in chunks],
        embeddings=embeddings,
    )

    MARKER_FILE.write_text(str(int(time.time())), encoding="utf-8")
    if verbose:
        print(f"Wrote {len(chunks)} chunks to ChromaDB at {CHROMA_DIR}")
    return len(chunks)


def index_age_seconds() -> Optional[float]:
    """Return seconds since the index was last built, or None if no marker."""
    if not MARKER_FILE.exists():
        return None
    try:
        ts = int(MARKER_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
    return max(0.0, time.time() - ts)


def kb_modified_after_index() -> bool:
    """True if any knowledge/*.md was modified after the last index build."""
    if not MARKER_FILE.exists():
        return True
    try:
        ts = int(MARKER_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return True
    md_files = list(KB_DIR.rglob("*.md"))
    if not md_files:
        return False
    return max(p.stat().st_mtime for p in md_files) > ts


# ----------------------------------------------------------------- CLI


def _main() -> None:
    parser = argparse.ArgumentParser(description="Build the PawPal RAG index.")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild (default action).")
    parser.add_argument("--mock", action="store_true", help="Use deterministic mock embeddings (no API call).")
    args = parser.parse_args()
    n = build_index(mock=args.mock)
    if n == 0:
        sys.exit(1)


if __name__ == "__main__":
    _main()

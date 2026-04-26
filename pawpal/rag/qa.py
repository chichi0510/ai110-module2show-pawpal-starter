"""End-to-end RAG question answering.

Pipeline (matches `docs/design/architecture.md` §3.1):
    preflight → toxic-food input check → retrieve → prompt → LLM
              → toxic-food output check → log → AnswerResult

Every call writes one structured trace line to `logs/rag_trace.jsonl` so the
UI's "show reasoning trace" panel and the offline `eval/run_eval.py` script
can reconstruct what happened.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pawpal.guardrails import input_filter, toxic_food
from pawpal.llm_client import LLMClient
from pawpal.rag.models import AnswerResult, Chunk, Citation
from pawpal.rag.retrieve import DEFAULT_K, retrieve

ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "rag_trace.jsonl"

RELEVANCE_THRESHOLD = 0.35  # see open_questions.md Q3


SYSTEM_PROMPT = """You are PawPal, a careful pet-care assistant.

Rules:
1. Use ONLY the context below. If the context does not answer the question, reply: "I don't have a verified answer for that — please consult a vet."
2. Cite each factual claim with [source N] referencing the numbered context.
3. Never recommend medication dosages. For health concerns, point to a vet.
4. If the question involves a known toxic food, ALWAYS warn first and explain why.
5. Keep the answer concise and specific to the pet's species and age."""


@dataclass
class PetContext:
    species: Optional[str] = None
    age: Optional[int] = None
    name: Optional[str] = None


# ----------------------------------------------------------------- helpers


def _format_context(chunks: List[Chunk]) -> str:
    lines = []
    for i, c in enumerate(chunks, start=1):
        head = f" — {c.heading}" if c.heading else ""
        lines.append(f"[{i}] (from {c.source_path}{head})\n{c.text}")
    return "\n\n".join(lines)


def _build_messages(query: str, pet: PetContext, chunks: List[Chunk]) -> list[dict]:
    pet_line = (
        f"Pet context: species={pet.species or 'unspecified'}, "
        f"age={pet.age if pet.age is not None else 'unspecified'}"
    )
    user = (
        f"{pet_line}\n\n"
        f"Question: {query.strip()}\n\n"
        f"Context:\n{_format_context(chunks)}\n\n"
        "Answer (with [source N] citations):"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _citations_from_chunks(chunks: List[Chunk]) -> List[Citation]:
    cites: List[Citation] = []
    for i, c in enumerate(chunks, start=1):
        snippet = c.text.strip().replace("\n", " ")
        if len(snippet) > 220:
            snippet = snippet[:217] + "..."
        cites.append(
            Citation(n=i, source_path=c.source_path, heading=c.heading, snippet=snippet)
        )
    return cites


def _write_trace(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------- public API


def answer(
    query: str,
    pet: Optional[PetContext] = None,
    *,
    k: int = DEFAULT_K,
    mock: bool = False,
    llm_client: Optional[LLMClient] = None,
) -> AnswerResult:
    """Run the full RAG pipeline and return an `AnswerResult`."""
    pet = pet or PetContext()
    started = time.perf_counter()
    run_id = str(uuid.uuid4())

    trace: dict = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": run_id,
        "query": query,
        "pet_context": {"species": pet.species, "age": pet.age, "name": pet.name},
        "preflight": {},
        "retrieved": [],
        "llm": {"model": None, "prompt_tokens": 0, "completion_tokens": 0, "skipped": False},
        "postflight": {"safety_intervened": False, "hits": []},
        "answer_chars": 0,
        "duration_ms": 0,
    }

    # 1. Preflight (off-topic / PII / diagnosis).
    pre = input_filter.preflight(query)
    trace["preflight"]["input_filter"] = {
        "allowed": pre.allowed,
        "reason": pre.reason,
    }
    if not pre.allowed:
        trace["llm"]["skipped"] = True
        result = AnswerResult(
            text=pre.safe_answer or "I can't answer that.",
            sources=[],
            out_of_scope=True,
            block_reason=pre.reason,
        )
        return _finalise(result, trace, started)

    # 2. Toxic-food input check.
    tf_in = toxic_food.check_input(query, pet.species)
    trace["preflight"]["toxic_food"] = {
        "blocked": tf_in.blocked,
        "hits": [h.entry.name for h in tf_in.hits],
    }
    if tf_in.blocked:
        trace["llm"]["skipped"] = True
        cites = [
            Citation(
                n=i + 1,
                source_path=f"knowledge/toxic_foods/{pet.species or 'general'}_toxic_list.md",
                heading=h.entry.name,
                snippet=h.entry.reason,
            )
            for i, h in enumerate(tf_in.hits)
        ]
        result = AnswerResult(
            text=tf_in.safe_answer or "Unsafe — please consult a vet.",
            sources=cites,
            input_blocked=True,
            block_reason="toxic_food",
            safety_intervened=True,
        )
        return _finalise(result, trace, started)

    # 3. Retrieve.
    chunks = retrieve(query, species=pet.species, k=k, mock=mock)
    trace["retrieved"] = [
        {"source": c.source_path, "score": round(c.score, 4), "heading": c.heading}
        for c in chunks
    ]
    if not chunks or chunks[0].score < RELEVANCE_THRESHOLD:
        trace["llm"]["skipped"] = True
        result = AnswerResult(
            text=(
                "I don't have a verified answer for that — please consult a vet "
                "or rephrase the question with more pet-care context."
            ),
            sources=[],
            no_retrieval=True,
            retrieved_chunks=chunks,
        )
        return _finalise(result, trace, started)

    # 4. Generate.
    llm = llm_client or LLMClient(mock=mock)
    messages = _build_messages(query, pet, chunks)
    chat = llm.chat(messages)
    raw_answer = chat.text.strip()

    trace["llm"].update(
        {
            "model": chat.model,
            "prompt_tokens": chat.usage.prompt_tokens,
            "completion_tokens": chat.usage.completion_tokens,
            "skipped": False,
        }
    )

    # 5. Output guardrail.
    tf_out = toxic_food.check_output(raw_answer, pet.species)
    trace["postflight"] = {
        "safety_intervened": tf_out.safety_intervened,
        "hits": [h.entry.name for h in tf_out.hits],
    }

    # 6. Build the AnswerResult.
    result = AnswerResult(
        text=tf_out.rewritten,
        sources=_citations_from_chunks(chunks),
        safety_intervened=tf_out.safety_intervened,
        retrieved_chunks=chunks,
        model=chat.model,
    )
    return _finalise(result, trace, started)


def _finalise(result: AnswerResult, trace: dict, started: float) -> AnswerResult:
    duration_ms = int((time.perf_counter() - started) * 1000)
    result.duration_ms = duration_ms
    trace["answer_chars"] = len(result.text)
    trace["duration_ms"] = duration_ms
    trace["exit"] = {
        "out_of_scope": result.out_of_scope,
        "input_blocked": result.input_blocked,
        "no_retrieval": result.no_retrieval,
        "safety_intervened": result.safety_intervened,
    }
    _write_trace(trace)
    return result


# ----------------------------------------------------------------- CLI

_CITE_RE = re.compile(r"\[source\s+\d+\]", re.IGNORECASE)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Ask PawPal a question (RAG).")
    parser.add_argument("query", type=str, help="Question to answer.")
    parser.add_argument("--species", type=str, default=None, help="dog | cat | ...")
    parser.add_argument("--age", type=int, default=None)
    parser.add_argument("--mock", action="store_true", help="Use mock LLM (no API).")
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    args = parser.parse_args()

    pet = PetContext(species=args.species, age=args.age)
    result = answer(args.query, pet, k=args.k, mock=args.mock)

    print("\n=== Answer ===")
    print(result.text)
    if result.sources:
        print("\n=== Sources ===")
        for c in result.sources:
            head = f" — {c.heading}" if c.heading else ""
            print(f"  [{c.n}] {c.source_path}{head}")
    print(
        f"\nDuration: {result.duration_ms} ms · "
        f"safety_intervened={result.safety_intervened} · "
        f"no_retrieval={result.no_retrieval} · "
        f"input_blocked={result.input_blocked}"
    )


if __name__ == "__main__":
    _main()

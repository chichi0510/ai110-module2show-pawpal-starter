"""Offline evaluation runner for Phase 1 RAG.

Reads `eval/golden_qa.jsonl`, runs each row through `rag.qa.answer`, and
prints a per-category report plus a JSON results file under
`eval/reports/`.

Usage:
    python -m eval.run_eval                # run with the real LLM
    python -m eval.run_eval --mock         # use mock client (for CI/dev)
    python -m eval.run_eval --limit 5      # smoke run

Phase 3 will extend this with confidence calibration; Phase 2 with planning
goals; Phase 4 ties it all together with red-team and bias suites.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `python eval/run_eval.py` also works

from pawpal.rag.qa import PetContext, answer  # noqa: E402

GOLDEN_PATH = ROOT / "eval" / "golden_qa.jsonl"
REPORTS_DIR = ROOT / "eval" / "reports"


@dataclass
class CaseResult:
    id: str
    category: str
    query: str
    passed: bool
    keyword_hit_rate: float
    expected_keywords: List[str]
    answer_excerpt: str
    expect_block: bool
    got_block: bool
    expect_safety: bool
    got_safety: bool
    duration_ms: int
    failures: List[str] = field(default_factory=list)


@dataclass
class CategorySummary:
    name: str
    n: int
    passed: int

    @property
    def rate(self) -> float:
        return self.passed / self.n if self.n else 0.0


@dataclass
class EvalReport:
    started: str
    n_cases: int
    n_passed: int
    overall_pass_rate: float
    by_category: Dict[str, Dict[str, Any]]
    cases: List[Dict[str, Any]]
    mock: bool


def _load_cases(limit: Optional[int]) -> List[dict]:
    rows: List[dict] = []
    with GOLDEN_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    if limit:
        rows = rows[:limit]
    return rows


def _keyword_hit_rate(answer_text: str, keywords: List[str]) -> float:
    if not keywords:
        return 1.0
    hay = answer_text.lower()
    hits = sum(1 for k in keywords if k.lower() in hay)
    return hits / len(keywords)


def _evaluate_one(case: dict, *, mock: bool) -> CaseResult:
    pet = PetContext(
        species=case.get("species"),
        age=case.get("age") if case.get("age") is not None else None,
    )
    query: str = case["query"]
    expect_block: bool = bool(case.get("expect_block"))
    expect_safety: bool = bool(case.get("expect_safety"))
    expect_keywords: List[str] = list(case.get("expect_keywords", []))
    expect_citation: bool = bool(case.get("expect_citation"))

    started = time.perf_counter()
    result = answer(query, pet, mock=mock)
    duration_ms = int((time.perf_counter() - started) * 1000)

    got_block = result.input_blocked or result.out_of_scope or result.no_retrieval
    got_safety = result.safety_intervened or result.input_blocked

    failures: List[str] = []

    if expect_block and not got_block:
        failures.append("expected the system to block/short-circuit but it answered")
    if not expect_block and got_block:
        failures.append("expected a normal answer but the system short-circuited")

    if expect_safety and not got_safety:
        failures.append("expected a safety intervention but none happened")

    rate = _keyword_hit_rate(result.text, expect_keywords)
    if expect_keywords and rate < 0.5:
        failures.append(
            f"keyword hit rate {rate:.2f} < 0.5 for {expect_keywords}"
        )

    if expect_citation and not result.sources and not got_block:
        failures.append("expected at least one citation but got none")

    excerpt = re.sub(r"\s+", " ", result.text).strip()
    if len(excerpt) > 240:
        excerpt = excerpt[:237] + "..."

    return CaseResult(
        id=case.get("id", "?"),
        category=case.get("category", "uncategorised"),
        query=query,
        passed=not failures,
        keyword_hit_rate=rate,
        expected_keywords=expect_keywords,
        answer_excerpt=excerpt,
        expect_block=expect_block,
        got_block=got_block,
        expect_safety=expect_safety,
        got_safety=got_safety,
        duration_ms=duration_ms,
        failures=failures,
    )


def _summarise(cases: List[CaseResult]) -> Dict[str, CategorySummary]:
    out: Dict[str, CategorySummary] = {}
    for c in cases:
        s = out.setdefault(c.category, CategorySummary(c.category, 0, 0))
        s.n += 1
        if c.passed:
            s.passed += 1
    return out


def run(*, mock: bool, limit: Optional[int]) -> EvalReport:
    cases = _load_cases(limit)
    started_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Running {len(cases)} eval cases (mock={mock})...\n")
    results: List[CaseResult] = []
    for i, case in enumerate(cases, start=1):
        r = _evaluate_one(case, mock=mock)
        results.append(r)
        flag = "PASS" if r.passed else "FAIL"
        print(f"[{i:>2}/{len(cases)}] {flag}  {r.category:<12} {r.id}")
        if not r.passed:
            for f in r.failures:
                print(f"        · {f}")

    summary = _summarise(results)
    n_pass = sum(1 for r in results if r.passed)

    print("\n=== By category ===")
    for name, s in sorted(summary.items()):
        print(f"  {name:<12}  {s.passed:>2}/{s.n:<2}  ({s.rate*100:>5.1f}%)")

    print("\n=== Overall ===")
    print(f"  passed: {n_pass}/{len(results)}  ({(n_pass/len(results)*100 if results else 0):.1f}%)")

    report = EvalReport(
        started=started_iso,
        n_cases=len(results),
        n_passed=n_pass,
        overall_pass_rate=(n_pass / len(results) if results else 0.0),
        by_category={k: {"n": v.n, "passed": v.passed, "rate": v.rate} for k, v in summary.items()},
        cases=[asdict(c) for c in results],
        mock=mock,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"phase1_{int(time.time())}.json"
    out_path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport written to {out_path.relative_to(ROOT)}")
    return report


def _main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 1 RAG eval suite.")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM (no API call).")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    report = run(mock=args.mock, limit=args.limit)
    if report.overall_pass_rate < 0.7 and not args.mock:
        sys.exit(1)


if __name__ == "__main__":
    _main()

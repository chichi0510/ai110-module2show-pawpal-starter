"""Prompt templates for the agent loop.

The planner asks the LLM for a STRICT JSON ``{"steps":[...]}`` document so
that we can parse it without the OpenAI function-calling SDK. Each step
references one tool from `pawpal.tools.TOOLS_SCHEMA` by name plus its args.

Why JSON-mode instead of native function-calling?
- It's portable across providers and trivially mockable in tests.
- Our planner is "produce one full plan, then execute" rather than
  "ReAct one step at a time". A single JSON blob fits that perfectly.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pawpal.tools import TOOLS_SCHEMA


PLANNER_SYSTEM = """You are PawPal Planner, an assistant that turns a pet-care goal \
into a concrete multi-step plan.

You MUST output ONLY a JSON object with this exact shape:

{
  "summary": "<one short sentence describing the plan>",
  "steps": [
    {"tool": "<tool name>", "args": { ... }, "rationale": "<short why>"},
    ...
  ]
}

Rules:
1. Use ONLY the tools listed under "Available tools" below. Never invent tool names.
2. For multi-day routines (a "first week", a daily plan, etc.), output AT LEAST 5 \
   add_task steps covering different aspects (feeding, exercise, rest, vet/vaccines).
3. Times must be "HH:MM" (24h, 00:00..23:59). Use spaced clock times to avoid clashes \
   (e.g. 08:00, 12:00, 18:00 — not all at 09:00).
4. Frequencies must be exactly "once", "daily", or "weekly".
5. NEVER schedule a task whose description names food or substances toxic to that \
   pet's species (chocolate, grapes, onion, xylitol, lily, etc.). The system will \
   refuse and force a re-plan.
6. If you are unsure about a fact (vaccine timing, feeding frequency for a young pet), \
   put a `rag_lookup` step BEFORE the relevant `add_task` steps.
7. Prefer specificity to species + age in the description ("Puppy small-meal #1 \
   (3-month diet)" beats "Feed dog").
8. Keep "rationale" short (≤ 20 words).
9. Do not include any prose before or after the JSON. Output raw JSON only."""


REPLAN_SUFFIX_HEADER = (
    "Your previous plan failed during execution. Here is the trace of what happened. "
    "Produce a NEW complete plan that avoids the failures. "
    "If a step was blocked because of a toxic-food, REMOVE the offending item entirely "
    "(do not just rephrase). If a step hit a time conflict, pick a different time."
)


def _format_tools_for_prompt(tools_schema: List[Dict[str, Any]]) -> str:
    lines: List[str] = ["Available tools:"]
    for t in tools_schema:
        params = t["parameters"].get("properties", {})
        required = t["parameters"].get("required", [])
        param_lines = []
        for name, spec in params.items():
            mark = "*" if name in required else " "
            type_label = spec.get("type", "any")
            extra = ""
            if "enum" in spec:
                extra = f" enum={spec['enum']}"
            elif "format" in spec:
                extra = f" format={spec['format']}"
            param_lines.append(f"      {mark} {name}: {type_label}{extra}")
        params_block = "\n".join(param_lines) if param_lines else "      (no arguments)"
        lines.append(f"- {t['name']}: {t['description']}\n    args:\n{params_block}")
    return "\n".join(lines)


TOOLS_BLOCK = _format_tools_for_prompt(TOOLS_SCHEMA)


def build_planner_messages(
    *,
    goal: str,
    pets: List[Dict[str, Any]],
    today_iso: str,
    prev_trace_summary: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Assemble the chat messages for the planner LLM call."""
    user_lines = [
        f"Today: {today_iso}",
        f"Owner has {len(pets)} pet(s):",
    ]
    for p in pets:
        user_lines.append(
            f"  - {p.get('name')} ({p.get('species')}, age {p.get('age')})"
        )
    user_lines.append("")
    user_lines.append(f"Goal: {goal}")
    user_lines.append("")
    user_lines.append(TOOLS_BLOCK)

    if prev_trace_summary:
        user_lines.append("")
        user_lines.append(REPLAN_SUFFIX_HEADER)
        user_lines.append("")
        user_lines.append("Previous trace:")
        user_lines.append(prev_trace_summary)

    return [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": "\n".join(user_lines)},
    ]


def summarise_trace_for_replan(trace_rows: List[Dict[str, Any]], max_rows: int = 10) -> str:
    """Compact textual summary of a failed trace, fed back to the planner.

    Truncated to ``max_rows`` to keep token usage bounded across re-plans.
    """
    rows = trace_rows[-max_rows:]
    lines: List[str] = []
    for r in rows:
        status = "OK" if r.get("ok") else "FAIL"
        err = f" — {r.get('error')}" if r.get("error") else ""
        args_short = json.dumps(r.get("args", {}), ensure_ascii=False)[:120]
        lines.append(
            f"  step {r.get('step_index')} [{r.get('tool')}] {status}: "
            f"args={args_short}{err}"
        )
    return "\n".join(lines)

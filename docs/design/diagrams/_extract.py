"""One-shot helper: pull every ```mermaid block out of architecture.md
and save each to a named .mmd file so we can hand them to mmdc.

Usage:
    python docs/design/diagrams/_extract.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "design" / "architecture.md"
OUT = ROOT / "design" / "diagrams"

# Order must match the mermaid blocks as they appear top-to-bottom in
# architecture.md. Update this list if you add/remove a diagram.
NAMES = [
    "system_overview",          # §1   high-level component diagram
    "flow_rag",                 # §3.1 RAG sequence
    "flow_agent",               # §3.2 Agent sequence (Plan-Execute-Critique)
    "flow_eval",                # §3.3 offline eval pipeline
    "state_layers",             # §4.1 state ownership layers
    "testing_checkpoints",      # §5   where humans / tests verify AI output
]

BLOCK = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    blocks = BLOCK.findall(text)
    if len(blocks) != len(NAMES):
        raise SystemExit(
            f"Expected {len(NAMES)} mermaid blocks in {SRC}, found {len(blocks)}.\n"
            "Update NAMES in this script to match."
        )
    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in zip(NAMES, blocks):
        path = OUT / f"{name}.mmd"
        path.write_text(body.rstrip() + "\n", encoding="utf-8")
        print(f"  wrote {path.relative_to(ROOT.parent)} ({len(body.splitlines())} lines)")


if __name__ == "__main__":
    main()

# Architecture Diagrams (PNG mirror)

These PNGs are static mirrors of the `mermaid` blocks in
[`../architecture.md`](../architecture.md), checked into git so reviewers can
see the diagrams in any markdown viewer (including ones that do not render
mermaid).

| File                       | Source section in `architecture.md`         |
|----------------------------|---------------------------------------------|
| `system_overview.png`      | §1 System at a glance (high-level component diagram) |
| `flow_rag.png`             | §3.1 RAG knowledge Q&A ("Ask PawPal")        |
| `flow_agent.png`           | §3.2 Agentic multi-step planning ("Plan My Week") |
| `flow_eval.png`            | §3.3 Evaluation flow (offline)               |
| `state_layers.png`         | §4.1 State layers                            |
| `testing_checkpoints.png`  | §5 Where humans / tests verify AI output     |
| `calibration.png`          | (generated) ROC curve from `python -m eval.run_eval --section calibration` — Phase 4 §4.1 |

## Regenerating

The PNGs were rendered with [`@mermaid-js/mermaid-cli`](https://github.com/mermaid-js/mermaid-cli)
(`mmdc`). You only need this if you edited `architecture.md` and want to refresh
the mirrors — **mmdc is intentionally NOT in `requirements.txt`** since most
contributors will never touch it.

```bash
# one-time install (requires Node.js)
npm install -g @mermaid-js/mermaid-cli

# extract the mermaid blocks to .mmd files (idempotent, regenerates from
# architecture.md so this script stays in sync)
python docs/design/diagrams/_extract.py

# render every .mmd in this folder to a same-name PNG, transparent bg, 1600px wide
cd docs/design/diagrams
for f in *.mmd; do
  mmdc -i "$f" -o "${f%.mmd}.png" -w 1600 -b transparent
done
```

If you don't have Node.js, an alternative is to paste each `.mmd` file into
<https://mermaid.live> and download the PNG.

## Why these are committed

Mermaid renders inside GitHub's web UI but **not** in:
- many offline markdown viewers (VSCode preview without an extension, Cursor,
  most IDE previews)
- most static-site generators by default
- PDFs exported via Pandoc

`docs/design/architecture.md` therefore links to both the mermaid block (live)
and the PNG mirror (always works).

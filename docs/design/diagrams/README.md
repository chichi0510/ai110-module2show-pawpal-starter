# Architecture Diagrams (PNG mirror)

These PNGs are static mirrors of the `mermaid` blocks in
[`../architecture.md`](../architecture.md), checked into git so reviewers can
see the diagrams in any markdown viewer (including ones that do not render
mermaid).

| File                       | Source section in `architecture.md`         |
|----------------------------|---------------------------------------------|
| `system_overview.png`      | §1 一图看懂整个系统（高层组件图）           |
| `flow_rag.png`             | §3.1 RAG 知识问答（"Ask PawPal"）           |
| `flow_agent.png`           | §3.2 Agentic 多步规划（"Plan My Week"）     |
| `flow_eval.png`            | §3.3 评估流（offline）                       |
| `state_layers.png`         | §4.1 状态分层                                |
| `testing_checkpoints.png`  | §5 人 / 测试在哪里检查 AI 结果              |
| `calibration.png`          | (生成) `python -m eval.run_eval --section calibration` 的 ROC 曲线 — Phase 4 §4.1 |

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

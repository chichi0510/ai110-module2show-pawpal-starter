# `assets/` — diagrams and demo screenshots

This folder is the canonical place to find every diagram and screenshot
referenced from the project README, in line with the Module 4
submission rubric ("system diagram and any demo screenshots should be
stored in a dedicated `/assets` or `/diagrams` folder").

| File | What it is |
|---|---|
| `diagrams/system_overview.png` | Full system architecture (UI / scheduler core / AI services ring) — embedded at the top of `README.md`. |
| `diagrams/flow_rag.png` | RAG request flow: preflight → retrieve → LLM → post-flight → critic → bias filter → log. |
| `diagrams/flow_agent.png` | Plan-Execute-Replan loop with tool calls and the `deepcopy(owner)` sandbox. |
| `diagrams/flow_eval.png` | Offline evaluation harness fan-out (RAG / safety / bias / planning / calibration). |
| `diagrams/state_layers.png` | State lifecycle: process / session / disk persistence boundaries. |
| `diagrams/testing_checkpoints.png` | Where unit tests, smoke tests, and behavioural eval each gate the pipeline. |
| `uml_final.png` | Original Module 1–3 UML class diagram for the deterministic PawPal+ scheduler. |
| `UML.md` | Markdown source for the original UML diagram. |

The same `flow_*` and `system_*` PNGs also live under
[`../docs/design/diagrams/`](../docs/design/diagrams/) alongside their
`.mmd` Mermaid source files; that folder is the authoring location and
this folder is the asset-rubric mirror.

For an explanation of each diagram, see
[`../docs/design/architecture.md`](../docs/design/architecture.md).

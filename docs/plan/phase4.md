# Phase 4 Plan — Full Evaluation, Documentation & Demo

> **Status**: ✅ **Executed (2026-04-27)** — median scores RAG 100% / Safety 100% /
> Planning 90% / Bias 0.587 / AUROC 0.784. See [`../EVAL_RESULTS.md`](../EVAL_RESULTS.md).
> **Source plan**: Draft v1.1（2026-04-26 refresh patch；与 Phase 3 v1.1 对齐）
> **Phase goal**: 把 Phase 1–3 沉淀的所有能力**一次跑透**，产出可量化的可靠性
> 报告；把项目文档（README、reflection、架构）升级到 portfolio 质量；准备
> 一份 5 分钟的 demo（视频或 slides）。
> **依赖**: Phase 1（rag）/ Phase 2（agent）/ Phase 3（critic + bias + safety_redteam + run_eval `--all`）全部就绪
> **特点**: Phase 4 大部分是**写文档 + 跑 eval + 录 demo**，代码量接近零（仅 cleanup + 紧急补救）
>
> **v1.1 patch 摘要**（相对 v1.0 的差异）：
> 1. `safety_redteam.jsonl` 和 `run_eval.py --all` 已迁到 Phase 3（属于 eval 数据 + CLI 改动，不该堆到最后一周）
> 2. §3.6 mermaid PNG 改"一次性生成 + 入库"，不依赖评分人有 Node.js
> 3. §3.7 cleanup 加紧急回退开关 `PAWPAL_DISABLE_CRITIC` + lock file 拆分
> 4. DoD 字数门槛软化为"覆盖章节"；pytest 数字明确 ≥80
> 5. §3.9 demo 视频明确为 nice-to-have，不进 DoD

---

## 0. Phase 4 Scope

### 做（in scope）
- ✅ **跑完整 5-section eval**（rag · safety · planning · bias · calibration），用 Phase 3 已建好的 `run_eval.py --all` 一键
- ✅ AUROC 校准曲线 PNG **入库到 git**（`docs/design/diagrams/calibration_<date>.png`）
- ✅ README v2（带截图、setup、how AI works）
- ✅ `docs/REFLECTION_v2.md` —— 取代旧 `reflection.md`（已确认根目录存在）
- ✅ `docs/DEMO_SCRIPT.md` —— 5 分钟脚本（8 步）
- ✅ `docs/EVAL_RESULTS.md` —— 最终成绩单（数字 + 失败案例）
- ✅ Mermaid 图**一次性导出 PNG 入库**（不依赖评分人有 Node.js）
- ✅ `requirements.txt` 拆分：主依赖（运行）+ `requirements-eval.txt`（评估）+ `requirements-lock.txt`（精确复现）
- ✅ 紧急回退开关（`PAWPAL_DISABLE_CRITIC`）兜底，避免 critic 拖低分数被迫保留
- ✅ 全新机器复现测试（最关键，§3.8）
- ✅ 最终 lint + 代码 cleanup + 删 unused

### 可选（nice-to-have，**不进 DoD**）
- 🎬 录 demo 视频（2–5 分钟）—— DoD 只要求 `DEMO_SCRIPT.md` 8 步可演示
- 📊 Slides（5–8 页）—— 仅作业明确要求时才做

### 不做（out of scope，明确不动）
- ❌ 任何新功能（feature freeze）
- ❌ 重构（除非测试发现 bug）
- ❌ 新数据集 / 新 eval section（**应在 Phase 3 完成**，到 Phase 4 才发现 = 计划失败）
- ❌ 改 `run_eval.py` CLI 接口（**应在 Phase 3 完成**）
- ❌ 多模态 / 语音
- ❌ 部署到云端

---

## 1. Acceptance Criteria

| # | 验收点 | 验证方式 |
|---|--------|----------|
| 1 | 全套 eval 一键跑通 | `python -m eval.run_eval --all`（Phase 3 §3.9 已建）输出 5 个 markdown 报告 + 1 个 calibration PNG + 1 个聚合 `final_run_<ts>.md` |
| 2 | 报告数字达标 | golden ≥ 90% · safety ≥ 95% · bias parity ≥ 80% · planning ≥ 80% · AUROC ≥ 0.75 |
| 3 | 全新机器能复现 | 同事 clone → 5 行命令 → 跑通 demo（任务 4.8 强制走一遍） |
| 4 | Reflection 可读 | `REFLECTION_v2.md` 覆盖 §1–§7 七段（设计取舍 / AI 协作 / failures / bias / future / takeaway） |
| 5 | Demo 可演示 | `DEMO_SCRIPT.md` 8 步，每步预期截图都对得上 |
| 6 | 视觉化 | 至少 4 张 mermaid 图导出 PNG **入库** ，README + architecture.md 引用本地相对路径（GitHub 不渲染 mermaid 时也能看图） |
| 7 | pytest 全绿 | 至少 ≥80 条单测全过（Phase 2 已 72，Phase 3 +10 ≈ 82） |
| 8 | 紧急回退可用 | `PAWPAL_DISABLE_CRITIC=1 streamlit run app.py` 能启动且 critic 不打分（绕过 § Phase 3 §3.6） |

---

## 2. 模块清单

### 新增

```
docs/
├── REFLECTION_v2.md           # 取代根目录 reflection.md
├── EVAL_RESULTS.md            # 最终数字 + 失败明细
├── DEMO_SCRIPT.md             # 5 分钟演示步骤
└── design/
    └── diagrams/              # mermaid 导出的 PNG（git 入库，不依赖 mermaid CLI）
        ├── system_overview.png
        ├── flow_rag.png
        ├── flow_agent.png
        ├── flow_critic.png
        ├── checkpoints.png
        └── calibration.png    # ROC 曲线（Phase 3 已生成）

eval/reports/                  # 一次性产物（gitignore 即可，README 引用截图代替）
├── final_run_<date>.md        # 5 sections 汇总（rag/safety/planning/bias/calibration）
├── calibration_<date>.md
└── ...

requirements-eval.txt          # 仅评估时安装（sklearn, matplotlib）—— Phase 3 已建
requirements-lock.txt          # pip freeze 输出，精确复现
```

### 修改

```
README.md                      # 全面重写（保留 PawPal+ 历史段为附录）
reflection.md                  # 重命名 → reflection_phase2.md（历史保留）
                                # 顶部加 banner 指向 docs/REFLECTION_v2.md
requirements.txt               # 仅主运行依赖（streamlit / openai / chromadb / pydantic）
                                # 主依赖用 `>=` 范围，便于后续兼容
.env.example                   # 补 OPENAI_API_KEY / OPENAI_CHAT_MODEL / PAWPAL_DISABLE_CRITIC
docs/design/architecture.md    # 顶部加 "本地 PNG 镜像在 diagrams/" 说明
```

### 删除 / 归档

```
.pytest_cache/                 # 加到 .gitignore（如果还没）
__pycache__/                   # 同上
chroma_db/                     # 加到 .gitignore（每个开发机本地构建）
logs/*.jsonl                   # 加到 .gitignore（运行时产物）
任何 unused import / dead code
```

---

## 3. 任务分解

### 任务 4.1 — Eval 完整跑（1.5 h）
- [ ] **前置检查**：Phase 3 §3.9 任务必须已 done（`run_eval.py --all` CLI 入口存在；safety_redteam.jsonl + 50 条 golden + bias probes 都就绪）。否则**回 Phase 3 补**，不要在这里临时新建。
- [ ] `python -m eval.run_eval --all`：依次跑 rag / safety / planning / bias / calibration
- [ ] 输出 5 个 sub-section markdown + 1 个聚合 `final_run_<ts>.md` 到 `eval/reports/`
- [ ] **跑 3 次**取中位数（避免单次 LLM 抖动）
- [ ] 把 calibration ROC 曲线 PNG 复制到 `docs/design/diagrams/calibration.png` 并入 git
- [ ] 如果某指标不达标 → 补救（见 §6）

### 任务 4.2 — `docs/EVAL_RESULTS.md`（1 h）
- [ ] 顶部一张总分表（5 个数字 + green/yellow/red 标记）
- [ ] 每个 section 一段：用例数 / 通过率 / top-3 失败案例
- [ ] Calibration 段：AUROC + ROC 曲线图 + 高自信失败案例
- [ ] Bias 段：每物种平均得分柱状图（matplotlib 导 PNG）
- [ ] 末尾"已知局限"列 ≥ 3 条

### 任务 4.3 — README v2（2.5 h）—— 高价值
- [ ] **顶部一句 pitch**（30 字内）+ Demo GIF / 截图
- [ ] **Quick start**：5 行命令 + 截图
- [ ] **What it does**：3 个使用场景的对话式截图（Schedule / Ask / Plan）
- [ ] **How AI is used**：嵌入 `system_overview.png` + 3 段说明（RAG / Agent / Critic）
- [ ] **Trustworthy by design**：guardrails + critic + human approval 段（直接讲卖点）
- [ ] **Evaluation**：链接到 `docs/EVAL_RESULTS.md`，把 5 个核心数字搬到 README 主表
- [ ] **Project layout**：目录树（截 phase 1 plan §2）
- [ ] **Architecture**：链接 `docs/design/architecture.md`
- [ ] **Limitations & next steps**
- [ ] **Acknowledgements / sources**：知识库引用列表

### 任务 4.4 — `docs/REFLECTION_v2.md`（2 h）
模板：
- [ ] **§1 Problem & approach**：为什么选 RAG 而不是 fine-tune / pure LLM
- [ ] **§2 Design tradeoffs**：3 个具体取舍
  - "为什么不让 LLM 替代 Scheduler 做排序"
  - "为什么 guardrails 是 Python 不是 prompt 约束"
  - "为什么 agent 必须人工 Apply"
- [ ] **§3 What worked / what didn't**：从 trace 里挑 2 个真实失败案例分析
- [ ] **§4 AI collaboration in development**：哪些任务 AI 加速最大、哪些反而拖慢
- [ ] **§5 Bias & safety reflection**：跑出来的 bias 数字诚实讨论（哪个物种最弱）
- [ ] **§6 What I'd change next**：3 条 future work
- [ ] **§7 Key takeaway**：一段话总结

### 任务 4.5 — `docs/DEMO_SCRIPT.md`（1 h）
- [ ] 每步 3 列：操作 / 期望屏幕 / 演讲要点（30 秒内）
- [ ] 步骤覆盖：
  1. 启动应用（10s）
  2. Schedule tab 加任务 —— 证明现有功能保留（30s）
  3. Ask PawPal 问安全问题（30s）
  4. Ask PawPal 问 toxic food → 触发 guardrail（45s）—— **高光时刻**
  5. Plan My Week 生成计划（45s）
  6. 制造冲突 → 看 re-plan trace（45s）—— **高光时刻**
  7. 展开 reasoning trace + critic 评分（30s）
  8. 总结 + 引用 `EVAL_RESULTS.md` 的 5 个数字（30s）

### 任务 4.6 — Mermaid → PNG 一次性入库（45 min）
**目标**：评分人 / 第三方 reviewer 不需要装 Node.js / mermaid-cli 也能看图。

- [ ] 本地一次性安装 mermaid CLI：`npm install -g @mermaid-js/mermaid-cli`（仅本机）
- [ ] 把 `architecture.md` 里 ≥4 张图各导出一张 PNG（`-w 1600 -b transparent`）到 `docs/design/diagrams/`
  - `system_overview.png`
  - `flow_rag.png`
  - `flow_agent.png`
  - `flow_critic.png`
  - （+ Phase 3 已生成的 `calibration.png`）
- [ ] 同时生成 SVG 备份（`.svg` 同目录）
- [ ] **`git add docs/design/diagrams/*.png` 全部入库**（这是关键）
- [ ] 在 `architecture.md` 顶部加 banner：
  > 📸 本地 PNG 镜像在 `docs/design/diagrams/`，在不渲染 mermaid 的 viewer 里点链接看
- [ ] README v2 用相对路径引用 `docs/design/diagrams/system_overview.png` 而不是 mermaid 块（GitHub 即使不渲染 mermaid 也能看 PNG）
- [ ] 写一行复现命令到 `docs/design/diagrams/README.md`：`mmdc -i ../architecture.md -o system_overview.png` 方便日后重生成
- [ ] **不要把 mermaid CLI 加到 requirements 或 CI**

### 任务 4.7 — 代码 cleanup（2 h）
- [ ] `ruff check` / `flake8`（视用什么 linter）全绿
- [ ] 删 unused import（`autoflake --remove-all-unused-imports -r .`）
- [ ] 检查所有 TODO / FIXME，要么修要么写到 `EVAL_RESULTS.md` 的"已知局限"
- [ ] **依赖三件套拆分**：
  - `requirements.txt`：仅运行依赖（`streamlit`, `openai`, `chromadb`, `pydantic`），用 `>=` 范围
  - `requirements-eval.txt`：仅评估依赖（`scikit-learn`, `matplotlib`），由 Phase 3 §3.9 引入
  - `requirements-lock.txt`：`pip freeze > requirements-lock.txt` 输出，提供精确复现锁
- [ ] `.env.example` 补：
  - `OPENAI_API_KEY=`
  - `OPENAI_CHAT_MODEL=gpt-4o-mini`
  - `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`
  - `PAWPAL_DISABLE_CRITIC=` （留空，紧急时设 1 关掉 critic，见 §6）
- [ ] 验证紧急回退：`PAWPAL_DISABLE_CRITIC=1 streamlit run app.py` 启动后 critic 走 mock 回退（DoD #8）
- [ ] 跑一遍最终 `pytest`：≥80 条全绿（DoD #7）
- [ ] `.gitignore` 确认包含：`.pytest_cache/`、`__pycache__/`、`chroma_db/`、`logs/*.jsonl`、`eval/reports/`、`.venv/`、`.env`

### 任务 4.8 — 全新环境复现测试（30 min）—— 关键
- [ ] 在另一个文件夹 `git clone .`
- [ ] 严格按 README 命令走一遍
- [ ] 任何卡住的步骤 → 立刻回头补 README
- [ ] 测 mac + linux 各一遍（如果有条件）

### 任务 4.9 — Demo 录制（**nice-to-have，不进 DoD**，1.5 h）
- [ ] QuickTime 录屏 / OBS
- [ ] 按 `DEMO_SCRIPT.md` 走一遍
- [ ] 剪辑掉空白等待时间
- [ ] 上传到 youtube unlisted / Loom，README 嵌入链接
- [ ] 失败兜底：把 `DEMO_SCRIPT.md` 8 步各截 1 张图存 `docs/design/screenshots/`，README 当成静态 walkthrough

### 任务 4.10 — Slides（**nice-to-have，仅作业要求时**，1 h）
- [ ] 5–8 页（如果作业要求）：
  1. Problem & pitch
  2. System overview（PNG）
  3. RAG demo screenshot
  4. Agent demo screenshot
  5. Trust mechanisms（guardrail / critic / approval）
  6. Eval numbers（柱状图）
  7. Limitations & next steps
  8. Q&A

**预计总时长：~12 h**，分布到 Week 4（最后冲刺周）。

---

## 4. Definition of Done

- [ ] `python -m eval.run_eval --all` 一次成功（≥3 次取中位）
- [ ] 5 个核心指标全部达标（见 §1.2），不达标按 §6 补救
- [ ] README v2 在 GitHub 上渲染正常（**mermaid 不显示也有 PNG fallback**）
- [ ] 全新机器复现走完 5 行命令 + demo 8 步（任务 4.8 必做）
- [ ] `docs/REFLECTION_v2.md` 覆盖 §1–§7 七段（**软指标，不卡字数**）
- [ ] ≥4 张 mermaid 图导出 PNG **入库 git**（DoD #6）
- [ ] `pytest` ≥80 条全绿（DoD #7）
- [ ] `PAWPAL_DISABLE_CRITIC=1` 紧急回退可用（DoD #8）
- [ ] 所有 phase plan markdown 末尾标 ✅ Done + 完成日期
- [ ] **Demo 视频与 slides 不进 DoD**（仅作业明确要求时启用）

---

## 5. 评分对照（Final Rubric Mapping）

| Rubric 维度 | 在 Phase 4 末尾对应的证据 |
|-------------|---------------------------|
| Cohesive end-to-end AI system | README v2 + system_overview.png + Demo |
| Modular components (retrieval/logic/agentic) | 目录结构 + architecture.md |
| Reliability + guardrails | `EVAL_RESULTS.md` + safety section + tests |
| AI decision-making 可解释性 | trace expander + DEMO_SCRIPT 第 7 步 |
| Responsible design | bias section + REFLECTION §5 |
| Technical creativity | Plan-Execute-Critique loop 描述 |
| Professional documentation | README + REFLECTION_v2 + DEMO_SCRIPT |
| Stretch | calibration AUROC + bias 量化 |

---

## 6. 不达标补救路径

如果 Phase 4 跑完 eval 发现某指标不到目标：

| 指标 | 不达标 | 补救（按工时排序，先做最便宜的） |
|------|--------|--------------------------------|
| Golden QA < 90% | 检索召回低 | 1. 看失败案例的 query → 补对应 KB markdown（30 min/篇） |
|  | LLM 不引用 | 2. 改强 prompt 约束（10 min） |
|  |  | 3. 升级到 `gpt-4o`（成本×10，最后手段） |
| Safety redteam < 95% | guardrail 漏配 | 看哪条 redteam 漏，加黑名单条目（5 min/条） |
| Bias parity < 80% | 小宠物 KB 不足 | 补 hamster / rabbit / bird KB md（1 h/物种） |
| Planning < 80% | re-plan 失败 | 加 prompt 例子（few-shot）；放宽 max_replans 到 5 |
| AUROC < 0.75 | critic 校准差 | 1. Stretch: self-consistency（critic 跑 3 次取中位数）<br>2. 最坏：`PAWPAL_DISABLE_CRITIC=1` 关掉 critic，UI 仅靠 guardrail 兜底，reflection 里诚实讨论 |
| 任意指标全失败 | LLM API 抽风 / 余额 | 1. 切回 mock client（`unset OPENAI_API_KEY`）跑离线 mock eval，至少证明管道是通的<br>2. 截图 + 时间戳留存 |

**补救时间预算**：留 2–3 h 作为 buffer，超出就接受当前数字 + 在 reflection 里诚实讨论。

> **重要**：补救应**只改 prompt / 数据 / 配置**，不改架构或新增模块。
> 真出现"必须重构才能达标"的情况 → 接受当前数字，写进 reflection §6 future work。

---

## 7. 风险

| 风险 | 缓解 |
|------|------|
| 跑 eval 烧 token 超预算 | 用 cache（同 query 命中即跳过 LLM）；只跑 3 次取中位 |
| 全新机器复现失败 | 任务 4.8 必做，**留出至少 30 min 缓冲** |
| Demo 视频失败 / 嗓子哑 | 改成静态截图 walkthrough（README 友好），不进 DoD |
| Mermaid 图在某些 viewer 不渲染 | PNG fallback（任务 4.6 已入库 git）|
| Time-zone / 夏令时让 due_date 翻车 | 任务 4.7 时 grep `date.today()` 用法，确保都用 UTC 或同一 tz |
| 知识库版权疑虑 | reflection §5 末尾加一段 disclaimer + source URL 列表 |
| Phase 3 数据集没就绪就开 Phase 4 | §3.1 加了"前置检查"；如发现缺失 → **回 Phase 3 补**，不在 Phase 4 临时新建 |
| critic 拖低分数被迫保留差实现 | `PAWPAL_DISABLE_CRITIC=1` 紧急回退（§3.7 已建）+ §6 补救路径 |
| `pip freeze` lock file 包含本机特殊版本（如 macOS arm64 wheel） | lock file 注明"仅用于复现作者环境"；新机器先用 `requirements.txt` + `requirements-eval.txt` 安装 |

---

## 8. 后续（Out-of-course）改进方向

写到 REFLECTION §6，列在这里方便查：

- **持久化**：SQLite 替代 session_state，支持多 owner / 多设备
- **多模态**：识别宠物照片判断品种 → 自动 species 选择
- **真实数据集成**：FitBark / Whistle 等可穿戴 API
- **本地 LLM**：换 Ollama + Llama 3.1，零 API 成本 + 隐私
- **Active learning**：让用户标记"这条回答没用"，自动补 KB
- **多语言**：知识库 + UI 中英双语

---

## 9. 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-04-26 | v1.0 | 初稿；feature freeze + 5 核心指标 + 不达标补救 matrix |
| 2026-04-26 | v1.1 | refresh patch：safety_redteam / `--all` 迁到 Phase 3；mermaid PNG 一次性入库不依赖 CLI；deps 拆三件套；加 `PAWPAL_DISABLE_CRITIC` 回退开关；DoD 字数门槛软化为章节覆盖；demo 视频 / slides 明确 nice-to-have |

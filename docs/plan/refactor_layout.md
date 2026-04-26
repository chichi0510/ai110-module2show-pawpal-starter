# Refactor: Project Layout (Phase 1.5)

> **Scope**: 一次性结构性重构，把根目录扁平的 Python 模块和子包整合进单一 `pawpal/` 包。
> **执行时机**: Phase 1 完成之后、Phase 2 开始之前。
> **预计耗时**: 1.5–2 小时（含验证）。
> **风险等级**: 低（38 个测试 + mock eval 全程兜底）。

## 1. 背景与动机

Phase 1 完成后的根目录长这样：

```
ai110-module2show-pawpal-starter/
├── app.py                 ← UI
├── main.py                ← CLI demo
├── pawpal_system.py       ← Domain
├── llm_client.py          ← AI 基础设施
├── tools.py               ← Domain 适配器
├── rag/                   ← AI 包
├── guardrails/            ← 规则包
├── knowledge/  chroma_db/  logs/
├── eval/  tests/  docs/
└── requirements.txt / .env / README.md
```

问题：

1. **UI 入口 `app.py` 和库代码混在同一层**，没有视觉分隔。
2. **Python 模块和包混用**：根目录有 4 个 `.py` 文件（`app.py`/`main.py`/`pawpal_system.py`/`llm_client.py`/`tools.py`）和 2 个包（`rag/`、`guardrails/`），看不出"什么是入口、什么是库"。
3. **Phase 2/3 还要加 `agent/`、`critic/`、`bias_filter`**，再加下去根目录会膨胀到 6 个 `.py` + 5 个包。
4. **Import 风格不统一**：`from pawpal_system import` vs `from rag.qa import` vs `from llm_client import`。
5. **架构文档 (`docs/design/architecture.md`) 已分 6 层**，但文件系统没有体现这个分层。

目标：让文件系统结构和架构文档对齐，并为 Phase 2/3/4 做好骨架。

## 2. 目标结构

```
ai110-module2show-pawpal-starter/
├── app.py                       ← Streamlit UI 入口（保留在根）
├── main.py                      ← CLI demo（保留在根）
├── requirements.txt / .env / README.md
│
├── pawpal/                      ← 所有库代码（单一包）
│   ├── __init__.py              ← 空文件
│   ├── domain.py                ← 原 pawpal_system.py
│   ├── llm_client.py
│   ├── tools.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── index.py
│   │   ├── retrieve.py
│   │   └── qa.py
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── toxic_food.py
│   │   └── input_filter.py
│   ├── (Phase 2) agent/
│   └── (Phase 3) critic/
│
├── knowledge/                   ← 数据，不变
├── chroma_db/  logs/            ← 运行时（gitignored）
├── eval/                        ← 评估，不变
├── tests/                       ← 测试，不变
└── docs/                        ← 文档，不变
```

### 2.1 命名说明

| 旧名 | 新名 | 理由 |
|---|---|---|
| `pawpal_system.py` | `pawpal/domain.py` | `from pawpal.pawpal_system import Owner` 太冗余；`domain` 直接表达"领域模型层" |
| `llm_client.py` | `pawpal/llm_client.py` | 名字保留 |
| `tools.py` | `pawpal/tools.py` | 名字保留 |
| `rag/` | `pawpal/rag/` | 子包路径加前缀 |
| `guardrails/` | `pawpal/guardrails/` | 子包路径加前缀 |

### 2.2 不动的部分

- `app.py`、`main.py` 留在根（Streamlit 习惯 + CLI 入口惯例）。
- `knowledge/`、`chroma_db/`、`logs/`、`eval/`、`tests/`、`docs/`、`assets/` 全部保持原位（它们不是 Python 包/库，是数据/配置/文档）。
- `pawpal/__init__.py` 留空，**不做 re-export**（避免 namespace 污染和循环 import）。

## 3. Acceptance Criteria

- [ ] 根目录的 `pawpal_system.py`、`llm_client.py`、`tools.py`、`rag/`、`guardrails/` 全部消失，对应文件移到 `pawpal/`。
- [ ] `streamlit run app.py` 仍能正常启动，**Schedule** 和 **Ask PawPal** 两个 tab 行为一致。
- [ ] `python main.py` 仍输出原有的 CLI demo。
- [ ] `python -m pytest` 仍 38/38 PASS。
- [ ] `python -m rag.index --rebuild` 改成 `python -m pawpal.rag.index --rebuild` 后能正常重建索引。
- [ ] `python -m eval.run_eval --mock` 仍能跑通且短路类用例全部 PASS。
- [ ] `README.md`、`docs/design/architecture.md`、`docs/plan/phase2.md`、`docs/plan/phase3.md`、`docs/plan/phase4.md`、`docs/design/open_questions.md` 中所有过时路径引用都已更新。
- [ ] `pytest` 不引入任何 deprecation/import warning。
- [ ] `git status` 干净，`git mv` 路径保留 history。

## 4. Import 改写表

按文件列出所有需要改的 import。**全部是机械替换**，不动逻辑。

### 4.1 移动 + 重命名

| 旧路径 | 新路径 |
|---|---|
| `pawpal_system.py` | `pawpal/domain.py` |
| `llm_client.py` | `pawpal/llm_client.py` |
| `tools.py` | `pawpal/tools.py` |
| `rag/__init__.py` | `pawpal/rag/__init__.py` |
| `rag/models.py` | `pawpal/rag/models.py` |
| `rag/index.py` | `pawpal/rag/index.py` |
| `rag/retrieve.py` | `pawpal/rag/retrieve.py` |
| `rag/qa.py` | `pawpal/rag/qa.py` |
| `guardrails/__init__.py` | `pawpal/guardrails/__init__.py` |
| `guardrails/toxic_food.py` | `pawpal/guardrails/toxic_food.py` |
| `guardrails/input_filter.py` | `pawpal/guardrails/input_filter.py` |

### 4.2 Import 替换

| 文件 | 旧 import | 新 import |
|---|---|---|
| `app.py` | `from pawpal_system import Owner, Pet, Scheduler, Task` | `from pawpal.domain import Owner, Pet, Scheduler, Task` |
| `app.py` | `from rag import index as rag_index` | `from pawpal.rag import index as rag_index` |
| `app.py` | `from rag.models import AnswerResult` | `from pawpal.rag.models import AnswerResult` |
| `app.py` | `from rag.qa import PetContext, answer` | `from pawpal.rag.qa import PetContext, answer` |
| `main.py` | `from pawpal_system import Owner, Pet, Scheduler, Task` | `from pawpal.domain import Owner, Pet, Scheduler, Task` |
| `pawpal/tools.py` | `from pawpal_system import Owner` | `from pawpal.domain import Owner` |
| `pawpal/rag/__init__.py` | `from rag.models import Chunk, Citation, AnswerResult` | `from pawpal.rag.models import Chunk, Citation, AnswerResult` |
| `pawpal/rag/index.py` | `from llm_client import LLMClient` | `from pawpal.llm_client import LLMClient` |
| `pawpal/rag/retrieve.py` | `from llm_client import LLMClient` | `from pawpal.llm_client import LLMClient` |
| `pawpal/rag/retrieve.py` | `from rag.index import CHROMA_DIR, COLLECTION` | `from pawpal.rag.index import CHROMA_DIR, COLLECTION` |
| `pawpal/rag/retrieve.py` | `from rag.models import Chunk` | `from pawpal.rag.models import Chunk` |
| `pawpal/rag/qa.py` | `from guardrails import input_filter, toxic_food` | `from pawpal.guardrails import input_filter, toxic_food` |
| `pawpal/rag/qa.py` | `from llm_client import LLMClient` | `from pawpal.llm_client import LLMClient` |
| `pawpal/rag/qa.py` | `from rag.models import AnswerResult, Chunk, Citation` | `from pawpal.rag.models import AnswerResult, Chunk, Citation` |
| `pawpal/rag/qa.py` | `from rag.retrieve import DEFAULT_K, retrieve` | `from pawpal.rag.retrieve import DEFAULT_K, retrieve` |
| `tests/test_pawpal.py` | `from pawpal_system import Owner, Pet, Scheduler, Task` | `from pawpal.domain import Owner, Pet, Scheduler, Task` |
| `tests/test_tools.py` | `import tools` | `from pawpal import tools` |
| `tests/test_tools.py` | `from pawpal_system import Owner, Pet` | `from pawpal.domain import Owner, Pet` |
| `tests/test_guardrails.py` | `from guardrails import input_filter, toxic_food` | `from pawpal.guardrails import input_filter, toxic_food` |
| `tests/test_rag_smoke.py` | `from llm_client import ChatResponse, ChatUsage, LLMClient` | `from pawpal.llm_client import ChatResponse, ChatUsage, LLMClient` |
| `tests/test_rag_smoke.py` | `from rag.index import build_index` | `from pawpal.rag.index import build_index` |
| `tests/test_rag_smoke.py` | `from rag.models import Chunk` | `from pawpal.rag.models import Chunk` |
| `tests/test_rag_smoke.py` | `from rag.qa import LOG_FILE, PetContext, answer` | `from pawpal.rag.qa import LOG_FILE, PetContext, answer` |
| `tests/test_rag_smoke.py` | `from rag import qa as qa_module` | `from pawpal.rag import qa as qa_module` |
| `tests/test_rag_smoke.py` | `from rag import retrieve as retrieve_module` | `from pawpal.rag import retrieve as retrieve_module` |
| `eval/run_eval.py` | `from rag.qa import PetContext, answer` | `from pawpal.rag.qa import PetContext, answer` |

### 4.3 CLI / 命令行入口

| 旧命令 | 新命令 |
|---|---|
| `python -m rag.index --rebuild` | `python -m pawpal.rag.index --rebuild` |
| `python -m rag.qa "..."` | `python -m pawpal.rag.qa "..."` |
| `python -m eval.run_eval` | `python -m eval.run_eval`（不变） |
| `streamlit run app.py` | `streamlit run app.py`（不变） |

## 5. 任务分解（Task Breakdown）

| # | 任务 | 预计 | 依赖 |
|---|---|---|---|
| R.1 | 创建 `pawpal/__init__.py`（空文件） | 5 min | — |
| R.2 | `git mv pawpal_system.py pawpal/domain.py` | 5 min | R.1 |
| R.3 | `git mv llm_client.py pawpal/llm_client.py` | 5 min | R.1 |
| R.4 | `git mv tools.py pawpal/tools.py` | 5 min | R.1 |
| R.5 | `git mv rag pawpal/rag` | 5 min | R.1 |
| R.6 | `git mv guardrails pawpal/guardrails` | 5 min | R.1 |
| R.7 | 改写 `pawpal/` 内部 import（rag、guardrails、tools） | 15 min | R.2–R.6 |
| R.8 | 改写 `app.py`、`main.py` import | 5 min | R.7 |
| R.9 | 改写 `tests/*.py` import | 10 min | R.7 |
| R.10 | 改写 `eval/run_eval.py` import | 3 min | R.7 |
| R.11 | 跑 `pytest` 确认 38/38 PASS | 5 min | R.9 |
| R.12 | 重建索引：`python -m pawpal.rag.index --mock --rebuild` | 3 min | R.11 |
| R.13 | 跑 `python -m eval.run_eval --mock` 确认短路类全 PASS | 3 min | R.12 |
| R.14 | 手动启动 `streamlit run app.py`（用户自测，可选） | 5 min | R.12 |
| R.15 | 更新 `README.md` 中所有路径/命令引用 | 10 min | R.13 |
| R.16 | 更新 `docs/design/architecture.md` 路径引用 | 10 min | R.13 |
| R.17 | 更新 `docs/plan/phase2.md`、`phase3.md`、`phase4.md` 路径引用 | 15 min | R.13 |
| R.18 | 更新 `docs/design/open_questions.md` 路径引用 | 5 min | R.13 |
| R.19 | 清理 `__pycache__` / `.pytest_cache` | 2 min | — |
| R.20 | `git status` & `git diff --stat` 复核 | 5 min | R.18 |

**合计**：约 2 小时。

## 6. 文档更新清单

下列文档里有 hard-coded 路径或命令，需要逐一扫描并更新：

- `README.md`
  - "Project layout (Phase 1)" 表格
  - 所有 `python -m rag.index` 改 `python -m pawpal.rag.index`
  - "Architecture at a glance" 树状图
- `docs/design/architecture.md`
  - "Main Components & Responsibilities" 表（路径列）
  - 所有 mermaid 图里如果有路径（标签里）
  - "Phase-Architecture mapping" 章节
- `docs/plan/phase2.md`
  - 新建文件路径：`agent/planner.py` → `pawpal/agent/planner.py`
  - tools 扩展路径：`tools.py` → `pawpal/tools.py`
  - "Module List" 表
- `docs/plan/phase3.md`
  - 新建文件路径：`critic/*` → `pawpal/critic/*`
  - `guardrails/bias_filter.py` → `pawpal/guardrails/bias_filter.py`
- `docs/plan/phase4.md`
  - 文件清单里的所有路径
- `docs/design/open_questions.md`
  - Q5 里的 `rag/retrieve.py` 路径示例
  - Q3 里的 `rag/qa.py` 路径示例

## 7. 验证步骤（Definition of Done）

按顺序执行，全部通过即可认为重构完成：

```bash
# 1. 单元测试
python -m pytest -q
# 期望：38 passed

# 2. 重建索引（mock）
rm -rf chroma_db
python -m pawpal.rag.index --mock --rebuild
# 期望：Wrote N chunks to ChromaDB

# 3. 评估 harness
python -m eval.run_eval --mock --limit 5
# 期望：harness 不报 ImportError，至少 toxic_food/off_topic 类 PASS

# 4. CLI 单查（mock）
python -c "from pawpal.rag.qa import answer, PetContext; print(answer('test', PetContext(species='dog')).text[:80])"
# 期望：返回 [mock answer] 或 short-circuit 文案，无 ImportError

# 5. Streamlit 启动（手动）
streamlit run app.py
# 期望：两个 tab 都正常渲染，Ask PawPal 能正常提交问题

# 6. Lint
# Cursor 内置 lints 应全绿
```

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Import 漏改导致 `ModuleNotFoundError` | 用全局 grep `from (pawpal_system\|llm_client\|tools\|rag\|guardrails)` 双向校验，pytest 会立刻暴露 |
| Streamlit 跑起来后某个 lazy import 报错 | R.14 步骤手动启动，至少切两次 tab |
| Chroma 索引里存的 metadata 路径过期 | 重建索引（步骤 2），数据量小 (~64 chunks) 几秒就完成 |
| `git mv` 在某些情况下退化为 delete+add | 用 `git log --follow pawpal/domain.py` 验证 history 链 |
| 文档里漏改路径不会被自动发现 | 重构提交后用 `rg "pawpal_system\|from rag\b\|from guardrails\b\|from llm_client\b" docs/ README.md` 全局复查 |
| 重构期间 phase2 开始写代码 → 双线作业冲突 | 重构必须在 phase2 任何代码写之前完成，本 plan 明确写死该顺序 |

## 9. 不在范围内（Out of Scope）

- 不改 `pawpal_system.py` 文件内部的类设计（`Owner`/`Pet`/`Task`/`Scheduler`），只改文件位置和文件名。
- 不引入 `src/` layout、`pyproject.toml`、`setup.py` 或 `pip install -e .`。Phase 4 之后如有需要可单独 plan。
- 不动 `eval/`、`tests/`、`knowledge/`、`docs/` 的目录结构，只改它们内部 import / 路径字符串。
- 不做 namespace re-export。`pawpal/__init__.py` 保持空文件。
- 不改 `Pet`、`Owner` 等类的行为或字段（38 个测试是不变量）。

## 10. 重构后 → Phase 2 衔接

重构完成后，Phase 2 将直接以新结构为起点：

- 新增 `pawpal/agent/__init__.py`、`pawpal/agent/planner.py`、`pawpal/agent/executor.py`、`pawpal/agent/models.py`、`pawpal/agent/prompts.py`
- 扩展 `pawpal/tools.py`：加上 `add_task`、`detect_conflicts`、`rag_lookup`
- 扩展 `pawpal/guardrails/toxic_food.py`：加 `assert_safe_for_task` 接口给 agent 调用
- `app.py` 增加 "🧠 Plan My Week" tab，import 路径直接 `from pawpal.agent.planner import plan_week`

整个 Phase 2 的 phase2.md 不需要再次重新组织目录，路径前缀已统一。

## 11. 一致性检查清单（重构后）

- [ ] 根目录只剩：`app.py`、`main.py`、`requirements.txt`、`.env*`、`.gitignore`、`README.md`、`UML.md`、`reflection.md`、`uml_final.png` + 子目录
- [ ] 没有任何 `from rag.` / `from guardrails.` / `from pawpal_system` / `from llm_client` / `^import tools` 的 import（全部带 `pawpal.` 前缀）
- [ ] `python -c "import pawpal.rag.qa, pawpal.guardrails.toxic_food, pawpal.domain, pawpal.tools, pawpal.llm_client"` 一行无报错
- [ ] `pytest` 全绿
- [ ] 文档全绿（grep 不到旧路径）

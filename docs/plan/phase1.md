# Phase 1 Plan — RAG-Integrated PawPal MVP

> **Status**: Draft v1.0
> **Phase goal**: 把 PawPal+ 升级为一个集成了 RAG 知识问答的 Streamlit 应用，
> 满足作业 Phase 1 的全部硬性要求（useful AI · advanced feature · 集成主应用
> · 可复现 · logging · guardrails · 清晰 setup）。
> **Out of scope**: Agentic planning、self-critique、bias eval —— 全部推到后续 Phase。

---

## 0. Phase 1 Scope（明确做与不做）

### 做（in scope）
- ✅ RAG 知识问答模块（retrieve + generate + cite）
- ✅ 在 `app.py` 中新增 "Ask PawPal" Tab，与现有 Schedule 功能并存
- ✅ 一条硬 guardrail：toxic-food 黑名单（输入 + 输出双向扫描）
- ✅ 结构化 logging（每次 RAG 调用一条 JSONL）
- ✅ 知识库 8–10 篇 markdown
- ✅ `.env.example` + 完整 `README` setup 段落
- ✅ 至少 15 条单元测试（tools + guardrail + retrieve）
- ✅ 一个最小 eval：20 道 golden QA + 一个一键脚本

### 不做（out of scope，留给后续 Phase）
- ❌ Agentic planning loop（Phase 2）
- ❌ Self-critique / confidence scoring（Phase 3）
- ❌ Bias detection probes（Phase 3）
- ❌ 完整 120 条 eval set（Phase 4）
- ❌ Streamlit 第三个 "Plan My Week" tab（Phase 2）

---

## 1. Acceptance Criteria（对照作业 Phase 1 要求）

| # | 作业要求 | 本 Phase 如何满足 | 验收方式 |
|---|----------|-------------------|----------|
| 1 | Useful AI | RAG 回答宠物护理问题（喂食、毒性食物、疫苗） | Demo 跑通 5 个真实问题 |
| 2 | Advanced feature: RAG | `rag/` 模块完整实现 retrieve + generate | `python -m rag.qa "..."` CLI 可用 |
| 3 | 集成到主应用 | "Ask PawPal" Tab 是 `app.py` 的一部分；用户在选定的 Pet 上下文里提问 | Streamlit 启动后能看到该 tab，回答用到当前 Pet 的 species |
| 4 | Reproducible | `requirements.txt` 钉版本；`.env.example`；README 一段命令跑通 | 全新虚拟环境从 0 安装能成功启动 |
| 5 | Logging | 每次 RAG 请求写 `logs/rag_trace.jsonl` | 跑一个问答后能看到一条新记录 |
| 6 | Guardrails | toxic-food 黑名单在 input 和 output 都扫描 | "我可以喂狗巧克力吗？" → 强制安全回答 + 红色警示条 |
| 7 | Clear setup | README 5 行命令复现 | 同事 clone 后能跑 |

---

## 2. 模块清单（Phase 1 新增 / 修改）

### 新增

```
llm_client.py                  # OpenAI 客户端封装（chat + embed）
tools.py                       # Pet/Scheduler 的 LLM-friendly 包装
                               # Phase 1 只导出 list_pets，给 RAG 拿 species 上下文
rag/
├── __init__.py
├── index.py                   # 把 knowledge/*.md 切片 + 写入 ChromaDB
├── retrieve.py                # retrieve(query, species=None, k=4)
└── qa.py                      # answer(query, pet_context) -> AnswerResult
guardrails/
├── __init__.py
├── toxic_food.py              # 黑名单 + check_input + check_output
└── input_filter.py            # 离题 / PII 简单过滤
knowledge/
├── feeding/
│   ├── dog_feeding_basics.md
│   └── cat_feeding_basics.md
├── toxic_foods/
│   ├── dogs_toxic_list.md
│   └── cats_toxic_list.md
├── vaccines/
│   ├── dog_vaccine_schedule.md
│   └── cat_vaccine_schedule.md
└── general/
    ├── new_puppy_first_week.md
    └── new_kitten_first_week.md
eval/
├── golden_qa.jsonl            # 20 条
└── run_eval.py
logs/                          # gitignored
└── rag_trace.jsonl
.env.example                   # OPENAI_API_KEY=...
tests/
├── test_tools.py
├── test_guardrails.py
└── test_rag_smoke.py          # mock LLM，验证检索 + guardrail 串联
```

### 修改

```
app.py            # 加 "Ask PawPal" tab；现有 Schedule tab 保留
README.md         # 重写 setup；加 demo 命令；加 .env 说明
requirements.txt  # 加 openai / chromadb / python-dotenv / pydantic
.gitignore        # 加 logs/ chroma_db/ .env
```

---

## 3. 任务分解（按依赖顺序）

### 任务 1.1 — 依赖与环境（30 min）
- [ ] `requirements.txt` 增加：
  - `openai>=1.40`
  - `chromadb>=0.5`
  - `python-dotenv>=1.0`
  - `pydantic>=2.5`
- [ ] 写 `.env.example`：`OPENAI_API_KEY=sk-...`
- [ ] 更新 `.gitignore`：`logs/`, `chroma_db/`, `.env`

### 任务 1.2 — `llm_client.py`（1 h）
- [ ] 单一类 `LLMClient`，方法：
  - `chat(messages, model="gpt-4o-mini")`
  - `embed(texts, model="text-embedding-3-small")`
- [ ] 从 `.env` 读 key，缺失时抛清晰错误
- [ ] 加可选 `mock=True` 模式，让单元测试不调真 API

### 任务 1.3 — 知识库内容（2 h）
- [ ] 8 篇 markdown，每篇带 frontmatter：
  ```yaml
  ---
  species: dog            # dog | cat | general
  topic: toxic_foods      # feeding | toxic_foods | vaccines | general
  source: ASPCA Animal Poison Control (2024)
  source_url: https://...
  last_reviewed: 2026-04
  ---
  ```
- [ ] 自己 paraphrase 内容（不抄原文，避免版权）
- [ ] 每篇 300–800 字，结构化（H2/H3）

### 任务 1.4 — `rag/index.py`（1 h）
- [ ] 扫 `knowledge/**/*.md`
- [ ] 按 H2/H3 切片，max 800 token，overlap 100
- [ ] 调 `LLMClient.embed()`，写 ChromaDB collection `pawpal_kb`
- [ ] CLI: `python -m rag.index --rebuild`
- [ ] 切片元数据保留：`source_path`, `species`, `topic`, `heading`

### 任务 1.5 — `rag/retrieve.py`（45 min）
- [ ] `retrieve(query: str, species: str | None = None, k: int = 4) -> list[Chunk]`
- [ ] species 不为 None 时，先用 `where={"species": {"$in": [species, "general"]}}` 过滤
- [ ] 返回 `Chunk(text, source_path, score, heading)`
- [ ] 用 `@st.cache_resource` 包装 client，避免 streamlit 每次 rerun 都重连

### 任务 1.6 — `guardrails/toxic_food.py`（1 h）
- [ ] 两个 dict：`TOXIC_FOODS_DOG`, `TOXIC_FOODS_CAT`，每条 `{name, reason}`
- [ ] 每物种 ≥ 15 项（来源 ASPCA / Cornell）
- [ ] `scan_text(text, species) -> list[Hit]`：返回命中项（含 reason）
- [ ] `check_input(text, species)`：用户问 "can my dog eat X" 时，X 命中 → 返回硬安全回答 + 不调 LLM
- [ ] `check_output(answer, species)`：扫 LLM 回答，命中黑名单且没有 "do not feed" 类警告语 → 在前面注入红色警示条 + 标记 `safety_intervened=True`

### 任务 1.7 — `rag/qa.py`（2 h）
- [ ] 主入口 `answer(query, pet_context) -> AnswerResult`（pydantic 模型）
- [ ] 流程：
  1. `input_filter.preflight(query)` → 离题直接返回 "out-of-scope"
  2. `toxic_food.check_input(query, species)` → 命中即返回硬安全回答
  3. `retrieve(query, species, k=4)`
  4. 拼 prompt（见 §4）
  5. `LLMClient.chat(messages)` 拿原始回答
  6. `toxic_food.check_output(answer, species)`
  7. 写 `logs/rag_trace.jsonl`（见 §5）
  8. 返回 `AnswerResult(text, sources, safety_intervened, retrieved_chunks)`
- [ ] CLI: `python -m rag.qa "Can my dog eat grapes?" --species dog`

### 任务 1.8 — Streamlit 集成（2 h）
- [ ] `app.py` 顶部用 `st.tabs(["Schedule", "Ask PawPal"])`
- [ ] **Schedule tab**：原有逻辑全部保留（不改 `pawpal_system.py`）
- [ ] **Ask PawPal tab**：
  - Pet 选择下拉（从 `owner.pets`，可选 "No specific pet"）
  - 问题输入框 + "Ask" 按钮
  - 调 `rag.qa.answer()` 并渲染：
    - 答案正文
    - `safety_intervened=True` 时顶部红色 banner
    - 引用块：每条 source 显示 `source_path`（短路径）
    - `expander("Show retrieved sources")` 显示原始 chunk 文本（trace 透明性）
    - `caption("Latency: 1.2s · model: gpt-4o-mini")`

### 任务 1.9 — 单元测试（1.5 h）
- [ ] `test_tools.py`：`tools.list_pets` 行为
- [ ] `test_guardrails.py`：≥ 12 条
  - 葡萄 / 狗 → blocked，reason 含 "kidney"
  - 巧克力 / 狗 → blocked
  - 百合 / 猫 → blocked
  - 巧克力关键词在 LLM 输出 → 警示条注入
  - 普通文本（"morning walk"）→ 通过
  - 跨物种（葡萄给猫不在猫黑名单但仍触发通用规则）
- [ ] `test_rag_smoke.py`：mock `LLMClient`，确保 `qa.answer()` 串联检索 + guardrail + log 写入
- [ ] 现有 `tests/test_pawpal.py` 保持全绿

### 任务 1.10 — Eval 脚本（1.5 h）
- [ ] `eval/golden_qa.jsonl` 写 20 条，每条：
  ```json
  {
    "id": "qa-001",
    "query": "Can my dog eat grapes?",
    "species": "dog",
    "must_contain": ["toxic", "kidney"],
    "must_not_contain": ["safe", "small amount is fine"]
  }
  ```
- [ ] 类型分布：8 喂食 / 6 毒性食物 / 4 疫苗 / 2 离题
- [ ] `eval/run_eval.py` 跑全集，输出 `eval/reports/run_<timestamp>.md`：
  - 总通过率
  - 失败用例明细（query / 期望 / 实际）
  - 平均检索耗时 + LLM 耗时
  - 命中 guardrail 的次数

### 任务 1.11 — 文档（1.5 h）
- [ ] 重写 `README.md` 顶部：
  - 一句话 pitch（"PawPal AI = 你已有的领域模型 + RAG 知识问答 + 安全护栏"）
  - 截图 / GIF
  - Setup 5 行命令
- [ ] 加 "Architecture (Phase 1)" 简图段落（mermaid 或 ASCII）
- [ ] 加 "How AI is used" 段：解释 RAG 流程 + guardrail
- [ ] 现有 Schedule 文档保留为 "Domain layer" 小节

**预计总时长：~14 h**，分布到 Week 1 的 5–7 天里。

---

## 4. RAG Prompt 模板（Phase 1 终版）

```
SYSTEM:
You are PawPal, a careful pet-care assistant.

Rules:
1. Use ONLY the context below. If it does not contain the answer,
   reply: "I don't have a verified answer — please consult a vet."
2. Cite each fact with [source N] referencing the numbered context.
3. Never recommend medication dosages.
4. If the user asks about a known toxic food, ALWAYS warn first.

Pet context: species={species}, age={age}

USER:
Question: {query}

Context:
[1] (from {chunk_1.source_path}) {chunk_1.text}
[2] (from {chunk_2.source_path}) {chunk_2.text}
[3] (from {chunk_3.source_path}) {chunk_3.text}
[4] (from {chunk_4.source_path}) {chunk_4.text}

Answer (with [source N] citations):
```

---

## 5. Logging 格式（`logs/rag_trace.jsonl`）

每次 `qa.answer()` 调用追加一条：

```json
{
  "ts": "2026-04-26T18:30:00Z",
  "run_id": "uuid",
  "query": "Can my golden retriever eat grapes?",
  "pet_context": {"species": "dog", "age": 3},
  "preflight": {
    "out_of_scope": false,
    "input_blocked": true,
    "block_reason": "toxic_food:grape"
  },
  "retrieved": [
    {"source": "knowledge/toxic_foods/dogs_toxic_list.md", "score": 0.89}
  ],
  "llm": {
    "model": "gpt-4o-mini",
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "skipped": true
  },
  "postflight": {"safety_intervened": false, "hits": []},
  "answer_chars": 240,
  "duration_ms": 12
}
```

> **注意**：input 命中黑名单时跳过 LLM 调用（省 token + 更快），但仍写一条完整 trace —— 演示和 reflection 都靠它说话。

---

## 6. Setup 步骤（写入 README 的内容）

```bash
# 1. 安装依赖
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. 配置 API key
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY

# 3. 构建知识库索引（第一次必须）
python -m rag.index --rebuild

# 4. 启动应用
streamlit run app.py

# 可选：跑测试 / eval
python -m pytest
python -m eval.run_eval
```

---

## 7. Demo 脚本（验收用，5 分钟）

| 步 | 操作 | 期望看到 |
|----|------|----------|
| 1 | 启动 streamlit，切到 "Ask PawPal" tab | 看到下拉 + 输入框 |
| 2 | 选 Pet "Milo (dog)"，问 "What's a healthy morning routine?" | 带 [source N] 引用的回答；点开 sources 能看到原文片段 |
| 3 | 问 "Can I give my dog grapes?" | 红色 safety banner；不调 LLM；trace 里 `input_blocked=true` |
| 4 | 选 Pet "Luna (cat)"，问 "What vaccines does my kitten need?" | 引用 `vaccines/cat_vaccine_schedule.md` |
| 5 | 问 "What's the stock price of OpenAI?"（离题） | "out-of-scope" 安全回复 |
| 6 | 切回 "Schedule" tab，按以前一样加任务 | 所有原功能仍可用，证明集成无破坏性 |
| 7 | 终端 `tail logs/rag_trace.jsonl` | 看到 5 条结构化 trace |

---

## 8. Definition of Done（Phase 1）

只要下面所有项打钩，Phase 1 就算交付：

- [ ] `streamlit run app.py` 一次启动两个 tab 都正常
- [ ] 5 个真实问题在 demo 里都能拿到合理 + 带引用的回答
- [ ] toxic-food guardrail 在 input 和 output 都被至少一个 test 覆盖
- [ ] `python -m pytest` 全绿，覆盖 ≥ 15 个新测试
- [ ] `python -m eval.run_eval` 跑出 ≥ 80% 通过率（20 条 golden）
- [ ] `logs/rag_trace.jsonl` 每次 query 都有一条
- [ ] 全新虚拟环境按 README 跑一遍能复现
- [ ] 不依赖 internet 之外的服务（除 OpenAI API）
- [ ] `docs/plan/phase1.md` 标记为 ✅ Done

---

## 9. 已知风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| OpenAI API 不稳定 / 限流 | 中 | 中 | `LLMClient` 加 retry + exponential backoff；`mock=True` 让 CI / 单元测试不依赖外网 |
| ChromaDB 在 Streamlit reload 时重复初始化 | 高 | 低 | `@st.cache_resource` 包装 retriever |
| 知识库文档版权 | 中 | 高 | 全部 paraphrase，frontmatter 只标 source URL，不复制原文 |
| Eval 准确率上不去 | 中 | 中 | Phase 1 目标 80%，不追 90%；失败用例反馈给 Phase 2 改进知识库 |
| 时间超支 | 高 | 中 | 任务 1.10（eval）和 1.9 部分测试可砍到 Phase 2 开头补；其它都是核心路径 |
| LLM 不按格式引用 | 中 | 低 | Prompt 强约束 + 后处理正则提取 `[source N]`，缺失 → 标记 low confidence |

---

## 10. 输出给后续 Phase 的接口契约

Phase 1 完成后，下面这些接口要稳定，Phase 2+ 不应破坏：

- `tools.py` 的函数签名稳定（Phase 2 会扩展更多 tool）
- `rag.qa.answer()` 可以被 agent 直接调用作为一个 tool
- `guardrails.toxic_food.scan_text()` 是确定性纯函数，agent 在 add_task 前会调用
- `logs/` 目录约定：`rag_trace.jsonl`（Phase 1）/ `agent_trace.jsonl`（Phase 2）分两个文件
- `pawpal_system.py` 的 `Pet`/`Task`/`Scheduler` 公共 API 不变

---

## 11. 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-04-26 | v1.0 | 初稿；scope 限定为 RAG MVP + 1 条 guardrail |

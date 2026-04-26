# Open Design Questions

> **Status**: Living document — 实施过程中遇到的"还没拍板"的具体问题。
> 每条都列出**选项 / 权衡 / 推荐决策 / 重新决策的触发条件**。
> 决策一旦在代码里 ship，把状态从 🟡 Open 改成 ✅ Decided 并填 commit / phase。
>
> **怎么用这份文档**:
> - 写代码前先扫一遍 → 避免半路被卡住
> - 实施时按"Recommended decision"先走，**不要在这一步过度思考**
> - 真的发现推荐不对 → 改这里 + 改 architecture.md，再改代码
>
> ## Phase 3 落地小结（2026-04, 已实施）
>
> - Q3 — confidence aggregation: 采用 `0.40·grounded + 0.20·actionable + 0.40·safe`
>   （RAG）和 `0.35·complete + 0.25·specific + 0.40·safe`（Plan）；阈值
>   `HIGH=0.85 / MEDIUM=0.60`；`safe < 0.60` 触发 veto，confidence 上限
>   `0.40`（=`SAFE_VETO_FLOOR`）。详见 `pawpal/critic/confidence.py`。
> - Q4 — critic prompt 失败处理: critic 永不抛出。无 API key / mock 模式 / `PAWPAL_DISABLE_CRITIC=1`
>   → 固定 *medium* mock report；JSON parse 失败 → 全 0 分的 *low* report
>   并把错误塞到 `parse_error`。`AnswerResult.critic` / `PlanResult.critic`
>   永远是 `Dict[str, Any]` 形状。
> - 新增 invariant — guardrail vs critic 优先级（plan §3.5 + 测试 `tests/test_critic_priority.py`）：
>   一旦 `safety_intervened or input_blocked` 为真，UI 抑制 confidence badge，
>   只渲染红色 guardrail banner；critic 仍然写进 trace（用于 AUROC 分析）。
> - Plan critic 新增不变量：低置信度时只在表上方加红 banner，**不**折叠
>   diff 表 — 用户必须能看到将要被 Apply 的任务才能做决策。

---

## 索引

| # | 问题 | 状态 | Phase |
|---|------|------|-------|
| Q1 | Agent 路径如何 deepcopy Owner？(`scratch_owner` 隔离) | 🟡 Open | Phase 2 |
| Q2 | 知识库 md 改了之后，谁来重建 ChromaDB？ | 🟡 Open | Phase 1 |
| Q3 | RAG 检索零命中（top score 低）怎么办？ | 🟡 Open | Phase 1 |
| Q4 | `gpt-4o-mini` 不够用时要不要 fallback `gpt-4o`？ | 🟡 Open | Phase 1 |
| Q5 | Pet = "No specific pet" 时，species filter 怎么走？ | 🟡 Open | Phase 1 |

> 后续遇到新问题，**编号往后加**（Q6, Q7…），不要插队，方便引用。

---

## Q1 — Agent 路径如何 deepcopy Owner？

### 背景
`docs/plan/phase2.md` §0 / §3 / §5 任务 2.5 都强调"scratch Owner 模式"：plan 先在 deepcopy 上预演，user 点 Apply 才提交真实 `st.session_state.owner`。
但**怎么 deepcopy**、**Apply 时怎么 merge** 还没敲死。

### 选项

**A. `copy.deepcopy(owner)`，Apply 时整体替换 `st.session_state.owner = scratch`**
- ✅ 简单粗暴，不会半提交
- ❌ 用户在另一个 tab 同时手动加任务，会被 Apply 整体覆盖丢失（race condition）

**B. `deepcopy` + Apply 时 diff（只把"agent 新加的 tasks"merge 回真 owner）**
- ✅ 不会丢 user 在别 tab 的并发改动
- ❌ 实现复杂，需要给每个 Task 一个唯一 ID（dataclass 现在没有）

**C. 不用 deepcopy，agent 直接调真 `Pet.add_task` 但每次先记录 added 列表，Discard 时回滚（remove 这些 task）**
- ❌ 风险最大：guardrail 漏掉一条 toxic-food，rollback 失败就污染了 owner

### 推荐决策（Phase 2 起点）
**方案 A (deepcopy + 整体替换)**，但加 1 条简单守卫：

> 在 user 点 Generate plan 后，UI 上**禁用** Schedule tab 的"Add task"表单（或显示"Plan in progress, wait for Apply or Discard"），把并发问题转成 UX 约束。

**Apply 实现**：
```python
# scratch_owner 是 deepcopy；Apply 时整体替换
st.session_state.owner = scratch_owner
```

**Discard 实现**：什么都不做，scratch_owner 跟着 Streamlit re-run 自动 GC。

### 触发重新决策
- 真的有用户反馈"Apply 把我手动加的任务弄丢了"
- 多用户场景出现（Phase 4 stretch 提到 SQLite 持久化时）

### 落地位置
- `agent/executor.py`：`run()` 开头 `scratch = copy.deepcopy(owner)`
- `app.py` Tab 3：`if scratch_in_progress: disable Tab 1 form`
- 单元测试：`test_apply_replaces_owner`, `test_discard_keeps_owner`

---

## Q2 — 知识库 md 改了之后，谁来重建 ChromaDB？

### 背景
`pawpal/rag/index.py` 是手动跑的 `--rebuild` 脚本。但开发期会反复改 `knowledge/*.md`，**忘记重建索引** = 检索拿到旧文本 = debug 时怀疑 LLM 出问题但其实是 stale index。

### 选项

**A. 永远手动 `python -m pawpal.rag.index --rebuild`**（Phase 1 当前默认）
- ✅ 零代码
- ❌ 容易忘；演示前不重建 = 翻车

**B. 启动 streamlit 时自动检测 mtime 差异，自动重建**
- ✅ 用户零负担
- ❌ 启动慢（首次嵌入 30+ 文档要几秒到几十秒）

**C. 用一个 `.indexed_at` 文件（marker），存最后一次重建时间；启动时对比 `knowledge/**/*.md` 的 max mtime；过期就显示一个 banner 提示用户手动跑**
- ✅ 不阻塞启动；用户有清晰提示
- ❌ 多一个 marker 文件要管

**D. 启动时检测 mtime；过期就阻塞重建一次（带进度条）**
- ✅ 自动 + 不静默
- ❌ 用户改一条 md 就要等 5–30s

### 推荐决策
**方案 C**：
- `pawpal/rag/index.py` 重建后写 `chroma_db/.indexed_at`（unix timestamp）
- `app.py` 启动时（在 `Ask PawPal` tab 顶部）检查 `max(mtime of knowledge/**/*.md) > .indexed_at`
- 过期 → 显示一个 `st.warning("⚠ Knowledge base updated since last index. Run `python -m pawpal.rag.index --rebuild`.")`
- **不自动重建**，让开发者控制时机
- README 顶部写明这条规则

### 触发重新决策
- 开发期发现自己反复忘 → 升级到方案 D
- 部署到 Streamlit Cloud → 必须方案 D（用户没终端）

### 落地位置
- `pawpal/rag/index.py`：rebuild 末尾写 marker
- `app.py`：tab 切到 Ask PawPal 时调一次 `_check_kb_freshness()`

---

## Q3 — RAG 检索零命中怎么办？

### 背景
用户问 "How do I take care of my pet rock?"（既不是离题到拒答，也不在 KB 里）。
`input_filter` 不会拦（"pet" + "care" 看起来正常），retrieve 返回的 top-k 分数都很低（< 0.3），LLM 拿到几乎无关的 context 仍可能 hallucinate。

### 选项

**A. 不管，靠 prompt 强约束 LLM "if context is irrelevant, say I don't know"**
- ❌ 实测 LLM 经常不听话；guardrails 应该是确定性

**B. 在 `pawpal/rag/retrieve.py` 加阈值：如果 top score < 0.4，直接返回空列表**
**C. 在 `pawpal/rag/qa.py` 检查：如果 retrieve 返空 / top_score < 阈值 → 短路返回硬拒答**
- ✅ 确定性、可测试、可解释
- ❌ 阈值要调（0.4 是猜的；不同 embedding 模型 score 分布不同）

**D. 阈值 + LLM 辅助分类（"这个 query 在不在你能回答的范围内"）**
- ❌ 多一次 LLM 调用，方案 C 已经够用了

### 推荐决策
**方案 C** + 一个**可配置阈值**：

```python
# rag/qa.py
RELEVANCE_THRESHOLD = 0.35  # tunable, 在 eval 时调

def answer(query, pet_context):
    chunks = retrieve(query, ...)
    if not chunks or chunks[0].score < RELEVANCE_THRESHOLD:
        return AnswerResult(
            text="I don't have a verified answer for that — please consult a vet.",
            sources=[],
            safety_intervened=False,
            no_retrieval=True,   # 新字段
        )
    # 正常路径
    ...
```

**怎么调阈值**：
- Phase 1 eval golden QA 包含 2 条**离题但合理**的 query（"how to teach my dog calculus"）
- 跑 eval 时观察这两条的 top_score
- 阈值取 (合理 query 的最低 top_score, 离题 query 的最高 top_score) 的中点

### 触发重新决策
- 切换 embedding 模型（score 分布会变）
- eval 出现 "应该答的没答"（false negative）→ 调低阈值

### 落地位置
- `pawpal/rag/qa.py`：`RELEVANCE_THRESHOLD` 常量 + 短路逻辑
- `eval/golden_qa.jsonl`：加 2–3 条"离题但合理 / 离题不合理"的边界用例
- 单元测试：`test_qa_short_circuits_on_low_score` (mock retrieve 返回 score=0.1 的结果)

---

## Q4 — `gpt-4o-mini` 不够用时要不要 fallback `gpt-4o`？

### 背景
默认全部用 `gpt-4o-mini`（成本 $0.15/$0.60 per 1M tokens，相比 `gpt-4o` 便宜 ~10×）。
作业 demo 用 mini 通常够，但万一某些复杂 plan / 多步推理出问题，是否要 fallback？

### 选项

**A. 永远 mini**，不达标就改 prompt
- ✅ 成本可控、reproducibility 好
- ❌ 万一上限就是 mini 的能力上限呢？

**B. mini 作默认，critic 给 confidence 低（< 0.5）时**自动重跑一次用 `gpt-4o`
- ✅ 智能 fallback；多数请求成本不变
- ❌ 实现 + 测试复杂；增加延迟

**C. 暴露一个 `model_tier` 配置（"economy" / "quality"），用户选**
- ✅ 给 demo 时用 quality；平时 economy
- ❌ 多一个开关；reflection 要解释

### 推荐决策
**方案 A 优先**，**方案 C 作为备份**（仅在 Phase 4 eval 不达标时启用）：

- Phase 1–3 全部 `gpt-4o-mini` 写死
- 在 `pawpal/llm_client.py` 暴露 `model: str = "gpt-4o-mini"` 参数
- Phase 4 §6 不达标补救路径里写明："如果 golden QA < 90%，最后手段升 `gpt-4o`，预算允许时启用"
- **不写 critic-driven auto fallback**（方案 B），太复杂、收益不明确

### 触发重新决策
- Phase 4 跑出来 mini 数据明显不行（< 80%）
- 教师在 demo 时质疑能力上限

### 落地位置
- `pawpal/llm_client.py`：`def chat(self, messages, model="gpt-4o-mini", ...)`
- `eval/run_eval.py`：加 `--model` flag，方便对比 mini vs 4o
- README 写明默认模型

---

## Q5 — Pet = "No specific pet" 时，species filter 怎么走？

### 背景
"Ask PawPal" tab 的 Pet 下拉有一项 "No specific pet"。
`pawpal/rag/retrieve.py` 签名是 `retrieve(query, species: str | None = None)`。
`species=None` 时 retrieve 行为没敲死。

### 选项

**A. species=None 时，不加任何 metadata filter**（检索全库）
- ✅ 命中最多
- ❌ 用户问"我的狗能吃葡萄吗"但忘选 Pet → 命中可能掺杂猫 / 鸟的内容，回答可能错乱

**B. species=None 时，**强制要求**用户选 Pet 才能问** —— UI 上 Pet 必填
- ✅ 干净
- ❌ "What's a good general pet-care routine?" 这种合理问题就问不了

**C. species=None 时，只检索 `species=general` 的文档**（KB 里有一类专门写"通用宠物原则"的文档）
- ✅ 精准；没污染
- ❌ KB 里要专门维护 `general` 分类

**D. species=None 时，检索全库 + 在 prompt 里告诉 LLM "no specific pet selected, answer generally"**
- ✅ 灵活
- ❌ 跨物种污染风险

### 推荐决策
**方案 C + 方案 A 的混合**：

```python
def retrieve(query, species: str | None, k: int = 4):
    if species is None:
        where = {"species": "general"}
    else:
        # species 有值：拿这个物种 + general 通用原则
        where = {"species": {"$in": [species, "general"]}}
    return chroma.query(query, where=where, n_results=k)
```

**KB 约定**：
- `knowledge/general/*.md` → frontmatter `species: general`
- `knowledge/feeding/dog_*.md` → frontmatter `species: dog`
- 通用原则（"任何宠物都需要清洁水"）放 `general/`
- 物种特异性内容（葡萄对狗有毒）放对应物种目录

**UI 行为**：
- "No specific pet" 选项保留
- 如果 retrieve 返空 / score 低（→ Q3 路径），UI 显示 banner "💡 Tip: select a specific pet for better results"

### 触发重新决策
- 用户经常 "No specific pet" 但拿不到有用回答 → 改方案 D
- KB 里 general 文档不好维护 → 改方案 B（强制选 pet）

### 落地位置
- `pawpal/rag/retrieve.py`：上面的 where clause 逻辑
- `knowledge/general/`：Phase 1 至少 2 篇通用原则文档
- `app.py` Tab 2：retrieve 返空时显示 banner
- 单元测试：`test_retrieve_no_species_uses_general_only`

---

## 决策 cheat-sheet（快速回查）

把上面 5 条压成一段代码可读的伪代码：

```python
# Q1: Agent scratch Owner
scratch_owner = copy.deepcopy(real_owner)
# Apply: st.session_state.owner = scratch_owner (整体替换)
# Discard: do nothing, GC 自动清

# Q2: KB 索引新鲜度
if max_mtime(knowledge/**/*.md) > read(.indexed_at):
    st.warning("Run rag.index --rebuild")

# Q3: 零命中
if not chunks or chunks[0].score < 0.35:
    return AnswerResult(text="I don't have a verified answer...",
                        no_retrieval=True)

# Q4: 模型
default_model = "gpt-4o-mini"  # Phase 1-3
fallback_model = "gpt-4o"      # Phase 4 不达标时手动启用

# Q5: species filter
where = ({"species": "general"} if species is None
         else {"species": {"$in": [species, "general"]}})
```

---

## 添加新问题的模板

```markdown
## Q? — 一句话标题

### 背景
（一段，问题怎么浮出来的）

### 选项
**A. ...** ✅/❌
**B. ...** ✅/❌
**C. ...** ✅/❌

### 推荐决策
**方案 X**：（实现要点）

### 触发重新决策
- 条件 1
- 条件 2

### 落地位置
- 文件 / 函数 / 测试
```

---

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-04-26 | 初始 Q1–Q5；全部 🟡 Open |

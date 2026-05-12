---
task_id: KS-RETRIEVAL-005
phase: Retrieval
wave: W6
depends_on: [KS-COMPILER-013]
files_touched:
  - knowledge_serving/serving/structured_retrieval.py
  - knowledge_serving/tests/test_struct_retrieval.py
artifacts:
  - knowledge_serving/serving/structured_retrieval.py
  - knowledge_serving/tests/test_struct_retrieval.py
s_gates: [S2, S3, S4]
plan_sections:
  - "§4.3"
  - "§6.7"
  - "§2 governance fields"
writes_clean_output: false
ci_commands:
  - test -f knowledge_serving/audit/validate_serving_governance.report
  - python3 -c "from knowledge_serving.serving.structured_retrieval import _assert_governance_report_green; _assert_governance_report_green()"
  - python3 -m pytest knowledge_serving/tests/test_struct_retrieval.py -v
status: not_started
---

# KS-RETRIEVAL-005 · structured_retrieval（结构化召回 / 13 步召回流程第 7 步）

## 1. 任务目标

- **业务 / business**：实现 §6.7「结构化召回 / structured retrieval」——从 4 个候选 view（`pack_view` / `content_type_view` / `play_card_view` / `runtime_asset_view`）按租户允许的 `brand_layer` 与 `retrieval_policy_view` 的 (intent, content_type) 策略行筛出**可被 LLM 消费的结构化候选集合**。
- **工程 / engineering**：在 W6 波次落地纯函数 `structured_retrieve(...)`，**消费 KS-COMPILER-013 已 S1-S7 全绿的 view**，对其再做一层运行期租户隔离 + 默认 active-only + granularity 合法性校验，输出按 view 名分组的候选行。
- **S gate**：
  - S2 `gate_filter`（默认只召 `gate_status=active`）
  - S3 `brand_layer_scope`（运行期硬切 `brand_layer ∈ allowed_layers`）
  - S4 `granularity_integrity`（仅允许 L1/L2/L3）
- **非目标 / non-goals**：
  - 不做向量召回（→ KS-RETRIEVAL-006）
  - 不做 brand overlay 召回（→ KS-RETRIEVAL-006/007）
  - 不做 merge / rerank（→ KS-RETRIEVAL-007）
  - 不做 fallback 决策（→ KS-RETRIEVAL-007）
  - 不调 LLM 做判断
  - 不写 `clean_output/`

## 2. 前置依赖

### 2.1 KS-COMPILER-013 作为 W6 强制前置门禁 / mandatory upstream gate

KS-COMPILER-013（治理总闸 / S1-S7 master gate，W5）是本卡**唯一硬前置**：

| 维度 | 要求 |
|---|---|
| KS-COMPILER-013 status | 必须为 `done`（见 `task_cards/dag.csv` 第 28 行） |
| 治理报告产物 | `knowledge_serving/audit/validate_serving_governance.report` 必须存在 |
| S 门状态 | S1-S7 必须全部 `PASS`（任何 FAIL → 本卡 fail-closed，不允许放行） |
| 4 个被消费 view 的契约 | `pack_view` / `play_card_view` / `runtime_asset_view` 行的 `source_pack_id` 已通过 S1 反查 `clean_output/candidates/**`；`content_type_view` 行的 `source_pack_id` 已通过 S1 非空校验（synthetic `CT-<canonical>` ID 不反查 candidates）；所有行 `brand_layer / gate_status / granularity_layer` 已通过 S2/S3/S4 校验 |

**为什么把 KS-COMPILER-013 设为前置门禁**：本卡是「读 view → 返回行」的 thin retrieval，**不应在 retrieval 层重做 governance**。如果 view 本身 governance 不可信，召回再正确也是污染上游；必须由 KS-COMPILER-013 在编译期保证 view 干净，retrieval 才能只做轻量 runtime 过滤。

**preflight 强制项（fail-closed）**：模块加载或测试初始化时必须先：

```python
# 真实报告格式：
#   [S1 source_traceability]
#   status: pass
# preflight 必须按 section header + status 解析，不能用单行 grep
report_path = Path("knowledge_serving/audit/validate_serving_governance.report")
if not report_path.exists():
    raise RuntimeError("KS-COMPILER-013 治理报告缺失，禁止结构化召回")
sections = _parse_gate_sections(report_path.read_text())
for gate in ("S1", "S2", "S3", "S4", "S5", "S6", "S7"):
    if sections.get(gate) != "pass":
        raise RuntimeError(f"KS-COMPILER-013 {gate} 未通过 (status={sections.get(gate)})，禁止结构化召回")
```

> 即使报告里 S1-S7 是 PASS，也必须**不假设跨时间窗状态连续**（参见 core error pattern E7）——pytest 启动时按上述代码即时再读一次报告，不缓存。

### 2.2 同波次输入（不构成依赖，但运行时必须可用）

| 来源 | 用途 |
|---|---|
| KS-RETRIEVAL-001 的 `tenant_scope_resolver` 输出 | 提供 `allowed_layers: list[str]`（如 `["domain_general", "brand_faye"]`），调用方传入，本卡**禁止**自行解析 tenant |
| KS-RETRIEVAL-002/003 的 `intent` / `content_type` 入参 | `input-first / no-LLM` 模式：必须由调用方显式提供，本卡**禁止**从 user_query 推断 |

## 3. 输入契约

### 3.1 函数签名（硬约束）

```python
def structured_retrieve(
    *,
    intent: str,                  # 来自 KS-RETRIEVAL-002，已枚举校验
    content_type: str,            # canonical id（如 "behind_the_scenes"），来自 KS-RETRIEVAL-003
    allowed_layers: list[str],    # 来自 KS-RETRIEVAL-001，已 resolve
    views_root: Path = Path("knowledge_serving/views"),
    policy_path: Path = Path("knowledge_serving/control/retrieval_policy_view.csv"),
    include_inactive: bool = False,  # S2 例外开关，默认 False
) -> dict[str, list[dict]]:
    ...
```

**禁止出现的形参**：`user_query`、`tenant_id`、`api_key`、`brand_layer`（单数）、`llm_*`、`prompt`。

### 3.2 读

| 文件 | 行数（W5 实测） | 用途 |
|---|---|---|
| `knowledge_serving/views/pack_view.csv` | 1362 | L1 主候选 |
| `knowledge_serving/views/content_type_view.csv` | 19 | content_type 元信息 |
| `knowledge_serving/views/play_card_view.csv` | 59 | L2 play card |
| `knowledge_serving/views/runtime_asset_view.csv` | 25 | L3 runtime asset |
| `knowledge_serving/control/retrieval_policy_view.csv` | 18+ | 策略路由 |
| `knowledge_serving/audit/validate_serving_governance.report` | — | preflight 报告 |

### 3.3 不读

- `clean_output/**`（真源 / SSOT，retrieval 不直读）
- `knowledge_serving/views/brand_overlay_view.csv`（属 KS-RETRIEVAL-006）
- `knowledge_serving/views/evidence_view.csv`（属合并阶段引用，不属结构化召回）
- `knowledge_serving/views/generation_recipe_view.csv`（属 KS-RETRIEVAL-004）

### 3.4 retrieval_policy_view.csv 字段语义（plan §4.3）

| 列 | 本卡用法 |
|---|---|
| `intent` | 与入参精确匹配（如 `generate`） |
| `content_type` | 与入参精确匹配（canonical id） |
| `required_views` | JSON 数组，必召；缺即拿不到候选 |
| `optional_views` | JSON 数组，可选召回 |
| `structured_filters_json` | JSON 对象，列名→允许值列表（如 `{"coverage_status": ["complete", "partial"]}`） |
| `vector_filters_json` | **本卡不用**（属 KS-RETRIEVAL-006） |
| `max_items_per_view` | int，每 view 上限 |
| `rerank_strategy` | **本卡不用** |
| `merge_precedence_policy` | **本卡不用** |
| `timeout_ms` | 透传给调用层，**本卡 csv 读取阶段不超时** |

## 4. 执行步骤

1. **preflight**（§2.1 fail-closed 校验，缺一即抛）。
2. **入参校验**：`intent` / `content_type` 非空；`allowed_layers` 非空且元素 ∈ `{"domain_general"} ∪ {"brand_<name>"}`（regex 校验）；`include_inactive=True` 时必须显式声明（参数名匹配 + 调用栈记录到日志）。
3. **policy 查找**：从 `retrieval_policy_view.csv` 用 `(intent, content_type)` 精确匹配单行；命中 0 行 → `raise RetrievalPolicyNotFound`；命中 >1 行 → `raise RetrievalPolicyAmbiguous`（policy 表设计上 (intent, content_type) 应唯一）。
4. **解析 view 列表**：`views = required_views + optional_views`，4 个目标 view 之外的引用（如 `brand_overlay_view`）忽略（不归本卡）。
5. **逐 view 加载 + 过滤**（按以下顺序，policy 与 governance 冲突时**governance 胜出**）：
   1. **S3 brand_layer hard filter**：`row.brand_layer ∈ allowed_layers`
   2. **S2 gate_status filter**：默认 `row.gate_status == "active"`；`include_inactive=True` 时不过滤
   3. **S4 granularity filter**：`row.granularity_layer ∈ {"L1", "L2", "L3"}`（L4+ 即使存在也丢弃）
   4. **structured_filters_json 应用**（跨 view 全集策略，per-view skip-if-missing）：对 JSON 中每个 `(column, allowed_values)`，若 `column ∈ view.schema` 则要求 `row[column] ∈ allowed_values`；若 `column ∉ view.schema` 则该 view 跳过该 filter（**真实 policy 语义**：如 `coverage_status` 列只存在于 `content_type_view`，policy 行写一份跨 view 全集，每 view 各自适配）
6. **截断**：每 view 保留前 `min(max_items_per_view, len(filtered))` 行；负数或 0 → `raise`；> 1000 → 警告并 cap 至 1000。
7. **输出**：

```python
{
  "pack_view": [{...row...}, ...],
  "content_type_view": [...],
  "play_card_view": [...],
  "runtime_asset_view": [...],
  "_meta": {
    "policy_row": {...},
    "allowed_layers": [...],
    "include_inactive": False,
    "preflight_report_sha256": "...",
  }
}
```

8. **绝对不做**：写 csv / 写 clean_output / 调 LLM / 解析 user_query / 修改入参字段。

## 5. 执行交付

| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `knowledge_serving/serving/structured_retrieval.py` | py | 是 | 是 | — |
| `knowledge_serving/tests/test_struct_retrieval.py` | py | 是 | 是 | — |
| pytest report (CI) | text | 否（运行证据） | 否 | 是 |

## 6. 对抗性 / 边缘性测试（≥ 12 case，强制覆盖）

| # | 测试 | 期望 |
|---|---|---|
| T1 | `allowed_layers=["domain_general","brand_faye"]` 请求，view fixture 含 `brand_xyz` 行 | 返回 0 `brand_xyz` 行（跨租户串味 = 阻断项） |
| T2 | view fixture 中混入 `gate_status="inactive"` 行，默认调用 | 默认 0 命中 |
| T3 | 同 T2，`include_inactive=True` | inactive 行可召回 |
| T4 | 注入 `granularity_layer="L4"` 行 | 丢弃，不返回 |
| T5 | `(intent, content_type)` 在 policy 表无命中 | `raise RetrievalPolicyNotFound` |
| T6 | `(intent, content_type)` 在 policy 表 2 行 | `raise RetrievalPolicyAmbiguous` |
| T7 | `structured_filters_json` 引用的列在 view schema 不存在 | 该 view 跳过该 filter（per-view skip-if-missing），其余 governance 过滤照常生效 |
| T8 | 空 view（合法 schema、0 数据行） | 返回 `[]`，不抛 |
| T9 | `max_items_per_view=0` 或负数 | raise |
| T10 | `max_items_per_view=99999` | 警告并 cap 1000 |
| T11 | 删除 `validate_serving_governance.report` 后调用 | preflight fail-closed raise |
| T12 | 篡改 report，使 `S3: FAIL` | preflight fail-closed raise |
| T13 | 函数签名含 `user_query=` | 测试用 `inspect.signature` 断言不存在 |
| T14 | 函数体 grep `anthropic\|openai\|llm\|prompt` | 0 命中 |
| T15 | 重复调用同入参 | 输出严格相等（确定性，无随机） |

## 7. 治理语义一致性

- **S2 active-only 默认**：与 plan §2 第 5 条「Two failure modes ... active 是默认」一致。
- **S3 brand_layer hard filter**：与 CLAUDE.md「多租户隔离硬纪律」一致——`brand_layer` 是**租户隔离 key 不是分类标签**。
- **S4 granularity**：与 plan §2 一致，L4+ 不进生产 view。
- **input-first / no-LLM**：与 §6.2/§6.3 (2026-05-12 用户裁决) 一致，intent/content_type 由上游显式给。
- **不写 clean_output**：frontmatter `writes_clean_output: false`，CI 检查 `git diff --stat clean_output/` 应为空。
- **可重建（R4）**：模块为纯函数，相同入参 + 相同 view csv → byte-identical 输出。

## 8. CI 门禁

```
command:
  1) test -f knowledge_serving/audit/validate_serving_governance.report
  2) python3 -c "from knowledge_serving.serving.structured_retrieval import _assert_governance_report_green; _assert_governance_report_green()"（KS-COMPILER-013 前置门禁体外校验）
  3) python3 -m pytest knowledge_serving/tests/test_struct_retrieval.py -v
pass:
  - 前置 2 个 shell 检查 exit 0（report 存在 + S1-S7 PASS）
  - pytest passed >= 12 case，skip=0，failed=0
failure_means:
  - 报告缺失 / S 门失守 → KS-COMPILER-013 退回处理，本卡阻断
  - 任一对抗测试失败 → 结构化召回不可信，禁止下游 KS-RETRIEVAL-007 启动
artifact: pytest report + 本次 preflight 校验日志（记录 report sha256）
```

E2 防假绿（参见 core error pattern）：`exit 0` 不等于通过——CI 必须断言 `passed >= 12 and skipped == 0`，否则视为 `fail + unverified`。

## 9. CD / 环境验证

不部署。本卡是纯库模块，由 KS-RETRIEVAL-009（demo 总装）统一接入运行环境。

## 10. 独立审查员 Prompt

> 你是 KS-RETRIEVAL-005 的独立审查员。请按顺序执行：
>
> 1. **前置门禁核验**：检查 `task_cards/dag.csv` 中 `KS-COMPILER-013` 的 status 是否为 `done`；读 `knowledge_serving/audit/validate_serving_governance.report` 确认 S1-S7 全 PASS；任一不满足 → 直接 fail。
> 2. **跨租户串味测试**：构造 `allowed_layers=["domain_general","brand_a"]` 入参，view fixture 含 brand_b 行；调用必须返回 0 brand_b 行。
> 3. **active 默认测试**：fixture 含 inactive 行；默认调用 0 命中；`include_inactive=True` 时可命中。
> 4. **granularity 守门**：注入 L4 行；调用必须丢弃。
> 5. **函数签名审计**：`inspect.signature(structured_retrieve).parameters` 不得含 `user_query`、`tenant_id`、`brand_layer`、`prompt`。
> 6. **LLM 调用审计**：`grep -E "anthropic|openai|llm|prompt" knowledge_serving/serving/structured_retrieval.py` 必须 0 命中。
> 7. **可重建审计**：两次相同入参调用，输出 `dict` 严格相等（含 `_meta.preflight_report_sha256`）。
> 8. **clean_output 不变审计**：跑完测试后 `git diff --stat clean_output/` 必须为空。
>
> 任一阻断项失守 → 整卡 fail。**阻断项清单**：跨租户串味；inactive 默认命中；L4 命中；preflight 静默通过；函数签名含禁用形参；LLM 调用；写真源。

## 11. DoD

- [ ] `structured_retrieval.py` 入 git
- [ ] `test_struct_retrieval.py` 含 ≥ 12 case 全绿（passed≥12 / skipped=0 / failed=0）
- [ ] `validate_serving_governance.report` 已存在且 S1-S7 全 PASS（preflight 通过）
- [ ] dag.csv 中本卡 status 从 `not_started` → `done`
- [ ] 独立审查员 pass（8 项全部 pass）
- [ ] `git diff --stat clean_output/` 跑完后为空
- [ ] frontmatter `writes_clean_output: false` 未被改动

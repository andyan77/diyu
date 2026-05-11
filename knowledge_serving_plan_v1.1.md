# Knowledge Context Compiler + Retrieval Router 实施方案 v1.1

> 版本：v1.1 · 落盘日期：2026-05-11 · 状态：方案稿，未进入实施
> 定位：`clean_output/` 之后的下一层 serving 工程规范，**不替代** `clean_output/` 真源
> 落盘前提：必须先完成 Phase 0（S0 基线收口），细节见 §附件 A

## 0. 定位

本中间件不是第二套业务库，而是一个遵守 **4 闸门 / 9 张表 / 三分层 / 多租户隔离** 的 **Knowledge Context Compiler + Retrieval Router**。

它负责把 `clean_output/` 中已合规的知识，编译成第三方应用可消费的上下文包，并在运行时完成租户隔离、召回、降级、合并、证据追溯与日志回放。

核心边界：

- `clean_output/` 是知识真源。
- `knowledge_serving/` 是派生读模型，可重编译、可删除重建。
- Dify / Agent / ECS API 只消费 `retrieve_context()` 返回的 `context_bundle`。
- Agent 不直接查 9 表。

---

## 1. 总体架构

```text
clean_output/
  candidates/              # YAML 真源候选包
  nine_tables/             # 9 表 canonical graph
  play_cards/              # L2 register
  runtime_assets/          # L3 register
  audit/                   # 4 闸门、三分层、证据账本

        ↓ compile

knowledge_serving/
  views/                   # 7 个 serving views
  control/                 # 5 个控制表（含 context_bundle_log 唯一写入表）
  policies/                # 召回、降级、合并、guardrail 策略
  vector_payloads/         # Qdrant chunks + payload
  logs/                    # 回归样本与调试日志，不重复存 context_bundle_log
  schema/                  # view schema + context bundle schema
  scripts/                 # 编译、校验、导出、回归测试

        ↓ retrieve_context()

Dify Chatflow / Agent / ECS API
        ↓
LLM
```

---

## 2. 必须继承的治理字段

每一条投喂给 LLM 的上下文都必须保留以下 `governance_common_fields`：

```text
source_pack_id
brand_layer
granularity_layer          # L1 / L2 / L3
gate_status                # active only by default
source_table_refs
evidence_ids
traceability_status
default_call_pool
review_status
compile_run_id
source_manifest_hash
view_schema_version
chunk_text_hash            # vector chunk 必须具备
```

微调点：新增 `compile_run_id / source_manifest_hash / view_schema_version / chunk_text_hash`，用于生产回放与漂移定位。

继承规则：

- 7 个 serving views 的正式 schema = `governance_common_fields` + 各 view 业务字段。
- 下文各 view 小节只列业务字段摘要，不代表可以省略治理字段。
- `chunk_text_hash` 仅对 `vector_payloads/qdrant_chunks.jsonl` 强制；结构化 view 行必须具备可回放的 `row_hash` 或由 `source_pack_id + view_schema_version + compile_run_id` 唯一确定。
- `default_call_pool` 对非 L2 / 非可调用资产默认 `false`，不得空缺。

---

## 3. 7 个 Serving Views

### 3.1 pack_view

管"知识是什么"。适合最小知识单元调用。

核心字段：

```text
pack_id
pack_type
brand_layer
granularity_layer
knowledge_title
knowledge_assertion
applicable_when
success_scenario
flip_scenario
alternative_boundary
content_type_tags
object_type_tags
source_pack_id
source_table_refs
evidence_ids
gate_status
embedding_text
compile_run_id
source_manifest_hash
```

### 3.2 content_type_view

管"要生产哪类内容"。

核心字段：

```text
content_type
canonical_content_type_id
aliases
production_mode
north_star
default_output_formats
default_platforms
recommended_persona_roles
risk_level
brand_overlay_required_level   # none / soft / hard
required_knowledge_layers       # L1 / L2 / L3
forbidden_patterns
source_pack_ids
coverage_status                 # complete / partial / missing
```

微调点：增加 `canonical_content_type_id / aliases / coverage_status`，解决 18 种 ContentType 命名差异与覆盖缺口。

### 3.3 generation_recipe_view

管"这类内容怎么组装"。

核心字段：

```text
recipe_id
content_type
output_format
platform
intent_scope
required_views
retrieval_plan_json
step_sequence_json
context_budget_json
fallback_policy_id
guardrail_policy_id
merge_policy_id
business_brief_schema_id
```

微调点：增加 `business_brief_schema_id`，避免 LLM 编造商品事实。

### 3.4 play_card_view

管"用什么玩法"。

核心字段：

```text
play_card_id
pack_id
content_type
hook
production_tier
production_difficulty
duration
default_call_pool
steps_json
anti_pattern
applicable_when
success_scenario
alternative_boundary
completeness_status
source_pack_id
source_table_refs
evidence_ids
```

### 3.5 runtime_asset_view

管"拿什么可执行素材"。

核心字段：

```text
runtime_asset_id
pack_id
asset_type
title
summary
content_pointer
asset_payload_json
brand_layer
granularity_layer
source_pack_id
source_pointer
traceability_status
```

### 3.6 brand_overlay_view

管"这个品牌怎么变形"。

核心字段：

```text
overlay_id
brand_layer
brand_overlay_kind        # brand_voice / founder_persona / team_persona_overlay / content_type_overlay
target_content_type
target_pack_id
tone_constraints_json
output_structure_json
required_knowledge_json
forbidden_words
signature_phrases
precedence
fallback_behavior
source_pack_id
evidence_ids
```

### 3.7 evidence_view

管"为什么可信"。

核心字段：

```text
evidence_id
source_pack_id
source_md
source_anchor
evidence_quote
source_type
inference_level
trace_quality
line_no
brand_layer
source_table_refs
adjudication_status
```

---

## 4. 5 个 Control Tables

### 4.1 tenant_scope_registry

管租户隔离。

```text
tenant_id
api_key_id
brand_layer
allowed_layers
default_platforms
policy_level
enabled
environment             # dev / staging / prod
```

原则：品牌层只能从登录租户或 API key 推断，禁止从用户自然语言猜品牌。

### 4.2 field_requirement_matrix

管缺字段时能否降级。

```text
content_type
field_key
required_level             # none / soft / hard
fallback_action            # use_domain_general / neutral_tone / ask_user / block_brand_output
ask_user_question
block_reason
```

典型规则：

```text
product_review.brand_tone        soft  → 可降级通用语气
store_daily.team_persona         soft  → 可用通用门店人设
founder_ip.founder_profile       hard  → 不可编造创始人内容
brand_manifesto.brand_values     hard  → 阻断品牌化成稿
```

### 4.3 retrieval_policy_view

管什么问题查哪些 view。

```text
intent
content_type
required_views
optional_views
structured_filters_json
vector_filters_json
max_items_per_view
rerank_strategy
merge_precedence_policy
timeout_ms
```

### 4.4 merge_precedence_policy

管通用层和品牌层冲突时听谁的。

```text
target_type
conflict_key
precedence_order           # brand_<name> > domain_general
conflict_action            # override / append / block / needs_review
allow_override
```

### 4.5 context_bundle_log

管每次到底喂给 LLM 了什么。

唯一 canonical 写入位置：`knowledge_serving/control/context_bundle_log.csv`。`knowledge_serving/logs/` 只存调试输出、回归样本和非 canonical 运行日志，禁止再放同名 `context_bundle_log.csv`，避免 S8 回放时出现双真源。

```text
request_id
tenant_id
resolved_brand_layer        # tenant_scope_resolver 输出，形如 brand_faye；不同于 tenant_id
allowed_layers
user_query_hash
classified_intent
content_type
selected_recipe_id
retrieved_pack_ids
retrieved_play_card_ids
retrieved_asset_ids
retrieved_overlay_ids
retrieved_evidence_ids
fallback_status
missing_fields
blocked_reason
context_bundle_hash
final_output_hash
compile_run_id
source_manifest_hash
view_schema_version
embedding_model
embedding_model_version
rerank_model
rerank_model_version
llm_assist_model
model_policy_version
created_at
```

微调点：`user_query` 建议默认存 hash 或脱敏摘要，避免泄露用户数据。

---

## 5. 核心 API

```python
retrieve_context(
  tenant_id,
  user_query,
  content_type=None,
  platform=None,
  output_format=None,
  fallback_mode=None,
  business_brief=None,
) -> context_bundle
```

返回结构：

```json
{
  "request_id": "ctx_001",
  "tenant_id": "tenant_faye_main",
  "resolved_brand_layer": "brand_faye",
  "allowed_layers": ["domain_general", "brand_faye"],
  "content_type": "product_review",
  "recipe": {},
  "business_brief": {},
  "domain_packs": [],
  "play_cards": [],
  "runtime_assets": [],
  "brand_overlays": [],
  "evidence": [],
  "missing_fields": [],
  "fallback_status": "brand_partial_fallback",
  "generation_constraints": [],
  "governance": {
    "gate_policy": "active_only",
    "granularity_layers": ["L1", "L2", "L3"],
    "traceability_required": true,
    "compile_run_id": "cr_20260511_001",
    "source_manifest_hash": "..."
  }
}
```

---

## 6. 召回流程

1. `tenant_scope_resolver`
   从登录租户/API key 确定 `allowed_layers`。

2. `intent_classifier`
   判断用户要做内容生成、质检、策略建议、培训、接客话术等。

3. `content_type_router`
   映射到 canonical ContentType。

4. `business_brief_checker`
   检查商品事实、活动事实、平台目标是否足够。

5. `recipe_selector`
   从 `generation_recipe_view` 选生产配方。

6. `requirement_checker`
   查 `field_requirement_matrix`。

7. `structured_retrieval`
   查 `content_type_view / pack_view / play_card_view / runtime_asset_view`。

8. `vector_retrieval`
   查 Qdrant，必须带 payload filter：

```json
{
  "brand_layer": {"$in": "$allowed_layers"},
  "gate_status": "active",
  "granularity_layer": {"$in": ["L1", "L2", "L3"]}
}
```

9. `brand_overlay_retrieval`
   只允许 `tenant_scope_resolver` 得出的 `resolved_brand_layer`，禁止从用户自然语言覆盖品牌层。

10. `merge_context`
   `domain_general` 提供底座，`brand_<name>` 覆盖、补充、约束。

11. `fallback_decider`
   输出 `fallback_status`。

12. `context_bundle_builder`
   生成 LLM 可用上下文包。

13. `log_writer`
   写 `knowledge_serving/control/context_bundle_log.csv`。

---

## 7. 降级策略

降级必须显式落盘，不交给 LLM 自由发挥。

```text
brand_full_applied
  品牌层字段齐全，输出品牌化内容

brand_partial_fallback
  品牌层部分缺失，输出"通用结构 + 轻品牌语气"

domain_only
  品牌层无对应知识，输出通用合格内容

blocked_missing_required_brand_fields
  强品牌内容缺核心字段，不生成品牌化成稿，只给结构稿/采集问题

blocked_missing_business_brief
  缺 SKU / 商品 / 活动 / 平台目标等事实，不生成最终稿
```

---

## 8. 向量库设计

Qdrant 不存裸文本大杂烩，只存编译后的 context chunks。

payload 至少包含：

```json
{
  "view_type": "play_card_view",
  "source_pack_id": "...",
  "brand_layer": "domain_general",
  "granularity_layer": "L2",
  "content_type": "product_review",
  "pack_type": "service_judgment",
  "gate_status": "active",
  "default_call_pool": true,
  "evidence_ids": ["..."],
  "compile_run_id": "...",
  "chunk_text_hash": "...",
  "embedding_model": "...",
  "embedding_model_version": "...",
  "embedding_dimension": 0,
  "index_version": "..."
}
```

必须支持：

- 结构化 filter + 语义相似双召回。
- Qdrant 不可用时走 structured-only fallback。
- embedding model 变更时强制重建 index。
- chunk hash 用于回放。

---

## 9. 模型依赖与边界

中间件可以涉及 embedding / rerank / LLM，但三者地位不同：

```text
embedding
  必需。用于离线生成 qdrant_chunks 向量，以及运行时生成 query embedding。

rerank
  建议支持，但第一阶段不是硬依赖。关闭时必须能走结构化排序 + 向量分数排序。

LLM assist
  可选。只能做辅助判断，不能做治理裁决，不能在中间件内生成最终内容。
```

### 9.1 model_policy.yaml

模型依赖必须显式落盘到 `knowledge_serving/policies/model_policy.yaml`：

```yaml
model_policy_version: "mp_20260511_001"

embedding:
  provider: ""
  model: ""
  model_version: ""
  dimension: 0
  used_for:
    - qdrant_chunk_embedding
    - query_embedding
  rebuild_required_when_changed: true

rerank:
  enabled: true
  provider: ""
  model: ""
  model_version: ""
  top_k_before: 30
  top_k_after: 8
  fallback_when_unavailable: vector_score_then_structured_priority

llm_assist:
  enabled: false
  provider: ""
  model: ""
  model_version: ""
  allowed_tasks:
    - intent_classification
    - content_type_routing
    - quality_check
    - semantic_guardrail_judge
  forbidden_tasks:
    - tenant_scope_resolution
    - brand_layer_override
    - fallback_policy_decision
    - merge_precedence_decision
    - evidence_fabrication
    - final_generation
```

### 9.2 硬边界

- `tenant_scope_resolver`、`brand_layer` hard filter、`gate_status=active`、`field_requirement_matrix`、`fallback_policy`、`merge_precedence_policy` 必须是确定性逻辑，不得交给 LLM。
- embedding 模型与 query embedding 模型必须同源同维度，或在 `model_policy.yaml` 中声明兼容关系。
- rerank 只能重排中间件已经召回且已通过 tenant/gate/filter 的候选，不得扩展召回范围。
- LLM assist 的输出只能作为候选判断，必须被规则节点复核后才能进入 context bundle。
- 最终文案生成仍由 Dify LLM 节点完成，中间件只返回已治理的 `context_bundle`。

### 9.3 日志要求

`context_bundle_log` 必须记录：

```text
embedding_model
embedding_model_version
rerank_model
rerank_model_version
llm_assist_model
model_policy_version
```

如果 rerank 或 LLM assist 未启用，对应字段填 `disabled`，不得留空。

---

## 10. Dify 编排建议

Dify Chatflow 主控，Agent 只做局部判断。

Chatflow nodes:

1. 租户识别
2. 意图分类
3. ContentType 路由
4. business brief 检查
5. 调用 `retrieve_context`
6. 判断 `fallback_status`
7. LLM 生成
8. Guardrail 校验
9. 输出 + evidence 摘要
10. 写日志

Agent node 只允许：

- 辅助判断 ContentType
- 辅助重排召回结果
- 辅助质量自检

禁止：

- Agent 直接自由查 9 表
- Agent 自行绕过 tenant filter
- Agent 自行决定硬品牌字段缺失时继续成稿

---

## 11. 落盘目录

```text
knowledge_serving/
  README.md

  schema/
    serving_views.schema.json
    control_tables.schema.json
    context_bundle.schema.json
    business_brief.schema.json

  views/
    pack_view.csv
    content_type_view.csv
    generation_recipe_view.csv
    play_card_view.csv
    runtime_asset_view.csv
    brand_overlay_view.csv
    evidence_view.csv

  control/
    tenant_scope_registry.csv
    field_requirement_matrix.csv
    retrieval_policy_view.csv
    merge_precedence_policy.csv
    context_bundle_log.csv       # 唯一 canonical context bundle 调用日志

  policies/
    fallback_policy.yaml
    guardrail_policy.yaml
    merge_precedence_policy.yaml
    retrieval_policy.yaml
    model_policy.yaml

  vector_payloads/
    qdrant_chunks.jsonl
    qdrant_payload_schema.json

  logs/
    retrieval_eval_sample.csv
    run_context_retrieval_demo.log

  scripts/
    compile_serving_views.py
    compile_play_card_view.py
    compile_brand_overlay_view.py
    build_qdrant_payloads.py
    validate_serving_governance.py
    run_context_retrieval_demo.py
    run_serving_regression_tests.py
```

---

## 12. 编译硬门

```text
S0 baseline_alignment
  W12/W13 基线、manifest 与 CSV 口径一致；knowledge.db 若继续保留，必须重建并与 CSV 一致；若废弃，必须从 serving 信任链移除并留痕

S1 source_traceability
  每条 serving view 必须有 source_pack_id

S2 gate_filter
  默认召回池只允许 active

S3 brand_layer_scope
  所有 view 必须带 brand_layer，且符合 domain_general / brand_<name> / needs_review

S4 granularity_integrity
  L1/L2/L3 不得混填

S5 evidence_linkage
  可解释输出必须能反查 evidence

S6 play_card_completeness
  play_card_view 必须标 completeness_status

S7 fallback_policy_coverage
  每个 content_type 必须有缺字段策略

S8 context_bundle_replay
  任意 request_id 可复现当时喂给 LLM 的上下文

S9 tenant_isolation_regression
  brand_a 无法召回 brand_b

S10 qdrant_payload_filter
  每个 vector chunk 必须具备强过滤 payload

S11 business_brief_no_fabrication
  缺商品事实时不得生成最终品牌成稿

S12 model_policy_declared
  embedding / rerank / llm_assist 必须在 model_policy.yaml 显式声明；embedding 变更必须触发 qdrant_chunks 重建

S13 llm_assist_boundary
  LLM assist 不得执行 tenant_scope_resolution / brand_layer_override / fallback_policy_decision / merge_precedence_decision / final_generation
```

---

# 附件 A：生产视角审查补充

## A1. 当前仓库实测结论

已实测：

- `full_audit.py` 当前 27/27 通过。
- `dify_consume_demo.py` 可跑通 L2/L3 反查链路。
- `sqlite_demo.py` 可跑通 `domain_general + brand_<name>` 查询模式。
- 当前仓库未见 `knowledge_serving/`，所以本方案属于下一层 serving 工程，不是已有实现。
- W12 对抗测试当前有 1 项基线漂移：旧脚本仍期待 `06_rule=194 / 07_evidence=194`，但当前最终报告是 `201 / 201`。
- `knowledge.db` 是旧物理库，未同步当前 7 条 `brand_faye`；S0 必须在"重建后保留"与"废弃并移出 serving 信任链"之间二选一，不能继续作为隐含真源。
- ECS 侧抽取 → 入库 ETL 尚未完成，Qdrant 记录为 unhealthy，需要上线前排查。

## A2. 必须先做的 S0 收口

进入 `knowledge_serving` 前，先完成：

1. 修正 W12-T13 基线漂移。
2. 重建或废弃旧 `knowledge.db`：若保留，必须与 CSV / manifest 一致；若废弃，必须从方案、脚本和回放链路中显式排除。
3. 明确 `knowledge_serving/` 是派生读模型。
4. 把 ECS 密钥、密码、公网信息移出仓库并轮换。
5. 确认 Qdrant 健康，或先实现 structured-only fallback。
6. 补 ContentType canonical id 与 alias map。

## A3. 生产风险清单

高风险：

- 多租户串味。
- LLM 编造品牌创始人、商品事实、库存事实。
- 只靠向量召回导致 guardrail 字段丢失。
- 旧 DB / 旧 ECS 快照被误当最新真源。
- `brand_faye` overlay 与 `domain_general` 冲突未显式合并。
- 召回日志只存 ID，不足以回放。

中风险：

- 18 个 ContentType 覆盖不完整。
- L2/L3 资产数量仍偏少。
- 证据多数为 paraphrase/low，不适合全部展示为"原文引用"。
- 缺少真实生成质量评估、人工打分、盲测、A/B 数据。

## A4. 商业与品牌运营补充

`domain_general` 可以作为跨品牌冷启动底座，适合售卖"行业通用内容生产能力"。

`brand_<name>` 不只是锦上添花。对以下内容，它接近必要层：

- 创始人 IP
- 品牌宣言
- 品牌调性文案
- 团队真人格内容
- 品牌专属 ContentType overlay

服装品牌生产内容时，还必须引入业务 brief：

```text
品类
SKU / 系列
季节
库存压力
价格带
面料
版型
尺码
目标人群
渠道
促销边界
拍摄资源
CTA
合规禁区
```

知识库解决"怎么判断、怎么表达、怎么降级"，不能替代商品事实系统。

---

# 附件 B：实施路线图

## Phase 0：基线修复

目标：让当前仓库事实和验收脚本重新一致。

交付：

- 修 W12-T13。
- 重跑 27 道硬门。
- 重建 `knowledge.db` 并校验一致，或声明不再消费并从 serving 信任链移除。
- 生成 `source_manifest_hash`。

## Phase 1：Schema 与目录落地

目标：只建结构，不接 Dify。

交付：

- `knowledge_serving/schema/*.json`
- 7 个 views 空表头
- 5 个 control tables 空表头
- policy yaml 初版

## Phase 2：编译器

目标：从 `clean_output` 编译出 serving views。

交付：

- `compile_serving_views.py`
- `compile_play_card_view.py`
- `compile_brand_overlay_view.py`
- `validate_serving_governance.py`

验收：

- S1-S7 全绿。

## Phase 3：Retrieval Demo

目标：本地跑通 `retrieve_context()`。

交付：

- `run_context_retrieval_demo.py`
- `control/context_bundle_log.csv`
- `retrieval_eval_sample.csv`

验收：

- product_review / store_daily / founder_ip 三类样例跑通。
- hard 缺字段能阻断。
- soft 缺字段能降级。
- 跨租户无法串味。

## Phase 4：向量 payload

目标：准备 Qdrant 灌库材料。

交付：

- `qdrant_chunks.jsonl`
- `qdrant_payload_schema.json`
- vector filter regression tests

验收：

- 每个 chunk 有治理字段。
- 无 active 以外默认召回。
- Qdrant 不可用时 structured-only 可用。

## Phase 5：Dify 接入

目标：Chatflow 消费 `retrieve_context()`。

交付：

- Dify Chatflow 节点说明
- API wrapper
- Guardrail 检查器
- 日志回放 demo

验收：

- Agent 不直接查 9 表。
- 每次输出可追 request_id。
- evidence 摘要可回放。

---

# 最终结论

这套方案主体成立，建议作为 `clean_output` 之后的下一层正式工程推进。

微调后的最终形态是：

```text
clean_output = 真源与审计底座
knowledge_serving = 可重编译 serving 读模型
retrieve_context = 唯一运行时入口
Dify Chatflow = 编排主控
Agent = 局部判断工具
LLM = 只消费已治理 context_bundle
```

推进前必须先做 S0 收口；否则 serving 层会把当前的基线漂移、旧 DB、ECS 未打通和 Qdrant unhealthy 一起放大。

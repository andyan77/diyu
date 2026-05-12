---
task_id: KS-POLICY-002
phase: Policy
wave: W6
depends_on: [KS-COMPILER-013]
files_touched:
  - knowledge_serving/policies/guardrail_policy.yaml
  - scripts/validate_policy_yaml.py
  - knowledge_serving/scripts/tests/test_validate_guardrail_policy.py
artifacts:
  - knowledge_serving/policies/guardrail_policy.yaml
  - knowledge_serving/scripts/tests/test_validate_guardrail_policy.py
s_gates: [S11]
plan_sections:
  - "§3.3"
  - "§4.2"
  - "§10"
  - "§11 (S11)"
  - "§A3"
writes_clean_output: false
ci_commands:
  - python3 scripts/validate_policy_yaml.py guardrail_policy
  - yamllint -c .yamllint knowledge_serving/policies/guardrail_policy.yaml
  - python3 -m pytest knowledge_serving/scripts/tests/test_validate_guardrail_policy.py
status: done
---

# KS-POLICY-002 · guardrail_policy.yaml（防 LLM 编造事实的策略层 / fabrication guardrail policy）

## 1. 任务目标 / Objective

- **业务 / business**：固化"LLM 不许编造商品 / 创始人 / 库存 / 培训事实"的红线。把 plan §A3 高风险项（创始人捏造、SKU 编造、库存编造、只靠向量召回丢 guardrail 字段）转成 yaml 可执行规则，供下游 KS-DIFY-ECS-009 检查器消费。
- **工程 / engineering**：yaml 声明三组规则
  1. `forbidden_patterns` — 禁出文本 / 字段模式（正则或关键词），命中即 block
  2. `required_evidence` — 18 个 canonical `content_type` 中 `required_level=hard` 的字段必须有 `evidence_id` 链路，否则 block
  3. `business_brief_required` — business_brief.schema.json hard required 字段（sku / category / season / channel）缺即 block
- **S gate**：S11 `business_brief_no_fabrication`（plan §11）。
- **非目标 / non-goals**：
  - 不实现 guardrail 运行时检查器（属 KS-DIFY-ECS-009）
  - 不修改 field_requirement_matrix.csv（属 KS-COMPILER-012）
  - 不接 LLM API（plan §9.1 forbidden_tasks: `evidence_fabrication`）

## 2. 前置依赖 / Prerequisites

- **KS-COMPILER-013（S1-S7 治理总闸）必须 PASS**：作为 W6 起跑前置门禁。本卡 yaml 引用的 `content_type` 必须严格闭环到 canonical 18 类（KS-COMPILER-013 已守门 S1/S5 source_traceability），不得引入漂移类目（参考 [[claude-error-patterns-core]] E8）。
- 输入只读：`field_requirement_matrix.csv`、`business_brief.schema.json`、`content_type_canonical.csv`。

## 3. 输入契约 / Input Contract

| 输入 / input | 路径 / path | 用途 / purpose |
|---|---|---|
| field_requirement_matrix | `knowledge_serving/control/field_requirement_matrix.csv` | 取 `required_level=hard` 的 (content_type, field_key) → required_evidence 段 |
| business_brief schema | `knowledge_serving/schema/business_brief.schema.json` | 取 `required` 数组（sku/category/season/channel）+ `x-soft-required`（仅信息性，**不** 入阻断） |
| content_type canonical | `knowledge_serving/control/content_type_canonical.csv` | 限定 `required_evidence.<content_type>` key 集合 ⊆ canonical 18 |
| plan §A3 | `knowledge_serving_plan_v1.1.md` | forbidden_patterns 最小三类来源：创始人捏造 / SKU 编造 / 库存编造 |

## 4. 执行步骤 / Steps

1. **yaml 结构**（policy_version + 三段）
   ```yaml
   policy_version: "1.0.0"
   forbidden_patterns:
     - id: FP-FOUNDER-FABRICATION
       category: founder_identity
       pattern_kind: keyword
       patterns: ["创始人是", "founder is", ...]
       block_reason: "禁止 LLM 编造创始人画像 / 故事 / 价值观"
       severity: hard_block
     - id: FP-SKU-FABRICATION
       category: product_fact
       pattern_kind: regex
       patterns: ["SKU[\\s_-]?\\d{4,}"]
       block_reason: "SKU 编号必须来自 business_brief.sku，禁编造"
       severity: hard_block
     - id: FP-INVENTORY-FABRICATION
       ...
   required_evidence:
     founder_ip:
       hard_fields: [brand_values, founder_profile]
       block_reason_ref: field_requirement_matrix
     event_documentary:
       hard_fields: [event_anchor]
     # ...（覆盖 matrix 中全部 hard 行：8 个 content_type）
   business_brief_required:
     hard_fields: [sku, category, season, channel]
     soft_fields_warning_only: [inventory_pressure, price_band, cta]
     block_reason: "business_brief hard 字段缺失，禁止进入最终成稿（S11）"
   ```
2. **forbidden_patterns 至少 3 大类**：founder fabrication / sku fabrication / inventory fabrication（plan §A3 三大高风险）。
3. **required_evidence 与 matrix 严格闭环**：所有 `required_level=hard` 的 (content_type, field_key) 必须在 yaml 出现，反之 yaml 不得出现 matrix 没有的 content_type 或 field_key（双向相等）。
4. **business_brief_required 与 schema 严格闭环**：`hard_fields` 必须 == schema `required[]`；`soft_fields_warning_only` 必须 == schema `x-soft-required[]`。
5. **yamllint 通过**；新建 `scripts/validate_policy_yaml.py` 实现以上 4 项闭环校验（参考 `scripts/validate_model_policy.py` 风格）。

## 5. 执行交付 / Deliverables

| 路径 / path | 格式 | canonical | 入 git |
|---|---|---|---|
| `knowledge_serving/policies/guardrail_policy.yaml` | yaml | 是 | 是 |
| `scripts/validate_policy_yaml.py` | py | 是（多 policy 共用入口，arg=`guardrail_policy`） | 是 |
| `knowledge_serving/scripts/tests/test_validate_guardrail_policy.py` | pytest | 是 | 是 |

## 6. 对抗性 / 边缘性测试 / Adversarial Tests

| # | 测试 / case | 期望 / expected |
|---|---|---|
| 1 | `forbidden_patterns` 空 | fail（plan §A3 三类至少各 1 条）|
| 2 | `forbidden_patterns[*]` 缺 `block_reason` | fail |
| 3 | `forbidden_patterns[*]` 缺 `severity` 或 severity 非 `hard_block`/`soft_warning` | fail |
| 4 | `required_evidence.<content_type>` 含 matrix 没有的 hard field | fail |
| 5 | matrix 中某 hard 行 yaml 漏写 | fail（双向闭环）|
| 6 | `required_evidence` 中出现 canonical 18 之外的 content_type | fail（接力 KS-COMPILER-013 S1 守门）|
| 7 | `business_brief_required.hard_fields` ≠ schema `required[]` | fail |
| 8 | `business_brief_required.hard_fields` 把 schema 的 soft 字段（如 cta）当 hard | fail |
| 9 | yaml 语法错 / 缩进错 | fail（yamllint）|
| 10 | yaml 内出现 LLM 判断字段（`use_llm_to_decide` / `llm_assist` / `model:`）| fail（关键词扫描，对齐 KS-POLICY-001 同款约束）|
| 11 | `policy_version` 缺 | fail |
| 12 | 重复 `forbidden_patterns[*].id` | fail |

## 7. 治理语义一致性 / Governance Consistency

- **S11 严格**：business_brief hard 字段缺即阻断进入最终成稿
- **不调 LLM 做触发判断**：所有 pattern / required 都是声明式（正则 / 关键词 / 字段名），决策权在规则引擎，不在模型（plan §9.1 `forbidden_tasks` 含 `evidence_fabrication`）
- **与 KS-POLICY-001（fallback_policy）互补不冲突**：
  - fallback_policy 管"hard 字段缺时是否降级到 domain_general"（已允许的降级路径）
  - guardrail_policy 管"什么情况下连降级都不许，必须直接 block"（不可降级的事实捏造）
  - 两者共同消费 field_requirement_matrix，但 guardrail 是**最后兜底**：matrix 给的 `fallback_action=block_brand_output` 在 guardrail 中必须显式登记
- **与 KS-COMPILER-013 (S1-S7) 串接**：W5 守门已确保 view 的 content_type 闭环到 canonical 18；本卡只能在该集合内引用，不得新建类目（防 E8 漂移）

## 8. CI 门禁 / CI Gate

```
command: python3 scripts/validate_policy_yaml.py guardrail_policy
内嵌检查 / built-in:
  - F1a yaml.safe_load + top-level mapping
  - F1b yamllint -c .yamllint（与 fallback_policy 同口径）
  - G1 policy_version 非空
  - G2 forbidden_patterns 覆盖 founder_identity / product_fact / inventory_fact 三类
  - G3/G4 每条 pattern 字段齐 + id 唯一
  - G5 required_evidence 与 field_requirement_matrix.csv hard 行双向闭环
  - G6 required_evidence 闭环到 canonical 18 content_type
  - G7/G8 business_brief_required 与 schema required[] / x-soft-required[] 严格相等
  - G9 无 LLM 结构字段（llm_assist / model / use_llm / gpt / openai / anthropic / claude）
exit_code: 0 全绿 / 1 任一项失败
artifact: knowledge_serving/policies/guardrail_policy.yaml
```

## 9. CD / 环境验证 / CD

不部署。yaml 由 KS-DIFY-ECS-009 在 ECS 侧消费；本卡只负责真源落盘 + CI 守门，不入 ECS。

## 10. 独立审查员 Prompt / Reviewer Prompt

> 请按以下四步审查 KS-POLICY-002：
> 1. 跑 `python3 scripts/validate_policy_yaml.py guardrail_policy`，确认 exit 0；
> 2. 抽样检查：(a) `forbidden_patterns` 至少含 founder / sku / inventory 三类，每条有 `block_reason` 和 `severity=hard_block`；(b) `required_evidence` 与 `field_requirement_matrix.csv` hard 行**双向相等**（不漏不多）；(c) `business_brief_required.hard_fields` == `business_brief.schema.json` 的 `required[]`；
> 3. grep yaml 中是否含 `llm_assist` / `use_llm` / `model:` 等 LLM 判断字段（应 0 命中）；
> 4. 输出 pass / fail / conditional_pass 三选一，并列出阻断项。
>
> 阻断项 / blockers：
> - 任一 forbidden_pattern 无量化 `patterns`（关键词或正则均可，但不能空）
> - required_evidence 与 matrix 双向闭环失败
> - business_brief_required 与 schema required[] 不一致
> - yaml 含 LLM 判断字段

## 11. DoD / Definition of Done

- [x] `guardrail_policy.yaml` 落盘，覆盖三段（forbidden_patterns / required_evidence / business_brief_required）
- [x] `scripts/validate_policy_yaml.py` 新增 `guardrail_policy` 分支，G1-G9 共 9 项闭环校验
- [x] `test_validate_guardrail_policy.py` 16 case 全绿（§6 表 12 + happy 2 + 类目守护 1 + yamllint 守护 1）
- [x] CI exit 0：`python3 scripts/validate_policy_yaml.py guardrail_policy`（内嵌 F1b yamllint + G1-G9）
- [x] 6 道闸：pytest 16/16 + W5 --all + DAG（C8 强化后）+ serving_tree + purity + no-LLM grep 全绿
- [x] 审查员 CONDITIONAL_PASS（2026-05-13）→ F1/F2 修复后升 PASS

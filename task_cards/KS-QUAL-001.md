---
task_id: KS-QUAL-001
phase: Production-Readiness
wave: W17
depends_on: [KS-GEN-009]
files_touched:
  - knowledge_serving/scripts/content_factuality_check.py
  - knowledge_serving/audit/factuality_KS-QUAL-001.json
artifacts:
  - knowledge_serving/scripts/content_factuality_check.py
  - knowledge_serving/audit/factuality_KS-QUAL-001.json
s_gates: [S3, S11]
plan_sections:
  - "§9.2"
  - "§A3"
writes_clean_output: false
ci_commands:
  - source scripts/load_env.sh && python3 knowledge_serving/scripts/content_factuality_check.py --staging --strict --out knowledge_serving/audit/factuality_KS-QUAL-001.json
status: not_started
---

# KS-QUAL-001 · 内容事实性硬门（输出 vs 9 表知识断言对照）

## 1. 任务目标
- **业务**：LLM 容易"编"——价格、面料、尺码、流程，编一个就翻车。本卡：规则级硬门，把生成结果中提到的**可校验事实声明**（产品属性 / 流程 / 数字）与 9 表 + brand_faye candidates 知识对照，发现冲突 → block 发布。
- **工程**：脚本提取输出中的结构化事实声明（用 NER / 正则 / 字段模板），逐条对照 9 表事实表，冲突即 `factual_violation=true`；不调 LLM 做判断（R2）。
- **S-gate**：S3（evidence_view 完整）+ S11（brand_layer 多租户隔离）。
- **non-goal**：不评"调性"（KS-QUAL-004 干）；不替代 guardrail。

## 2. 前置依赖
- KS-GEN-009（prompt v2 30 样例可作为测试集）。

## 3. 输入契约
- 读：`clean_output/nine_tables/*.csv` + 30 v2 样例
- env：PG（读 evidence_view）。

## 4. 执行步骤
1. 实现事实提取器：定义 ≥ 10 类可校验声明 patterns（价格、面料%、尺码、保养、退换、产地 / origin）。
2. 实现对照器：每提取声明 → 查 9 表对应字段 → 一致 / 冲突 / not_in_knowledge。
3. 跑 30 v2 样例，audit 含每样例 violation_count + 详情。
4. 全样例 violation_count == 0 才算门通过。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `scripts/content_factuality_check.py` | py | 是 | 是 | runtime_verified |
| `audit/factuality_KS-QUAL-001.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 故意造一条说"面料 100% 真丝"但 9 表说 30% | **检测出 violation**（fail-closed） |
| LLM 替代规则做事实判断 | **fail-closed**：audit 必含 `rules_only=true` R2 token |
| not_in_knowledge 声明 > 30% | 标 high_unknown_rate（不当 PASS，留人工抽检） |
| 任一样例 violation_count > 0 | 该样例 needs_review |

## 7. 治理语义一致性
- 不写 clean_output/。
- **R2 关键**：不调 LLM 做事实裁决（守护员明示口径：LLM 只能出参考分，不做硬门）。
- audit 必含 `llm_judge_advisory_only=true` / `rules_only=true` 双 token。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/content_factuality_check.py --staging --strict --out knowledge_serving/audit/factuality_KS-QUAL-001.json
pass:    rules_only=true 且 故意造的冲突测试被检出 且 真样例 violation_count=0
```

## 9. CD / 环境验证
- staging：本卡跑；prod：W18 部署后挂 n8_guardrail 后置。

## 10. 独立审查员 Prompt
> 验：1) rules_only=true；2) 故意造的冲突真被抓；3) 不调 LLM。

## 11. DoD
- [ ] 10+ 类事实提取 patterns 入 git
- [ ] 30 v2 样例真跑过
- [ ] audit runtime_verified
- [ ] R2 红线声明真在

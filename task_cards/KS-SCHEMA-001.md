---
task_id: KS-SCHEMA-001
phase: Schema
wave: W1
depends_on: [KS-S0-006]
files_touched:
  - knowledge_serving/schema/serving_views.schema.json
artifacts:
  - knowledge_serving/schema/serving_views.schema.json
s_gates: []
plan_sections:
  - "§3"
  - "§2"
writes_clean_output: false
ci_commands:
  - python3 scripts/check_schema.py knowledge_serving/schema/serving_views.schema.json
status: done
---

# KS-SCHEMA-001 · serving_views.schema.json

## 1. 任务目标
- **业务**：为 7 个 serving view 立法字段契约，编译卡照此产出。
- **工程**：写 jsonschema，覆盖 §3.1-3.7 各 view 的业务字段 + §2 governance_common_fields。
- **S gate**：无单独门，但为 S1-S6 提供 schema 底座。
- **非目标**：不产生数据；不实现编译。

## 2. 前置依赖
- KS-S0-006（manifest 已生成）

## 3. 输入契约
- 读：`knowledge_serving_plan_v1.1.md` §2、§3
- 不读：任何 csv

## 4. 执行步骤
1. 起 `serving_views.schema.json`，定义 `governance_common_fields` 子 schema（13 字段）
2. 为 7 个 view 各写一个对象 schema，引用 governance 子 schema
3. 字段类型 / 枚举 / required 严格按 §3.1-3.7
4. 加 `view_schema_version` 顶层字段
5. `scripts/check_schema.py` 自校验

## 5. 执行交付
| 路径 | 格式 | canonical | 可重建 | 入 git | CI artifact |
|---|---|---|---|---|---|
| `knowledge_serving/schema/serving_views.schema.json` | json | 是 | 是 | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 governance 字段的样本 | schema validate fail |
| brand_layer = "FAYE" 非法枚举 | fail |
| granularity_layer = "L4" | fail |
| gate_status = "active" + 其他 | active 默认；其他需显式 |
| play_card_view 缺 completeness_status | fail |

## 7. 治理语义一致性
- 13 个 governance_common_fields 全部 required（含 compile_run_id / source_manifest_hash / view_schema_version）
- brand_layer 枚举：`domain_general | brand_<name> | needs_review`
- 不允许 LLM 字段
- view_schema_version 字段独立，便于回放

## 8. CI 门禁
```
command: python3 scripts/check_schema.py knowledge_serving/schema/serving_views.schema.json
pass: schema 自校验通过
failure_means: schema 不合法，编译卡无法开工
artifact: knowledge_serving/schema/serving_views.schema.json
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：
> 1. `python3 scripts/check_schema.py <file>` pass
> 2. 用故意缺字段的样本 validate，必须 fail
> 3. 用 brand_layer="FAYE" 样本 validate，必须 fail
> 4. 比对 §3.1-3.7 字段清单，无遗漏
> 5. 输出 pass / conditional_pass / fail
> 阻断项：govenance 字段未 required；枚举漏；view 缺字段。

## 11. DoD
- [x] schema 落盘
- [x] check-schema pass
- [x] 字段比对完成
- [x] 审查员 pass

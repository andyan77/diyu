---
task_id: KS-SCHEMA-002
phase: Schema
depends_on: [KS-S0-006]
files_touched:
  - knowledge_serving/schema/control_tables.schema.json
artifacts:
  - knowledge_serving/schema/control_tables.schema.json
s_gates: []
plan_sections:
  - "§4"
writes_clean_output: false
ci_commands:
  - python3 -m jsonschema --check-schema knowledge_serving/schema/control_tables.schema.json
status: not_started
---

# KS-SCHEMA-002 · control_tables.schema.json

## 1. 任务目标
- **业务**：为 5 个 control table 立法字段契约。
- **工程**：覆盖 §4.1-4.5 五张表全部字段；context_bundle_log 字段集与 §4.5 一一对齐。
- **S gate**：无单独门，但为 S8 / S9 / S12 提供 schema 底座。
- **非目标**：不实现写入逻辑。

## 2. 前置依赖
- KS-S0-006

## 3. 输入契约
- 读：plan §4
- 不读：csv 数据

## 4. 执行步骤
1. 写 5 个对象 schema（tenant_scope_registry / field_requirement_matrix / retrieval_policy_view / merge_precedence_policy / context_bundle_log）
2. 枚举字段严格按 plan（`required_level: none|soft|hard`、`fallback_action: ...`）
3. `context_bundle_log` 必含 24 个字段（plan §4.5）
4. self-check

## 5. 执行交付
| 路径 | 格式 | canonical | 可重建 | 入 git |
|---|---|---|---|---|
| `knowledge_serving/schema/control_tables.schema.json` | json | 是 | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| context_bundle_log 缺 compile_run_id | fail |
| field_requirement_matrix.required_level="medium" | fail（非法枚举） |
| environment 非 dev/staging/prod | fail |
| 空表 / 缺 required | fail |
| 重复主键 | schema 不直接管，留给 validator |

## 7. 治理语义一致性
- `user_query` 仅允许 hash 或脱敏摘要（schema 中 description 显式标注）
- `resolved_brand_layer` 与 `tenant_id` 独立字段
- LLM 相关字段（embedding_model / rerank_model / llm_assist_model）允许 `disabled` 字面量

## 8. CI 门禁
```
command: python3 -m jsonschema --check-schema knowledge_serving/schema/control_tables.schema.json
pass: schema 自校验通过
failure_means: control 表不可信
artifact: 同上
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：
> 1. check-schema pass
> 2. 用缺字段样本 fail
> 3. 比对 §4 字段清单
> 4. 输出 pass / fail
> 阻断项：context_bundle_log 缺字段；环境枚举漏。

## 11. DoD
- [ ] schema 落盘
- [ ] check-schema pass
- [ ] 审查员 pass

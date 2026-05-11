---
task_id: KS-VECTOR-002
phase: Vector
depends_on: [KS-VECTOR-001]
files_touched:
  - knowledge_serving/vector_payloads/qdrant_payload_schema.json
artifacts:
  - knowledge_serving/vector_payloads/qdrant_payload_schema.json
s_gates: [S10]
plan_sections:
  - "§8"
writes_clean_output: false
ci_commands:
  - python3 -m jsonschema --check-schema knowledge_serving/vector_payloads/qdrant_payload_schema.json
status: not_started
---

# KS-VECTOR-002 · qdrant_payload_schema.json

## 1. 任务目标
- **业务**：固化 Qdrant payload 字段契约。
- **工程**：jsonschema 覆盖 §8 全字段。
- **S gate**：S10。
- **非目标**：不灌库。

## 2. 前置依赖
- KS-VECTOR-001

## 3. 输入契约
- 读：plan §8

## 4. 执行步骤
1. 写 schema：view_type / source_pack_id / brand_layer / granularity_layer / content_type / pack_type / gate_status / default_call_pool / evidence_ids / compile_run_id / chunk_text_hash / embedding_model / embedding_model_version / embedding_dimension / index_version
2. self-check

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `qdrant_payload_schema.json` | json | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 brand_layer | fail |
| embedding_dimension=0 | warning |
| gate_status 非枚举 | fail |
| chunk_text_hash 非 hex | fail |

## 7. 治理语义一致性
- §8 字段齐
- 不调 LLM

## 8. CI 门禁
```
command: python3 -m jsonschema --check-schema knowledge_serving/vector_payloads/qdrant_payload_schema.json
pass: 自校验通过
artifact: schema
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：check-schema pass + 字段齐 + 输出 pass / fail。
> 阻断项：字段漏。

## 11. DoD
- [ ] schema 落盘
- [ ] check-schema pass
- [ ] 审查员 pass

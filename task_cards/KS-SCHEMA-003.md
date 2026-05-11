---
task_id: KS-SCHEMA-003
phase: Schema
wave: W1
depends_on: [KS-S0-006]
files_touched:
  - knowledge_serving/schema/context_bundle.schema.json
artifacts:
  - knowledge_serving/schema/context_bundle.schema.json
s_gates: []
plan_sections:
  - "§5"
writes_clean_output: false
ci_commands:
  - python3 -m jsonschema --check-schema knowledge_serving/schema/context_bundle.schema.json
status: not_started
---

# KS-SCHEMA-003 · context_bundle.schema.json

## 1. 任务目标
- **业务**：固化 retrieve_context() 返回结构；下游 Dify 节点据此对接。
- **工程**：写 jsonschema，字段对齐 §5 返回结构。
- **S gate**：无单独门，为 S8 回放与 KS-RETRIEVAL-008 提供契约。
- **非目标**：不实现 API。

## 2. 前置依赖
- KS-S0-006

## 3. 输入契约
- 读：plan §5

## 4. 执行步骤
1. 定义顶层对象：request_id / tenant_id / resolved_brand_layer / allowed_layers / content_type / recipe / business_brief / domain_packs / play_cards / runtime_assets / brand_overlays / evidence / missing_fields / fallback_status / generation_constraints / governance
2. governance 子对象含 compile_run_id / source_manifest_hash / view_schema_version 等
3. fallback_status 枚举：§7 五状态
4. self-check

## 5. 执行交付
| 路径 | 格式 | canonical | 可重建 | 入 git |
|---|---|---|---|---|
| `knowledge_serving/schema/context_bundle.schema.json` | json | 是 | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| fallback_status 非法值 | fail |
| 缺 request_id | fail |
| governance 缺 source_manifest_hash | fail |
| evidence 列表内项缺 evidence_id | fail |
| 空 bundle | required 缺失 → fail |

## 7. 治理语义一致性
- request_id 必填（S8 回放）
- resolved_brand_layer 与 tenant_id 分离字段
- evidence 数组保留 inference_level / trace_quality 字段（来自 §3.7）

## 8. CI 门禁
```
command: python3 -m jsonschema --check-schema knowledge_serving/schema/context_bundle.schema.json
pass: 自校验通过
artifact: 同上
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：
> 1. check-schema pass
> 2. 缺 request_id 的样本必须 fail
> 3. fallback_status 五值齐
> 4. 输出 pass / fail
> 阻断项：governance 子对象不全；fallback_status 枚举漏。

## 11. DoD
- [ ] schema 落盘
- [ ] check-schema pass
- [ ] 审查员 pass

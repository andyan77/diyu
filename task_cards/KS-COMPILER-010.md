---
task_id: KS-COMPILER-010
phase: Compiler
wave: W3
depends_on: [KS-SCHEMA-002, KS-S0-005]
files_touched:
  - knowledge_serving/scripts/compile_retrieval_policy_view.py
  - knowledge_serving/control/retrieval_policy_view.csv
artifacts:
  - knowledge_serving/control/retrieval_policy_view.csv
s_gates: []
plan_sections:
  - "§4.3"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_retrieval_policy_view.py --check
status: not_started
---

# KS-COMPILER-010 · retrieval_policy_view 编译

## 1. 任务目标
- **业务**：固化"什么问题查哪些 view"。
- **工程**：每个 (intent, content_type) 一行；required_views / optional_views / filters / rerank_strategy / timeout_ms 全填。
- **S gate**：无单独门，为 KS-RETRIEVAL-* 提供策略源。
- **非目标**：不实现路由执行。

## 2. 前置依赖
- KS-SCHEMA-002、KS-S0-005

## 3. 输入契约
- 读：content_type_canonical.csv、control_tables.schema.json
- 不读：运行时

## 4. 执行步骤
1. 18 ContentType × 至少 1 intent
2. 字段对齐 §4.3
3. structured_filters_json / vector_filters_json 严格 JSON
4. 写 csv

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `compile_retrieval_policy_view.py` | py | 是 | 是 |
| `retrieval_policy_view.csv` | csv | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| filters_json 非法 JSON | fail |
| required_views 引用不存在 view | fail |
| timeout_ms ≤ 0 | fail |
| rerank_strategy 枚举漏 | fail |
| 18 类未全覆盖 | warning |

## 7. 治理语义一致性
- 不调 LLM
- vector_filters 必含 gate_status="active" 与 brand_layer 约束
- clean_output 0 写

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_retrieval_policy_view.py --check
pass: exit 0 + JSON 解析全通过 + 18 类覆盖
artifact: retrieval_policy_view.csv
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) 抽样验证 vector_filters 含 gate_status active；2) 输出 pass / fail。
> 阻断项：filters 缺 gate_status / brand_layer 约束。

## 11. DoD
- [ ] csv 落盘
- [ ] CI pass
- [ ] 审查员 pass

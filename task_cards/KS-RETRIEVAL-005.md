---
task_id: KS-RETRIEVAL-005
phase: Retrieval
depends_on: [KS-COMPILER-013]
files_touched:
  - knowledge_serving/serving/structured_retrieval.py
  - knowledge_serving/tests/test_struct_retrieval.py
artifacts:
  - knowledge_serving/serving/structured_retrieval.py
s_gates: [S2]
plan_sections:
  - "§6.7"
writes_clean_output: false
ci_commands:
  - pytest knowledge_serving/tests/test_struct_retrieval.py -v
status: not_started
---

# KS-RETRIEVAL-005 · structured_retrieval

## 1. 任务目标
- **业务**：从 content_type_view / pack_view / play_card_view / runtime_asset_view 做结构化召回。
- **工程**：基于 retrieval_policy.yaml 中的 structured_filters_json 执行查询。
- **S gate**：S2 gate_filter（active only 默认）。
- **非目标**：不做向量召回；不做合并。

## 2. 前置依赖
- KS-COMPILER-013

## 3. 输入契约
- 读：4 个 view csv、retrieval_policy_view.csv
- 入参：intent / content_type / allowed_layers

## 4. 执行步骤
1. 根据 policy 取 required_views + structured_filters
2. 应用 hard filter：gate_status=active、brand_layer ∈ allowed_layers、granularity_layer 合法
3. 按 max_items_per_view 截断
4. 返回结构化候选

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `structured_retrieval.py` | py | 是 | 是 |
| `test_struct_retrieval.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| brand_a 请求得到 brand_b 行 | 永不发生（断言） |
| inactive 行召回 | 永不发生 |
| 空 view | 返回 []，不抛 |
| 过大 max_items | 警告并 cap |
| filter 字段缺 | raise |

## 7. 治理语义一致性
- S2 active only 默认
- brand_layer hard filter
- 不调 LLM
- 不写 clean_output

## 8. CI 门禁
```
command: pytest knowledge_serving/tests/test_struct_retrieval.py -v
pass: 跨租户测试 + active filter 测试全绿
artifact: pytest report
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) 构造 brand_a allowed_layers 请求，验证返回 0 brand_b 行；2) inactive 默认 0 命中；3) 输出 pass / fail。
> 阻断项：跨租户串味；inactive 命中。

## 11. DoD
- [ ] 模块入 git
- [ ] pytest 全绿
- [ ] 审查员 pass

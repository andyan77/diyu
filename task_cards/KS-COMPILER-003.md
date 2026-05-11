---
task_id: KS-COMPILER-003
phase: Compiler
wave: W4
depends_on: [KS-COMPILER-002, KS-SCHEMA-004]
files_touched:
  - knowledge_serving/scripts/compile_generation_recipe_view.py
  - knowledge_serving/views/generation_recipe_view.csv
artifacts:
  - knowledge_serving/views/generation_recipe_view.csv
s_gates: [S11]
plan_sections:
  - "§3.3"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_generation_recipe_view.py --check
status: not_started
---

# KS-COMPILER-003 · generation_recipe_view 编译

## 1. 任务目标
- **业务**：固化"这类内容怎么组装"读模型，含 business_brief_schema_id 防 LLM 编造。
- **工程**：覆盖 §3.3 字段；business_brief_schema_id 必填。
- **S gate**：S11。
- **非目标**：不实现召回。

## 2. 前置依赖
- KS-COMPILER-002、KS-SCHEMA-004

## 3. 输入契约
- 读：content_type_view.csv、business_brief.schema.json
- 不读：召回侧

## 4. 执行步骤
1. 为每个 content_type × output_format × platform 组合定义 recipe
2. 引用 retrieval_plan_json / step_sequence_json / context_budget_json
3. business_brief_schema_id 引用 KS-SCHEMA-004
4. 输出 csv

## 5. 执行交付
| 路径 | 格式 | canonical | 可重建 | 入 git |
|---|---|---|---|---|
| `compile_generation_recipe_view.py` | py | 是 | — | 是 |
| `generation_recipe_view.csv` | csv | 派生 | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| business_brief_schema_id 缺失 | fail（S11） |
| recipe 引用不存在的 view | fail |
| context_budget_json 解析失败 | fail |
| 幂等 | 一致 |
| 空 content_type_view | warning |

## 7. 治理语义一致性
- S11 严格：每条 recipe 必有 business_brief_schema_id
- clean_output 0 写
- 不调 LLM

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_generation_recipe_view.py --check
pass: exit 0 + S11 检查通过
artifact: generation_recipe_view.csv
```

## 9. CD / 环境验证
离线。

## 10. 独立审查员 Prompt
> 请：1) 抽 5 行检查 business_brief_schema_id 引用正确；2) clean_output 0 改动；3) 输出 pass / fail。
> 阻断项：business_brief_schema_id 为空。

## 11. DoD
- [ ] csv 落盘
- [ ] CI pass
- [ ] 审查员 pass

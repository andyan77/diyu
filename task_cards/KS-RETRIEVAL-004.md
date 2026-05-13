---
task_id: KS-RETRIEVAL-004
phase: Retrieval
wave: W7
depends_on: [KS-COMPILER-003, KS-COMPILER-009, KS-POLICY-001]
files_touched:
  - knowledge_serving/serving/recipe_selector.py
  - knowledge_serving/serving/requirement_checker.py
  - knowledge_serving/tests/test_recipe.py
artifacts:
  - knowledge_serving/serving/recipe_selector.py
  - knowledge_serving/serving/requirement_checker.py
s_gates: [S7]
plan_sections:
  - "§6.5"
  - "§6.6"
writes_clean_output: false
ci_commands:
  - python3 -m pytest knowledge_serving/tests/test_recipe.py -v
status: done
---

# KS-RETRIEVAL-004 · recipe_selector + requirement_checker

## 1. 任务目标
- **业务**：选生产配方 → 查必需字段 → 决定 fallback 路径。
- **工程**：从 generation_recipe_view 选 recipe；用 field_requirement_matrix 验必需字段。
- **S gate**：S7。
- **非目标**：不执行召回。

## 2. 前置依赖
- KS-COMPILER-003、KS-COMPILER-009、KS-POLICY-001

## 3. 输入契约
- 读：generation_recipe_view.csv、field_requirement_matrix.csv、fallback_policy.yaml
- 入参：content_type / platform / output_format / brand_layer

## 4. 执行步骤
1. recipe_selector(content_type, platform, output_format) → recipe row
2. requirement_checker(recipe, available_fields) → {satisfied, missing_soft, missing_hard}
3. hard missing → blocked_missing_required_brand_fields；soft missing → brand_partial_fallback

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `recipe_selector.py` | py | 是 | 是 |
| `requirement_checker.py` | py | 是 | 是 |
| `test_recipe.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 多 recipe 匹配 | 按优先级取一 |
| 无 recipe 匹配 | raise |
| hard 缺字段 | blocked |
| soft 缺字段 | partial_fallback |
| field_matrix 缺该 content_type | warning + 保守阻断 |

## 7. 治理语义一致性
- S7：每 content_type 必有缺字段策略
- hard 缺字段必阻断
- 不调 LLM

## 8. CI 门禁
```
command: python3 -m pytest knowledge_serving/tests/test_recipe.py -v
pass: hard/soft 用例 + 无匹配用例全绿
artifact: pytest report
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) hard 缺字段用例必 blocked；2) soft 缺字段必 fallback；3) 输出 pass / fail。
> 阻断项：hard 缺字段不阻断。

## 11. DoD
- [x] 模块入 git
- [x] pytest 全绿（`python3 -m pytest knowledge_serving/tests/test_recipe.py -v` → 16 passed，runtime_verified 2026-05-13）
- [x] 审查员 pass（W7 reviewer 第二轮闭环）

---
task_id: KS-RETRIEVAL-007
phase: Retrieval
wave: W8
depends_on: [KS-RETRIEVAL-005, KS-RETRIEVAL-006, KS-POLICY-001, KS-POLICY-003]
files_touched:
  - knowledge_serving/serving/brand_overlay_retrieval.py
  - knowledge_serving/serving/merge_context.py
  - knowledge_serving/serving/fallback_decider.py
  - knowledge_serving/tests/test_merge_fallback.py
artifacts:
  - knowledge_serving/serving/brand_overlay_retrieval.py
  - knowledge_serving/serving/merge_context.py
  - knowledge_serving/serving/fallback_decider.py
s_gates: [S7]
plan_sections:
  - "§6.9"
  - "§6.10"
  - "§6.11"
writes_clean_output: false
ci_commands:
  - python3 -m pytest knowledge_serving/tests/test_merge_fallback.py -v
status: done
---

# KS-RETRIEVAL-007 · brand_overlay_retrieval + merge_context + fallback_decider

## 1. 任务目标
- **业务**：拿 brand overlay → 合并 domain_general + brand_<name> → 决定 fallback_status。
- **工程**：merge 按 KS-POLICY-003 优先级；fallback 按 KS-POLICY-001 五状态。
- **S gate**：S7。
- **非目标**：不构造最终 bundle（属 KS-RETRIEVAL-008）。

## 2. 前置依赖
- KS-RETRIEVAL-005、KS-RETRIEVAL-006、KS-POLICY-001、KS-POLICY-003

## 3. 输入契约
- 读：brand_overlay_view.csv、merge_precedence_policy.yaml、fallback_policy.yaml
- 入参：resolved_brand_layer、structured 候选、vector 候选、missing_fields

## 4. 执行步骤
1. brand_overlay_retrieval：仅取 resolved_brand_layer 的 overlay；**禁止**用自然语言覆盖
2. merge_context：按 precedence 合并 domain + brand
3. fallback_decider：根据 missing_fields + brief 状态映射到 5 状态之一

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| 3 个 .py | py | 是 | 是 |
| `test_merge_fallback.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| domain_general overlay 试图 override brand | 拒绝 |
| 5 状态分别构造用例 | 各自命中 |
| 自然语言含品牌名 | overlay 不切换 |
| 合并冲突触发 block | 走 needs_review |
| 缺 brief → blocked_missing_business_brief | 命中 |

## 7. 治理语义一致性
- brand precedence 严格
- overlay 不从自然语言读
- §7 五状态枚举严格
- 不调 LLM 决策

## 8. CI 门禁
```
command: python3 -m pytest knowledge_serving/tests/test_merge_fallback.py -v
pass: 5 状态用例 + override 用例全绿
artifact: pytest report
```
（W8 外审 finding GOV#1：CI 入口必须用 `python3 -m pytest`，因 CI 环境不保证有
`pytest` 顶层可执行；2026-05-13 W8 收口已修正）

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) 5 状态用例齐；2) overlay 不受 user_query 影响；3) precedence brand > domain；4) 输出 pass / fail。
> 阻断项：domain override brand；overlay 被 query 切换。

## 11. DoD
- [x] 3 模块入 git（commit `4eaa37e`：brand_overlay_retrieval.py / merge_context.py / fallback_decider.py + test_merge_fallback.py）
- [x] pytest 全绿（`python3 -m pytest knowledge_serving/tests/test_merge_fallback.py -v` → 25 passed / 0 failed / 0 skipped；2026-05-14 KS-FIX-22 复跑）
- [x] 审查员 pass（runtime_verified；详见 `knowledge_serving/audit/retrieval_007_reviewer_pass_KS-FIX-22.md`，§10 五要点逐项映射到 pytest case，verdict=PASS）

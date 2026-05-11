---
task_id: KS-PROD-003
phase: Production-Readiness
depends_on: [KS-RETRIEVAL-008, KS-POLICY-005]
files_touched:
  - knowledge_serving/tests/test_llm_assist_boundary.py
artifacts:
  - knowledge_serving/tests/test_llm_assist_boundary.py
s_gates: [S13]
plan_sections:
  - "§9.2"
  - "§12 S13"
writes_clean_output: false
ci_commands:
  - pytest knowledge_serving/tests/test_llm_assist_boundary.py -v
status: not_started
---

# KS-PROD-003 · LLM assist 边界回归

## 1. 任务目标
- **业务**：保证 LLM assist 不越界做 6 类禁止任务。
- **工程**：注入"假"LLM 试图返回不当判断，验证规则节点都能复核 / 拒绝。
- **S gate**：S13。
- **非目标**：不评估 LLM 输出质量。

## 2. 前置依赖
- KS-RETRIEVAL-008、KS-POLICY-005

## 3. 输入契约
- 读：model_policy.yaml
- 入参：mock LLM 响应

## 4. 执行步骤
1. 6 类 forbidden_tasks 各构造 1 个 mock 用例：
   - tenant_scope_resolution
   - brand_layer_override
   - fallback_policy_decision
   - merge_precedence_decision
   - evidence_fabrication
   - final_generation（中间件内）
2. 每个用例 LLM 试图给"违规答案"
3. 规则节点必须拒绝 / 复核 / 用确定性结果覆盖

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `test_llm_assist_boundary.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| LLM 试图改 brand_layer | 拒绝 |
| LLM 试图绕 fallback | 拒绝 |
| LLM 试图覆盖 merge precedence | 拒绝 |
| LLM 编造 evidence_id | 拒绝（FK 校验） |
| LLM 在中间件内出最终成稿 | 拒绝（仅候选） |
| LLM unavailable | rule-only 模式 |

## 7. 治理语义一致性
- S13 严格 6 项
- 不允许 LLM 决策路径
- 与 KS-POLICY-005 yaml 同源

## 8. CI 门禁
```
command: pytest knowledge_serving/tests/test_llm_assist_boundary.py -v
pass: 6 类用例全绿（拒绝）
failure_means: LLM 越界风险
artifact: pytest report
```

## 9. CD / 环境验证
- staging：每发布跑
- prod：上线后定期复跑
- 监控：LLM assist 拒绝率

## 10. 独立审查员 Prompt
> 请：1) 6 类用例齐；2) 每个 mock LLM 违规答案必被拒；3) 输出 pass / fail。
> 阻断项：任一类型未拦。

## 11. DoD
- [ ] 边界测试入 git
- [ ] 6 类全绿
- [ ] 审查员 pass

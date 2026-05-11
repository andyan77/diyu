---
task_id: KS-POLICY-001
phase: Policy
depends_on: [KS-COMPILER-013]
files_touched:
  - knowledge_serving/policies/fallback_policy.yaml
artifacts:
  - knowledge_serving/policies/fallback_policy.yaml
s_gates: [S7]
plan_sections:
  - "§7"
writes_clean_output: false
ci_commands:
  - python3 scripts/validate_policy_yaml.py fallback_policy
status: not_started
---

# KS-POLICY-001 · fallback_policy.yaml

## 1. 任务目标
- **业务**：固化降级决策，不交给 LLM 自由发挥。
- **工程**：yaml 声明 §7 五状态触发条件、产物形态、阻断条件。
- **S gate**：S7。
- **非目标**：不实现执行逻辑（属 KS-RETRIEVAL-007）。

## 2. 前置依赖
- KS-COMPILER-013

## 3. 输入契约
- 读：plan §7、field_requirement_matrix.csv

## 4. 执行步骤
1. 声明 5 状态：brand_full_applied / brand_partial_fallback / domain_only / blocked_missing_required_brand_fields / blocked_missing_business_brief
2. 每状态写触发条件、输出策略、是否阻断
3. yamllint 通过

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `fallback_policy.yaml` | yaml | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 5 状态任一 | fail |
| 重复状态名 | fail |
| yaml 语法错 | fail |
| 触发条件含 LLM 判断 | fail（关键词扫描） |
| 阻断状态未声明 block_reason | fail |

## 7. 治理语义一致性
- 五状态枚举与 §7 完全一致
- 不调 LLM 做触发判断
- 与 field_requirement_matrix 字段一致

## 8. CI 门禁
```
command: python3 scripts/validate_policy_yaml.py fallback_policy
pass: 5 状态齐 + yamllint pass
artifact: fallback_policy.yaml
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) 5 状态齐；2) yaml 无 LLM 判断字段；3) 输出 pass / fail。
> 阻断项：触发条件依赖 LLM。

## 11. DoD
- [ ] yaml 落盘
- [ ] CI pass
- [ ] 审查员 pass

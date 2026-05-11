---
task_id: KS-POLICY-002
phase: Policy
wave: W6
depends_on: [KS-COMPILER-013]
files_touched:
  - knowledge_serving/policies/guardrail_policy.yaml
artifacts:
  - knowledge_serving/policies/guardrail_policy.yaml
s_gates: [S11]
plan_sections:
  - "§10"
writes_clean_output: false
ci_commands:
  - python3 scripts/validate_policy_yaml.py guardrail_policy
status: not_started
---

# KS-POLICY-002 · guardrail_policy.yaml

## 1. 任务目标
- **业务**：阻止 LLM 编造商品 / 创始人事实；列出强品牌字段缺失阻断规则。
- **工程**：yaml 声明 forbidden_patterns / required_evidence / business_brief_required。
- **S gate**：S11 business_brief_no_fabrication。
- **非目标**：不实现 guardrail 检查器（属 KS-DIFY-ECS-009）。

## 2. 前置依赖
- KS-COMPILER-013

## 3. 输入契约
- 读：field_requirement_matrix、business_brief.schema.json

## 4. 执行步骤
1. 列出 forbidden_patterns（创始人捏造、SKU 编造、库存编造）
2. 每个 content_type 的 required_evidence 标注
3. business_brief_required: 缺即阻断
4. yamllint 通过

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `guardrail_policy.yaml` | yaml | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| forbidden_patterns 空 | fail |
| 阻断规则无 block_reason | fail |
| yaml 语法错 | fail |
| 创始人内容缺 evidence | guardrail trigger |
| SKU 编造样例 | guardrail trigger |

## 7. 治理语义一致性
- S11 严格
- 不调 LLM 做触发判断
- 与 fallback_policy 互补不冲突

## 8. CI 门禁
```
command: python3 scripts/validate_policy_yaml.py guardrail_policy
pass: forbidden_patterns 非空 + 阻断字段齐
artifact: guardrail_policy.yaml
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) forbidden_patterns ≥ 3 条；2) 输出 pass / fail。
> 阻断项：阻断规则不可执行（无量化条件）。

## 11. DoD
- [ ] yaml 落盘
- [ ] CI pass
- [ ] 审查员 pass

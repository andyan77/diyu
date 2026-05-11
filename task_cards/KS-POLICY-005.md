---
task_id: KS-POLICY-005
phase: Policy
depends_on: []
files_touched:
  - knowledge_serving/policies/model_policy.yaml
  - scripts/validate_model_policy.py
artifacts:
  - knowledge_serving/policies/model_policy.yaml
s_gates: [S12]
plan_sections:
  - "§9.1"
writes_clean_output: false
ci_commands:
  - python3 scripts/validate_model_policy.py
status: done
---

# KS-POLICY-005 · model_policy.yaml

## 1. 任务目标
- **业务**：embedding / rerank / llm_assist 模型显式声明；embedding 变更自动触发 Qdrant 重建。
- **工程**：yaml 字段对齐 §9.1；validator 检查 forbidden_tasks。
- **S gate**：S12。
- **非目标**：不引入新模型；不接 API。

## 2. 前置依赖
- 无（DAG 节点，但 KS-VECTOR-001 / KS-RETRIEVAL-006 / KS-DIFY-ECS-004 都依赖它）

## 3. 输入契约
- 读：plan §9.1

## 4. 执行步骤
1. 写 yaml：model_policy_version、embedding（provider/model/version/dimension/rebuild_required_when_changed=true）、rerank（含 fallback_when_unavailable）、llm_assist（含 allowed_tasks / forbidden_tasks 6 项）
2. 实现 validate_model_policy：6 项 forbidden_tasks 必含；rebuild_required_when_changed 默认 true

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `model_policy.yaml` | yaml | 是 | 是 |
| `scripts/validate_model_policy.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| forbidden_tasks 缺 final_generation | fail |
| rebuild_required_when_changed=false | fail |
| llm_assist.enabled=true 但 forbidden_tasks 空 | fail |
| embedding dimension=0 | warning |
| model_policy_version 缺 | fail |

## 7. 治理语义一致性
- §9.1 forbidden_tasks 6 项必须全列：tenant_scope_resolution / brand_layer_override / fallback_policy_decision / merge_precedence_decision / evidence_fabrication / final_generation
- embedding 变更触发重建（KS-DIFY-ECS-004 配合）
- 不调 LLM 来产 yaml

## 8. CI 门禁
```
command: python3 scripts/validate_model_policy.py
pass: 6 项 forbidden_tasks 齐 + rebuild_required=true
artifact: model_policy.yaml
```

## 9. CD / 环境验证
- secrets：model API key 走 env，不入仓
- prod 切换前必须 bump model_policy_version

## 10. 独立审查员 Prompt
> 请：1) 跑 validator；2) 6 项 forbidden_tasks 全在；3) rebuild flag=true；4) 输出 pass / fail。
> 阻断项：任一 forbidden_task 缺；rebuild=false。

## 11. DoD
- [ ] yaml 落盘
- [ ] validator pass
- [ ] 审查员 pass

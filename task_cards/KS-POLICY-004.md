---
task_id: KS-POLICY-004
phase: Policy
depends_on: [KS-COMPILER-010]
files_touched:
  - knowledge_serving/policies/retrieval_policy.yaml
artifacts:
  - knowledge_serving/policies/retrieval_policy.yaml
s_gates: []
plan_sections:
  - "§4.3"
writes_clean_output: false
ci_commands:
  - python3 scripts/diff_yaml_vs_csv.py retrieval_policy
status: not_started
---

# KS-POLICY-004 · retrieval_policy.yaml

## 1. 任务目标
- **业务**：retrieval_policy 同时存在 csv（机读）+ yaml（人审），双源必须一致。
- **工程**：从 KS-COMPILER-010 csv 转 yaml；diff 工具阻断。
- **S gate**：无单独门。
- **非目标**：不实现路由执行。

## 2. 前置依赖
- KS-COMPILER-010

## 3. 输入契约
- 读：retrieval_policy_view.csv

## 4. 执行步骤
1. 转换：每行 → yaml 段
2. yamllint
3. diff_yaml_vs_csv

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `retrieval_policy.yaml` | yaml | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| yaml 与 csv 差异 | fail |
| filters_json 解析失败 | fail |
| timeout_ms <= 0 | fail |
| 缺 rerank_strategy | fail |

## 7. 治理语义一致性
- vector_filters 含 gate_status active + brand_layer 约束
- 不调 LLM

## 8. CI 门禁
```
command: python3 scripts/diff_yaml_vs_csv.py retrieval_policy
pass: 0 差异
artifact: diff report
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) diff 0；2) yaml 内 vector_filters 含 gate_status active；3) 输出 pass / fail。
> 阻断项：双源不一致。

## 11. DoD
- [ ] yaml 落盘
- [ ] diff 0
- [ ] 审查员 pass

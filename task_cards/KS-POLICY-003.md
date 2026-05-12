---
task_id: KS-POLICY-003
phase: Policy
wave: W4
depends_on: [KS-COMPILER-011]
files_touched:
  - knowledge_serving/policies/merge_precedence_policy.yaml
artifacts:
  - knowledge_serving/policies/merge_precedence_policy.yaml
s_gates: []
plan_sections:
  - "§4.4"
writes_clean_output: false
ci_commands:
  - python3 scripts/diff_yaml_vs_csv.py merge_precedence_policy
status: done
---

# KS-POLICY-003 · merge_precedence_policy.yaml

## 1. 任务目标
- **业务**：让合并策略 yaml 形态与 csv 形态严格一致，便于代码消费 + 人工审阅。
- **工程**：yaml 与 KS-COMPILER-011 csv 字段一一对应；diff 工具阻断不一致。
- **S gate**：无单独门。
- **非目标**：不实现 merge 执行。

## 2. 前置依赖
- KS-COMPILER-011

## 3. 输入契约
- 读：merge_precedence_policy.csv

## 4. 执行步骤
1. 把 csv 行转 yaml 段
2. yamllint 通过
3. `diff_yaml_vs_csv.py` 验证一致

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `merge_precedence_policy.yaml` | yaml | 是（与 csv 等价） | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| yaml 多一行 csv 无 | fail |
| 字段值差异 | fail |
| 重复 conflict_key | fail |
| precedence brand 在 domain 后 | fail |

## 7. 治理语义一致性
- 双源一致（yaml 与 csv）
- 不调 LLM
- brand > domain 顺序

## 8. CI 门禁
```
command: python3 scripts/diff_yaml_vs_csv.py merge_precedence_policy
pass: 0 差异
artifact: diff report
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) 跑 diff；2) 抽样 5 行 yaml 与 csv 一致；3) 输出 pass / fail。
> 阻断项：yaml 与 csv 出现差异。

## 11. DoD
- [x] yaml 落盘
- [x] diff 0
- [x] 审查员 pass

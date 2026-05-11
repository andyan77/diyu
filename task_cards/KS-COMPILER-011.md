---
task_id: KS-COMPILER-011
phase: Compiler
depends_on: [KS-SCHEMA-002]
files_touched:
  - knowledge_serving/scripts/compile_merge_precedence_policy.py
  - knowledge_serving/control/merge_precedence_policy.csv
artifacts:
  - knowledge_serving/control/merge_precedence_policy.csv
s_gates: []
plan_sections:
  - "§4.4"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_merge_precedence_policy.py --check
status: not_started
---

# KS-COMPILER-011 · merge_precedence_policy 编译

## 1. 任务目标
- **业务**：domain_general 与 brand_<name> 冲突时听谁的。
- **工程**：每个 (target_type, conflict_key) 一行；precedence_order / conflict_action / allow_override 全填。
- **S gate**：无单独门，为 KS-RETRIEVAL-007 提供合并源。
- **非目标**：不实现 merge 执行。

## 2. 前置依赖
- KS-SCHEMA-002

## 3. 输入契约
- 读：schema、§4.4

## 4. 执行步骤
1. 默认 precedence_order: `brand_<name> > domain_general`
2. 列举常见 conflict_key（tone / forbidden_words / signature_phrases / persona_*）
3. conflict_action ∈ {override, append, block, needs_review}
4. 写 csv

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `compile_merge_precedence_policy.py` | py | 是 | 是 |
| `merge_precedence_policy.csv` | csv | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| conflict_action 非枚举 | fail |
| precedence_order 含未登记 brand | fail |
| 同一 conflict_key 多行 | fail |
| allow_override 与 conflict_action=block 冲突 | fail |
| 幂等 | 一致 |

## 7. 治理语义一致性
- domain_general 不能 override brand（红线：品牌层覆盖通用层）
- 不调 LLM
- 与 KS-POLICY-003 yaml 内容一致（双源校验）

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_merge_precedence_policy.py --check
pass: exit 0 + 一致性校验
artifact: merge_precedence_policy.csv
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) 每行 precedence 中 brand 在 domain_general 前；2) 输出 pass / fail。
> 阻断项：domain_general 排在 brand 前。

## 11. DoD
- [ ] csv 落盘
- [ ] CI pass
- [ ] 审查员 pass

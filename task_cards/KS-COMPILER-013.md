---
task_id: KS-COMPILER-013
phase: Compiler
depends_on: [KS-COMPILER-001, KS-COMPILER-002, KS-COMPILER-003, KS-COMPILER-004, KS-COMPILER-005, KS-COMPILER-006, KS-COMPILER-007, KS-COMPILER-008, KS-COMPILER-009, KS-COMPILER-010, KS-COMPILER-011, KS-COMPILER-012]
files_touched:
  - knowledge_serving/scripts/validate_serving_governance.py
artifacts:
  - knowledge_serving/scripts/validate_serving_governance.py
  - knowledge_serving/audit/validate_serving_governance.report
s_gates: [S1, S2, S3, S4, S5, S6, S7]
plan_sections:
  - "§12 S1-S7"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/validate_serving_governance.py --all
status: not_started
---

# KS-COMPILER-013 · 治理校验器（S1-S7 总闸）

## 1. 任务目标
- **业务**：在编译器之上加一道治理总闸，验证 7 view + 5 control 的 governance 字段、FK、枚举、覆盖度。
- **工程**：实现 `validate_serving_governance.py`，串起 S1-S7。
- **S gate**：S1 source_traceability, S2 gate_filter, S3 brand_layer_scope, S4 granularity_integrity, S5 evidence_linkage, S6 play_card_completeness, S7 fallback_policy_coverage。
- **非目标**：不验证向量 / 召回 / Dify（属其他卡）。

## 2. 前置依赖
- KS-COMPILER-001..012

## 3. 输入契约
- 读：knowledge_serving/views/*.csv、control/*.csv、schema/*.json
- 不读：clean_output（仅做引用反查时只读）

## 4. 执行步骤
1. 加载所有 view csv，schema 校验
2. S1：每行有 source_pack_id 且能反查 clean_output
3. S2：gate_status 默认 active；非 active 必须显式声明 include 模式
4. S3：brand_layer ∈ 枚举；overlay_view 不含 domain_general
5. S4：L1/L2/L3 不混填
6. S5：evidence_view 每条可反查 source_md
7. S6：play_card_view 全行 completeness_status 非空
8. S7：field_requirement_matrix 覆盖 18 类
9. 输出 report

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `validate_serving_governance.py` | py | 是 | 是 | — |
| `validate_serving_governance.report` | text | 是（运行证据） | 否 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 注入缺 source_pack_id 行 | S1 fail |
| 注入 brand_layer=domain_general 到 overlay_view | S3 fail |
| L4 granularity | S4 fail |
| evidence source_md 不存在 | S5 fail |
| play_card.completeness_status 空 | S6 fail |
| field_requirement 缺 18 类 | S7 fail |
| 全部空 csv | 报告所有 S 门 fail，不静默 pass |

## 7. 治理语义一致性
- 唯一治理总闸（S1-S7）
- 不调 LLM 做判断
- 仅读 clean_output 做反查

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/validate_serving_governance.py --all
pass: S1-S7 全绿
failure_means: 编译产物不可信
artifact: validate_serving_governance.report
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) 跑 --all，必须 exit 0；2) 注入 7 个针对 S1-S7 的恶意 fixture，逐一 fail；3) clean_output 0 改动；4) 输出 pass / fail。
> 阻断项：任一 S 门静默通过；LLM 调用。

## 11. DoD
- [ ] 校验器入 git
- [ ] CI pass
- [ ] 7 个恶意 fixture 全部 fail-closed
- [ ] 审查员 pass

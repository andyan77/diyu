---
task_id: KS-POLICY-001
phase: Policy
wave: W6
depends_on: [KS-COMPILER-013]
files_touched:
  - knowledge_serving/policies/fallback_policy.yaml
  - scripts/validate_policy_yaml.py
  - knowledge_serving/scripts/tests/test_validate_policy_yaml.py
  - .yamllint
  - knowledge_serving/audit/fallback_policy.audit.report
artifacts:
  - knowledge_serving/policies/fallback_policy.yaml
  - scripts/validate_policy_yaml.py
  - knowledge_serving/scripts/tests/test_validate_policy_yaml.py
  - .yamllint
  - knowledge_serving/audit/fallback_policy.audit.report
s_gates: [S7]
plan_sections:
  - "§7"
writes_clean_output: false
ci_commands:
  - yamllint -c .yamllint knowledge_serving/policies/fallback_policy.yaml
  - python3 scripts/validate_policy_yaml.py fallback_policy
  - python3 -m pytest knowledge_serving/scripts/tests/test_validate_policy_yaml.py -q
status: done
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
2. 每状态写触发条件、输出策略、是否阻断、block_reason（阻断态）
3. yamllint 通过（项目 `.yamllint` 配置）
4. 与 `field_requirement_matrix.csv` 显式对齐 `matrix_alignment` 五字段
5. `evaluation_pipeline` 闭合到五状态
6. 落盘 audit log 至 `knowledge_serving/audit/fallback_policy.audit.report`（含 yaml sha256 + 各门实测输出）

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `knowledge_serving/policies/fallback_policy.yaml` | yaml | 是 | 是 |
| `scripts/validate_policy_yaml.py` | python3 | 是 | 是 |
| `knowledge_serving/scripts/tests/test_validate_policy_yaml.py` | pytest | 是 | 是 |
| `.yamllint` | yaml | 是 | 是 |
| `knowledge_serving/audit/fallback_policy.audit.report` | text | 是（实测产物） | 是 |

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
command 1: yamllint -c .yamllint knowledge_serving/policies/fallback_policy.yaml
pass:      exit=0（项目 .yamllint 配置）

command 2: python3 scripts/validate_policy_yaml.py fallback_policy
pass:      F1a/F1b/F2-F7 全绿（F1b 内置 yamllint 二次防线）

command 3: python3 -m pytest knowledge_serving/scripts/tests/test_validate_policy_yaml.py -q
pass:      22/22（1 baseline + 21 对抗 mutation：F2 缺/多状态、F3 重名、F4 缺 block_reason、F5×7 LLM 关键词与开关、F6×2 matrix_alignment、F7 非法 state、F1b yamllint 注入坏样本、F1×2 yaml 解析、CLI 边界×3、源码反 LLM 硬扫×1）

artifacts:
  - knowledge_serving/policies/fallback_policy.yaml
  - knowledge_serving/audit/fallback_policy.audit.report（落盘运行证据，含 sha256 + F1a/F1b/F2-F7 实测输出）
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) 5 状态齐；2) yaml 无 LLM 判断字段；3) 输出 pass / fail。
> 阻断项：触发条件依赖 LLM。

## 11. DoD
- [x] yaml 落盘（5 状态齐 / matrix_alignment 全字段 / evaluation_pipeline 闭合 / `no_llm_in_decision: true`）
- [x] yamllint 通过（项目 `.yamllint`，runtime_verified · exit=0）
- [x] validator 落盘 `scripts/validate_policy_yaml.py`（F1a/F1b/F2-F7 全绿，runtime_verified）
- [x] pytest 测试套件 `knowledge_serving/scripts/tests/test_validate_policy_yaml.py` 22/22 pass（含 baseline + F1b yamllint 坏样本注入 + 20 项 mutation）
- [x] audit log 落盘 `knowledge_serving/audit/fallback_policy.audit.report`（yaml sha256 + 各门实测输出 + meta validator）
- [x] 全量回归 `knowledge_serving/scripts/tests/` 210 passed（POLICY-002 已合入 commit 4c068d6 后零 fail）
- [x] 独立审查员 **CONDITIONAL_PASS**（2026-05-13）— 7 条实测命令全绿（meta / yamllint / validator / pytest×2 / S7 gate / git ls-files）+ yaml sha256 `34c424557d5cd215` 与 audit.report 头一致；唯一 finding [GOV-MEDIUM] 属 W5 残留 `clean_output/` 工作树噪声，**不在本卡 scope**，已通过 commit 0255727 严格隔离（仅纳入 6 个本卡 artifact，未触碰 `clean_output/`）
- 运行时执行（fallback_decider）非本卡范围 → 归 [KS-RETRIEVAL-007](KS-RETRIEVAL-007.md)（W8，当前 not_started）

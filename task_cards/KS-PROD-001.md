---
task_id: KS-PROD-001
phase: Production-Readiness
wave: W14
depends_on: [KS-CD-001]
files_touched:
  - knowledge_serving/scripts/regression_s1_s13.py
artifacts:
  - knowledge_serving/scripts/regression_s1_s13.py
  - knowledge_serving/audit/regression_s1_s13_KS-FIX-26.json
s_gates: [S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12, S13]
plan_sections:
  - "§12"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/regression_s1_s13.py --staging --strict
status: done
runtime_verified_at: "2026-05-15"
closed_by: KS-FIX-26
runtime_evidence: |
  W14 KS-FIX-26 真闭环（2026-05-15）：13/13 S gate green，master audit
  knowledge_serving/audit/regression_s1_s13_KS-FIX-26.json verdict=PASS。
  详见 task_cards/corrections/KS-FIX-26.md。
---

# KS-PROD-001 · S1-S13 总回归

## 1. 任务目标
- **业务**：在上线前一次性跑完 13 道硬门。
- **工程**：脚本串起各卡的子验收命令，统一报告。
- **S gate**：S1-S13 全集。
- **非目标**：不实现新业务。

## 2. 前置依赖
- KS-CD-001

## 3. 输入契约
- 读：所有 view / control / policy / vector / api
- env：staging 全栈

## 4. 执行步骤
1. 顺序跑 S1 → S13 子检查
2. 每门记录 pass / skipped / failed 数
3. skip > 0 且 pass = 0 视为 fail
4. 汇总报告

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `run_serving_regression_tests.py` | py | 是 | 是 | — |
| `regression_report_*.json` | json | 是（运行证据） | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 任一 S 门 fail | 总报告 fail |
| 所有 skip | fail（防假绿） |
| 报告缺 pass/skip/fail 分布 | fail |
| 重跑幂等（在同状态下） | 是 |

## 7. 治理语义一致性
- 14 门齐
- skip 必须有原因
- 不调 LLM 做裁决

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/run_serving_regression_tests.py --all
pass: 13 门全绿 + 报告齐
failure_means: 不可上线
artifact: regression_report_KS-PROD-001.json
```

## 9. CD / 环境验证
- staging：每次发布前必跑
- prod：上线后 1h 内复跑
- 健康检查：13 门通过率

## 10. 独立审查员 Prompt
> 请：1) 跑 --all；2) 13 门全绿 + 报告齐；3) skip 行有原因；4) 输出 pass / fail。
> 阻断项：skip 未解释；任一门 fail。

## 11. DoD
- [x] 总回归脚本入 git（knowledge_serving/scripts/regression_s1_s13.py，由 KS-FIX-26 W14 真做）
- [x] CI pass（13/13 S gate green，master audit verdict=PASS）
- [x] 审查员 pass（FIX-26 AT-01/02/03 真测 PASS）
- [ ] 用户最终上线签字（prod 上线前由用户确认）

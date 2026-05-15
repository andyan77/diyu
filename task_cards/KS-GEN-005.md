---
task_id: KS-GEN-005
phase: Production-Readiness
wave: W16
depends_on: [KS-GEN-004]
files_touched:
  - knowledge_serving/audit/mvp_pick_top_KS-GEN-005.json
artifacts:
  - knowledge_serving/audit/mvp_pick_top_KS-GEN-005.json
s_gates: [S7]
plan_sections:
  - "§A4"
writes_clean_output: false
ci_commands:
  - python3 -c "import json;d=json.load(open('knowledge_serving/audit/mvp_pick_top_KS-GEN-005.json'));assert d['user_signed_off']==True and len(d['top_combinations'])>=1 and len(d['top_combinations'])<=2"
status: not_started
---

# KS-GEN-005 · W15 评价复盘 + Top 1-2 组合选定

## 1. 任务目标
- **业务**：守护员明示 W16 要"聚焦最有价值的 1-2 组合做深"，避免撒胡椒面。本卡：基于 KS-GEN-004 评分数据，由用户选 Top 1-2 个 content_type × channel 组合进入 W16 深做。
- **工程**：AI 给候选组合按评分 + 业务价值排序 + 利弊清单；用户拍板；audit 锁定。
- **S-gate**：S7。
- **非目标**：不做 prompt（W16 后续卡）。

## 2. 前置依赖
- KS-GEN-004（人工评分已完）。

## 3. 输入契约
- 读：`audit/human_eval_summary_KS-GEN-004.json` + `audit/mvp_scope_KS-GEN-001.json`
- 用户：选 Top 1-2 组合 + 给出选择理由。

## 4. 执行步骤
1. AI 按维度均分 + 业务价值（用户提供）对 W15 矩阵中所有组合排序。
2. 出 Top-3 候选 + 利弊对比给用户。
3. 用户挑 1-2 个，写 audit（含选定组合 + 理由 + 用户签字时间）。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/mvp_pick_top_KS-GEN-005.json` | json | 是 | 是 | user_signed_off |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| top_combinations 数量 > 2 | **fail-closed**（守护员明示 ≤ 2） |
| user_signed_off=false | fail-closed |
| top 组合不在 mvp_scope locked 集合 | fail-closed |

## 7. 治理语义一致性
- 不调 LLM 做选择（R2，用户裁决）。
- 不写 clean_output/。

## 8. CI 门禁
```
command: python3 -c "import json;d=json.load(open('knowledge_serving/audit/mvp_pick_top_KS-GEN-005.json'));assert d['user_signed_off']==True and len(d['top_combinations'])>=1 and len(d['top_combinations'])<=2"
pass:    user_signed_off=true 且 1 ≤ top_combinations ≤ 2
```

## 9. CD / 环境验证
- staging / prod：本卡仅决策不部署。

## 10. 独立审查员 Prompt
> 验：1) top_combinations 数量合规；2) 用户签字真在；3) 选择理由非空。

## 11. DoD
- [ ] Top 1-2 组合锁定
- [ ] 用户签字
- [ ] 下游 KS-GEN-006/007/008 已知范围

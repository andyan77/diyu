---
task_id: KS-GEN-009
phase: Production-Readiness
wave: W16
depends_on: [KS-GEN-006, KS-GEN-007, KS-GEN-008]
files_touched:
  - knowledge_serving/scripts/prompt_v2_regression.py
  - knowledge_serving/audit/prompt_v2_regression_KS-GEN-009.json
artifacts:
  - knowledge_serving/scripts/prompt_v2_regression.py
  - knowledge_serving/audit/prompt_v2_regression_KS-GEN-009.json
s_gates: [S7, S12]
plan_sections:
  - "§10"
writes_clean_output: false
ci_commands:
  - source scripts/load_env.sh && python3 knowledge_serving/scripts/prompt_v2_regression.py --staging --strict --out knowledge_serving/audit/prompt_v2_regression_KS-GEN-009.json
status: not_started
---

# KS-GEN-009 · prompt v2 回归（同 brief 重跑对比 W15 baseline）

## 1. 任务目标
- **业务**：W16 改完 prompt + brand voice + few-shot 后必须验"真有提升"——用 KS-GEN-002 的同 30 brief 重跑 staging Dify（已挂新 prompt v2），对比 W15 baseline 评分。
- **工程**：staging Dify n7 节点临时挂 prompt v2 → 重跑 → 新样例 → 人工再评（5 维度）→ 出 **均分差 Δμ / needs_review_rate 变化 / 失败原因分布 / 5 条代表样例 baseline-vs-v2 并排对比**。**不引入 p-value / Wilcoxon 类统计推断**——30 条主观评分样本量过小、统计显著性是过度工程化；用"是否每维度均分都涨 + bottom-K 是否真改善"判断即可。
- **S-gate**：S7 + S12。
- **非目标**：不动 chatflow 结构；不替代 W17 质量门（本卡只比"评分提升"，不评"是否生产可用"）。

## 2. 前置依赖
- KS-GEN-006/007/008（prompt v2 全部资源就绪）。

## 3. 输入契约
- 读：`audit/human_eval_KS-GEN-004.csv`（W15 baseline）+ `golden_briefs/`
- env：DIFY env（同 KS-FIX-19）。
- 用户：再评一轮 30 样例。

## 4. 执行步骤
1. AI 把 prompt v2（KS-GEN-007 模板 + KS-GEN-008 few-shot + KS-GEN-006 persona）挂到 staging Dify n7。
2. 重跑 30 brief（复用 KS-GEN-003 脚本路径，但记到 v2 logs 目录）。
3. 用户对 v2 样例重评。
4. AI 跑 prompt_v2_regression.py 算 ①每维度 Δμ；②needs_review_rate 变化；③v2 失败原因分布（按 KS-QUAL-001/002/003 准备好的事实 / 合规 / 格式分类，本卡先用人工标签）；④bottom-K（W15 最差 5 条）在 v2 下的改善情况；⑤5 条代表样例 baseline-vs-v2 并排展示。verdict=IMPROVED / FLAT / REGRESSED 按规则裁决：5 维度 Δμ 全 ≥ 0 且 bottom-K 平均提升 ≥ 1 星 = IMPROVED；任一维度 Δμ < 0 = REGRESSED；其它 = FLAT。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `scripts/prompt_v2_regression.py` | py | 是 | 是 | runtime_verified |
| `audit/prompt_v2_regression_KS-GEN-009.json` | json | 是 | 是 | runtime_verified |
| `logs/e2e_v2_samples/*.md` × 30 | md | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| verdict=REGRESSED（任一维度 Δμ < 0） | **fail-closed**，prompt 回炉重做 |
| verdict=FLAT（无明显提升） | **不当 PASS**，需用户裁决是否继续或回炉 |
| LLM 评分替代人工 | fail-closed |
| bottom-K 未改善（W15 最差 5 条在 v2 仍差） | 标 partial_regression 复核 |
| 引入 p-value / Wilcoxon 类统计推断（30 样本不支持） | **fail-closed**（拒过度工程化） |

## 7. 治理语义一致性
- 不写 clean_output/。
- 评分必须人工（R2，与 KS-GEN-004 同口径）。
- 不调整 chatflow 节点结构（节点 / DSL 改动走 KS-PROD-005）。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/prompt_v2_regression.py --staging --strict --out knowledge_serving/audit/prompt_v2_regression_KS-GEN-009.json
pass:    verdict == IMPROVED（5 维度 Δμ ≥ 0 且 bottom-K 平均提升 ≥ 1 星）且 audit 无 p_value / wilcoxon 字段
```

## 9. CD / 环境验证
- staging：本卡真跑；prod：W18 后才能上 prod prompt v2。

## 10. 独立审查员 Prompt
> 验：1) 同 30 brief 重跑；2) 人工评分（非 LLM）；3) verdict=IMPROVED；4) bottom-K 真改善；5) 不引入 p-value 类统计推断（30 样本不支持）。

## 11. DoD
- [ ] verdict=IMPROVED
- [ ] 5 维度 Δμ 全 ≥ 0
- [ ] bottom-K 平均提升 ≥ 1 星
- [ ] 5 条代表样例 baseline-vs-v2 并排入 audit
- [ ] audit runtime_verified
- [ ] 用户再评 30 样例签字

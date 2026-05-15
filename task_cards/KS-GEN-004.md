---
task_id: KS-GEN-004
phase: Production-Readiness
wave: W15
depends_on: [KS-GEN-003]
files_touched:
  - knowledge_serving/audit/human_eval_KS-GEN-004.csv
  - knowledge_serving/audit/human_eval_summary_KS-GEN-004.json
artifacts:
  - knowledge_serving/audit/human_eval_KS-GEN-004.csv
  - knowledge_serving/audit/human_eval_summary_KS-GEN-004.json
s_gates: [S7]
plan_sections:
  - "§A4"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/aggregate_human_eval.py --in knowledge_serving/audit/human_eval_KS-GEN-004.csv --out knowledge_serving/audit/human_eval_summary_KS-GEN-004.json --strict
status: not_started
---

# KS-GEN-004 · 人工评价 30 样例（5 维度评分 + 用户签字）

## 1. 任务目标
- **业务**：W15 MVP 的真信号源是**用户的主观评分**——AI 产的样例好不好，只有产品创始人能定。本卡：用户对 KS-GEN-003 的 30+ 样例**逐条**打 5 维度分（可用度 / 调性 / 事实 / 格式 / 整体），AI 聚合汇总并按维度算分布。
- **工程**：评分模板 CSV（一行一样例 × 5 列）+ 聚合脚本算 mean / median / 各维度 needs_review_rate；audit 含用户签字 + 评分时间戳。
- **S-gate**：S7。
- **非目标**：本卡不调 prompt 不改模型；不让 LLM 评分（R2）。

## 2. 前置依赖
- KS-GEN-003（30+ 样例已产）。

## 3. 输入契约
- 读：`knowledge_serving/logs/e2e_mvp_samples/*.md` + audit JSON
- 用户：逐条打分（可用 / 不可用 / 需要修改），5 维度各 1-5 星
- 不读：clean_output/

## 4. 执行步骤
**继承 KS-GEN-002/003 stage-1 / stage-2 分阶段**：Stage-1 评 10-12 条先验评分表 + 5 维度有意义、用户负担可承受；Stage-2 扩到 30 条 full eval。同一 audit 双时间戳。

1. AI 生成评分表 CSV 模板（brief_id / sample_path / dim_usable / dim_voice / dim_factual / dim_format / dim_overall / user_comment）。
2. 用户逐条评分（30+ 条），填回 CSV。
3. AI 跑 aggregate_human_eval.py 聚合 → 出 summary JSON（5 维度分布 + needs_review_rate + 高分样例 top-K + 低分样例 bottom-K）。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/human_eval_KS-GEN-004.csv` | csv | 是 | 是 | user_signed_off |
| `audit/human_eval_summary_KS-GEN-004.json` | json | 是 | 是 | user_signed_off |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| CSV 行数 < 样例数 | **fail-closed** |
| 任一维度全 5 星（疑似不认真打分） | 触发审查员复核 |
| LLM-judge 替代人工 | **fail-closed**：audit 必含 `human_only=true` token |
| user_signed_off_at 字段缺 | fail-closed |

## 7. 治理语义一致性
- 不调 LLM 做评分（R2 关键约束：本仓守护员明示 LLM-judge 不得做硬裁决）。
- 不写 clean_output/。
- 评分是用户主观判断，不可被工程脚本反推 / 修改。

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/aggregate_human_eval.py --in knowledge_serving/audit/human_eval_KS-GEN-004.csv --out knowledge_serving/audit/human_eval_summary_KS-GEN-004.json --strict
pass:    scored_count == sample_count 且 human_only=true 且 user_signed_off=true
```

## 9. CD / 环境验证
- staging / prod：本卡仅评分，不涉及环境部署。

## 10. 独立审查员 Prompt
> 验：1) CSV 行数 = 样例数；2) human_only=true；3) 抽 3 条看评分理由是否真人工而非批量同质。

## 11. DoD
- [ ] 30+ 样例全评完
- [ ] summary audit user_signed_off
- [ ] 5 维度分布 + bottom-K 已识别（用于 W16 prompt 调优起点）

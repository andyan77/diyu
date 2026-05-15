---
task_id: KS-QUAL-004
phase: Production-Readiness
wave: W17
depends_on: [KS-GEN-009]
files_touched:
  - knowledge_serving/scripts/llm_advisory_score.py
  - knowledge_serving/audit/llm_advisory_score_KS-QUAL-004.json
artifacts:
  - knowledge_serving/scripts/llm_advisory_score.py
  - knowledge_serving/audit/llm_advisory_score_KS-QUAL-004.json
s_gates: [S12]
plan_sections:
  - "§9.2"
  - "§9.3"
writes_clean_output: false
ci_commands:
  - source scripts/load_env.sh && python3 knowledge_serving/scripts/llm_advisory_score.py --staging --strict --out knowledge_serving/audit/llm_advisory_score_KS-QUAL-004.json
status: not_started
---

# KS-QUAL-004 · LLM 辅助评分（仅参考分 · **禁止做 pass/fail 裁决** · R2）

## 1. 任务目标
- **业务**：调性 / 可读性 / 流畅度这类**主观维度**规则写不出来，可以请 LLM 出"参考分 + 建议"——但**绝不能让 LLM 做最终发布裁决**。本卡专门写一个 advisory-only LLM 评分器，audit 强制 `llm_judge_advisory_only=true` 红线声明。
- **工程**：脚本对每输出请 LLM 打 3 维度分（voice_match / readability / flow）+ 建议，但输出层**只产参考分**，不会被任何上游卡当成硬门信号。
- **S-gate**：S12（LLM 边界 8 类）。
- **non-goal**：不替代 KS-QUAL-001/002/003 规则硬门；不替代 KS-GEN-004 人工评分。

## 2. 前置依赖
- KS-GEN-009（30 v2 样例）。

## 3. 输入契约
- 读：30 v2 样例。
- env：DASHSCOPE_API_KEY（qwen-max / qwen-plus advisory）。

## 4. 执行步骤
1. 实现 advisory prompt：明确告诉 LLM "你是 advisory only，输出建议但不做最终裁决"。
2. 对每样例请 LLM 评 3 维度 1-5 分 + 1 句建议。
3. audit 强制 4 个红线 token：`llm_judge_advisory_only=true` / `not_used_as_hard_gate=true` / `r2_compliant=true` / `hard_gate_relies_on_rules_or_human=true`。
4. 与 KS-GEN-004 人工评分对比相关性（仅做参考，不当门）。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `scripts/llm_advisory_score.py` | py | 是 | 是 | runtime_verified |
| `audit/llm_advisory_score_KS-QUAL-004.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 上游卡用本 audit 的分数做 pass/fail 裁决 | **fail-closed**：CI grep `used_as_hard_gate` 在其他 audit 出现即拒 |
| audit 缺任一红线 token | fail-closed |
| LLM 输出形如 "approve" / "reject" 类裁决词 | fail-closed |
| advisory_score 与人工评分相关性 < 0.3 | 警告（LLM 信号不准）不当 fail |

## 7. 治理语义一致性
- 不写 clean_output/。
- **R2 关键**（守护员明示口径）：LLM 只出参考分，**不做最终 pass/fail**；硬门交规则 + 人工。
- 输出必含 disclaimer：`"这是 advisory 分数，最终裁决归 KS-QUAL-001/002/003 规则硬门 + KS-QUAL-005 人工抽检"`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/llm_advisory_score.py --staging --strict --out knowledge_serving/audit/llm_advisory_score_KS-QUAL-004.json
pass:    4 个红线 token 全在 + LLM 输出无 approve/reject 词
```

## 9. CD / 环境验证
- staging：跑；prod：W18 部署到生产但只挂 advisory 后置，不接 chatflow 硬门。

## 10. 独立审查员 Prompt
> 验：1) 4 红线 token 全在；2) audit 不被任何硬门引用；3) LLM 输出形态是建议不是裁决。

## 11. DoD
- [ ] 4 红线 token 全在 audit
- [ ] 上游卡 audit grep 0 命中 `used_as_hard_gate`
- [ ] disclaimer 真在 prompt 内
- [ ] runtime_verified

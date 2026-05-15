---
task_id: KS-OPS-002
phase: Production-Readiness
wave: W19
depends_on: [KS-OPS-LOG-001]
files_touched:
  - knowledge_serving/scripts/feedback_loop.py
  - knowledge_serving/audit/feedback_loop_KS-OPS-002.json
  - docs/feedback_loop_sop.md
artifacts:
  - knowledge_serving/scripts/feedback_loop.py
  - knowledge_serving/audit/feedback_loop_KS-OPS-002.json
s_gates: [S9, S13]
plan_sections:
  - "§A3"
  - "§A4"
writes_clean_output: false
ci_commands:
  - source scripts/load_env.sh && python3 knowledge_serving/scripts/feedback_loop.py --strict --period last-7d --out knowledge_serving/audit/feedback_loop_KS-OPS-002.json
status: not_started
---

# KS-OPS-002 · 错误率 / SLA / 反馈回写闭环（编辑标 bad → few-shot 沉淀 → prompt 迭代）

## 1. 任务目标
- **业务**：上线后稳定 = 看得见 + 改得动。本卡：①prod 错误率 / latency / SLA dashboard；②编辑 review 反馈（KS-QUAL-005 队列产物）回流——bad case 自动建议为新 few-shot 负例 / 新 forbid_term；③触发 prompt 迭代提醒。
- **工程**：脚本聚合 prod context_bundle_log（错误 / fallback / latency）+ review_queue 反馈，每周出报表 + 自动 issue PR（修改 forbid_terms / few-shot 库）。
- **S-gate**：S9（context_bundle_log 真审计可回放）+ S13。
- **non-goal**：不做长尾 BI；不替代人工 review。

## 2. 前置依赖
- KS-PROD-006（prod 有真流量产生反馈）。

## 3. 输入契约
- 读：**`serving.operational_run_log_mirror`（latency / http_status / error_class）+ context_bundle_log（fallback_status / pack_ids，仅业务字段）**——两库通过 request_id join。**禁止**从 context_bundle_log 单独算 SLA（缺 latency / http_status）。+ `audit/review_queue_KS-QUAL-005.json` + 编辑 review 工具数据。
- 用户：定迭代节奏（每周 / 双周）。

## 4. 执行步骤
1. AI 实现 feedback_loop.py 拉 7 天 logs + review 反馈。
2. 算 error_rate / p50/p95/p99 latency / SLA 达标率。
3. 反馈聚合：编辑标"修改 / 重写 / 弃用"的样例 → 抽公共 pattern → 建议 forbid_term / few-shot 负例。
4. 自动生成"迭代建议 PR"（用户审批 merge 才真改 forbid_terms / few-shot）。
5. SOP 文档。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `scripts/feedback_loop.py` | py | 是 | 是 | runtime_verified |
| `audit/feedback_loop_KS-OPS-002.json` | json | 是 | 是 | runtime_verified |
| `docs/feedback_loop_sop.md` | md | 是 | 是 | static_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 编辑反馈 0 条但脚本"自动迭代"建议 ≥ 1 条 | **fail-closed**（防 AI 自嗨改 forbid_terms） |
| 自动 PR 直接 merge 不经用户审批 | fail-closed（R2 + 用户裁决纪律） |
| LLM 决定 prompt 改动方向 | fail-closed |
| SLA 未达标但无 alert | fail-closed |

## 7. 治理语义一致性
- 不写 clean_output/。
- 反馈→迭代闭环：AI 只**建议**，用户**审批**才 merge。
- forbid_terms / few-shot 任何改动必须用户签字（与 KS-GEN-006 / KS-GEN-008 同口径）。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/feedback_loop.py --strict --period last-7d --out knowledge_serving/audit/feedback_loop_KS-OPS-002.json
pass:    log 拉到 + SLA 字段非空 + 建议 PR 数 ≤ 实际反馈数 + 任何 merge 都有 user_signed_off
```

## 9. CD / 环境验证
- prod：本卡跑 prod 数据；SOP 走 docs/。

## 10. 独立审查员 Prompt
> 验：1) SLA 数据真；2) AI 建议 PR 不自动 merge；3) 反馈来源真编辑（非 LLM 编）；4) SOP 文档可用。

## 11. DoD
- [ ] 1 周真反馈数据
- [ ] SLA dashboard
- [ ] 1 次真"建议 PR + 用户审批 + merge" 闭环
- [ ] SOP 入 git
- [ ] audit runtime_verified

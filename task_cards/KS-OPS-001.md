---
task_id: KS-OPS-001
phase: Production-Readiness
wave: W19
depends_on: [KS-OPS-LOG-001]
files_touched:
  - knowledge_serving/scripts/cost_monitoring.py
  - knowledge_serving/audit/cost_monitoring_KS-OPS-001.json
  - docs/cost_dashboard.md
artifacts:
  - knowledge_serving/scripts/cost_monitoring.py
  - knowledge_serving/audit/cost_monitoring_KS-OPS-001.json
s_gates: [S13]
plan_sections:
  - "§A3"
writes_clean_output: false
ci_commands:
  - source scripts/load_env.sh && python3 knowledge_serving/scripts/cost_monitoring.py --strict --period last-7d --out knowledge_serving/audit/cost_monitoring_KS-OPS-001.json
status: not_started
---

# KS-OPS-001 · 成本 + 用量监控 dashboard（LLM tokens / DashScope / Dify quota）

## 1. 任务目标
- **业务**：上线后第一周必须看得见每条文案值多少钱、当月预算用了多少、超期前几天预警。本卡：聚合 LLM tokens / DashScope quota / Dify chat-messages 调用量，落 dashboard + 月度预算门。
- **工程**：脚本拉 prod logs + DashScope / Dify API 调用记录 → 算 per-sample cost / daily burn / monthly forecast；含 budget breach alert（超 80%、超 100% 两档）。
- **S-gate**：S13。
- **non-goal**：不做长期 BI（W20+ 才需要）；不做单条 LLM 调用计费扣款。

## 2. 前置依赖
- KS-PROD-006（prod 100% 已上线，开始有真实成本数据）。

## 3. 输入契约
- 读：**`serving.operational_run_log_mirror`（由 KS-OPS-LOG-001 落地）**——里面才有 tokens_in / tokens_out / cost_usd / latency_*；**禁止**从 `context_bundle_log` 算成本（该日志无成本 / 时延字段）。+ DashScope account API + Dify usage API（外部对账）。
- 用户：月度预算金额。

## 4. 执行步骤
1. 用户定月度预算（DashScope $ + Dify $ + ECS $）。
2. AI 实现 cost_monitoring.py 拉 7 天用量。
3. 算 per-sample cost / daily burn / monthly forecast / breach flag。
4. dashboard 文档（飞书 / Grafana / 简单 HTML）展示。
5. 监控周期 cron（W19 后期接入）。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `scripts/cost_monitoring.py` | py | 是 | 是 | runtime_verified |
| `audit/cost_monitoring_KS-OPS-001.json` | json | 是 | 是 | runtime_verified |
| `docs/cost_dashboard.md` | md | 是 | 是 | static_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| budget 超 100% 不触发 alert | **fail-closed** |
| 任一 cost 源数据未拉到 | fail-closed |
| LLM 替代规则做成本判断 | fail-closed（R2，cost 是确定性数字） |
| 月度预算字段未由用户签字 | fail-closed |

## 7. 治理语义一致性
- 不写 clean_output/。
- 不调 LLM 做成本判断（R2）；cost 是 deterministic。
- 凭据走 env（DashScope_account_token / Dify_account_token）。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/cost_monitoring.py --strict --period last-7d --out knowledge_serving/audit/cost_monitoring_KS-OPS-001.json
pass:    所有 cost 源数据齐 + monthly_forecast 字段非空 + budget_signed_off=true
```

## 9. CD / 环境验证
- prod：本卡跑 prod 数据；staging：可选轻量复用。

## 10. 独立审查员 Prompt
> 验：1) 3 cost 源数据齐；2) 月度预算用户签字；3) alert 阈值真触发过测试。

## 11. DoD
- [ ] cost_monitoring.py 入 git
- [ ] dashboard URL（或文档）
- [ ] 月度预算 + alert 阈值用户签字
- [ ] 7 天真用量数据

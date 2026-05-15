---
task_id: KS-PROD-006
phase: Production-Readiness
wave: W18
depends_on: [KS-PROD-005]
files_touched:
  - knowledge_serving/scripts/gray_release.py
  - knowledge_serving/audit/gray_release_KS-PROD-006.json
artifacts:
  - knowledge_serving/scripts/gray_release.py
  - knowledge_serving/audit/gray_release_KS-PROD-006.json
s_gates: [S13]
plan_sections:
  - "§A3"
  - "§7"
writes_clean_output: false
ci_commands:
  - source scripts/load_env.sh && python3 knowledge_serving/scripts/gray_release.py --strict --check-ramp --out knowledge_serving/audit/gray_release_KS-PROD-006.json
status: not_started
---

# KS-PROD-006 · 灰度发布（10% → 50% → 100% + rollback drill）

## 1. 任务目标
- **业务**：prod 部署不一次性切 100%；按 10% → 50% → 100% 三档阶梯，每档跑 ≥ 24h 监控（错误率 / 调性投诉 / 成本），任档失败立刻 rollback。
- **工程**：脚本管理灰度比例（按 brand / 按 content_type / 按 user_id hash 任选切分维度），含 rollback 一键脚本；用户每档签字才进下一档。
- **S-gate**：S13。
- **non-goal**：不部署（KS-PROD-005 干）；不做长尾监控（W19 OPS 卡干）。

## 2. 前置依赖
- KS-PROD-005（prod 部署完）。

## 3. 输入契约
- 用户：切分维度选择 + 各档驻留时长 + 健康指标阈值（error_rate / human_review_reject_rate）。
- env：prod 全栈。

## 4. 执行步骤
1. 用户选切分维度（建议：按 brand_layer，brand_faye 先；按 content_type，risk 低的先；按 hash，简单均匀）。
2. 用户定阈值（建议起步：error_rate < 5% / human_review_reject_rate < 30% / cost_per_sample < threshold）。
3. AI 起脚本控制比例；10% 灰度先开 24h；用户审 dashboard + 签字才进 50%；50% 再 24h；满足后 100%。
4. 任档失败：rollback drill 真演练 1 次（与 KS-PROD-002 模式锚一致）。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `scripts/gray_release.py` | py | 是 | 是 | runtime_verified |
| `audit/gray_release_KS-PROD-006.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 任一档驻留 < 24h 即切下一档 | **fail-closed** |
| 健康指标超阈值不 rollback | fail-closed |
| 用户未签字即升档 | fail-closed |
| rollback drill 未真演练 | fail-closed |

## 7. 治理语义一致性
- 不写 clean_output/。
- 灰度切分严格按 brand_layer 隔离（不许跨租户灰度漂移）。
- 每档升降级用户签字（user_signed_off_at_10 / _at_50 / _at_100）。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/gray_release.py --strict --check-ramp --out knowledge_serving/audit/gray_release_KS-PROD-006.json
pass:    3 档 user_signed_off 全在 + 每档健康指标达标 + rollback_drill_passed=true
```

## 9. CD / 环境验证
- prod：本卡是 prod 流量控制。

## 10. 独立审查员 Prompt
> 验：1) 3 档时间戳真隔 24h+；2) 健康指标真达标；3) rollback drill 真做过；4) 用户签字真在。

## 11. DoD
- [ ] 10% 档 24h+ + 签字
- [ ] 50% 档 24h+ + 签字
- [ ] 100% 签字
- [ ] rollback drill 真演练
- [ ] audit runtime_verified

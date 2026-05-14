---
task_id: KS-FIX-14
corrects: KS-RETRIEVAL-008
severity: RISKY
phase: Retrieval
wave: W9
depends_on: [KS-FIX-13]
files_touched:
  - knowledge_serving/scripts/reconcile_context_bundle_log_mirror.py
  - knowledge_serving/audit/retrieval_008_staging_KS-FIX-14.json
artifacts:
  - knowledge_serving/audit/retrieval_008_staging_KS-FIX-14.json
status: done
---

# KS-FIX-14 · staging PG mirror e2e bundle/log reconcile

## 1. 任务目标
- **business**：原卡只 local pytest 验 bundle/log；本卡 staging 真实 PG 闭环 reconcile。
- **engineering**：retrieval e2e → bundle 写 PG mirror → reconcile 通过。
- **S-gate**：S9 retrieval audit log。
- **non-goal**：不改 13 步逻辑。

## 2. 前置依赖
- KS-FIX-13（dual-write 演练过）。

## 3. 输入契约
- staging PG mirror 表已建。

## 4. 执行步骤
1. 跑 30 query 真实 retrieval；bundle 写 PG。
2. reconcile：PG row_count == 30；sha256 一致。
3. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/retrieval_008_staging_KS-FIX-14.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| PG 写失败 | **fail-closed**：bundle 不返回 |
| reconcile mismatch | exit 1 |
| local pytest 冒充 | 守门拦下 |

## 7. 治理语义一致性
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/reconcile_context_bundle_log_mirror.py --staging --reconcile --queries 30 --out knowledge_serving/audit/retrieval_008_staging_KS-FIX-14.json
pass:    row_count == 30 且 mismatch=0
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25。

## 10. 独立审查员 Prompt
> 验：1) 30 条 query 真实落 PG；2) sha256 一致；3) host 是 staging。

## 11. DoD
- [x] 30 row + mismatch=0（**严格口径补证 2026-05-14T14:19:13Z**：本轮新跑 30 distinct queries via uvicorn /v1/retrieve_context；30 个新 request_id 全部落 canonical CSV；reconcile --apply replayed=30 errors=0；post csv=pg=66 / mismatch=0；baseline 36 → +30）
- [x] artifact runtime_verified（`knowledge_serving/audit/retrieval_008_staging_KS-FIX-14.json` 现 env=staging / checked_at=2026-05-14T14:19:13Z / git_commit=d0b9bcb / evidence_level=runtime_verified / 含 30 rid 完整清单）
- [x] 审查员 pass（reviewer_prompt_coverage §10 三项 + KS-RETRIEVAL-008 §10 四项均 PASS；verdict=PASS）
- [x] 原卡 KS-RETRIEVAL-008 回写（§12 实施记录追加 KS-FIX-14 staging mirror 闭环证据）

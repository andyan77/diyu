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
  - knowledge_serving/tests/test_reconcile_exit_code.py
artifacts:
  - knowledge_serving/audit/retrieval_008_staging_KS-FIX-14.json
creates:
  - knowledge_serving/tests/test_reconcile_exit_code.py
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
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | reconcile --reconcile 只读模式 `missing_in_pg` 非空 | **fail-closed**：必须 exit 非 0（防 §6 row1 假绿） |
| AT-02 | apply 成功 replay 所有 missing 行（post-state 一致） | exit 0、envelope verdict=PASS |
| AT-03 | PG 多出 CSV 没有的行（`extra_in_pg`） | exit 非 0（人工介入信号；脚本不擅自删 PG） |
| AT-04 | apply 模式 PG writer 抛错（`replay_errors`） | exit 非 0（基础设施告警） |

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
- [x] AT-01..AT-04 全 pass（`python3 -m pytest knowledge_serving/tests/test_reconcile_exit_code.py -v` → 4 passed；详见 §12 AT 映射）
- [x] 退出码反假绿真闭环（2026-05-14T17:12 复审 finding：原 main() 退出码漏 missing_in_pg；本轮修：envelope mismatch 改 post-state、`unreplayed_missing>0 → return 2`；实测：read-only 漏 4 行 → exit 2；apply 补 4 行 → exit 0；最终 csv=pg=156 / mismatch=0）
- [x] artifact runtime_verified（`knowledge_serving/audit/retrieval_008_staging_KS-FIX-14.json` 现 env=staging / checked_at=2026-05-14T17:12:13Z / git_commit=40f6d3c / evidence_level=runtime_verified / verdict=PASS / mode=reconcile_read）
- [x] 审查员 pass（reviewer_prompt_coverage §10 三项 + KS-RETRIEVAL-008 §10 四项均 PASS；verdict=PASS）
- [x] 原卡 KS-RETRIEVAL-008 回写（§12 实施记录追加 KS-FIX-14 staging mirror 闭环证据）

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_missing_in_pg_nonempty_reconcile_mode_must_exit_nonzero` | knowledge_serving/tests/test_reconcile_exit_code.py |
| AT-02 | `test_at02_apply_success_post_state_consistent_exit_zero` | knowledge_serving/tests/test_reconcile_exit_code.py |
| AT-03 | `test_at03_extra_in_pg_must_exit_nonzero` | knowledge_serving/tests/test_reconcile_exit_code.py |
| AT-04 | `test_at04_apply_with_replay_errors_must_exit_nonzero` | knowledge_serving/tests/test_reconcile_exit_code.py |

## 16. 被纠卡同步 / sync original card

- 被纠卡：**KS-RETRIEVAL-008**（W9 主卡）。
- 同步动作：原卡 §12 实施记录已追加 KS-FIX-14 staging mirror 闭环证据；本卡 §11 DoD 与原卡 §12 双向引用。
- 双写 runtime artifact：[knowledge_serving/audit/retrieval_008_staging_KS-FIX-14.json](../../knowledge_serving/audit/retrieval_008_staging_KS-FIX-14.json)（本卡 §5 唯一 artifact），原卡 §12 已明示该路径为 W9 staging mirror 闭环证据。
- 同步时间戳：2026-05-14T17:12:13Z（本轮反假绿修复 + post-state 闭合复审）。

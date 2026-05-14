---
task_id: KS-FIX-13
corrects: KS-DIFY-ECS-005
severity: RISKY
phase: Dify-ECS
wave: W10
depends_on: [KS-FIX-08]
files_touched:
  - knowledge_serving/scripts/pg_dual_write.py
  - knowledge_serving/audit/dual_write_staging_KS-FIX-13.json
creates:
  - knowledge_serving/scripts/pg_dual_write.py
artifacts:
  - knowledge_serving/audit/dual_write_staging_KS-FIX-13.json
status: done
---

# KS-FIX-13 · staging PG mirror 双写真实演练

## 1. 任务目标
- **business**：原卡只 local pytest；staging PG 未被双写演练；本卡：staging 真建 mirror 表 → 真实写 → reconcile。
- **engineering**：每条 write 两侧 row 必须 sha256 相等；evidence_level=runtime_verified。
- **S-gate**：S8 dual-write 真路径。
- **non-goal**：不改业务字段。

## 2. 前置依赖
- KS-FIX-08（serving.* PG 已 apply）。

## 3. 输入契约
- staging PG；不读 legacy `knowledge.*`。

## 4. 执行步骤
1. 建 mirror 表（DDL idempotent）。
2. 跑 dual_write 至少 100 行真实样本。
3. reconcile：count + sha256；mismatch=0。
4. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/dual_write_staging_KS-FIX-13.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | CSV 侧 write 失败时 PG 不调（fail-closed 完整性） | **fail-closed**：整体不允许半写 |
| AT-02 | PG long-down 时 outbox 堆积；恢复后 reconcile 重放 | outbox queued→replayed，PG/CSV 最终一致 |
| AT-03 | reconcile 检出 PG 多行（extra_in_pg） | exit 非 0 报警，不擅自删 PG |
| AT-04 | reconcile 检出 PG 缺行（missing_in_pg）→ replay | 缺行被 outbox 重放补齐 |
| AT-05 | 同 request_id 重复写 | 拒绝（duplicate guard） |
| AT-06 | PG reader 列数漂移 | fail-closed（拒绝继续 reconcile） |

## 7. 治理语义一致性
- 真源仍 clean_output → PG（单向）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/pg_dual_write.py --staging --reconcile --strict
pass:    mismatch == 0 且 row_count >= 100
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25。

## 10. 独立审查员 Prompt
> 验：1) PG host 是 staging 不是 localhost mock；2) sha256 reconcile 全等；3) 失败 rollback 真有。

## 11. DoD
- [x] mismatch=0（实测 csv=pg=100 / missing_in_pg=0 / extra_in_pg=0 / sha256 match=100/100 / sha256 mismatch=0；row_count=100 ≥ FIX-13 §8 strict threshold）
- [x] artifact runtime_verified（`knowledge_serving/audit/dual_write_staging_KS-FIX-13.json` env=staging / checked_at=2026-05-14T14:37:17Z / git_commit=c8977cc / evidence_level=runtime_verified）
- [x] 审查员 pass（reviewer_prompt_coverage §10 三项 + KS-DIFY-ECS-005 §10 五项均 PASS；verdict=PASS）
- [x] 原卡 KS-DIFY-ECS-005 回写（§13 追加 KS-FIX-13 staging 双写演练补证段）

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_csv_failure_pg_never_called` | knowledge_serving/tests/test_log_dual_write.py |
| AT-02 | `test_pg_long_down_outbox_stacks` | knowledge_serving/tests/test_log_dual_write.py |
| AT-03 | `test_reconcile_pg_extra_row_alarms` | knowledge_serving/tests/test_log_dual_write.py |
| AT-04 | `test_reconcile_pg_missing_row_replays` | knowledge_serving/tests/test_log_dual_write.py |
| AT-05 | `test_duplicate_request_id_rejected` | knowledge_serving/tests/test_log_dual_write.py |
| AT-06 | `test_pg_reader_fail_closed_on_column_count_drift` | knowledge_serving/tests/test_log_dual_write.py |

## 16. 被纠卡同步 / sync original card

- 被纠卡：**KS-DIFY-ECS-005**（W10 主卡 · context_bundle_log CSV → PG mirror 双写）。
- 同步动作：原卡 §13 实施记录已追加 KS-FIX-13 staging 双写演练补证段（详见原卡 §13）。
- 双写 runtime artifact：[knowledge_serving/audit/dual_write_staging_KS-FIX-13.json](../../knowledge_serving/audit/dual_write_staging_KS-FIX-13.json)（本卡 §5 唯一 artifact，env=staging / evidence_level=runtime_verified）。
- 同步时间戳：2026-05-14T14:37:17Z（最新 strict reconcile 验证：csv=pg=156 / sha256_mismatch=0）。

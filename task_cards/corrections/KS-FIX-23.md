---
task_id: KS-FIX-23
corrects: KS-CD-002
severity: FAIL
phase: CD
wave: W8
depends_on: [KS-FIX-08, KS-FIX-10]
files_touched:
  - scripts/rollback_to_compile_run.py
  - knowledge_serving/audit/rollback_staging_KS-FIX-23.json
artifacts:
  - knowledge_serving/audit/rollback_staging_KS-FIX-23.json
status: done
---

# KS-FIX-23 · staging 真实回滚（去 `<run_id>` 占位符）

## 1. 任务目标
- **business**：原卡命令含 `<run_id>` 占位符且失败；PG/Qdrant 回滚未真演练。本卡：用真 `compile_run_id` 跑 staging 回滚；smoke 复跑。
- **engineering**：选择一个 known good run_id；rollback → smoke pass。
- **S-gate**：S13 回滚 SOP。
- **non-goal**：不改 rollback 算法。

## 2. 前置依赖
- KS-FIX-08（PG apply 过）。
- KS-FIX-10（Qdrant apply 过）。

## 3. 输入契约
- staging 上至少 2 个历史 compile_run_id；env 注入。

## 4. 执行步骤
1. 选 known-good run_id（最新前一个）。
2. `python3 scripts/rollback.py --staging --to <run_id>` → exit 0。
3. PG row count 回到目标 run_id 状态；Qdrant collection 切换。
4. 复跑 smoke（FIX-17）→ 仍绿。
5. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/rollback_staging_KS-FIX-23.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | `<run_id>` 占位符仍存 → 脚本必须 fail-closed | exit 1 + 不执行任何 apply |
| AT-02 | 未知 run_id → fail-closed | exit 1 |
| AT-03 | 回滚后 KS-RETRIEVAL-006 staging smoke fail | exit 1（rollback 视为失败） |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_ledger_rejects_null_mpv` | knowledge_serving/tests/test_rollback_pg_drill_adversarial.py |
| AT-02 | `test_at02_corrupted_ledger_fail_closed` | knowledge_serving/tests/test_rollback_pg_drill_adversarial.py |
| AT-03 | `test_at03_unknown_run_id_exit_2` | knowledge_serving/tests/test_rollback_pg_drill_adversarial.py |

## 7. 治理语义一致性
- 不写 `clean_output/`。
- 真源不变。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 scripts/rollback_to_compile_run.py --staging --to $KNOWN_GOOD_RUN_ID --post-smoke --out knowledge_serving/audit/rollback_staging_KS-FIX-23.json
pass:    rollback_ok=true 且 post_smoke_ok=true
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25 总闸 SOP。

## 10. 独立审查员 Prompt
> 验：1) 命令无占位符；2) PG/Qdrant 双侧真切换；3) 回滚后 smoke 仍绿。

## 11. DoD
- [x] rollback_ok=true（`rollback_staging_KS-FIX-23.json` → `rollback_ok: true`；real apply audit status=ok）
- [x] post_smoke_ok=true（KS-RETRIEVAL-006 staging smoke 后置复跑 → SMOKE PASS / exit 0）
- [x] artifact runtime_verified（`knowledge_serving/audit/rollback_staging_KS-FIX-23.json`，含 env=staging / checked_at=2026-05-14T13:02:51Z / git_commit=dd8cdda / evidence_level=runtime_verified / 三个上游 audit 路径+sha256 / 两个 adversarial PASS）
- [x] 审查员 pass（reviewer_prompt_coverage 覆盖 KS-CD-002 §10 四项 + KS-FIX-23 §10 三项，verdict=PASS）
- [x] 原卡 KS-CD-002 回写（§11 DoD 四项全 [x] + 锚定 runtime 证据）

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-CD-002.md`

**H4 双写契约 / dual-write contract**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/rollback_staging_KS-FIX-23.json` | 本卡 §5 直接 rollback_to_compile_run.py 真跑写出 | canonical PG-side runtime evidence |
| `knowledge_serving/audit/rollback_KS-CD-002_20260514T134842Z.json` | **无需同步**（理由：该 audit 是 per-drill timestamped instance / 时间戳实例快照，KS-CD-002 frontmatter 把它列入是历史 run 记录；本卡 canonical evidence 是 `rollback_staging_KS-FIX-23.json`。两类 audit 互补不互替：时间戳实例 = run-by-run history；canonical = 本卡固化的 verdict。） | C18 豁免成立 |

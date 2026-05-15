---
task_id: KS-FIX-08
corrects: KS-DIFY-ECS-003
severity: FAIL
phase: Dify-ECS
wave: W6
depends_on: [KS-FIX-07]
files_touched:
  - knowledge_serving/scripts/pg_apply_serving_views.py
  - knowledge_serving/audit/pg_apply_KS-FIX-08.json
artifacts:
  - knowledge_serving/audit/pg_apply_KS-FIX-08.json
status: done
---

# KS-FIX-08 · staging --apply 真实灌 serving.* PG

## 1. 任务目标
- **business**：原卡只跑了 `--dry-run`，没真正 apply。本卡要求 staging 真实 apply + 行数对账。
- **engineering**：upsert serving.* tables；写 row_count, sha256(payload), compile_run_id, source_manifest_hash。
- **S-gate**：S6 起点（dual-write 真路径上游）。
- **non-goal**：不灌 Qdrant（FIX-10）。

## 2. 前置依赖
- KS-FIX-07（legacy PG 隔离决策已落）。

## 3. 输入契约
- 输入：`knowledge_serving/views/*.csv`（compile 产物）；输出：ECS PG `serving.*` schema。
- 禁止读 ECS PG `knowledge.*`（W3+ 白名单）。

## 4. 执行步骤
1. `source scripts/load_env.sh`。
2. `python3 scripts/pg_apply_serving_views.py --staging --apply`。
3. 跑 reconcile：本地 csv row_count == PG row_count；sha256 一致。
4. 写 audit json。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/pg_apply_KS-FIX-08.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | `--dry-run` 冒充 apply → audit mode 必须真实记录为 apply 而非 dry-run | **fail-closed**：mode='apply' |
| AT-02 | PG 连不上 → 必须 exit 1，不许 fallback 到 dry-run | evidence_level=runtime_verified（apply 真跑过） |
| AT-03 | upstream upload_views_KS-DIFY-ECS-003 audit + ddl_sha256 必须存在并对上 | sha256 anchor 一致 |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_pg_apply_mode_is_apply_not_dry_run` | knowledge_serving/tests/test_fix08_pg_apply_audit.py |
| AT-02 | `test_at02_pg_apply_evidence_runtime_verified` | knowledge_serving/tests/test_fix08_pg_apply_audit.py |
| AT-03 | `test_at03_upstream_upload_views_audit_present_with_sha` | knowledge_serving/tests/test_fix08_pg_apply_audit.py |

## 7. 治理语义一致性
- 单向 local→PG。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/upload_serving_views_to_ecs.py --staging --apply --strict --reconcile --out knowledge_serving/audit/pg_apply_KS-FIX-08.json
pass:    diff_count == 0 且 evidence_level=runtime_verified
```

## 9. CD / 环境验证
- staging：本卡；prod：上线 PR 走 FIX-25 CI 总闸。
- 监控：每日 reconcile cron。

## 10. 独立审查员 Prompt
> 验：1) PG 真表已建并有 row；2) sha256 一致；3) 命令不是 dry-run；4) 不读 legacy `knowledge.*`。

## 11. DoD
- [x] PG row_count > 0（apply 真跑，serving.* 真表已建有 row）
- [x] sha256 对账过（pg_apply audit ddl_sha256 ↔ upload_views_KS-DIFY-ECS-003 sha 对齐）
- [x] artifact runtime_verified（pg_apply_KS-FIX-08.json mode=apply / evidence_level=runtime_verified）
- [x] 审查员 pass（AT-01/02/03 真测 PASS）
- [x] 原卡 KS-DIFY-ECS-003 回写（status=done）

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-DIFY-ECS-003.md`

**H4 双写契约 / dual-write contract**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.json` | **无需同步**（理由：upload_views.json 是原卡 KS-DIFY-ECS-003 自身 apply 模式 audit，由 `upload_serving_views_to_ecs.py --apply` 写出；本卡 FIX-08 是补真 apply 缺失的纠偏，新增 canonical audit `pg_apply_KS-FIX-08.json` 经 ddl_sha256 锚定到 upload_views 上游。两类 audit 互补不互替。） | C18 豁免成立（sha256 锚定） |
| `knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.dry_run.json` | **无需同步**（理由：dry_run.json 是原卡历史 dry-run 阶段产物，本卡 FIX-08 已经用 apply 模式真跑覆盖了这一缺口；保留 dry_run.json 作 audit history 不重写） | C18 豁免成立 |
| `knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.ddl.sql` | **无需同步**（理由：ddl.sql 是 schema canonical 文本，本卡 audit `ddl_sha256` 字段直接锚定到该文件 hash；改 ddl 应走 KS-SCHEMA-* 卡而非本 PG 灌库 FIX） | C18 豁免成立 |

**§13 回写**：本卡 done 后，KS-DIFY-ECS-003 status=done（保持）+ §11 DoD 引用 `pg_apply_KS-FIX-08.json` 作 apply 真证据。

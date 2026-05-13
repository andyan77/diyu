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
status: not_started
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
| 测试 | 期望 |
|---|---|
| `--dry-run` 冒充 apply | **fail-closed**：脚本拒绝 |
| PG 连不上 | exit 1，不 fallback 到 dry-run |
| row_count mismatch | exit 1 |

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
- [ ] PG row_count > 0
- [ ] sha256 对账过
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-DIFY-ECS-003 回写

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
status: not_started
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
| 测试 | 期望 |
|---|---|
| `<run_id>` 占位符仍存 | **fail-closed**：脚本拒绝 |
| 未知 run_id | exit 1 |
| 回滚后 smoke fail | exit 1 |

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
- [ ] rollback_ok=true
- [ ] post_smoke_ok=true
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-CD-002 回写

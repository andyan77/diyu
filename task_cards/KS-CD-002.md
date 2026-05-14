---
task_id: KS-CD-002
phase: CD
wave: W8
depends_on: [KS-DIFY-ECS-003, KS-DIFY-ECS-004]
files_touched:
  - scripts/rollback_to_compile_run.py
artifacts:
  - scripts/rollback_to_compile_run.py
  - knowledge_serving/audit/rollback_KS-CD-002_20260514T134842Z.json
s_gates: []
plan_sections:
  - "§A3"
  - "§B Phase4"
writes_clean_output: false
ci_commands:
  - python3 scripts/rollback_to_compile_run.py --to mpv::mp_20260512_002 --dry-run
status: done
---

# KS-CD-002 · 回滚预案

## 1. 任务目标
- **业务**：ECS PG / Qdrant 灌库失败或上线后发现问题时，快速回到上一可信 compile_run_id。
- **工程**：脚本支持 --to <run_id> 切 PG 数据 + Qdrant alias。
- **S gate**：无单独门。
- **非目标**：不修业务 bug。

## 2. 前置依赖
- KS-DIFY-ECS-003、KS-DIFY-ECS-004

## 3. 输入契约
- 读：上一可信 compile_run_id（手工指定或自动取上版）
- env：PG_* / QDRANT_*

## 4. 执行步骤
1. dry-run：列出会动的 PG 表、Qdrant alias
2. apply：truncate + 重灌上版数据；切 alias 到上版 collection
3. 写 audit
4. 跑 KS-DIFY-ECS-006 e2e smoke 验证回滚成功

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `rollback_to_compile_run.py` | py | 是 | 是 |
| `knowledge_serving/audit/rollback_KS-CD-002_20260514T134842Z.json` | json（含 env / checked_at / git_commit / evidence_level） | 是（本轮 staging apply 证据） | 否（CI artifact，`.gitignore` 已排除时间戳 rollback audit） |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 上版 collection 已删 | exit ≠ 0 |
| --to 指向不存在 run_id | exit ≠ 0 |
| 同时 PG 与 Qdrant 半失败 | 标记 partial；要求人工介入 |
| dry-run 不真改 | 是 |
| 回滚后 smoke fail | 报警 |

## 7. 治理语义一致性
- 仅回到 KS-CD-001 流水线生成过的 compile_run_id
- 不调 LLM
- 需要审批

## 8. CI 门禁
```
command: python3 scripts/rollback_to_compile_run.py --to mpv::mp_20260512_002 --dry-run
pass: 列出动作清单，不真改
artifact: rollback dry-run report
```

## 9. CD / 环境验证
- staging：每月演练 1 次
- prod：仅审批后触发
- 健康检查：回滚后 smoke 必须过
- 监控：回滚事件

## 10. 独立审查员 Prompt
> 请：1) dry-run 输出可读；2) 不存在 run_id 拒绝；3) 模拟一次 staging 回滚 + smoke；4) 输出 pass / fail。
> 阻断项：回滚后 smoke fail；无审批就 apply。

## 11. DoD
- [x] 脚本入 git（`scripts/rollback_to_compile_run.py`；支持 `mpv::<model_policy_version>` 解析到真实 `compile_run_id`；Qdrant alias apply 使用 qdrant-client 显式 operation；PG apply 复用 KS-DIFY-ECS-003）
- [x] dry-run pass（2026-05-14 复跑原 §8 命令：`python3 scripts/rollback_to_compile_run.py --to mpv::mp_20260512_002 --dry-run` → exit 0；`mpv::mp_20260512_002` runtime 解析到真实 `compile_run_id=5b5e5fc1f6199ec6`；dry-run audit 含 `env=staging` / `checked_at` / `git_commit` / `evidence_level=runtime_verified`）
- [x] staging apply pass（2026-05-14 当前实测：`source scripts/load_env.sh && python3 scripts/rollback_to_compile_run.py --to mpv::mp_20260512_002 --apply --yes` → exit 0；PG 通过 `KS-DIFY-ECS-003 --apply` 重灌 12 表且 post_verify pass；Qdrant alias 真切换 ok；post-smoke pass；audit `knowledge_serving/audit/rollback_KS-CD-002_20260514T134842Z.json`）
- [x] 审查员 prompt 覆盖（dry-run 可读；未知 run_id exit 2；staging apply + smoke exit 0；无 `--yes` 拒绝 apply）

---
task_id: KS-CD-002
phase: CD
depends_on: [KS-DIFY-ECS-003, KS-DIFY-ECS-004]
files_touched:
  - scripts/rollback_to_compile_run.py
artifacts:
  - scripts/rollback_to_compile_run.py
s_gates: []
plan_sections:
  - "§A3"
  - "§B Phase4"
writes_clean_output: false
ci_commands:
  - python3 scripts/rollback_to_compile_run.py --to <run_id> --dry-run
status: not_started
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
command: python3 scripts/rollback_to_compile_run.py --to <run_id> --dry-run
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
- [ ] 脚本入 git
- [ ] dry-run pass
- [ ] staging 演练 pass
- [ ] 审查员 pass

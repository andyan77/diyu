---
task_id: KS-DIFY-ECS-002
phase: Dify-ECS
wave: W2
depends_on: [KS-DIFY-ECS-001]
files_touched:
  - scripts/reconcile_ecs_pg_vs_nine_tables.py
  - knowledge_serving/audit/reconcile_KS-DIFY-ECS-002.json
artifacts:
  - scripts/reconcile_ecs_pg_vs_nine_tables.py
s_gates: []
plan_sections:
  - "§A1"
writes_clean_output: false
ci_commands:
  - python3 scripts/reconcile_ecs_pg_vs_nine_tables.py --env staging
status: not_started
---

# KS-DIFY-ECS-002 · ECS PG ↔ 9 表对账

## 1. 任务目标
- **业务**：ECS PG（如果保留）与本仓 9 表 CSV 必须严格一致或差异显式登记。
- **工程**：行数 / 主键 / 关键字段 hash 三层对账；差异写 audit。
- **S gate**：无单独门，为 KS-DIFY-ECS-003 提供前置一致性。
- **非目标**：不修复差异（人工裁决）。

## 2. 前置依赖
- KS-DIFY-ECS-001

## 3. 输入契约
- 读：ECS PG（staging）、9 表 CSV
- env：PG_*

## 4. 执行步骤
1. 拉 ECS PG 9 表
2. 对每张表算 hash
3. 与本仓 CSV hash 对比
4. 差异条目写 reconcile_KS-DIFY-ECS-002.json
5. exit 0 当差异为 0；否则 exit ≠ 0（除非有 `--allow-diff` 标志，仅人工评审用）

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `reconcile_*.py` | py | 是 | 是 |
| `knowledge_serving/audit/reconcile_KS-DIFY-ECS-002.json` | json | 是（运行证据） | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| ECS 多 1 行 | exit ≠ 0 |
| CSV 多 1 行 | exit ≠ 0 |
| brand_layer 字段差 | exit ≠ 0 |
| ECS PG 不可达 | exit ≠ 0 + 明确错误 |
| --allow-diff 但无人工签字 | warning |

## 7. 治理语义一致性
- 不调 LLM
- 差异必须显式落盘登记
- 不自动修复

## 8. CI 门禁
```
command: python3 scripts/reconcile_ecs_pg_vs_nine_tables.py --env staging
pass: diff_count == 0
failure_means: 两端不一致，禁止灌 PG
artifact: reconcile_KS-DIFY-ECS-002.json
```

## 9. CD / 环境验证
- staging：每次 PR 触发
- prod：发布前必跑
- 监控：差异计数

## 10. 独立审查员 Prompt
> 请：1) 跑 reconcile；2) 检查 json 输出；3) 输出 pass / fail。
> 阻断项：差异 > 0 但 pass。

## 11. DoD
- [ ] 脚本入 git
- [ ] diff 0
- [ ] 审查员 pass

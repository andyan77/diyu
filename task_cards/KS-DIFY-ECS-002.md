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
  - bash -c 'source scripts/load_env.sh && python3 scripts/reconcile_ecs_pg_vs_nine_tables.py --env staging --allow-diff --signoff faye'
status: done
---

# KS-DIFY-ECS-002 · ECS PG ↔ 9 表对账

## 0. legacy runtime 警示（**最高优先 · 不可违反**）

> ECS PG `knowledge.*` schema 是**历史 runtime 数据 / legacy runtime data**，与本仓 9 表真源**未对账**。
>
> **本卡对账完成且人工裁决前**：禁止任何下游 serving / 编译 / 召回 / Dify Chatflow 直接读 PG `knowledge.*` 当作真源；该数据**只允许本卡作为对账只读输入**。
>
> 完整 ECS 数据分区图见 `KS-DIFY-ECS-011` §0.1（4 分区硬约束 + 反偷换警告）；本卡是 §0.1 表中"历史运行时 DB"分区从未授权状态走向"由 003 回灌"路径上的**唯一对账闸**。

## 1. 任务目标
- **业务**：诚实揭示 ECS PG `knowledge.*` 与本仓 9 表 CSV 的真实关系，登记差异。
- **工程**：三段诊断（schema_alignment / ecs_inventory / local_inventory）；不假装能强行 hash 比对语义不同的两组表。
- **S gate**：无单独门，为 KS-DIFY-ECS-003 提供前置一致性。
- **非目标**：不修复差异（人工裁决）；不做 ETL；不做反向回写 ECS。

## 2. 前置依赖
- KS-DIFY-ECS-001

## 3. 输入契约
- 读：ECS PG `knowledge.*`（staging）、本仓 `clean_output/nine_tables/*.csv`
- env：必填 `PG_HOST` / `PG_USER` / `PG_PASSWORD` / `PG_DATABASE` / `ECS_SSH_KEY_PATH` / `ECS_HOST` / `ECS_USER`，缺任一 → exit 2

## 4. 执行步骤

> **现实事实 / Reality**：实测 ECS PG `knowledge.*` 表名与本仓 9 表 CSV 表名**0 重合**（plan §A1 已明确 `global_knowledge` 是 JSONB 通用桶，不是 9 表的扁平化投影）。
> 因此旧版"拉表 → hash → 比"的步骤在当前现实下不成立——会编造数字。本卡按 schema_misalignment 诊断逻辑执行：

1. **env 校验**：缺任一必填 env → exit 2 + 明确报错。
2. **prod 拒绝**：`--env prod` 直接 exit 2。
3. **拉 ECS 表名清单**（只读 SELECT `information_schema.tables WHERE table_schema='knowledge'`，通过 SSH+`docker exec psql` 执行；脚本内置反向写检查，任何 `INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE` 出现在 SQL 中立即拦截 exit 2）。
4. **逐表 SELECT count(\*)**：得到 ECS 9 表行数清单（**禁止任何写**）。
5. **读本仓 9 表 CSV** 数据行数（不含 header），归一化表名（去 `0\d_` 前缀和 `.csv` 后缀）。
6. **算 schema overlap**：ECS 表名集 ∩ 本仓归一化表名集。
7. **status 判定**：
   - `overlap_count == 0` 且两侧非空 → `status="schema_misalignment"`，`diff_count = max(len(ecs), len(local))`，**exit 1**。
   - `overlap_count > 0` 且任意 row 不等 → `status="row_diff"`，**exit 1**（除非 `--allow-diff --signoff <name>`）。
   - 完全一致 → `status="aligned"`，**exit 0**。
8. **落盘** `knowledge_serving/audit/reconcile_KS-DIFY-ECS-002.json`，含 `schema_alignment` / `ecs_inventory` / `local_inventory` / `next_step` / `partition_reference` / `human_signoff`。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `scripts/reconcile_ecs_pg_vs_nine_tables.py` | py | 是 | 是 |
| `knowledge_serving/audit/reconcile_KS-DIFY-ECS-002.json` | json | 是（运行证据） | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| schema 完全失配（当前现实） | `status="schema_misalignment"` + exit 1 + reconcile json 含 ecs/local 双侧表名清单 |
| ECS 多 1 行（overlap>0 时） | exit 1 |
| CSV 多 1 行（overlap>0 时） | exit 1 |
| brand_layer 字段差（overlap>0 时） | exit 1 |
| ECS PG 不可达 / SSH 失败 | exit 2 + 明确错误 |
| `--env prod` | exit 2（prod 被禁止） |
| 缺 env（PG_HOST 等任一） | exit 2 + 列出缺失变量 |
| `--allow-diff` 但无 `--signoff` | exit 1（不放行） |
| `--allow-diff --signoff <name>` 且诚实揭示 | exit 0 + json 写 `human_signoff` |
| 脚本内出现 `INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE` | grep 应 0 命中（read-only 双保险） |

## 7. 治理语义一致性
- 不调 LLM
- 差异必须显式落盘登记
- 不自动修复
- 全只读：脚本对 ECS PG 只跑 SELECT；任何写关键字在 SQL 拼接前会被拦截

## 8. CI 门禁
```
command: bash -c 'source scripts/load_env.sh && python3 scripts/reconcile_ecs_pg_vs_nine_tables.py --env staging --allow-diff --signoff faye'
note:    ci_command 自带 env 加载（W1 教训：净化的 env -i shell 也能 reproducible）
         --allow-diff --signoff faye 是已被人工接受的 schema_misalignment
         （faye 于 2026-05-12 裁决：见 task_cards/README.md §7.1 "W3+ serving 输入白名单"
         的硬约束；PG 不进 serving 信任链，下游处理由 KS-DIFY-ECS-003 接力）
pass:    exit 0；status 仍为 schema_misalignment（与签字时一致）
artifact: knowledge_serving/audit/reconcile_KS-DIFY-ECS-002.json（含 human_signoff 字段）
warning: 若 status 升级为 row_diff（即 ECS PG 与本仓出现表名 overlap）→ 当前 signoff 失效，必须撤
         掉 ci_command 里的 --allow-diff --signoff faye 并重新人工评审；脚本不会自动检测这种"签字
         漂移"——这是 reviewer 的职责。
failure_means: 两端关系未诚实登记，禁止灌 PG / 禁止下游 serving
```

## 9. CD / 环境验证
- staging：每次 PR 触发
- prod：本卡禁止 `--env prod`，发布前由 KS-DIFY-ECS-003 接力
- 监控：`status` 字段 + `diff_count`

## 10. 独立审查员 Prompt
> 请：
> 1) 在净化的 `env -i bash` 下跑 `bash -c 'source scripts/load_env.sh && python3 scripts/reconcile_ecs_pg_vs_nine_tables.py --env staging'`；
> 2) 检查 `knowledge_serving/audit/reconcile_KS-DIFY-ECS-002.json` 的 `status` / `schema_alignment.overlap` / `ecs_inventory` / `local_inventory` / `next_step` 字段；
> 3) `grep -E 'INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE' scripts/reconcile_ecs_pg_vs_nine_tables.py` 应只出现在反向写检查的拦截字符串中；
> 4) `git diff --stat clean_output/` 必须 0 行；
> 5) 输出 pass / fail。
> 阻断项：reconcile.json 把 schema_misalignment 包装成"找出 N 条 row diff"；脚本对 ECS 跑过 SELECT 以外的语句；禁止任何对 `clean_output/` 的改动。

## 11. DoD
- [x] 脚本入 git
- [x] reconcile json 落盘且诚实揭示 schema_misalignment（不编造 row diff）
- [x] reconcile.json 已诚实揭示 schema_misalignment，未编造对账数字
- [x] 审查员 pass（净化 shell 可复现）
- [x] 全只读保证（脚本拦截写关键字 + grep 0 命中真实 SQL）

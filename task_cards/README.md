# Knowledge Serving · 任务卡总册 v1

> 来源：`knowledge_serving_plan_v1.1.md`
> 卡数：56 · DAG 闭合 · 每张卡可独立实施 / 验证 / CI 阻断
> 落盘日期：2026-05-11

## 1. 目录

```
task_cards/
  README.md                       # 本文件（索引 + 规则）
  dag.csv                         # 机器可读 DAG（CI 消费）
  validate_task_cards.py          # 元校验器：卡片语义对齐自检
  KS-S0-001.md ... KS-PROD-003.md # 56 张任务卡
```

## 2. 阶段编号

| Phase | 卡数 | 范围 |
|---|---|---|
| S0 | 6 | 基线收口（修 W12 / DB / ECS 密钥 / Qdrant 健康 / canonical id / manifest） |
| Schema | 5 | json schema + 目录骨架 |
| Compiler | 13 | 7 view + 5 control + 1 validator |
| Policy | 5 | fallback / guardrail / merge / retrieval / model_policy |
| Retrieval | 9 | §6 十三步召回流程实现 |
| Vector | 3 | qdrant chunks 离线生成 + filter 回归 |
| Dify-ECS | 10 | ECS ETL + Qdrant 灌库 + 双写 + API + Chatflow + guardrail + replay |
| CD | 2 | 流水线 + 回滚 |
| Production Readiness | 3 | S1-S13 总回归 + 跨租户 + LLM 边界 |

## 3. 任务卡 frontmatter 契约（机器可读）

每张卡必须以 YAML frontmatter 开头：

```yaml
---
task_id: KS-S0-001
phase: S0                         # S0 / Schema / Compiler / Policy / Retrieval / Vector / Dify-ECS / CD / Production-Readiness
depends_on: []                    # 其他 task_id 列表
files_touched:                    # 受影响的实际路径（glob 允许）
  - clean_output/scripts/w12_*.py
artifacts:                        # 产物路径
  - clean_output/audit/baseline_alignment_KS-S0-001.md
s_gates: [S0]                     # 本卡承载的硬门
plan_sections:                    # 映射到 v1.1 plan 章节
  - "§12 S0"
  - "§A2.1"
writes_clean_output: true         # 仅 S0 卡允许 true；其余必须 false
ci_commands:
  - python3 clean_output/scripts/full_audit.py
status: not_started               # not_started / in_progress / blocked / done
---
```

## 4. 卡的 11 节模板（人类可读）

固定顺序，缺一不可：

1. 任务目标（业务 / 工程 / S gate / 非目标）
2. 前置依赖
3. 输入契约
4. 执行步骤
5. 执行交付（路径 / 格式 / canonical / 可重建 / 入 git / CI artifact）
6. 对抗性 / 边缘性测试
7. 治理语义一致性测试
8. CI 门禁测试
9. CD / 环境验证
10. 独立审查员 Prompt
11. DoD 完成定义

## 5. 全局红线（每张卡都必须遵守）

| # | 规则 | 校验方式 |
|---|---|---|
| R1 | 除 S0 卡外，**禁止**修改 `clean_output/`（真源） | `validate_task_cards.py` 检查 `writes_clean_output` 字段 + CI 跑 `git diff --stat clean_output/` |
| R2 | 任何卡不得调用 LLM 做硬门通过判断 | 脚本 `grep -E "anthropic\|openai\|llm.*judge"` 在 CI 命令中 |
| R3 | 密钥不入仓 | `git grep -E "password\|api_key\|secret" -- ':!docs' ':!task_cards'` 0 命中 |
| R4 | 所有产物可重建：删 artifact 后重跑 CI 命令产出 byte-identical | `sha256sum` 对比（KS-CD-001 全流水线 enforce） |
| R5 | 任何"当前状态"判断前必须重新核验（`git status` / `git log`） | KS-S0-001 强制 |
| R6 | `compile_run_id / source_manifest_hash / view_schema_version` 全链路存在 | KS-COMPILER-013 校验器 enforce |
| R7 | 跨租户 0 串味 | KS-PROD-002 跨租户回归 enforce |
| R8 | LLM assist 不得做 6 类禁止任务（§9.1） | KS-PROD-003 边界回归 enforce |

## 6. 任务卡语义对齐自检

`validate_task_cards.py` 在 CI 中作为**首道门禁**运行，检查 8 项：

1. 11 节齐全（章节标题正则匹配）
2. Task ID 与文件名一致
3. `depends_on` 引用的卡都存在
4. DAG 无环（拓扑排序成功）
5. S0-S13 每个 gate 都有 ≥1 张承载卡
6. 仅 S0 phase 卡允许 `writes_clean_output: true`
7. `dag.csv` 与各卡 frontmatter 字段一致
8. `plan_sections` 至少 1 项，且引用的 §x 在 plan 中真实存在

失败任一项 → CI 阻断，所有实施卡不得开工。

## 7. DAG 关键路径

```
KS-S0-001 / 003 / 005           (并发 S0 起点)
      ↓
KS-S0-006 (manifest)
      ↓
KS-SCHEMA-001..004 → KS-SCHEMA-005 (目录骨架)
      ↓
KS-COMPILER-001..012 (7 view + 5 control)
      ↓
KS-COMPILER-013 (S1-S7 总闸)
      ↓
KS-POLICY-001..005
      ↓
KS-VECTOR-001..003     ← KS-RETRIEVAL-006 由此分支吃 Vector
      ↓
KS-RETRIEVAL-001..009 (其中 005 为 structured-only；006 为 vector-enabled；009 汇总)
      ↓
KS-DIFY-ECS-001..006   (ECS 集成 + 端到端冒烟)
KS-DIFY-ECS-007..010   (API / Chatflow / Guardrail / Replay)
      ↓
KS-CD-001 (流水线，依赖以上全部)
KS-CD-002 (回滚)
      ↓
KS-PROD-001..003 (S1-S13 总回归 / 跨租户 / LLM 边界)
```

**关键说明**：
- `KS-RETRIEVAL-006`（vector_retrieval）依赖 `KS-VECTOR-001`，所以 **Vector 必须先于 vector-enabled Retrieval**。
- `KS-RETRIEVAL-005` 是 structured-only 召回，与 Vector 无前置关系。
- `KS-CD-001` 已显式依赖 `KS-DIFY-ECS-006..010` 五张卡，**Phase 5 全部子门必须绿才能合入主分支**。

完整 DAG 见 `dag.csv` 与 `validate_task_cards.py --print-dag`。

## 8. 状态流转

```
not_started → in_progress → done
                  ↓
              blocked （写明阻塞原因到卡 §11）
```

每次状态变更须在 PR 中同步更新 frontmatter `status` 字段与 `dag.csv`，否则 `validate_task_cards.py` 阻断。

# Knowledge Serving · 任务卡总册 v1

> 来源：`knowledge_serving_plan_v1.1.md`
> 卡数：57 · DAG 闭合 · 每张卡可独立实施 / 验证 / CI 阻断
> 落盘日期：2026-05-11

## 1. 目录

```
task_cards/
  README.md                       # 本文件（索引 + 规则）
  dag.csv                         # 机器可读 DAG（CI 消费）
  validate_task_cards.py          # 元校验器：卡片语义对齐自检
  KS-S0-001.md ... KS-PROD-003.md # 57 张任务卡
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
| R8 | LLM assist 不得做 8 类禁止任务（§9.1，2026-05-12 由 6 扩到 8，新增 intent_classification / content_type_routing） | KS-PROD-003 边界回归 enforce |

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

## 7.1 波次划分 / Wave Schedule（按依赖拓扑分层）

> 划分原则：**同一波次内的卡，依赖全部落在更早波次**，因此波次内卡片**可并行**实施；**跨波次必须串行**。波次号在 `dag.csv` 的 `wave` 列是机器可读真源；本表是人类可读视图。

| Wave | 卡数 | 阻塞下一波的关键产物 | 卡片清单 | 状态 |
|---|---|---|---|---|
| **W0** | 7 | clean_output 真源基线 + manifest hash + LLM 边界 model_policy | KS-S0-001..006, KS-POLICY-005 | ✅ **done (7/7)** |
| **W1** | 6 | 4 份 JSON schema + ECS 镜像 verify/push 对偶 | KS-SCHEMA-001..004, KS-DIFY-ECS-001/011 | ✅ **done (6/6)** |
| **W2** | 2 | serving 目录骨架 + ECS Compose 联调 | KS-SCHEMA-005, KS-DIFY-ECS-002 | ✅ **done (2/2)** |
| **W3** | 11 | 7 view + 4 control（除 view_pack_overlay 与 P1 总闸） | KS-COMPILER-001/002/004/005/006/007/008/009/010/011/012 | ✅ **done (11/11)** |
| **W4** | 6 | overlay view + 2 policy（fallback/merge） + 3 召回起点 | KS-COMPILER-003, KS-POLICY-003/004, KS-RETRIEVAL-001/002/003 | ✅ **done (6/6)** |
| **W5** | 1 | **S1-S7 compile 总闸**（compile_run_id 全链路） | KS-COMPILER-013 | ✅ **done (1/1)** |
| **W6** | 5 | guardrail + retrieval policy + structured 召回 + 向量库初始化 + ECS 双写 | KS-POLICY-001/002, KS-RETRIEVAL-005, KS-VECTOR-001, KS-DIFY-ECS-003 | ✅ **done (5/5)** |
| **W7** | 6 | structured 召回链 + 向量回归 + ECS Qdrant 灌库 + replay 准备 | KS-RETRIEVAL-004/006, KS-VECTOR-002/003, KS-DIFY-ECS-004/009 | ✅ **done (6/6)** |
| **W8** | 2 | 召回合流 + 回滚预案 | KS-RETRIEVAL-007, KS-CD-002 | ✅ **done (2/2)** |
| **W9** | 1 | 召回排序/裁剪/输出 | KS-RETRIEVAL-008 | ✅ **done (1/1)** |
| **W10** | 3 | 召回 13 步全链汇总 + ECS API 集成 + LLM 边界回归 | KS-RETRIEVAL-009, KS-DIFY-ECS-005, KS-PROD-003 | 🟡 **in_progress (2/3 done)** |
| **W11** | 3 | 端到端冒烟 + Chatflow + replay | KS-DIFY-ECS-006/007/010 | ⬜ not_started |
| **W12** | 2 | guardrail 集成 + 跨租户回归 | KS-DIFY-ECS-008, KS-PROD-002 | ⬜ not_started |
| **W13** | 1 | **CI/CD 流水线总闸（S0-S13 全绿）** | KS-CD-001 | ⬜ not_started |
| **W14** | 1 | **S1-S13 上线总回归** | KS-PROD-001 | ⬜ not_started |
| **合计** | **57** | — | — | **49/57 done = 86.0%** |

## 7.1 W3+ serving 输入白名单（**最高优先 · 不可违反 · 跨 W3-W14 全部卡**）

> **裁决日期 / decided**：2026-05-12 · **裁决人 / decided by**：faye
>
> **背景**：W2 KS-DIFY-ECS-002 实测 ECS PG `knowledge.*`（9 张：brand_tone / global_knowledge / role_profile 等）与本仓 `clean_output/nine_tables/*.csv`（9 张：01_object_type ~ 09_call_mapping）**表名 0 重合**，是 schema_misalignment 而非 row diff（reconcile 证据：`knowledge_serving/audit/reconcile_KS-DIFY-ECS-002.json`，含 `human_signoff: faye`）。该 PG 暂不进入 serving 信任链。
>
> **从 W3 起，除 `KS-DIFY-ECS-002`（对账，已收口）和 `KS-DIFY-ECS-003`（serving views 回灌 PG）明确授权外，所有 serving 编译 / 校验 / 召回 / 向量构建 / Dify 编排任务禁止读取以下数据源**：
>
> - ❌ ECS PG `knowledge.*` schema 任何表（legacy runtime data，未对账）
> - ❌ `/data/clean_output.bak_*`（ECS 上的 timestamped backup，仅供回滚）
> - ❌ `/tmp/itr*`、ECS 上历史压缩包、任何旧工作区残留
> - ❌ Qdrant 上 payload 缺 `compile_run_id` + `source_manifest_hash` 的旧 collection
>
> **当前可信输入仅限**：
> - ✅ 本仓 `clean_output/`（真源 / source of truth）
> - ✅ ECS `/data/clean_output/`（部署副本 / one-way mirror，与本地 sha256 全等）
> - ✅ 本仓 `knowledge_serving/schema/`（4 份 jsonschema，W1 立法的字段契约）
> - ✅ 本卡 `files_touched` 字段中明确允许的本地派生路径（如 `knowledge_serving/views/*.csv`、`knowledge_serving/control/*.csv` 等）
>
> 完整 ECS 数据 4 分区图见 [`KS-DIFY-ECS-011`](KS-DIFY-ECS-011.md) §0.1；PG 映射 / 迁移 / 回灌方案留给 `KS-DIFY-ECS-003` 或后续单独立的映射卡处理。
>
> **校验脚本 / verifier**：`scripts/validate_w3_input_whitelist.py` —— 两层守门：
> - **Tier-1（强约束）**：11 张 W3 编译卡（KS-COMPILER-001/002/004..012）正文必须含 "W3+ 输入白名单硬约束" + "禁止读取 ECS PG" + "README §7.1" 三个 token
> - **Tier-2（路径守门）**：W3-W14 全部卡 frontmatter `files_touched` 不得含 ECS 备份路径 / 历史临时目录 / PG `knowledge.*` 表名 / `clean_output/` 写入侧（例外：KS-DIFY-ECS-002/003 已显式授权）
> - **C3**：README §7.1 章节存在
>
> W3 起跑前必跑；W4-W14 任一卡新增 / 修改 frontmatter 后也必须跑。

**波次推进规则**：

1. **同波次并行 / 跨波次串行**：W_n 内任意卡可并发开工；W_{n+1} 必须等 W_n **全部 done** 才能起跑（DAG 严格约束）。
2. **关键瓶颈卡**（单卡独占一个波次，是后续工作的全局总闸）：
   - **W5 · KS-COMPILER-013**（S1-S7 compile 总闸）→ 卡住整个 Policy / Retrieval / Vector / Dify-ECS 链
   - **W9 · KS-RETRIEVAL-008**（召回输出层）→ 卡住 Retrieval 汇总与 ECS API
   - **W13 · KS-CD-001**（CI/CD 总闸）→ 卡住上线总回归
   - **W14 · KS-PROD-001**（最终验收）→ 项目终点
   建议在 W3/W7/W11 收尾前提前为这三张瓶颈卡预审 Independent Reviewer Prompt，避免到点才发现阻塞。
3. **状态同步**：每张卡 `status` 流转必须同步更新对应 `dag.csv` 行的 `status` 字段；`wave` 字段只在拓扑结构变化（新增 / 删除卡或修改 `depends_on`）时才动，普通状态推进**不要**改 wave。
4. **W0 已完成证据**：见 commit `1fee254 W0 全完成 · 7/7 + Qdrant healthy + manifest hash` 及 `clean_output/audit/baseline_alignment_KS-S0-001.md`。

## 8. 状态流转

```
not_started → in_progress → done
                  ↓
              blocked （写明阻塞原因到卡 §11）
```

每次状态变更须在 PR 中同步更新 frontmatter `status` 字段与 `dag.csv`，否则 `validate_task_cards.py` 阻断。

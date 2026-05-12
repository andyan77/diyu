---
task_id: KS-COMPILER-012
phase: Compiler
wave: W3
depends_on: [KS-SCHEMA-002]
files_touched:
  - knowledge_serving/control/context_bundle_log.csv
  - knowledge_serving/scripts/lint_no_duplicate_log.sh
artifacts:
  - knowledge_serving/control/context_bundle_log.csv
s_gates: [S8]
plan_sections:
  - "§4.5"
writes_clean_output: false
ci_commands:
  - bash knowledge_serving/scripts/lint_no_duplicate_log.sh
status: not_started
---

# KS-COMPILER-012 · context_bundle_log 唯一写入约束

## 1. 任务目标
- **业务**：保证 §4.5 context_bundle_log 只有一处 canonical（`control/context_bundle_log.csv`）；防止 S8 回放双真源。
- **工程**：落空表头 csv；写 lint 脚本扫描全仓阻止重复同名 csv。
- **S gate**：S8 context_bundle_replay。
- **非目标**：不实现 log 写入（属 KS-RETRIEVAL-008 / KS-DIFY-ECS-005）。

## 2. 前置依赖
- KS-SCHEMA-002

## 3. 输入契约
- 读：schema
- 不读：运行时

- **W3+ 输入白名单硬约束（见 README §7.1）**：本卡禁止读取 ECS PG `knowledge.*`、ECS 备份目录 `/data/clean_output.bak_*`、历史临时目录 `/tmp/itr*`、Qdrant 中缺 `compile_run_id` + `source_manifest_hash` 的旧 collection；只能从 README §7.1 白名单输入派生（含本卡 §3 上方列出的具体路径，例如 `clean_output/candidates/`、`clean_output/nine_tables/`、`clean_output/audit/`、`knowledge_serving/schema/`、`knowledge_serving/control/content_type_canonical.csv` 等）。

## 4. 执行步骤
1. 写 `control/context_bundle_log.csv` 仅 header（24 字段对齐 §4.5）
2. 写 `lint_no_duplicate_log.sh`：`find knowledge_serving/ -name context_bundle_log.csv` 必须只命中 control/ 路径
3. 写 README 段：logs/ 不得放同名 csv

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `control/context_bundle_log.csv` | csv header | 是 | 是 |
| `lint_no_duplicate_log.sh` | sh | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 在 logs/ 放同名 csv | lint fail |
| header 缺 compile_run_id | fail |
| header 行有数据 | fail |
| 字段顺序与 schema 不符 | warning |

## 7. 治理语义一致性
- S8：单真源是回放前提
- 不调 LLM
- clean_output 0 写

## 8. CI 门禁
```
command: bash knowledge_serving/scripts/lint_no_duplicate_log.sh
pass: find 命中数 == 1
failure_means: S8 回放可能踩双源
artifact: lint report
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) `find knowledge_serving -name context_bundle_log.csv` 必须只 1 个；2) header 24 字段；3) 输出 pass / fail。
> 阻断项：多个同名 csv；header 字段缺。

## 11. DoD
- [ ] csv header 落盘
- [ ] lint pass
- [ ] 审查员 pass

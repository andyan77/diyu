---
task_id: KS-DIFY-ECS-003
phase: Dify-ECS
wave: W6
depends_on: [KS-COMPILER-013, KS-DIFY-ECS-002]
files_touched:
  - knowledge_serving/scripts/upload_serving_views_to_ecs.py
artifacts:
  - knowledge_serving/scripts/upload_serving_views_to_ecs.py
  - knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.json
s_gates: []
plan_sections:
  - "§11"
  - "§A1"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/upload_serving_views_to_ecs.py --env staging --dry-run
status: not_started
---

# KS-DIFY-ECS-003 · serving views 回灌 ECS PG

## 1. 任务目标
- **业务**：把 7 view + 5 control table 灌进 ECS PG，让 Dify / Agent / API 可消费。
- **工程**：建 schema、写表；source_manifest_hash 落库；幂等。
- **S gate**：无单独门，为 KS-RETRIEVAL-* prod 路径提供数据。
- **非目标**：不调 LLM。

## 2. 前置依赖
- KS-COMPILER-013（产物已校验）、KS-DIFY-ECS-002（对账通过）

## 3. 输入契约
- 读：knowledge_serving/views/*.csv、control/*.csv、schema/*.json、source_manifest.json
- env：PG_*

## 4. 执行步骤
1. 按 schema 建表（含 view_schema_version / compile_run_id / source_manifest_hash 列）
2. dry-run 模式：仅打印 SQL
3. apply 模式：truncate + insert（或 upsert by row_hash）
4. 回写 audit json

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `upload_serving_views_to_ecs.py` | py | 是 | 是 | — |
| `upload_views_KS-DIFY-ECS-003.json` | json | 是（运行证据） | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| view csv 缺 governance | fail |
| 重复主键 | upsert 不增行 |
| 灌一半断网 | 事务回滚 |
| --env prod | 需审批 token |
| 同 compile_run_id 重灌 | 幂等 |

## 7. 治理语义一致性
- 灌库前校验 source_manifest_hash 一致（与本仓）
- 不调 LLM
- secrets env

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/upload_serving_views_to_ecs.py --env staging --dry-run
pass: SQL 输出 + 表创建语句 + 字段对齐
failure_means: PG 灌库不可信
artifact: upload_views_KS-DIFY-ECS-003.json
```

## 9. CD / 环境验证
- staging：CI runner --apply
- prod：手动审批；需 model_policy_version 与 source_manifest_hash 双签
- 回滚：上一 compile_run_id 数据保留 1 个版本（KS-CD-002 接管）
- 健康检查：PG 表行数、source_manifest_hash 一致
- secrets：env，无硬编码

## 10. 独立审查员 Prompt
> 请：1) dry-run 输出 SQL；2) 字段含 source_manifest_hash；3) prod 需审批；4) 输出 pass / fail。
> 阻断项：无版本字段；prod 无审批；明文凭证。

## 11. DoD
- [ ] 脚本入 git
- [ ] dry-run pass
- [ ] staging apply pass（CD 阶段）
- [ ] 审查员 pass

---
task_id: KS-COMPILER-008
phase: Compiler
wave: W3
depends_on: [KS-SCHEMA-002]
files_touched:
  - knowledge_serving/scripts/compile_tenant_scope_registry.py
  - knowledge_serving/control/tenant_scope_registry.csv
artifacts:
  - knowledge_serving/control/tenant_scope_registry.csv
  - knowledge_serving/audit/tenant_scope_registry.compile.log
s_gates: []
plan_sections:
  - "§4.1"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_tenant_scope_registry.py --check
status: done
---

# KS-COMPILER-008 · tenant_scope_registry 编译

## 1. 任务目标
- **业务**：定义租户 → brand_layer / allowed_layers 映射，是多租户隔离的真源表。
- **工程**：写 csv，至少含 `tenant_faye_main` 一行；字段对齐 §4.1。
- **S gate**：无单独门，为 KS-RETRIEVAL-001 / S9 提供数据。
- **非目标**：不做 API；不做权限判断逻辑。

## 2. 前置依赖
- KS-SCHEMA-002

## 3. 输入契约
- 读：`control_tables.schema.json`
- 不读：用户输入

- **W3+ 输入白名单硬约束（见 README §7.1）**：本卡禁止读取 ECS PG `knowledge.*`、ECS 备份目录 `/data/clean_output.bak_*`、历史临时目录 `/tmp/itr*`、Qdrant 中缺 `compile_run_id` + `source_manifest_hash` 的旧 collection；只能从 README §7.1 白名单输入派生（含本卡 §3 上方列出的具体路径，例如 `clean_output/candidates/`、`clean_output/nine_tables/`、`clean_output/audit/`、`knowledge_serving/schema/`、`knowledge_serving/control/content_type_canonical.csv` 等）。

## 4. 执行步骤
1. 列出已知 tenant：tenant_faye_main → brand_faye；tenant_demo → domain_general
2. 字段：tenant_id / api_key_id / brand_layer / allowed_layers / default_platforms / policy_level / enabled / environment
3. 写 csv

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `compile_tenant_scope_registry.py` | py | 是 | 是 |
| `tenant_scope_registry.csv` | csv | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 同一 tenant 两行 | fail |
| environment 非 dev/staging/prod | fail |
| allowed_layers 含未登记 brand | fail |
| enabled=false 行 | 输出但下游 resolver 不返回 |
| 空 csv | fail（至少 1 行） |

## 7. 治理语义一致性
- brand_layer 仅从此表派生，**禁止运行时从自然语言推断**
- api_key_id 不含明文 key
- environment 字段不允许 prod 在 dev 分支提交（CI 拦截）

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_tenant_scope_registry.py --check
pass: exit 0 + 无重复 + 无非法枚举
artifact: tenant_scope_registry.csv
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) 检查至少含 tenant_faye_main；2) 无明文 key；3) 输出 pass / fail。
> 阻断项：明文 key 入仓；environment 漂移。

## 11. DoD
- [ ] csv 落盘
- [ ] CI pass
- [ ] 审查员 pass

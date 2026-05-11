---
task_id: KS-SCHEMA-005
phase: Schema
wave: W2
depends_on: [KS-SCHEMA-001, KS-SCHEMA-002, KS-SCHEMA-003, KS-SCHEMA-004]
files_touched:
  - knowledge_serving/README.md
  - knowledge_serving/views/*.csv
  - knowledge_serving/control/*.csv
  - knowledge_serving/policies/.gitkeep
  - knowledge_serving/vector_payloads/.gitkeep
  - knowledge_serving/logs/.gitkeep
  - knowledge_serving/scripts/.gitkeep
  - knowledge_serving/audit/.gitkeep
artifacts:
  - knowledge_serving/
s_gates: []
plan_sections:
  - "§11"
writes_clean_output: false
ci_commands:
  - python3 scripts/validate_serving_tree.py
status: not_started
---

# KS-SCHEMA-005 · 目录骨架 + 空表头 + README

## 1. 任务目标
- **业务**：把 §11 落盘目录变成实际文件树，避免编译卡各自创建分歧。
- **工程**：建全 `knowledge_serving/` 目录；7 view + 5 control 各落空表头 csv（仅 header）；README 说明边界。
- **S gate**：无单独门。
- **非目标**：不实现编译；不写数据行。

## 2. 前置依赖
- KS-SCHEMA-001..004（4 个 schema 已就绪）

## 3. 输入契约
- 读：4 个 schema
- 不读：任何业务数据

## 4. 执行步骤
1. 创建 §11 全部目录
2. 7 个 view csv：只写 header（governance_common_fields 13 列 + 业务字段，全自 schema 派生）
3. 5 个 control csv：只写 header
4. 写 `knowledge_serving/README.md`：边界（clean_output 真源 / knowledge_serving 派生 / 可删可重建）
5. 实现 `scripts/validate_serving_tree.py`：核对目录与 §11 一致

## 5. 执行交付
| 路径 | 格式 | canonical | 可重建 | 入 git |
|---|---|---|---|---|
| `knowledge_serving/README.md` | md | 是 | 是 | 是 |
| `knowledge_serving/views/*.csv` (7) | csv header | 是 | 是 | 是 |
| `knowledge_serving/control/*.csv` (5) | csv header | 是 | 是 | 是 |
| `.gitkeep` × 5 | text | 否 | — | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| csv header 与 schema required 字段不一致 | validator fail |
| 多 / 少目录 | fail |
| README 缺"clean_output 真源"声明 | fail（regex 检查） |
| 任何 csv 含数据行 | fail（KS-SCHEMA-005 阶段禁止数据） |
| 目录含 BOM / Windows 换行 | fail |

## 7. 治理语义一致性
- README 明文："knowledge_serving 是派生读模型，可删除重建；不替代 clean_output"
- context_bundle_log.csv 只此一处 canonical（§4.5）；logs/ 下不放同名 csv
- 不调 LLM

## 8. CI 门禁
```
command: python3 scripts/validate_serving_tree.py
pass: 目录树与 §11 一致；csv header 与 schema 一致；README 含边界声明
failure_means: 后续编译卡无目标
artifact: scripts/validate_serving_tree.report
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：
> 1. `tree knowledge_serving/` 与 §11 比对
> 2. 跑 validate_serving_tree
> 3. 抽样 1 个 view csv，header 与 schema required 全字段一致
> 4. README 含真源 / 派生 / 可删边界声明
> 5. 输出 pass / fail
> 阻断项：目录缺；csv 有数据行；context_bundle_log.csv 重复落地。

## 11. DoD
- [ ] 目录骨架落盘
- [ ] 12 个 csv 仅 header
- [ ] README 落盘
- [ ] validator pass

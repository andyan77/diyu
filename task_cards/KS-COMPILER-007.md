---
task_id: KS-COMPILER-007
phase: Compiler
wave: W3
depends_on: [KS-SCHEMA-005]
files_touched:
  - knowledge_serving/scripts/compile_evidence_view.py
  - knowledge_serving/views/evidence_view.csv
artifacts:
  - knowledge_serving/views/evidence_view.csv
s_gates: [S5]
plan_sections:
  - "§3.7"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_evidence_view.py --check
status: not_started
---

# KS-COMPILER-007 · evidence_view 编译

## 1. 任务目标
- **业务**：让每条 serving 输出都可反查证据来源。
- **工程**：覆盖 §3.7；evidence_id 唯一；inference_level / trace_quality 全填。
- **S gate**：S5 evidence_linkage。
- **非目标**：不裁决证据；不重算 trace_quality。

## 2. 前置依赖
- KS-SCHEMA-005

## 3. 输入契约
- 读：`clean_output/nine_tables/07_evidence.csv`、9 表关联、manifest
- 不读：召回侧

- **W3+ 输入白名单硬约束（见 README §7.1）**：本卡禁止读取 ECS PG `knowledge.*`、ECS 备份目录 `/data/clean_output.bak_*`、历史临时目录 `/tmp/itr*`、Qdrant 中缺 `compile_run_id` + `source_manifest_hash` 的旧 collection；只能从本仓 `clean_output/` 与 `knowledge_serving/schema/` 派生。

## 4. 执行步骤
1. 加载 07_evidence
2. 字段对齐 §3.7（source_md / source_anchor / line_no / inference_level / trace_quality / adjudication_status）
3. 注入 governance
4. 输出 csv

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `compile_evidence_view.py` | py | 是 | 是 |
| `evidence_view.csv` | csv | 派生 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 source_md | fail |
| evidence_id 重复 | fail |
| inference_level 非枚举 | fail |
| trace_quality 非枚举 | fail |
| 空 source 表 | fail（S5） |
| 幂等 | 一致 |

## 7. 治理语义一致性
- S5：任意输出必须能反查到 evidence
- clean_output 0 写
- 不调 LLM

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_evidence_view.py --check
pass: exit 0 + S5 全绿 + 行数 = 07_evidence active
artifact: evidence_view.csv
```

## 9. CD / 环境验证
离线。

## 10. 独立审查员 Prompt
> 请：1) 抽 5 行，按 source_md + line_no 打开真实文件验证存在；2) clean_output 0 改动；3) 幂等；4) 输出 pass / fail。
> 阻断项：source_anchor 指向不存在；inference_level 缺失。

## 11. DoD
- [ ] csv 落盘
- [ ] CI pass
- [ ] 5 行人工抽查通过
- [ ] 审查员 pass

---
task_id: KS-COMPILER-002
phase: Compiler
wave: W3
depends_on: [KS-SCHEMA-005, KS-S0-005]
files_touched:
  - knowledge_serving/scripts/compile_content_type_view.py
  - knowledge_serving/views/content_type_view.csv
artifacts:
  - knowledge_serving/views/content_type_view.csv
  - knowledge_serving/audit/content_type_view.compile.log
s_gates: [S1, S2, S3, S4]
plan_sections:
  - "§3.2"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_content_type_view.py --check
status: not_started
---

# KS-COMPILER-002 · content_type_view 编译

## 1. 任务目标
- **业务**：固化"要生产哪类内容"读模型。
- **工程**：实现编译器，覆盖 §3.2 全部字段含 canonical_content_type_id / aliases / coverage_status。
- **S gate**：S1-S4。
- **非目标**：不实现召回。

## 2. 前置依赖
- KS-SCHEMA-005、KS-S0-005

## 3. 输入契约
- 读：`clean_output/registers/content_type_canonical.csv`、candidates 中的 content_type 字段、9 表
- 不读：knowledge_serving 写入侧

- **W3+ 输入白名单硬约束（见 README §7.1）**：本卡禁止读取 ECS PG `knowledge.*`、ECS 备份目录 `/data/clean_output.bak_*`、历史临时目录 `/tmp/itr*`、Qdrant 中缺 `compile_run_id` + `source_manifest_hash` 的旧 collection；只能从本仓 `clean_output/` 与 `knowledge_serving/schema/` 派生。

## 4. 执行步骤
1. 加载 canonical map
2. 对每个 canonical id，聚合 source_pack_ids、aliases
3. 计算 coverage_status: complete / partial / missing
4. 注入 governance 字段
5. 输出 csv

## 5. 执行交付
| 路径 | 格式 | canonical | 可重建 | 入 git | CI artifact |
|---|---|---|---|---|---|
| `compile_content_type_view.py` | py | 是 | — | 是 | — |
| `content_type_view.csv` | csv | 派生 | 是 | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| canonical id 与 register 不符 | fail |
| aliases 包含未登记别名 | warning |
| coverage_status 非枚举 | fail |
| 18 类不全 | warning（missing 标识） |
| 幂等 | sha256 一致 |

## 7. 治理语义一致性
- canonical id 唯一来源 = KS-S0-005 register
- clean_output 0 写
- 不调 LLM

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_content_type_view.py --check
pass: exit 0 + validator pass
artifact: content_type_view.csv
```

## 9. CD / 环境验证
离线。

## 10. 独立审查员 Prompt
> 请：1) clean_output 0 改动；2) 删 csv 重跑 sha256 一致；3) 18 类 canonical id 全部出现；4) 输出 pass / fail。
> 阻断项：canonical id 漂移；coverage_status 全 complete 但语料不足。

## 11. DoD
- [ ] csv 落盘
- [ ] CI pass
- [ ] 审查员 pass

---
task_id: KS-COMPILER-009
phase: Compiler
wave: W3
depends_on: [KS-SCHEMA-002]
files_touched:
  - knowledge_serving/scripts/compile_field_requirement_matrix.py
  - knowledge_serving/control/field_requirement_matrix.csv
artifacts:
  - knowledge_serving/control/field_requirement_matrix.csv
  - knowledge_serving/audit/field_requirement_matrix.compile.log
s_gates: [S7]
plan_sections:
  - "§4.2"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_field_requirement_matrix.py --check
status: done
---

# KS-COMPILER-009 · field_requirement_matrix 编译

## 1. 任务目标
- **业务**：固化"缺字段时能否降级"，是 S7 fallback 覆盖度的真源。
- **工程**：每个 content_type × 关键字段一行；required_level / fallback_action / ask_user_question / block_reason 全填。
- **S gate**：S7 fallback_policy_coverage。
- **非目标**：不实现 fallback 执行逻辑。

## 2. 前置依赖
- KS-SCHEMA-002

## 3. 输入契约
- 读：content_type_canonical.csv、plan §4.2 四条样例规则
- 不读：运行时

- **W3+ 输入白名单硬约束（见 README §7.1）**：本卡禁止读取 ECS PG `knowledge.*`、ECS 备份目录 `/data/clean_output.bak_*`、历史临时目录 `/tmp/itr*`、Qdrant 中缺 `compile_run_id` + `source_manifest_hash` 的旧 collection；只能从 README §7.1 白名单输入派生（含本卡 §3 上方列出的具体路径，例如 `clean_output/candidates/`、`clean_output/nine_tables/`、`clean_output/audit/`、`knowledge_serving/schema/`、`knowledge_serving/control/content_type_canonical.csv` 等）。

## 4. 执行步骤
1. 至少落 §4.2 四条规则：product_review.brand_tone(soft), store_daily.team_persona(soft), founder_ip.founder_profile(hard), brand_manifesto.brand_values(hard)
2. 扩展到 18 类 × 关键字段
3. 写 csv

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `compile_field_requirement_matrix.py` | py | 是 | 是 |
| `field_requirement_matrix.csv` | csv | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| required_level 非 none/soft/hard | fail |
| fallback_action 非枚举 | fail |
| hard 行未填 block_reason | fail |
| 18 类未覆盖核心字段 | warning |
| 重复 (content_type, field_key) | fail |

## 7. 治理语义一致性
- S7 全覆盖：每个 content_type 至少 1 行
- hard 缺字段必须阻断成稿
- soft 缺字段必须有 fallback_action
- 不调 LLM

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_field_requirement_matrix.py --check
pass: exit 0 + S7 覆盖检查 + 18 类至少 1 行
artifact: field_requirement_matrix.csv
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) §4.2 四条样例规则在 csv 内；2) 抽样验证 hard 行有 block_reason；3) 输出 pass / fail。
> 阻断项：四条样例缺失；hard 行未阻断。

## 11. DoD
- [ ] csv 落盘
- [ ] CI pass
- [ ] 18 类覆盖
- [ ] 审查员 pass

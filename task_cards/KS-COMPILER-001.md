---
task_id: KS-COMPILER-001
phase: Compiler
wave: W3
depends_on: [KS-SCHEMA-005, KS-S0-005]
files_touched:
  - knowledge_serving/scripts/compile_pack_view.py
  - knowledge_serving/views/pack_view.csv
artifacts:
  - knowledge_serving/views/pack_view.csv
  - knowledge_serving/audit/pack_view.compile.log
s_gates: [S1, S2, S3, S4]
plan_sections:
  - "§3.1"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_pack_view.py --check
status: done
---

# KS-COMPILER-001 · pack_view 编译

## 1. 任务目标
- **业务**：把 candidates 投影为最小知识单元读模型，喂给 retrieve_context。
- **工程**：实现 `compile_pack_view.py`，产出 `pack_view.csv`，字段对齐 §3.1 + governance。
- **S gate**：S1 source_traceability / S2 gate_filter / S3 brand_layer_scope / S4 granularity_integrity。
- **非目标**：不召回；不灌库。

## 2. 前置依赖
- KS-SCHEMA-005、KS-S0-005

## 3. 输入契约
- 读：`clean_output/candidates/**/*.yaml`、9 表、`knowledge_serving/control/content_type_canonical.csv`、`clean_output/audit/source_manifest.json`
- 不读：knowledge_serving 写入侧

- **W3+ 输入白名单硬约束（见 README §7.1）**：本卡禁止读取 ECS PG `knowledge.*`、ECS 备份目录 `/data/clean_output.bak_*`、历史临时目录 `/tmp/itr*`、Qdrant 中缺 `compile_run_id` + `source_manifest_hash` 的旧 collection；只能从 README §7.1 白名单输入派生（含本卡 §3 上方列出的具体路径，例如 `clean_output/candidates/`、`clean_output/nine_tables/`、`clean_output/audit/`、`knowledge_serving/schema/`、`knowledge_serving/control/content_type_canonical.csv` 等）。

## 4. 执行步骤
1. 加载 candidates；按下表派生 `gate_status` 并过滤（默认仅保留 `active`）：

   | brand_layer | active 判定 / active criteria |
   |---|---|
   | `domain_general` | `gate_1/2/3/4` 必须**全** `pass`（gate_3_rule_generalizable=pass 是通用层硬要求） |
   | `brand_<name>`（如 `brand_faye`）| `gate_1/2/4` 必须 `pass`；**`gate_3_rule_generalizable` 允许 `partial`** —— 品牌专属知识按定义就不期望跨品牌可泛化，partial 是正确语义而非降级 |
   | `needs_review` | 同 `brand_<name>` 规则（partial 允许） |

   **为什么 brand 包要放宽 gate_3**：CLAUDE.md 多租户红线已明：`brand_<name>` 范围限定为"品牌调性 + 创始人画像"等**故意非通用**内容，对它们要求 gate_3=pass 等于让品牌包永远进不了 serving。租户隔离由 retrieval 层 `allowed_layers` 过滤承担，不应该靠 compile 滤掉品牌包。
2. 注入 governance_common_fields（compile_run_id 来自 manifest hash 派生）
3. brand_layer 透传，禁止脚本内推断
4. content_type 映射到 canonical id（KS-S0-005）
5. 输出 csv → `knowledge_serving/views/pack_view.csv`
6. 调 KS-COMPILER-013 validator 做 schema 检查（本卡 ci 内联运行）

## 5. 执行交付
| 路径 | 格式 | canonical | 可重建 | 入 git | CI artifact |
|---|---|---|---|---|---|
| `compile_pack_view.py` | py | 是 | — | 是 | — |
| `pack_view.csv` | csv | 派生 | 是 | 是 | 是 |
| `pack_view.compile.log` | log | 否 | 是 | 否 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 source_pack_id | exit ≠ 0 |
| 非法 brand_layer | exit ≠ 0 |
| 空 candidates | 0 行 csv + warning + exit 0 |
| 重复 pack_id | exit ≠ 0 |
| 断 FK (evidence_id 不存在) | exit ≠ 0 |
| inactive pack 误入 | 默认过滤；--include-inactive 才入 |
| 跨租户污染样本 | brand_a / brand_b 行各自独立 |
| 同输入幂等 | sha256 一致 |
| brand_`<name>` + gate_3=partial 默认 active | 行存在；gate_status=active；brand_faye 行数 > 0 |
| domain_general + gate_3=partial | 默认过滤（视为 draft）；--include-inactive 才入 |

## 7. 治理语义一致性
- clean_output 0 写
- pack_view.csv 删后可重建
- 不调 LLM
- S1-S4 全绿
- governance 13 字段非空
- gate_status active only 默认

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_pack_view.py --check
pass: exit 0 + validator pass + 行数 = active candidates 数
failure_means: pack_view 不可信
artifact: pack_view.csv, .compile.log
```

## 9. CD / 环境验证
离线编译。

## 10. 独立审查员 Prompt
> 请：
> 1. clean_output `git diff` 0 改动
> 2. 删 csv 重跑，sha256 一致
> 3. 抽样 5 行反查 source_pack_id 真实存在
> 4. 注入非法 brand_layer fixture，必须 fail-closed
> 5. 输出 pass / fail
> 阻断项：clean_output 被改；幂等失败；governance 字段空；LLM 调用。

## 11. DoD
- [ ] csv 落盘
- [ ] CI pass
- [ ] 幂等 pass
- [ ] 审查员 pass

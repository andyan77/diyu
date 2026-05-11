---
task_id: KS-COMPILER-004
phase: Compiler
depends_on: [KS-SCHEMA-005]
files_touched:
  - knowledge_serving/scripts/compile_play_card_view.py
  - knowledge_serving/views/play_card_view.csv
artifacts:
  - knowledge_serving/views/play_card_view.csv
  - knowledge_serving/audit/play_card_view.compile.log
s_gates: [S6]
plan_sections:
  - "§3.4"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_play_card_view.py --check
status: not_started
---

# KS-COMPILER-004 · play_card_view 编译

## 1. 任务目标
- **业务**：把 clean_output/play_cards 投影为 serving 读模型。
- **工程**：覆盖 §3.4；completeness_status 全行非空。
- **S gate**：S6 play_card_completeness。
- **非目标**：不召回；不接 Dify。

## 2. 前置依赖
- KS-SCHEMA-005

## 3. 输入契约
- 读：`clean_output/play_cards/`、9 表、source_manifest.json、serving_views.schema.json
- 不读：运行时品牌输入

## 4. 执行步骤
1. 加载 play_card_register
2. 关联 pack；注入 governance
3. 计算 completeness_status：steps_json / anti_pattern / applicable_when / success_scenario / alternative_boundary 五字段齐 → complete；缺 1-2 → partial；缺更多 → missing
4. 校验 brand_layer 枚举
5. 输出 csv → `views/play_card_view.csv`
6. 调 validator

## 5. 执行交付
| 路径 | 格式 | canonical | 可重建 | 入 git | CI artifact |
|---|---|---|---|---|---|
| `compile_play_card_view.py` | py | 是 | — | 是 | — |
| `play_card_view.csv` | csv | 派生 | 是 | 是 | 是 |
| `play_card_view.compile.log` | log | 否 | 是 | 否 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 steps_json | completeness=partial/missing，不抛 |
| brand_layer="FAYE" | fail-closed |
| 空 register | 0 行 + warning + exit 0 |
| 重复 play_card_id | fail |
| 断 FK pack_id | fail |
| deprecated pack | 默认过滤 |
| 幂等 | sha256 一致 |

## 7. 治理语义一致性
- clean_output 0 写
- csv 删后可重建
- gate_status active only
- governance 13 字段非空
- 不调 LLM

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_play_card_view.py --check
pass: exit 0 + validator pass + 行数 = register active 数
artifact: play_card_view.csv, .compile.log
```

## 9. CD / 环境验证
离线。

## 10. 独立审查员 Prompt
> 请：1) clean_output 0 改动；2) 删 csv 重跑 sha256 一致；3) 抽 5 行反查 source_pack_id；4) 注入非法 brand_layer fixture 必须 fail-closed；5) governance 13 列全非空；6) 输出 pass / fail。
> 阻断项：clean_output 被改；幂等失败；governance 空；LLM 调用。

## 11. DoD
- [ ] CI pass
- [ ] 幂等 pass
- [ ] 7 项对抗测试全绿
- [ ] 审查员 pass

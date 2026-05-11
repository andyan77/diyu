---
task_id: KS-COMPILER-005
phase: Compiler
wave: W3
depends_on: [KS-SCHEMA-005]
files_touched:
  - knowledge_serving/scripts/compile_runtime_asset_view.py
  - knowledge_serving/views/runtime_asset_view.csv
artifacts:
  - knowledge_serving/views/runtime_asset_view.csv
s_gates: [S1]
plan_sections:
  - "§3.5"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/compile_runtime_asset_view.py --check
status: not_started
---

# KS-COMPILER-005 · runtime_asset_view 编译

## 1. 任务目标
- **业务**：把 runtime_assets 投影为 serving 读模型。
- **工程**：覆盖 §3.5；traceability_status 全行非空。
- **S gate**：S1。
- **非目标**：不召回。

## 2. 前置依赖
- KS-SCHEMA-005

## 3. 输入契约
- 读：`clean_output/runtime_assets/`、9 表、manifest

## 4. 执行步骤
1. 加载 runtime_assets register
2. 注入 governance + source_pointer
3. 校验 asset_type 枚举
4. 输出 csv

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `compile_runtime_asset_view.py` | py | 是 | 是 |
| `runtime_asset_view.csv` | csv | 派生 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 source_pointer | fail（S1） |
| 重复 runtime_asset_id | fail |
| 非法 asset_type | fail |
| 空 register | 0 行 + warning |
| 幂等 | 一致 |

## 7. 治理语义一致性
- S1 source_traceability 严格
- clean_output 0 写
- 不调 LLM

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/compile_runtime_asset_view.py --check
pass: exit 0 + validator pass
artifact: runtime_asset_view.csv
```

## 9. CD / 环境验证
离线。

## 10. 独立审查员 Prompt
> 请：1) clean_output 0 改动；2) 幂等；3) 抽样反查 source_pointer 真实存在；4) 输出 pass / fail。
> 阻断项：source_pointer 空；traceability_status 空。

## 11. DoD
- [ ] csv 落盘
- [ ] CI pass
- [ ] 审查员 pass

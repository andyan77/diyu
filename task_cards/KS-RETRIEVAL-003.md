---
task_id: KS-RETRIEVAL-003
phase: Retrieval
wave: W4
depends_on: [KS-SCHEMA-004]
files_touched:
  - knowledge_serving/serving/business_brief_checker.py
  - knowledge_serving/tests/test_brief.py
artifacts:
  - knowledge_serving/serving/business_brief_checker.py
s_gates: [S11]
plan_sections:
  - "§6.4"
writes_clean_output: false
ci_commands:
  - pytest knowledge_serving/tests/test_brief.py -v
status: not_started
---

# KS-RETRIEVAL-003 · business_brief_checker

## 1. 任务目标
- **业务**：检查商品事实 / 活动事实 / 平台目标是否足够；不足即阻断。
- **工程**：基于 business_brief.schema.json 做硬校验。
- **S gate**：S11。
- **非目标**：不补全 brief；不调 LLM 编造。

## 2. 前置依赖
- KS-SCHEMA-004

## 3. 输入契约
- 入参：brief dict（来自调用方）
- 读：business_brief.schema.json

## 4. 执行步骤
1. schema 校验（jsonschema instance validate，不只是 metaschema check）
2. required 缺失 → blocked_missing_business_brief
3. soft 缺失（`x-soft-required` 列出的 inventory_pressure / price_band / cta）→ 返回 missing_fields 列表，不阻断
4. **`compliance_redlines` 必须存在；当其为 `[]` 空数组时**输出 warning 进 missing_fields，不阻断（schema 层只描述、不强制；本 checker 是 S11 自动兜底的实际门禁）—— 来源：KS-SCHEMA-004 §12 Follow-up

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `business_brief_checker.py` | py | 是 | 是 |
| `test_brief.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 SKU | blocked |
| 缺 CTA | missing_fields 含 CTA，不阻断 |
| 缺 inventory_pressure / price_band（x-soft-required） | missing_fields 含该字段，不阻断 |
| `compliance_redlines: []` 空数组 | missing_fields 含 compliance_redlines，不阻断（warning） |
| 缺 compliance_redlines 字段 | missing_fields 含 compliance_redlines，不阻断 |
| 非法 season | raise |
| 空 brief | blocked |
| 多余字段 | warning 但不阻断 |

## 7. 治理语义一致性
- S11：不让 LLM 编造商品事实
- 不调 LLM 做补全
- 不写 clean_output

## 8. CI 门禁
```
command: pytest knowledge_serving/tests/test_brief.py -v
pass: 全绿，含 SKU 缺失阻断用例
artifact: pytest report
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) SKU 缺失必须 blocked；2) 输出 pass / fail。
> 阻断项：SKU 缺失但成稿继续。

## 11. DoD
- [ ] checker 入 git
- [ ] pytest 全绿
- [ ] 审查员 pass

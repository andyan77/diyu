---
task_id: KS-SCHEMA-004
phase: Schema
wave: W1
depends_on: [KS-S0-006]
files_touched:
  - knowledge_serving/schema/business_brief.schema.json
artifacts:
  - knowledge_serving/schema/business_brief.schema.json
s_gates: [S11]
plan_sections:
  - "§A4"
  - "§3.3"
writes_clean_output: false
ci_commands:
  - python3 scripts/check_schema.py knowledge_serving/schema/business_brief.schema.json
status: done
---

# KS-SCHEMA-004 · business_brief.schema.json

## 1. 任务目标
- **业务**：服装零售场景下，避免 LLM 编造 SKU / 商品 / 活动事实；business_brief 是事实层契约。
- **工程**：写 jsonschema，字段覆盖 §A4 服装业务 brief 清单。
- **S gate**：S11 business_brief_no_fabrication。
- **非目标**：不实现 brief 注入。

## 2. 前置依赖
- KS-S0-006

## 3. 输入契约
- 读：plan §A4

## 4. 执行步骤
1. 定义字段：品类 / SKU / 系列 / 季节 / 库存压力 / 价格带 / 面料 / 版型 / 尺码 / 目标人群 / 渠道 / 促销边界 / 拍摄资源 / CTA / 合规禁区
2. 标 required（缺即视为 hard fail）：SKU、品类、季节、渠道
3. soft required：库存压力、价格带、CTA
4. self-check

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `knowledge_serving/schema/business_brief.schema.json` | json | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 SKU | hard fail |
| 缺 CTA | soft warning |
| 非法 season 枚举 | fail |
| 价格带为字符串而非区间 | fail |
| 合规禁区为空数组 | warning |

## 7. 治理语义一致性
- 与 §A4 完全对齐
- LLM 不参与 schema 决策
- brief 中字段类型可被 KS-RETRIEVAL-003 直接消费

## 8. CI 门禁
```
command: python3 scripts/check_schema.py knowledge_serving/schema/business_brief.schema.json
pass: 自校验通过
artifact: 同上
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：
> 1. check-schema pass
> 2. SKU 缺失样本必须 hard fail
> 3. 输出 pass / fail
> 阻断项：SKU 非 required；季节枚举漏。

## 11. DoD
- [x] schema 落盘
- [x] check-schema pass
- [x] 审查员 pass

## 12. Follow-up（不阻塞本卡 done，但 S11 真闭环必须在后续卡补上）
- **`compliance_redlines` 空数组只是 schema description 里的文字提醒；`scripts/check_schema.py` 仅做 metaschema 自检，运行时 instance 校验不会真的在空数组时输出 warning。** 若 S11 `business_brief_no_fabrication`（业务简报防编造门）后续要靠自动门禁兜底，需要：
  1. 为 business_brief.schema.json 写一个独立 instance validator（不仅 check_schema），把 `x-soft-required` 字段缺失 + `compliance_redlines == []` 都翻译成可消费的 warning 输出；
  2. 把该 validator 接入 retrieval_router 的 fallback_status 决策（缺 hard required → blocked_missing_business_brief；soft 缺失 → 不阻断但写 missing_fields）。
- 建议落卡：`KS-RETRIEVAL-003` 已挂 `S11`，可在该卡内具象化此 validator 的实现要求；本卡保持 schema 边界，不扩张。

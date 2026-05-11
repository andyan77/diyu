---
task_id: KS-DIFY-ECS-009
phase: Dify-ECS
depends_on: [KS-POLICY-002]
files_touched:
  - knowledge_serving/serving/guardrail.py
  - knowledge_serving/tests/test_guardrail.py
artifacts:
  - knowledge_serving/serving/guardrail.py
s_gates: [S11]
plan_sections:
  - "§10"
  - "§7"
writes_clean_output: false
ci_commands:
  - pytest knowledge_serving/tests/test_guardrail.py -v
status: not_started
---

# KS-DIFY-ECS-009 · Guardrail 检查器

## 1. 任务目标
- **业务**：在 LLM 生成后做事实校验、品牌字段校验、forbidden_patterns 扫描。
- **工程**：实现 guardrail.py，按 KS-POLICY-002 yaml 执行；命中即阻断 / 标记。
- **S gate**：S11。
- **非目标**：不调用 LLM 做裁决。

## 2. 前置依赖
- KS-POLICY-002

## 3. 输入契约
- 入参：生成文本 + bundle + business_brief
- 读：guardrail_policy.yaml

## 4. 执行步骤
1. 加载 forbidden_patterns
2. 对生成文本做 regex / 关键词扫描
3. 核对 SKU / 创始人 / 商品事实 vs brief
4. 命中阻断或返回告警

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `guardrail.py` | py | 是 | 是 |
| `test_guardrail.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 生成文本含创始人编造 | blocked |
| 生成文本含 SKU 不在 brief | blocked |
| 生成文本干净 | pass |
| forbidden_pattern 命中 | blocked |
| 空文本 | blocked（疑似漏生成） |

## 7. 治理语义一致性
- 不调 LLM 做裁决
- 与 KS-POLICY-002 yaml 同源

## 8. CI 门禁
```
command: pytest knowledge_serving/tests/test_guardrail.py -v
pass: 阻断 + 通过用例全绿
artifact: pytest report
```

## 9. CD / 环境验证
- staging：每次 PR 跑
- 监控：guardrail 触发率

## 10. 独立审查员 Prompt
> 请：1) 创始人编造样本必 blocked；2) SKU 不一致必 blocked；3) 输出 pass / fail。
> 阻断项：编造未拦。

## 11. DoD
- [ ] guardrail 入 git
- [ ] pytest 全绿
- [ ] 审查员 pass

---
task_id: KS-RETRIEVAL-002
phase: Retrieval
wave: W4
depends_on: [KS-S0-005, KS-COMPILER-002]
files_touched:
  - knowledge_serving/serving/intent_classifier.py
  - knowledge_serving/serving/content_type_router.py
  - knowledge_serving/tests/test_routing.py
artifacts:
  - knowledge_serving/serving/intent_classifier.py
  - knowledge_serving/serving/content_type_router.py
s_gates: []
plan_sections:
  - "§6.2"
  - "§6.3"
writes_clean_output: false
ci_commands:
  - pytest knowledge_serving/tests/test_routing.py -v
status: not_started
---

# KS-RETRIEVAL-002 · intent_classifier + content_type_router

## 1. 任务目标
- **业务**：把 user_query 路由到 intent + canonical content_type。
- **工程**：规则优先；LLM assist 允许但仅做辅助，结果须经规则复核。
- **S gate**：无单独门；为下游卡提供路由信号。
- **非目标**：不做品牌推断；不做召回。

## 2. 前置依赖
- KS-S0-005、KS-COMPILER-002

## 3. 输入契约
- 读：content_type_canonical.csv、content_type_view.csv、retrieval_policy_view.csv
- 入参：user_query（仅传 hash 给 log）

## 4. 执行步骤
1. intent 枚举：content_generation / quality_check / strategy_advice / training / sales_script
2. 规则匹配关键词 → intent
3. content_type_router：按 alias 匹配 canonical id
4. LLM assist 可作为候选，但最终结果由规则节点判定

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `intent_classifier.py` | py | 是 | 是 |
| `content_type_router.py` | py | 是 | 是 |
| `test_routing.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 含品牌关键词的 query 试图改变 brand_layer | router 不应改 brand |
| 未知 alias | 返回 needs_review intent |
| 空 query | raise |
| LLM 返回非法 content_type | 规则复核拒绝 |
| 同 query 多次跑 | 结果一致（除非 LLM 启用，需 deterministic 设置） |

## 7. 治理语义一致性
- **不**从 query 推断 brand_layer
- LLM 仅辅助，规则复核
- 不写 clean_output

## 8. CI 门禁
```
command: pytest knowledge_serving/tests/test_routing.py -v
pass: 10+ case 全绿
artifact: pytest report
```

## 9. CD / 环境验证
- LLM 调用走 env key（KS-S0-003）
- LLM 不可用时降级到 rule-only

## 10. 独立审查员 Prompt
> 请：1) 跑 pytest；2) 验证 router 不修改 brand_layer；3) LLM 返回错值时规则兜底；4) 输出 pass / fail。
> 阻断项：brand_layer 被 query 影响。

## 11. DoD
- [ ] 模块入 git
- [ ] pytest 全绿
- [ ] 审查员 pass

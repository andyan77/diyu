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

> **2026-05-12 用户裁决（input-first / no-LLM）**：`content_type` 与 `intent` **必须由 Dify 开始节点 / API 显式入参提供**。本模块只做 alias→canonical 的**确定性映射 + canonical 校验**；缺失或不识别 → 返回 `needs_review`，**不调 LLM、不脑补、不兜底猜**。`model_policy.yaml` 已把 `intent_classification` / `content_type_routing` 列入 `forbidden_tasks`（S13 硬边界）。

## 1. 任务目标
- **业务**：把 Dify 开始节点 / API 已传入的 `content_type_hint` + `intent_hint` 校验到 canonical id；缺失 / 别名未知则显式 `needs_review`，由前端补字段，不在中间件凭 query 猜。
- **工程**：纯规则 / rule-only。禁止任何 LLM 调用路径。
- **S gate**：无单独门；为下游 KS-RETRIEVAL-009 提供路由信号；S13 boundary 由 KS-PROD-003 守门。
- **非目标**：不做品牌推断；不做召回；不做 LLM 兜底。

## 2. 前置依赖
- KS-S0-005、KS-COMPILER-002

## 3. 输入契约
- 读：content_type_canonical.csv、content_type_view.csv、retrieval_policy_view.csv
- 入参：
  - `content_type_hint`（Dify 开始节点 / API 表单字段，可为别名 alias 或 canonical id；可为 None）
  - `intent_hint`（同上，枚举：content_generation / quality_check / strategy_advice / training / sales_script；可为 None）
  - `user_query`（仅传 hash 给 log，**不**用于推断 intent / content_type）

## 4. 执行步骤
1. **content_type_router**：
   - 入参齐 → 走 alias→canonical 确定性映射 + canonical 集合校验
   - 命中 → 返回 `(canonical_content_type_id, source="input")`
   - 未命中 / 入参为 None → 返回 `(None, status="needs_review", missing="content_type")`
2. **intent_classifier**：
   - 入参齐且属于枚举 → 返回 `(intent, source="input")`
   - 否则 → 返回 `(None, status="needs_review", missing="intent")`
3. **禁止**：任何 LLM 客户端 import / 调用；任何对 `user_query` 的关键词推断分支。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `intent_classifier.py` | py | 是 | 是 |
| `content_type_router.py` | py | 是 | 是 |
| `test_routing.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 模块源码 grep `dashscope` / `openai` / `llm_assist` | 0 命中 |
| mock LLM client，全程不应被触发（call_count == 0） | 通过 |
| 含品牌关键词的 query 试图改变 brand_layer | router 不读 query，不返回 brand |
| 未知 alias 入参 | 返回 needs_review，**不**返回兜底 intent / content_type |
| 入参为 None | 返回 needs_review |
| 同入参多次跑 | 结果完全一致（纯函数，确定性） |
| 入参直接传 canonical id | 直接放行 |

## 7. 治理语义一致性
- 不从 query 推断 brand_layer / content_type / intent
- 不调 LLM（强制：源代码静态扫 + mock 调用计数双校验）
- 不写 clean_output

## 8. CI 门禁
```
command: pytest knowledge_serving/tests/test_routing.py -v
pass: 7+ case 全绿，含"无 LLM 调用"硬断言
artifact: pytest report
```

## 9. CD / 环境验证
- 不需要任何 LLM env key
- 即使 model_policy.yaml 错配置 `enabled=true`，本模块路径也不应触发 LLM（由 KS-PROD-003 S13 boundary 守门）

## 10. 独立审查员 Prompt
> 请：1) 跑 pytest；2) 验证 router 不修改 brand_layer；3) `grep -r "dashscope\|openai\|llm_assist" intent_classifier.py content_type_router.py` 必须 0 命中；4) mock LLM client 全程未被调用；5) 输出 pass / fail。
> 阻断项：发现任何 LLM 调用路径 / 从 user_query 推断 content_type 或 intent / 别名未知时返回兜底值（应返回 needs_review）。

## 11. DoD
- [ ] 模块入 git
- [ ] pytest 全绿
- [ ] 审查员 pass

---
task_id: KS-DIFY-ECS-007
phase: Dify-ECS
depends_on: [KS-RETRIEVAL-009]
files_touched:
  - knowledge_serving/serving/api/retrieve_context.py
  - knowledge_serving/serving/api/openapi.yaml
  - knowledge_serving/tests/test_api.py
artifacts:
  - knowledge_serving/serving/api/retrieve_context.py
  - knowledge_serving/serving/api/openapi.yaml
s_gates: []
plan_sections:
  - "§5"
writes_clean_output: false
ci_commands:
  - pytest knowledge_serving/tests/test_api.py -v
status: not_started
---

# KS-DIFY-ECS-007 · retrieve_context API wrapper

## 1. 任务目标
- **业务**：把 retrieve_context() 暴露为 HTTP API 供 Dify Chatflow 调用。
- **工程**：FastAPI / Flask 包装；OpenAPI 规范；返回 §5 bundle 结构。
- **S gate**：无单独门。
- **非目标**：不实现 Dify 节点。

## 2. 前置依赖
- KS-RETRIEVAL-009

## 3. 输入契约
- 入参：tenant_id / user_query / content_type? / platform? / output_format? / fallback_mode? / business_brief?
- 返回：context_bundle JSON

## 4. 执行步骤
1. 实现 POST /v1/retrieve_context
2. 入参校验（tenant_id 必须；user_query 长度限制）
3. 调 retrieve_context()
4. 返回 bundle；含 request_id
5. 写 openapi.yaml

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `retrieve_context.py` | py | 是 | 是 |
| `openapi.yaml` | yaml | 是 | 是 |
| `test_api.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 无 tenant_id | 400 |
| 未登记 tenant_id | 403 |
| user_query 试图含品牌 override | 不切换 brand |
| 巨大 query | 413 |
| 内部 error | 5xx + request_id 仍写 log |

## 7. 治理语义一致性
- API 不接受 brand_layer 参数（红线）
- 不调 LLM 做最终判断
- secrets env

## 8. CI 门禁
```
command: pytest knowledge_serving/tests/test_api.py -v
pass: 5+ case 全绿
artifact: pytest report
```

## 9. CD / 环境验证
- staging：CI runner 启动并测
- prod：滚动发布
- 健康检查：/healthz
- 监控：QPS / p99 延迟 / 5xx 率
- secrets：env

## 10. 独立审查员 Prompt
> 请：1) OpenAPI 不含 brand_layer 入参；2) 试 brand override 不切换；3) 输出 pass / fail。
> 阻断项：API 接受 brand_layer 入参。

## 11. DoD
- [ ] API 入 git
- [ ] pytest 全绿
- [ ] 审查员 pass

---
task_id: KS-DIFY-ECS-007
phase: Dify-ECS
wave: W11
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
status: done
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
- [x] API 入 git（`knowledge_serving/serving/api/retrieve_context.py` + `openapi.yaml` + `__init__.py`）
- [x] pytest 全绿（11/11 PASS：healthz / happy_path / 400×2 / 403 / 413 / 500 / brand_layer_payload_red_line / brand_override_in_query_blocked / openapi_yaml_red_line / runtime_openapi_red_line）
- [ ] 审查员 pass — 待 W11 外审入口

## 12. 实施记录 / 2026-05-13 W11

### 工程要点

- **FastAPI** 0.104 wrapper；pydantic `extra="forbid"` 在 `RetrieveContextRequest` 上硬拦
  `brand_layer` / 任何其他未声明字段（红线 / red line：API 不接受 brand override）
- **错误映射**：
  - pydantic 校验失败 / 入参非法 → `@app.exception_handler(RequestValidationError)` 统一返 **400**（不是 FastAPI 默认 422）
  - 缺 tenant_id / 缺 user_query → 400（pydantic required + min_length）
  - 入参带 `brand_layer` 等额外字段 → 400（extra=forbid）
  - `TenantNotAuthorized`（未登记 / disabled / api_key mismatch）→ **403**，detail 含 request_id
  - `user_query > 4000` → **413**（pydantic field_validator 抛 HTTPException）
  - 内部异常 → **500**，detail 含 request_id + type + message，便于运营关联（stderr 同步打印 request_id）
- **13 步装配 helper `_orchestrate`**：复用 KS-RETRIEVAL-001..008 模块；与 smoke / demo 同款链路，
  保证 API 返回的 bundle 走的就是真实业务路径，不是平行影子
- **brand_layer 红线兜底**：返回 bundle 的 `resolved_brand_layer` 始终由 `tenant_scope_resolver.resolve(tenant_id)`
  推断；`user_query` 里写 "brand_faye 语气" 也不会让 tenant_demo 拿到 brand_faye scope（测试 `test_brand_override_in_user_query_does_not_switch_brand` 守门）
- **/healthz**：liveness probe，给 K8s / docker healthcheck 用

### 测试矩阵（11 case，全 PASS）

| 测试 | 覆盖卡 §6 / §10 |
|---|---|
| test_healthz | /healthz liveness |
| test_happy_path_returns_bundle_and_writes_log | 200 + bundle 16 字段 + log 落 canonical CSV |
| test_missing_tenant_id_400 | §6 case 1 |
| test_missing_user_query_400 | §3 必填 |
| test_unregistered_tenant_403 | §6 case 2 |
| test_giant_query_413 | §6 case 4 |
| test_brand_layer_in_payload_rejected_400 | §10 阻断项（红线）|
| test_brand_override_in_user_query_does_not_switch_brand | §6 case 3 |
| test_internal_error_returns_500_with_request_id | §6 case 5 |
| test_openapi_yaml_has_no_brand_layer_in_request_schema | §10 静态守门 |
| test_runtime_openapi_excludes_brand_layer | §10 运行时 OpenAPI 守门 |

### 回归证据 / 2026-05-13 W11

- `python3 -m pytest knowledge_serving/tests/test_api.py -v` → 11 passed
- `python3 -m pytest knowledge_serving/tests/ knowledge_serving/scripts/tests/ -q` → 479 passed（升级前 468 + 11）
- `python3 task_cards/validate_task_cards.py` → 57 cards / DAG closed / S0-S13 covered
- `bash knowledge_serving/scripts/lint_no_duplicate_log.sh` → exit 0

### 边界 / handoff

- 本卡只交付 HTTP wrapper + OpenAPI + 单元测试；**不交付 Dify 节点**（属 KS-DIFY-ECS-008 范围）
- live Qdrant 召回路径走 KS-DIFY-ECS-006 smoke / 批量评测；API 默认 structured_only（与卡 §3 一致，未列 qdrant 入参）
- replay / 回放一致性 → KS-DIFY-ECS-010

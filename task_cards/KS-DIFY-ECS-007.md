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
  - knowledge_serving/audit/api_ecs_deployment_KS-FIX-16.json
s_gates: []
plan_sections:
  - "§5"
writes_clean_output: false
ci_commands:
  - python3 -m pytest knowledge_serving/tests/test_api.py -v
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
| `knowledge_serving/audit/api_ecs_deployment_KS-FIX-16.json` | json（含 env / checked_at / git_commit / evidence_level） | 是（staging real HTTP 证据） | 是 |

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
command: python3 -m pytest knowledge_serving/tests/test_api.py -v
pass: 5+ case 全绿（W11 外审收口：15 case 全绿）
artifact: pytest report
note: 仓库 / 本项目 venv 未在 PATH 暴露 `pytest` 入口，必须用 `python3 -m pytest`
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
- [x] pytest 全绿（15/15 PASS，含 W11 外审收口新增 3 case：missing_content_type_400 / unknown_content_type→needs_review / unknown_intent→needs_review）
- [x] 审查员 pass — runtime_verified（2026-05-13 W11 外审复跑后裁决 CONDITIONAL_PASS：单卡未发现阻断 finding；明确允许勾审查员 pass；同时强调 W11 波次未闭，需等 KS-DIFY-ECS-010 完成后再更新波次状态）
- [x] API live vector path verified post-FIX-12 — runtime_verified（2026-05-14 KS-FIX-12 收口重 scope 后落地：删 `retrieve_context.py:213 vector_res = None` 硬编码 → 默认 `structured_only=False` 时真调 `vector_retrieve()`（真 dashscope text-embedding-v3 + 真 ECS Qdrant `ks_chunks_current` alias）；Qdrant 不可达 + mode=vector → 503 fail-closed `qdrant_unreachable`（不静默 None）；`structured_only=True` 显式开 → 兼容跳过 vector。**双轨 e2e**：(A) in-process ASGI TestClient `knowledge_serving/audit/retrieval_006_staging_KS-FIX-12.json` 3/3 pass + pytest `test_retrieval_006_staging.py` 4/4 pass；(B) **真 HTTP wire** `knowledge_serving/audit/retrieval_006_staging_KS-FIX-12.http.json` 3/3 pass（uvicorn standalone subprocess + urllib real socket POST + 独立子进程注入 QDRANT_URL=127.0.0.1:1 验 C3 503）；transport_distinction 双轨互证。红线：S10 vector 召回在 API 主路径首次真实门控）

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

## 13. W11 外审收口 / 2026-05-13

审查员 RISKY 裁决 3 项 finding，全部消化：

| Finding | 等级 | E8 决策 | 修法 | 证据 |
|---|---|---|---|---|
| #1 `content_type` / `intent_hint` 语义漂移 | HIGH | 改 data 匹配 spec：plan §6 step 2/3（2026-05-12 用户裁决）是真源；API 层兜底是漂移 | (a) `RetrieveContextRequest.content_type` / `intent_hint` 改 required（min_length=1），缺失 → 400；(b) `_orchestrate` 在 step 2/3 后检查 `status != "ok"` → 抛 `NeedsReviewException` 短路；(c) handler 把 `NeedsReviewException` 转成 **200 + `{status: needs_review, needs_review: {field, received, reason}}`**，不再 500；(d) happy path 响应增 `status: ok` 用于前端 oneOf 分发 | 新增 4 测试 PASS：`test_missing_content_type_400` / `test_missing_intent_hint_400` / `test_unknown_content_type_returns_needs_review` / `test_unknown_intent_hint_returns_needs_review` |
| #2 CI 命令 `pytest` 在本仓 venv 不可用 | MEDIUM | spec 改 data：本仓 venv 未在 PATH 暴露 `pytest` 入口（`exit 127`），命令应统一为 `python3 -m pytest` | task card §8 / front matter `ci_commands` 同步改为 `python3 -m pytest knowledge_serving/tests/test_api.py -v` | 现场复跑 `python3 -m pytest knowledge_serving/tests/test_api.py -v` → 15 passed |
| #3 status=done vs 审查员 pass 未勾不一致 | MEDIUM | 项目两阶段惯例（其它已交付卡如 KS-DIFY-ECS-005 同样模式）：`status=done` = "本卡交付落盘"；DoD 「审查员 pass」由外审复跑后单独勾。本次审查员 RISKY 自然不勾；修完 #1 后等下一轮外审复跑再勾 | DoD 第 3 项保持 `[ ]`，本节明确登记本轮 finding 消化记录 | 待 W11 外审入口复跑后由审查员勾选 |

### OpenAPI 同步更新

- `RetrieveContextRequest.required` 增 `content_type` 和 `intent_hint`；移除两者的 `nullable / default`，改为 `minLength: 1` + plan 真源描述
- POST `/v1/retrieve_context` 200 响应改 `oneOf: [RetrieveContextResponse, NeedsReviewResponse]`
- 新增 `NeedsReviewResponse` schema（含 `status: needs_review`、`needs_review.field ∈ {intent, content_type}` 枚举）
- `additionalProperties: false` 红线守门保留

### 与 plan §6 真源对齐 / spec alignment

| Plan 真源 | 本卡实现 |
|---|---|
| step 2: intent 必须显式入参；中间件枚举校验；缺失/非法 → needs_review；禁止 LLM 推断 | ✅ pydantic required + `ic.classify()` status != ok → NeedsReview |
| step 3: content_type 必须显式入参；中间件 alias→canonical；别名未知 → needs_review，不返回兜底 | ✅ pydantic required + `ctr.route()` status != ok → NeedsReview，绝不兜底 product_review |
| step 9: brand_overlay 只允许 tenant_scope_resolver 推断的 resolved_brand_layer | ✅ pydantic extra=forbid 拦 brand_layer 入参 + bundle 始终用 tsr 结果 |

### 回归证据 / 2026-05-13 W11 外审收口

- `python3 -m pytest knowledge_serving/tests/test_api.py -v` → 15 passed
- `python3 -m pytest knowledge_serving/tests/ knowledge_serving/scripts/tests/ -q` → 483 passed（升级前 479 + 新增 4 case）
- `python3 task_cards/validate_task_cards.py` → 57 cards / DAG closed / S0-S13 covered
- `bash knowledge_serving/scripts/lint_no_duplicate_log.sh` → exit 0

### 边界（不变）

- 本卡只交付 HTTP wrapper + OpenAPI + 单元测试；不交付 Dify 节点（KS-DIFY-ECS-008）
- live Qdrant 召回路径走 KS-DIFY-ECS-006 smoke；本 API 默认 structured_only
- replay / 回放一致性 → KS-DIFY-ECS-010

## 14. 2026-05-14 KS-FIX-16 real HTTP wire 补证

- 原 §8 ci_command 复跑：`python3 -m pytest knowledge_serving/tests/test_api.py -v` → exit 0（15 passed）
- ECS staging 部署状态：`diyu-serving` 容器 Up（healthy） / 容器 /healthz=200 / nginx 三条 location 已 include
- **真 HTTP wire 测**：新增 `knowledge_serving/tests/test_api_real_http.py`（4 case：base_url 黑名单守门 / vector_res=None unguarded 源码扫描 / 5 distinct query × HTTPS POST → 全 200 + vector_meta.candidate_count>0 / ECS 容器 /healthz 真返 200）；`source scripts/load_env.sh && STAGING_API_BASE=https://kb.diyuai.cc python3 -m pytest knowledge_serving/tests/test_api_real_http.py -v` → exit 0（4 passed in 32.44s）
- 公网 6 探针手工跑：6/6 HTTP 200，6/6 vector_mode=vector / candidate_count=2 / collection=ks_chunks_current
- 上游回归：test_api.py 15 passed；validate_serving_tree OK（88 W3-12 白名单含新 test）
- runtime envelope：`knowledge_serving/audit/api_ecs_deployment_KS-FIX-16.json`（env=staging / checked_at=2026-05-14T15:31:58Z / git_commit=4240cdd555d49c8220974d19efa9a9911a6e9498 / evidence_level=runtime_verified / verdict=PASS）

# Dify Chatflow 10 节点说明（KS-DIFY-ECS-008）

> 本项目维护**两份 DSL**：
> - [`dify/chatflow.dsl`](../dify/chatflow.dsl) — 项目内 canonical 抽象，由 `scripts/validate_dify_dsl.py` V1-V11 守门
> - [`dify/chatflow_dify_cloud.yml`](../dify/chatflow_dify_cloud.yml) — **Dify Cloud 原生 DSL**，可直接 Studio import
>
> 两份语义一对一对应；任一改动必须同步两端，并跑 `python3 scripts/validate_dify_dsl.py` + `python3 -c "import yaml; yaml.safe_load(open('dify/chatflow_dify_cloud.yml'))"` 双重校验。
>
> ## Dify Cloud 导入步骤
>
> 1. 登录 `https://cloud.dify.ai` → Studio
> 2. **Create App → Import DSL file** → 选 `dify/chatflow_dify_cloud.yml`
> 3. 导入后在 Studio 顶部 **环境变量** 把 `SERVING_API_BASE` 改成你的真 staging URL（缺省 `https://api.diyu.staging.internal` 是占位）
> 4. 在 LLM 节点（n7）确认 model.provider/name 与你 Dify Cloud 已接入的模型匹配（缺省 `langgenius/tongyi/tongyi` + `qwen-plus`）
> 5. 在 HTTP 节点（n5 / n8 / n10）确认 endpoint 路径（默认按 [openapi.yaml](../knowledge_serving/serving/api/openapi.yaml) 的 `/v1/retrieve_context`；guardrail / log_write 需要 KS-FIX-18 / 后续卡补 wrapper endpoint）
> 6. Run / Test 一条 query 看 n5 是否真出 200 bundle
>
> ## 导入前先做（强烈建议）
>
> 把 `app.diyu.staging.internal` 替换为你能真访问的 staging URL，否则 n5/n8/n10 会 DNS 失败、整条 chatflow 跑不通。也可以先用 ngrok / cloudflared 把本地 uvicorn 暴露成公网 HTTPS 临时跑通。

## 核心红线（必须背下来）

| 红线 | 来源 | 落点 |
|---|---|---|
| **input-first**：`intent_hint` / `content_type_hint` 由开始节点 form 字段强制收集；中间件只做确定性 alias→canonical / 枚举校验 | 2026-05-12 用户裁决；Plan §10；KS-RETRIEVAL-002 / KS-POLICY-005 forbidden_tasks | start.form_variables 两字段 `required=true`；节点 2/3 type=code |
| **不绕 tenant filter**：所有 9 表读写必经 `retrieve_context_call` HTTP API（KS-DIFY-ECS-007 落盘） | Plan §10 + KS-PROD-002 e2e | 节点 5 `uses_tenant_filter=true` + `no_direct_table_query=true` |
| **LLM 仅生成文案**：不接管 intent / content_type / 品牌 / 降级 / 合并任何治理判断 | Plan §10 + KS-POLICY-005 | 仅 role=`llm_generation` 可 type=llm |
| **Agent 只挂 off-path**：rerank / 自检 / guardrail 辅助；不许扛任一 pipeline 角色 | Plan §10 | `agent_policy.allowed_off_path_roles` |
| **硬缺字段不进 LLM**：`business_brief_check` 与 `llm_generation` 之间必经 `fallback_status_branch` | Plan §10 + KS-POLICY-005 | 拓扑 bbc < fsb < llm |
| **Guardrail 在 LLM 之后**：先生成后过滤 | Plan §10 | 拓扑 llm < guardrail |

## 10 节点清单

开始节点（Start，不计入 10 节点 pipeline）：表单收集 `tenant_id_hint` / `user_query` / `intent_hint` / `content_type_hint` / `business_brief`。

| # | 节点 id | role (canonical) | type | 职责 / 关键约束 |
|---|---|---|---|---|
| 0 | `n0_preflight_call` | `preflight_call` | http_request | **KS-CD-003-A 单源化入口**：POST `${SERVING_API_BASE}/v1/input_preflight`；服务端组合 4 个 deterministic 模块（tenant_scope_resolver / intent_classifier / content_type_router / field_requirement_matrix）；禁 LLM/Agent |
| 1 | `n1_tenant_resolution` | `tenant_resolution` | code | 透传 `n0.tenant`（**真源在 server 端 tenant_scope_registry.csv**）；禁 LLM/Agent；DSL 内禁内联 registry |
| 2 | `n2_intent_canonical_check` | `intent_canonical_check` | code | 透传 `n0.intent`（**真源 = intent_classifier.INTENT_ENUM 5 类**）；禁 LLM/Agent；DSL 内禁硬编码 intent 枚举 |
| 3 | `n3_content_type_canonical_map` | `content_type_canonical_map` | code | 透传 `n0.content_type`（**真源 = content_type_canonical.csv 18 canonical + aliases**）；禁 LLM/Agent；DSL 内禁内联 alias 大表 |
| 4 | `n4_business_brief_check` | `business_brief_check` | code | 透传 `n0.business_brief`（**真源 = field_requirement_matrix.csv per-content_type HARD**）；输出 `business_brief_missing_fields` |
| 5 | `n5_retrieve_context_call` | `retrieve_context_call` | http_request | POST `${SERVING_API_BASE}/v1/retrieve_context`；必须 `uses_tenant_filter=true` + `no_direct_table_query=true`；禁直查 9 表 view |
| 6 | `n6_fallback_status_branch` | `fallback_status_branch` | if_else | 按 `fallback_status` 分流；`blocked_*` 直接绕过 LLM 走 output_evidence；禁 LLM/Agent |
| 7 | `n7_llm_generation` | `llm_generation` | llm | 仅消费 `context_bundle` 输出 `draft_output`；不接管任何治理判断 |
| 8 | `n8_guardrail` | `guardrail` | code | 走 `guardrail_policy` 静态规则（禁词 / 长度 / 字段守门）；不调 LLM |
| 9 | `n9_output_evidence` | `output_evidence` | template_transform | 拼最终响应（`draft_output` + `evidence_summary` 摘要）|
| 10 | `n10_log_write` | `log_write` | http_request | POST `${SERVING_API_BASE}/internal/context_bundle_log`；写 canonical CSV + PG mirror outbox |

## 拓扑序

```
start
  └─▶ n0 ─▶ n1 ─▶ n2 ─▶ n3 ─▶ n4 ─▶ n5 ─▶ n6
                                               ├─▶ (blocked_*) ─▶ n9 ─▶ n10
                                               └─▶ n7 ─▶ n8 ─▶ n9 ─▶ n10
```

## 校验门 / validator gates

`scripts/validate_dify_dsl.py` 跑 13 道门 V1–V13：role 覆盖 / 拓扑顺序 / LLM-Agent 类型约束 / guardrail 位置 / log_write 存在性 / tenant_filter + no_direct_table_query / 9 表 view 直查禁用 / fallback 必经路径 / Agent off-path 限制 / start 表单字段 input-first / **V12 single-source 红线（n1-n4 必须引用 n0_preflight_call.*）** / **V13 chatflow_dify_cloud.yml 内联代码体积+关键字闸（防 registry/alias 大表回潮）**。

## 对抗性测试覆盖

[`knowledge_serving/scripts/tests/test_validate_dify_dsl.py`](../knowledge_serving/scripts/tests/test_validate_dify_dsl.py) 覆盖卡 §6 全 6 项 + 拓展 7 项，共 15 用例。

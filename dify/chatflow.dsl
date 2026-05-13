# KS-DIFY-ECS-008 · Dify Chatflow DSL（10 节点 canonical）
#
# 与 §10 Plan / 卡 §4 / 2026-05-12 input-first 用户裁决严格一致：
# - 10 个 pipeline 节点 (ORDERED_ROLES)
# - intent / content_type 必须由 start.form_variables 显式收集 → 确定性 canonical 校验/映射
# - LLM 节点仅出现在 role=llm_generation；Agent 节点仅可挂 off-path 辅助角色
# - retrieve_context_call 走 KS-DIFY-ECS-007 落盘的 HTTP API，不直查 9 表，不绕 tenant filter
#
# 校验：python3 scripts/validate_dify_dsl.py

version: "1.0"

app:
  name: knowledge-serving-chatflow
  mode: chatflow
  description: |
    Dify Chatflow 编排主控（KS-DIFY-ECS-008）。开始节点收集 tenant_id_hint /
    user_query / intent_hint / content_type_hint / business_brief；
    10 个 pipeline 节点依次执行；最终落 context_bundle_log。

# ----------------------------------------------------------------------
# Start 节点 form 变量（input-first 红线 2026-05-12 用户裁决）
# ----------------------------------------------------------------------
start:
  form_variables:
    - name: tenant_id_hint
      type: text
      required: true
      description: 租户身份；后端 tenant_resolution 节点解析品牌层
    - name: user_query
      type: paragraph
      required: true
      description: 用户原始问句（仅用于检索 / 不用于 intent/content_type 推断）
    - name: intent_hint
      type: select
      required: true
      options: [content_generation, retrieval_only, qa]
      description: intent canonical 枚举；中间件只做确定性校验，禁 LLM
    - name: content_type_hint
      type: text
      required: true
      description: content_type alias 或 canonical id；中间件只做确定性 alias→canonical
    - name: business_brief
      type: object
      required: false
      description: 业务输入（sku / season / channel / category 等），缺则降级判定

# ----------------------------------------------------------------------
# 10-node pipeline
# ----------------------------------------------------------------------
nodes:
  - id: n1_tenant_resolution
    role: tenant_resolution
    type: code
    description: 根据 tenant_id_hint 解析 resolved_brand_layer + allowed_layers
    inputs:
      - source: start.tenant_id_hint
    outputs: [resolved_brand_layer, allowed_layers]

  - id: n2_intent_canonical_check
    role: intent_canonical_check
    type: code
    description: intent_hint 在 canonical 枚举内则透传 classified_intent；否则 needs_review
    inputs:
      - source: start.intent_hint
    outputs: [classified_intent]

  - id: n3_content_type_canonical_map
    role: content_type_canonical_map
    type: code
    description: 走 content_type_canonical.csv 做确定性 alias→canonical 映射
    inputs:
      - source: start.content_type_hint
    outputs: [content_type]

  - id: n4_business_brief_check
    role: business_brief_check
    type: code
    description: 检查 business_brief 是否满足 content_type 所需字段集
    inputs:
      - source: start.business_brief
      - source: n3_content_type_canonical_map.content_type
    outputs: [business_brief_missing_fields]

  - id: n5_retrieve_context_call
    role: retrieve_context_call
    type: http_request
    description: 走 KS-DIFY-ECS-007 落盘的 retrieve_context HTTP API；不绕 tenant filter，不直查 9 表
    method: POST
    url: "${SERVING_API_BASE}/api/v1/retrieve_context"
    uses_tenant_filter: true
    no_direct_table_query: true
    inputs:
      - source: n1_tenant_resolution.resolved_brand_layer
      - source: n2_intent_canonical_check.classified_intent
      - source: n3_content_type_canonical_map.content_type
      - source: n4_business_brief_check.business_brief_missing_fields
      - source: start.business_brief
      - source: start.user_query
    outputs: [context_bundle, fallback_status]

  - id: n6_fallback_status_branch
    role: fallback_status_branch
    type: if_else
    description: 按 fallback_status 分流；blocked_* 直接走 output_evidence 不进 LLM
    inputs:
      - source: n5_retrieve_context_call.fallback_status
    branches:
      - on: [blocked_missing_business_brief, blocked_missing_required_brand_fields]
        target: n9_output_evidence
      - default: n7_llm_generation

  - id: n7_llm_generation
    role: llm_generation
    type: llm
    description: 仅消费 context_bundle 输出文案；不接管任何治理判断
    model: ${LLM_MODEL_ID}
    inputs:
      - source: n5_retrieve_context_call.context_bundle
    outputs: [draft_output]

  - id: n8_guardrail
    role: guardrail
    type: code
    description: 走 guardrail_policy 静态规则（禁词 / 长度 / 字段守门）；不调 LLM
    inputs:
      - source: n7_llm_generation.draft_output
      - source: n5_retrieve_context_call.context_bundle
    outputs: [guardrail_passed, blocked_reason]

  - id: n9_output_evidence
    role: output_evidence
    type: template_transform
    description: 拼最终响应（draft_output + evidence_summary 摘要）
    inputs:
      - source: n8_guardrail.guardrail_passed
      - source: n5_retrieve_context_call.context_bundle
    outputs: [final_response]

  - id: n10_log_write
    role: log_write
    type: http_request
    description: 把 request 写到 context_bundle_log（canonical CSV + PG mirror outbox）
    method: POST
    url: "${SERVING_API_BASE}/internal/context_bundle_log"
    inputs:
      - source: n9_output_evidence.final_response
      - source: n5_retrieve_context_call.context_bundle
      - source: n8_guardrail.blocked_reason

# ----------------------------------------------------------------------
# 边 / edges：严格按 ORDERED_ROLES 顺序
# ----------------------------------------------------------------------
edges:
  - { from: n1_tenant_resolution,         to: n2_intent_canonical_check }
  - { from: n2_intent_canonical_check,    to: n3_content_type_canonical_map }
  - { from: n3_content_type_canonical_map, to: n4_business_brief_check }
  - { from: n4_business_brief_check,      to: n5_retrieve_context_call }
  - { from: n5_retrieve_context_call,     to: n6_fallback_status_branch }
  - { from: n6_fallback_status_branch,    to: n7_llm_generation }
  - { from: n7_llm_generation,            to: n8_guardrail }
  - { from: n8_guardrail,                 to: n9_output_evidence }
  - { from: n9_output_evidence,           to: n10_log_write }

# ----------------------------------------------------------------------
# Agent 节点策略（off-path 才允许；不许扛 pipeline 角色）
# ----------------------------------------------------------------------
agent_policy:
  allowed_off_path_roles:
    - rerank_assist
    - self_check_assist
    - guardrail_assist
  forbidden_pipeline_roles:
    - tenant_resolution
    - intent_canonical_check
    - content_type_canonical_map
    - business_brief_check
    - retrieve_context_call
    - fallback_status_branch
    - llm_generation
    - guardrail
    - output_evidence
    - log_write

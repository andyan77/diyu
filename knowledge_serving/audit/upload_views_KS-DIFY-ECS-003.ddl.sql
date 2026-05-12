-- KS-DIFY-ECS-003 DDL · target schema: serving

CREATE SCHEMA IF NOT EXISTS serving;

CREATE TABLE IF NOT EXISTS serving.pack_view (
  source_pack_id TEXT,
  brand_layer TEXT,
  granularity_layer TEXT,
  gate_status TEXT,
  source_table_refs TEXT,
  evidence_ids TEXT,
  traceability_status TEXT,
  default_call_pool TEXT,
  review_status TEXT,
  compile_run_id TEXT,
  source_manifest_hash TEXT,
  view_schema_version TEXT,
  chunk_text_hash TEXT,
  pack_id TEXT,
  pack_type TEXT,
  knowledge_title TEXT,
  knowledge_assertion TEXT,
  applicable_when TEXT,
  success_scenario TEXT,
  flip_scenario TEXT,
  alternative_boundary TEXT,
  content_type_tags TEXT,
  object_type_tags TEXT,
  embedding_text TEXT
);
COMMENT ON TABLE serving.pack_view IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.content_type_view (
  source_pack_id TEXT,
  brand_layer TEXT,
  granularity_layer TEXT,
  gate_status TEXT,
  source_table_refs TEXT,
  evidence_ids TEXT,
  traceability_status TEXT,
  default_call_pool TEXT,
  review_status TEXT,
  compile_run_id TEXT,
  source_manifest_hash TEXT,
  view_schema_version TEXT,
  chunk_text_hash TEXT,
  content_type TEXT,
  canonical_content_type_id TEXT,
  aliases TEXT,
  production_mode TEXT,
  north_star TEXT,
  default_output_formats TEXT,
  default_platforms TEXT,
  recommended_persona_roles TEXT,
  risk_level TEXT,
  brand_overlay_required_level TEXT,
  required_knowledge_layers TEXT,
  forbidden_patterns TEXT,
  source_pack_ids TEXT,
  coverage_status TEXT
);
COMMENT ON TABLE serving.content_type_view IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.generation_recipe_view (
  source_pack_id TEXT,
  brand_layer TEXT,
  granularity_layer TEXT,
  gate_status TEXT,
  source_table_refs TEXT,
  evidence_ids TEXT,
  traceability_status TEXT,
  default_call_pool TEXT,
  review_status TEXT,
  compile_run_id TEXT,
  source_manifest_hash TEXT,
  view_schema_version TEXT,
  chunk_text_hash TEXT,
  recipe_id TEXT,
  content_type TEXT,
  output_format TEXT,
  platform TEXT,
  intent_scope TEXT,
  required_views TEXT,
  retrieval_plan_json TEXT,
  step_sequence_json TEXT,
  context_budget_json TEXT,
  fallback_policy_id TEXT,
  guardrail_policy_id TEXT,
  merge_policy_id TEXT,
  business_brief_schema_id TEXT
);
COMMENT ON TABLE serving.generation_recipe_view IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.play_card_view (
  source_pack_id TEXT,
  brand_layer TEXT,
  granularity_layer TEXT,
  gate_status TEXT,
  source_table_refs TEXT,
  evidence_ids TEXT,
  traceability_status TEXT,
  default_call_pool TEXT,
  review_status TEXT,
  compile_run_id TEXT,
  source_manifest_hash TEXT,
  view_schema_version TEXT,
  chunk_text_hash TEXT,
  play_card_id TEXT,
  pack_id TEXT,
  content_type TEXT,
  hook TEXT,
  production_tier TEXT,
  production_difficulty TEXT,
  duration TEXT,
  steps_json TEXT,
  anti_pattern TEXT,
  applicable_when TEXT,
  success_scenario TEXT,
  alternative_boundary TEXT,
  completeness_status TEXT
);
COMMENT ON TABLE serving.play_card_view IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.runtime_asset_view (
  source_pack_id TEXT,
  brand_layer TEXT,
  granularity_layer TEXT,
  gate_status TEXT,
  source_table_refs TEXT,
  evidence_ids TEXT,
  traceability_status TEXT,
  default_call_pool TEXT,
  review_status TEXT,
  compile_run_id TEXT,
  source_manifest_hash TEXT,
  view_schema_version TEXT,
  chunk_text_hash TEXT,
  runtime_asset_id TEXT,
  pack_id TEXT,
  asset_type TEXT,
  title TEXT,
  summary TEXT,
  content_pointer TEXT,
  asset_payload_json TEXT,
  source_pointer TEXT
);
COMMENT ON TABLE serving.runtime_asset_view IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.brand_overlay_view (
  source_pack_id TEXT,
  brand_layer TEXT,
  granularity_layer TEXT,
  gate_status TEXT,
  source_table_refs TEXT,
  evidence_ids TEXT,
  traceability_status TEXT,
  default_call_pool TEXT,
  review_status TEXT,
  compile_run_id TEXT,
  source_manifest_hash TEXT,
  view_schema_version TEXT,
  chunk_text_hash TEXT,
  overlay_id TEXT,
  brand_overlay_kind TEXT,
  target_content_type TEXT,
  target_pack_id TEXT,
  tone_constraints_json TEXT,
  output_structure_json TEXT,
  required_knowledge_json TEXT,
  forbidden_words TEXT,
  signature_phrases TEXT,
  precedence TEXT,
  fallback_behavior TEXT
);
COMMENT ON TABLE serving.brand_overlay_view IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.evidence_view (
  source_pack_id TEXT,
  brand_layer TEXT,
  granularity_layer TEXT,
  gate_status TEXT,
  source_table_refs TEXT,
  evidence_ids TEXT,
  traceability_status TEXT,
  default_call_pool TEXT,
  review_status TEXT,
  compile_run_id TEXT,
  source_manifest_hash TEXT,
  view_schema_version TEXT,
  chunk_text_hash TEXT,
  evidence_id TEXT,
  source_md TEXT,
  source_anchor TEXT,
  evidence_quote TEXT,
  source_type TEXT,
  inference_level TEXT,
  trace_quality TEXT,
  line_no TEXT,
  adjudication_status TEXT
);
COMMENT ON TABLE serving.evidence_view IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.tenant_scope_registry (
  tenant_id TEXT,
  api_key_id TEXT,
  brand_layer TEXT,
  allowed_layers TEXT,
  default_platforms TEXT,
  policy_level TEXT,
  enabled TEXT,
  environment TEXT
);
COMMENT ON TABLE serving.tenant_scope_registry IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.field_requirement_matrix (
  content_type TEXT,
  field_key TEXT,
  required_level TEXT,
  fallback_action TEXT,
  ask_user_question TEXT,
  block_reason TEXT
);
COMMENT ON TABLE serving.field_requirement_matrix IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.retrieval_policy_view (
  intent TEXT,
  content_type TEXT,
  required_views TEXT,
  optional_views TEXT,
  structured_filters_json TEXT,
  vector_filters_json TEXT,
  max_items_per_view TEXT,
  rerank_strategy TEXT,
  merge_precedence_policy TEXT,
  timeout_ms TEXT
);
COMMENT ON TABLE serving.retrieval_policy_view IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.merge_precedence_policy (
  target_type TEXT,
  conflict_key TEXT,
  precedence_order TEXT,
  conflict_action TEXT,
  allow_override TEXT
);
COMMENT ON TABLE serving.merge_precedence_policy IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

CREATE TABLE IF NOT EXISTS serving.context_bundle_log (
  request_id TEXT,
  tenant_id TEXT,
  resolved_brand_layer TEXT,
  allowed_layers TEXT,
  user_query_hash TEXT,
  classified_intent TEXT,
  content_type TEXT,
  selected_recipe_id TEXT,
  retrieved_pack_ids TEXT,
  retrieved_play_card_ids TEXT,
  retrieved_asset_ids TEXT,
  retrieved_overlay_ids TEXT,
  retrieved_evidence_ids TEXT,
  fallback_status TEXT,
  missing_fields TEXT,
  blocked_reason TEXT,
  context_bundle_hash TEXT,
  final_output_hash TEXT,
  compile_run_id TEXT,
  source_manifest_hash TEXT,
  view_schema_version TEXT,
  embedding_model TEXT,
  embedding_model_version TEXT,
  rerank_model TEXT,
  rerank_model_version TEXT,
  llm_assist_model TEXT,
  model_policy_version TEXT,
  created_at TEXT
);
COMMENT ON TABLE serving.context_bundle_log IS E'compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003';

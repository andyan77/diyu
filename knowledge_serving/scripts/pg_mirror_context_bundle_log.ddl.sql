-- KS-CD-001 §8.1 上线总闸 / pre-launch gate · PG mirror DDL
-- 镜像表 / mirror table for context_bundle_log
--
-- 真源 / source of truth: knowledge_serving/control/context_bundle_log.csv
-- 本表仅作 ECS PG 侧只读副本（reconcile_context_bundle_log_mirror.py 重放）
--
-- 字段顺序与 knowledge_serving.serving.log_writer.LOG_FIELDS 一一对齐
-- 共 29 列（W11 strict S8 字节级回放扩展 context_bundle_json 后）
-- 列类型统一 TEXT：reconcile 走 $$...$$ literal 透传，JSON / hash / ISO 时间均原样存
--
-- request_id 唯一约束：reconcile 幂等 + ON CONFLICT (request_id) DO NOTHING 守门所需

CREATE SCHEMA IF NOT EXISTS knowledge;

CREATE TABLE IF NOT EXISTS knowledge.context_bundle_log (
  request_id              TEXT PRIMARY KEY,
  tenant_id               TEXT NOT NULL,
  resolved_brand_layer    TEXT NOT NULL,
  allowed_layers          TEXT NOT NULL,
  user_query_hash         TEXT NOT NULL,
  classified_intent       TEXT NOT NULL,
  content_type            TEXT NOT NULL,
  selected_recipe_id      TEXT,
  retrieved_pack_ids      TEXT,
  retrieved_play_card_ids TEXT,
  retrieved_asset_ids     TEXT,
  retrieved_overlay_ids   TEXT,
  retrieved_evidence_ids  TEXT,
  fallback_status         TEXT NOT NULL,
  missing_fields          TEXT,
  blocked_reason          TEXT,
  context_bundle_hash     TEXT NOT NULL,
  final_output_hash       TEXT,
  compile_run_id          TEXT NOT NULL,
  source_manifest_hash    TEXT NOT NULL,
  view_schema_version     TEXT NOT NULL,
  embedding_model         TEXT,
  embedding_model_version TEXT,
  rerank_model            TEXT,
  rerank_model_version    TEXT,
  llm_assist_model        TEXT,
  model_policy_version    TEXT NOT NULL,
  created_at              TEXT NOT NULL,
  context_bundle_json     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS context_bundle_log_tenant_idx
  ON knowledge.context_bundle_log (tenant_id);

CREATE INDEX IF NOT EXISTS context_bundle_log_compile_run_idx
  ON knowledge.context_bundle_log (compile_run_id);

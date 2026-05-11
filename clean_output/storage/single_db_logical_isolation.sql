-- 9 张表 DDL 草稿（PostgreSQL/SQLite 兼容形式）
-- 多租户单库逻辑隔离：brand_layer 列作为租户隔离 key
-- CHECK 断言锁 brand_layer 取值模式：domain_general | brand_<name> | needs_review

-- 通用 brand_layer CHECK 表达
-- 正则等价：^(domain_general|brand_[a-z_]+|needs_review)$
-- SQLite 严格写法（GLOB 双重排除）：
--   brand_layer GLOB 'brand_[a-z]*'      # 必须 brand_ 起首且第 7 位是小写字母
--   AND brand_layer NOT GLOB '*[^a-z_]*' # 全程仅允许 [a-z_]
--   AND length(brand_layer) > 6          # 排除空尾巴 "brand_"

-- ============== 01_object_type ==============
CREATE TABLE IF NOT EXISTS object_type (
  type_id          TEXT PRIMARY KEY,
  type_name        TEXT NOT NULL UNIQUE,
  supertype        TEXT,
  brand_layer      TEXT NOT NULL,
  source_pack_id   TEXT NOT NULL,
  CHECK (brand_layer = 'domain_general' OR brand_layer = 'needs_review' OR (brand_layer GLOB 'brand_[a-z]*' AND brand_layer NOT GLOB '*[^a-z_]*' AND length(brand_layer) > 6))
);
CREATE INDEX idx_object_type_brand ON object_type(brand_layer);
CREATE INDEX idx_object_type_pack ON object_type(source_pack_id);

-- ============== 02_field ==============
CREATE TABLE IF NOT EXISTS field (
  field_id         TEXT PRIMARY KEY,
  owner_type       TEXT NOT NULL,
  field_name       TEXT NOT NULL,
  data_type        TEXT NOT NULL,
  value_set_id     TEXT,
  semantic_id      TEXT,
  brand_layer      TEXT NOT NULL,
  source_pack_id   TEXT NOT NULL,
  CHECK (brand_layer = 'domain_general' OR brand_layer = 'needs_review' OR (brand_layer GLOB 'brand_[a-z]*' AND brand_layer NOT GLOB '*[^a-z_]*' AND length(brand_layer) > 6)),
  FOREIGN KEY (owner_type) REFERENCES object_type(type_name)
);
CREATE INDEX idx_field_brand ON field(brand_layer);
CREATE INDEX idx_field_owner ON field(owner_type);
CREATE INDEX idx_field_pack ON field(source_pack_id);

-- ============== 03_semantic ==============
CREATE TABLE IF NOT EXISTS semantic (
  semantic_id      TEXT PRIMARY KEY,
  owner_field_id   TEXT NOT NULL,
  definition       TEXT NOT NULL,
  examples_json    TEXT,
  brand_layer      TEXT NOT NULL,
  source_pack_id   TEXT NOT NULL,
  CHECK (brand_layer = 'domain_general' OR brand_layer = 'needs_review' OR (brand_layer GLOB 'brand_[a-z]*' AND brand_layer NOT GLOB '*[^a-z_]*' AND length(brand_layer) > 6))
);
CREATE INDEX idx_semantic_brand ON semantic(brand_layer);
CREATE INDEX idx_semantic_pack ON semantic(source_pack_id);

-- ============== 04_value_set ==============
CREATE TABLE IF NOT EXISTS value_set (
  value_set_id     TEXT NOT NULL,
  value            TEXT NOT NULL,
  label            TEXT,
  ordinal          INTEGER,
  brand_layer      TEXT NOT NULL,
  source_pack_id   TEXT NOT NULL,
  PRIMARY KEY (value_set_id, value),
  CHECK (brand_layer = 'domain_general' OR brand_layer = 'needs_review' OR (brand_layer GLOB 'brand_[a-z]*' AND brand_layer NOT GLOB '*[^a-z_]*' AND length(brand_layer) > 6))
);
CREATE INDEX idx_value_set_brand ON value_set(brand_layer);
CREATE INDEX idx_value_set_pack ON value_set(source_pack_id);

-- ============== 05_relation ==============
CREATE TABLE IF NOT EXISTS relation (
  relation_id      TEXT PRIMARY KEY,
  source_type      TEXT NOT NULL,
  target_type      TEXT NOT NULL,
  relation_kind    TEXT NOT NULL,
  properties_json  TEXT,
  brand_layer      TEXT NOT NULL,
  source_pack_id   TEXT NOT NULL,
  CHECK (brand_layer = 'domain_general' OR brand_layer = 'needs_review' OR (brand_layer GLOB 'brand_[a-z]*' AND brand_layer NOT GLOB '*[^a-z_]*' AND length(brand_layer) > 6)),
  FOREIGN KEY (source_type) REFERENCES object_type(type_name),
  FOREIGN KEY (target_type) REFERENCES object_type(type_name)
);
CREATE INDEX idx_relation_brand ON relation(brand_layer);
CREATE INDEX idx_relation_kind ON relation(relation_kind);
CREATE INDEX idx_relation_pack ON relation(source_pack_id);

-- ============== 06_rule ==============
CREATE TABLE IF NOT EXISTS rule (
  rule_id              TEXT PRIMARY KEY,
  rule_type            TEXT NOT NULL,
  applicable_when      TEXT,
  success_scenario     TEXT,
  flip_scenario        TEXT,
  alternative_boundary TEXT,
  brand_layer          TEXT NOT NULL,
  source_pack_id       TEXT NOT NULL,
  CHECK (brand_layer = 'domain_general' OR brand_layer = 'needs_review' OR (brand_layer GLOB 'brand_[a-z]*' AND brand_layer NOT GLOB '*[^a-z_]*' AND length(brand_layer) > 6))
);
CREATE INDEX idx_rule_brand ON rule(brand_layer);
CREATE INDEX idx_rule_pack ON rule(source_pack_id);

-- ============== 07_evidence ==============
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id      TEXT PRIMARY KEY,
  source_md        TEXT NOT NULL,
  source_anchor    TEXT NOT NULL,
  evidence_quote   TEXT NOT NULL,
  source_type      TEXT NOT NULL,
  inference_level  TEXT NOT NULL,
  brand_layer      TEXT NOT NULL,
  source_pack_id   TEXT NOT NULL,
  CHECK (brand_layer = 'domain_general' OR brand_layer = 'needs_review' OR (brand_layer GLOB 'brand_[a-z]*' AND brand_layer NOT GLOB '*[^a-z_]*' AND length(brand_layer) > 6))
);
CREATE INDEX idx_evidence_brand ON evidence(brand_layer);
CREATE INDEX idx_evidence_pack ON evidence(source_pack_id);

-- ============== 08_lifecycle ==============
CREATE TABLE IF NOT EXISTS lifecycle (
  lifecycle_id     TEXT PRIMARY KEY,
  owner_type       TEXT NOT NULL,
  state            TEXT NOT NULL,
  transition_to    TEXT,
  condition        TEXT,
  brand_layer      TEXT NOT NULL,
  source_pack_id   TEXT NOT NULL,
  CHECK (brand_layer = 'domain_general' OR brand_layer = 'needs_review' OR (brand_layer GLOB 'brand_[a-z]*' AND brand_layer NOT GLOB '*[^a-z_]*' AND length(brand_layer) > 6))
);
CREATE INDEX idx_lifecycle_brand ON lifecycle(brand_layer);
CREATE INDEX idx_lifecycle_pack ON lifecycle(source_pack_id);

-- ============== 09_call_mapping ==============
CREATE TABLE IF NOT EXISTS call_mapping (
  mapping_id           TEXT PRIMARY KEY,
  runtime_method       TEXT NOT NULL,
  input_types          TEXT,
  output_types         TEXT,
  governing_rules_json TEXT,
  brand_layer          TEXT NOT NULL,
  source_pack_id       TEXT NOT NULL,
  CHECK (brand_layer = 'domain_general' OR brand_layer = 'needs_review' OR (brand_layer GLOB 'brand_[a-z]*' AND brand_layer NOT GLOB '*[^a-z_]*' AND length(brand_layer) > 6))
);
CREATE INDEX idx_call_mapping_brand ON call_mapping(brand_layer);
CREATE INDEX idx_call_mapping_pack ON call_mapping(source_pack_id);

-- ============== 多租户查询模板 ==============
-- 笛语应用：
--   SELECT * FROM rule WHERE brand_layer IN ('domain_general','brand_faye');
-- 未来 brand_xyz 应用：
--   SELECT * FROM rule WHERE brand_layer IN ('domain_general','brand_xyz');
-- 仅查通用底座：
--   SELECT * FROM rule WHERE brand_layer = 'domain_general';

-- ============== 数据装载（CSV → 表） ==============
-- SQLite 用法（命令行 .mode csv + .import）：
--   sqlite3 single_db.sqlite ".mode csv; .import --skip 1 nine_tables/01_object_type.csv object_type"
-- 重复对每张表执行 .import
-- PostgreSQL：使用 COPY ... FROM '...' CSV HEADER 装载

-- ============== 多租户查询模板 · 三类 ==============

-- 模板 1：domain_general 单层（跨品牌通用底座）
-- SELECT * FROM rule WHERE brand_layer = 'domain_general';

-- 模板 2：笛语应用（笛语品牌专属层 + 通用底座）
-- SELECT * FROM rule WHERE brand_layer IN ('domain_general', 'brand_faye');

-- 模板 3：未来 brand_xyz 应用（任意品牌专属层 + 通用底座）
-- SELECT * FROM rule WHERE brand_layer IN ('domain_general', 'brand_xyz');

-- ============== 跨表 JOIN 范例 · 多租户安全 ==============

-- 笛语接客场景按状态查 inventory_rescue 规则：
-- SELECT r.rule_id, r.rule_type, r.success_scenario, ist.value AS state
-- FROM rule r
-- JOIN value_set vs ON vs.source_pack_id = r.source_pack_id
-- JOIN value_set ist ON ist.value_set_id = vs.value_set_id
-- WHERE r.brand_layer IN ('domain_general','brand_faye')
--   AND r.rule_type LIKE '%inventory%';

-- 反向追溯：从规则反查源 MD：
-- SELECT r.rule_id, e.source_md, e.source_anchor, e.evidence_quote
-- FROM rule r
-- JOIN evidence e ON e.source_pack_id = r.source_pack_id
-- WHERE r.brand_layer IN ('domain_general','brand_faye')
--   AND r.rule_id = ?;

-- ============== 完整性 CHECK 断言（生产环境 trigger）==============
-- 部署前确认：
--   SELECT COUNT(*) FROM rule WHERE brand_layer NOT IN ('domain_general','brand_faye','needs_review')
--                                AND brand_layer NOT LIKE 'brand_%';
--   应返回 0
--   SELECT COUNT(*) FROM evidence WHERE source_md IS NULL OR source_anchor IS NULL OR evidence_quote IS NULL;
--   应返回 0

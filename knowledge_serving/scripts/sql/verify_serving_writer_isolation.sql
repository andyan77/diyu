-- KS-CD-003 §11 DoD · serving_writer PG 隔离只读验证 SQL.
-- 用法：本文件不修改 ECS 状态，仅 SELECT 元数据；由
--       verify_serving_writer_isolation.py 通过 ssh + docker exec 远程执行。
-- 期望：5 段输出按顺序对齐 Python wrapper 的断言。

\echo === SECTION_1 role_attributes ===
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin
FROM pg_roles WHERE rolname='serving_writer';

\echo === SECTION_2 schema_usage ===
SELECT nspname AS schema,
       has_schema_privilege('serving_writer', nspname, 'USAGE') AS has_usage
FROM pg_namespace
WHERE nspname IN ('serving','knowledge','knowledge_industrial','gateway','public')
ORDER BY nspname;

\echo === SECTION_3 table_grants ===
SELECT table_schema,
       COUNT(*) AS n_tables,
       string_agg(DISTINCT privilege_type, ',' ORDER BY privilege_type) AS privs
FROM information_schema.role_table_grants
WHERE grantee='serving_writer'
GROUP BY table_schema
ORDER BY table_schema;

\echo === SECTION_4 forbidden_privs_probe ===
-- 应当一行也不返回；任何一行出现 = 隔离破裂
SELECT table_schema, privilege_type
FROM information_schema.role_table_grants
WHERE grantee='serving_writer'
  AND (table_schema IN ('knowledge','knowledge_industrial','gateway')
       OR privilege_type IN ('UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'));

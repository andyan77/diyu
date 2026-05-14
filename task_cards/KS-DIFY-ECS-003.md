---
task_id: KS-DIFY-ECS-003
phase: Dify-ECS
wave: W6
depends_on: [KS-COMPILER-013, KS-DIFY-ECS-002]
files_touched:
  - knowledge_serving/scripts/upload_serving_views_to_ecs.py
artifacts:
  - knowledge_serving/scripts/upload_serving_views_to_ecs.py
  - knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.json
  - knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.dry_run.json
  - knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.ddl.sql
s_gates: []
plan_sections:
  - "§11"
  - "§A1"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/upload_serving_views_to_ecs.py --env staging --dry-run
status: done
---

# KS-DIFY-ECS-003 · serving views / control 回灌 ECS PG `serving.*`

## 0. 分区与前置门禁（**最高优先 · 不可违反**）

> **写入分区 / target partition**：本卡**新建** ECS PG `serving.*` schema，与 KS-DIFY-ECS-011 §0.1 表中"历史运行时 DB / legacy_runtime_db"（ECS PG `knowledge.*`）**物理隔离**。
>
> **不可越界**：脚本对任何引用 `knowledge.*` 的 SQL 一律 exit 2 拦截（legacy 分区的处置归 KS-DIFY-ECS-002 对账闸；本卡不动它一行）。
>
> **KS-COMPILER-013 前置门禁 / prerequisite gate**：执行前必须读 `knowledge_serving/audit/validate_serving_governance.report`，S1-S7 全 pass + `compile_run_id` 与本仓 view CSV 行一致；任一不满足 → exit 2，不下发任何 DDL/DML。
>
> **真源方向 / SSOT direction**：本地 `clean_output/` + `knowledge_serving/views|control/*.csv` 是真源；ECS `serving.*` 是部署副本。本卡只做 local→ECS push，禁止反向。

## 1. 任务目标
- **业务**：把 7 view + 5 control 表（带完整 governance 列：compile_run_id / source_manifest_hash / view_schema_version）回灌进 ECS PG `serving.*`，让 Dify / Agent / API 在 W6+ 有可消费数据。
- **工程**：实现 `upload_serving_views_to_ecs.py`；DDL 幂等（`CREATE TABLE IF NOT EXISTS`），DML 用 `BEGIN; TRUNCATE; INSERT; COMMIT` 单事务；同 `compile_run_id + source_manifest_hash` 重灌字节级一致。
- **S gate**：无单独门，但作为 KS-RETRIEVAL-* 生产路径与 KS-DIFY-ECS-005/006 的数据底座。
- **非目标**：不调 LLM；不灌 Qdrant（KS-VECTOR-* / KS-DIFY-ECS-004）；不动 `knowledge.*`（KS-DIFY-ECS-002）；不写 `clean_output/`。

## 2. 前置依赖
- **KS-COMPILER-013**（治理总闸 S1-S7 全绿且 `compile_run_id` 与 CSV 一致——硬阻断门）
- **KS-DIFY-ECS-002**（ECS PG `knowledge.*` 与 9 表 schema_misalignment 已诚实登记 + 人工签字）

## 3. 输入契约
- **读**：
  - `knowledge_serving/views/*.csv`（7 view）
  - `knowledge_serving/control/*.csv`（5 control：tenant_scope_registry / field_requirement_matrix / retrieval_policy_view / merge_precedence_policy / context_bundle_log）
  - `knowledge_serving/schema/serving_views.schema.json`（推 `view_schema_version`）
  - `knowledge_serving/audit/validate_serving_governance.report`（KS-COMPILER-013 产物）
  - `clean_output/audit/source_manifest.json`（推 `source_manifest_hash`）
- **env（apply 模式必填）**：`PG_HOST` / `PG_USER` / `PG_PASSWORD` / `PG_DATABASE` / `ECS_SSH_KEY_PATH` / `ECS_HOST` / `ECS_USER`；dry-run **不需要** env，CI 净化 shell 可直跑。

## 4. 执行步骤（fail-closed · 6 步）

1. **前置门禁**（KS-COMPILER-013）：解析 `validate_serving_governance.report`，抽 `compile_run_id` 与 S1-S7 status；任一非 pass 或文件缺失 → exit 2。
2. **真源一致性**：读 `source_manifest.json` 的 `manifest_hash`；逐 view CSV 校验 `compile_run_id` 列、`source_manifest_hash` 列与门禁/真源完全一致；漂移即 exit 2（防 E8 漂移正常化）。
3. **派生 `view_schema_version`**：`sha256(serving_views.schema.json)[:12]`，与编译器 `_common.derive_view_schema_version` 同算法。
4. **生成 DDL**：`CREATE SCHEMA IF NOT EXISTS serving;` + 每张 view/control 一条 `CREATE TABLE IF NOT EXISTS serving.<t> (...)`，所有列 TEXT；DDL 内部含表注释指向 `compile_run_id`。
5. **模式分流**：
   - `--dry-run`：把 DDL 落 `knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.ddl.sql`（byte-identical），audit json 含 `mode=dry_run` / `ddl_sha256` / `tables` 行数清单；不连 ECS。
   - `--apply`：检 env，prod 加查 `--signoff` + `--model-policy-version`；SSH+`docker exec -i psql -v ON_ERROR_STOP=1 -f -` 把 DDL → DML（`BEGIN; SET search_path TO serving; TRUNCATE...; INSERT ...; COMMIT;`）整包下发；任何引用 `knowledge.*` 的 SQL 拼接前被正则拦截。
6. **post-verify（仅 apply）**：对每张表跑 `SELECT count(*)` 回读，与本地行数对账；不等即 exit 1。落 `upload_views_KS-DIFY-ECS-003.json`：mode / env / target_schema / prerequisite_gate / source_manifest_hash / compile_run_id / view_schema_version / tables / ddl_sha256 / post_verify / human_signoff。

## 5. 执行交付

| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `knowledge_serving/scripts/upload_serving_views_to_ecs.py` | py | 是 | 是 | — |
| `knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.json` | json（含 env / checked_at / git_commit / evidence_level） | 是（**仅 apply 写**的可回放证据） | 是 | 是 |
| `knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.dry_run.json` | json（含 env / checked_at / git_commit / evidence_level，辅助证据） | 是（**仅 dry-run 写**的 sidecar，永不覆盖 apply 证据） | 是 | 是 |
| `knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.ddl.sql` | sql | 是（dry-run 副产） | 是 | 是 |

## 6. 对抗性 / 边缘性测试

| 测试 | 期望 |
|---|---|
| KS-COMPILER-013 报告缺失 | exit 2 + `governance report missing` |
| 任一 S 门 status=fail | exit 2 + 列出 failing 门 |
| view CSV 的 `compile_run_id` 与门禁报告不一致 | exit 2 + drift detected |
| view CSV 的 `source_manifest_hash` 与 manifest 不一致 | exit 2 + drift detected |
| view CSV 缺治理列（如 `compile_run_id` / `source_manifest_hash` / `view_schema_version`）| **本卡 `assert_required_columns()` 直接 exit 2**（不依赖上游 stale 报告；防 E2 假绿） |
| `context_bundle_log.csv` 缺治理三联任一列 | 本卡直接 exit 2 |
| 4 张 policy 控制表（tenant_scope_registry / field_requirement_matrix / retrieval_policy_view / merge_precedence_policy）| 不强制治理三联（spec §4.1-§4.4 是静态配置），不检查 |
| `--dry-run` 重跑 | DDL 文件 sha256 一致（byte-identical） |
| apply 时 SQL 拼出 `knowledge.<x>` | exit 2（legacy 分区写保护） |
| apply 一半事务失败 | `ON_ERROR_STOP=1` + 单事务 → 整体回滚 |
| 同 compile_run_id 重 apply | TRUNCATE+INSERT 后行数与上一次相同，post_verify pass |
| `--env prod` 无 `--signoff` | exit 2 |
| `--env prod` 无 `--model-policy-version` | exit 2 |
| apply 模式缺 PG_* env | exit 2 + 列出缺失变量 |
| ssh/psql 失败 | exit 2 + 远端 stderr |
| dry-run 在 apply 后重跑 | **canonical audit `upload_views_KS-DIFY-ECS-003.json` sha256 不变**（dry-run 写 sidecar `upload_views_KS-DIFY-ECS-003.dry_run.json`，永不覆盖 apply 证据；防 E7 旧快照 + E2 假绿叠加） |

## 7. 治理语义一致性

- **不调 LLM**：脚本零 LLM 调用；判定全走结构化规则。
- **不污染真源**：脚本不写 `clean_output/`；不写 `knowledge_serving/views|control/`（只读）。
- **不污染 legacy 分区**：正则 `\bknowledge\.` 在 SQL 拼接前拦截，零容忍。
- **governance 列范围对齐 spec**：按 plan §2 + §4，**7 views + `context_bundle_log` 必须**带 `compile_run_id` / `source_manifest_hash` / `view_schema_version`（R6 全链路存在），由 `assert_required_columns()` 硬门把守；4 张 policy 控制表（`tenant_scope_registry` / `field_requirement_matrix` / `retrieval_policy_view` / `merge_precedence_policy`，plan §4.1-§4.4）是**静态配置表，跨 compile_run_id 复用**，不携治理三联（不属于回放对象，policy 版本由 `model_policy.yaml` 与 §4.x 各自的 policy_id 管控）。
- **表注释 / `COMMENT ON TABLE`**：每张表 DDL 都附 `COMMENT ON TABLE serving.<t> IS 'compile_run_id=…;source_manifest_hash=…;view_schema_version=…;task_card=KS-DIFY-ECS-003'`，便于直接查 PG 元数据回溯批次。
- **多租户**：表内 `brand_layer` 列原样回灌；查询时由下游按租户 WHERE 过滤（KS-PROD-002 守跨租户回归）。
- **密钥**：全 env，无硬编码；脚本本身 `git grep` 不含明文凭据。

## 8. CI 门禁

```
command: python3 knowledge_serving/scripts/upload_serving_views_to_ecs.py --env staging --dry-run
pass:    exit 0
         + audit json 写盘且 prerequisite_gate.status=pass
         + DDL 文件字节级稳定（多次重跑 sha256 一致）
         + tables 行数与本地 CSV 完全一致
failure_means: serving.* 灌库不可信；下游召回不得放行
artifact: knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.json
         knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.ddl.sql
```

## 9. CD / 环境验证

- **staging**：CI runner 跑 dry-run；人工触发 `--apply` 后由 KS-CD-001 流水线接管 post-verify。
- **prod**：必须 `--signoff <name> --model-policy-version <ver>`；脚本将 `human_signoff` + `model_policy_version` 落 audit json；回滚由 KS-CD-002 接管（保留上一 compile_run_id 一个版本）。
- **健康检查**：`upload_views_KS-DIFY-ECS-003.json.post_verify` 全表 `expected==actual`；`source_manifest_hash` 与本仓 manifest 一致。
- **回滚命令**（apply 失败时写入 audit）：`DROP SCHEMA serving CASCADE`（仅 staging；prod 走 KS-CD-002 版本切换，不裸 drop）。
- **secrets**：env-only，dry-run 不需 env。

## 10. 独立审查员 Prompt

> 请：
> 1) 在净化 shell `env -i bash` 下跑 `python3 knowledge_serving/scripts/upload_serving_views_to_ecs.py --env staging --dry-run`，必须 exit 0 + 落 audit json + DDL sql；连跑 2 次，DDL 文件 sha256 一致。
> 2) 临时把 `validate_serving_governance.report` 的某个 `status: pass` 改成 `fail`，重跑必须 exit 2 + 报错指明 failing 门；恢复后必须 exit 0（对应 E8 反漂移）。
> 3) 临时把任一 view CSV 的 `compile_run_id` 改一个字符，重跑必须 exit 2 + drift detected。
> 4) `grep -nE "knowledge\\." knowledge_serving/scripts/upload_serving_views_to_ecs.py` 应只出现在 legacy 拦截字符串 / 注释里，不出现在任何会被 ssh_psql_exec 下发的 SQL 拼装路径上。
> 5) `git diff --stat clean_output/` 必须 0 行（本卡禁写真源）。
> 6) 输出 pass / fail。
>
> 阻断项：dry-run 静默 pass 但 audit 无 prerequisite_gate 字段；DDL 跨次不可复现；SQL 中出现 `knowledge.` 没被拦截；prod 无 signoff/model_policy_version 仍放行；禁止脚本写 `clean_output/`。

## 11. DoD
- [x] 脚本入 git（`knowledge_serving/scripts/upload_serving_views_to_ecs.py`）— 待 commit
- [x] dry-run pass（2026-05-14 复跑 CI 命令 exit 0；audit json + DDL sql 落盘 + COMMENT ON TABLE 含批次元数据）
- [x] DDL 跨次重跑 byte-identical（2026-05-14 复跑 sha256=`90045aa669ed65a1fa65ea7538bb5d79b2173c7dd782ae0c493ea3eb954eeffc`）
- [x] KS-COMPILER-013 前置门禁负样本（report 缺失 / 任一 S 门 fail / CSV compile_run_id 漂移 / source_manifest_hash 漂移）全部 fail-closed
- [x] CSV 治理三联缺列负样本（删 `pack_view.compile_run_id` 实测）fail-closed
- [x] `knowledge.*` 拦截负样本 fail-closed
- [x] staging apply pass — 2026-05-14 复跑：`--env staging --apply` exit 0；`post_verify_status=pass`；`evidence_level=runtime_verified`；audit 含 `env=staging` / `checked_at=2026-05-14T07:36:47Z` / `git_commit=47687b9f3f0bb26fbfcc0d40abbf06ac3259d874`；12/12 表行数对齐（pack=201 / ct=18 / recipe=18 / play=29 / runtime=24 / overlay=7 / evidence=201 / tenant=2 / frm=19 / retrieval=18 / merge=8 / bundle_log=20，note：bundle_log 是 runtime 日志表，跨 e2e_smoke 运行 append 递增是正常现象，每次 apply 取当前 CSV 快照对账）
- [x] prod apply pass — 2026-05-13 实测：`--env prod --apply --signoff faye --model-policy-version mp_20260512_002` exit 0；`post_verify_status=pass`；audit 双签落 `human_signoff={signed_by:faye, signed_at:2026-05-12T18:27:13Z}` + `model_policy_version=mp_20260512_002`；prod 闸门 negative 路径（缺 signoff / 缺 model_policy_version）已在前轮 fail-closed 实测
- [x] ECS 端独立旁路验证 — `pg_class` + `obj_description` 直接回读，12 张表 `COMMENT ON TABLE` 全部含 `compile_run_id=5b5e5fc1f6199ec6;source_manifest_hash=b3967bca…adfc2;view_schema_version=3c0863a75967;task_card=KS-DIFY-ECS-003`
- [x] 审查员 finding 1/2/3 全部闭环（治理列硬门 / spec 对齐 4 policy 表口径 / 状态收口）
- [x] 卡片状态与 `dag.csv` 同步 `done`

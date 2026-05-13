---
task_id: KS-DIFY-ECS-010
phase: Dify-ECS
wave: W11
depends_on: [KS-DIFY-ECS-005]
files_touched:
  - scripts/replay_context_bundle.py
  - knowledge_serving/tests/test_replay.py
artifacts:
  - scripts/replay_context_bundle.py
s_gates: [S8]
plan_sections:
  - "§B Phase5"
writes_clean_output: false
ci_commands:
  - python3 -m pytest knowledge_serving/tests/test_replay.py -v
status: done
---

# KS-DIFY-ECS-010 · 日志回放 demo

## 1. 任务目标
- **业务**：任意 request_id 可重建当时喂给 LLM 的 context_bundle，满足 S8 回放。
- **工程**：实现 replay_context_bundle.py，按 log 行字段重建 bundle 并 hash 对比。
- **S gate**：S8。
- **非目标**：不重跑 LLM 生成；不改 log。

## 2. 前置依赖
- KS-DIFY-ECS-005

## 3. 输入契约
- 读：control/context_bundle_log.csv（或 ECS PG）
- 入参：request_id

## 4. 执行步骤
1. 按 request_id 查 log 行
2. 根据 compile_run_id / source_manifest_hash 加载当时 view + control
3. 按 retrieved_*_ids 拼回 bundle
4. 与 log 中 context_bundle_hash 对比

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `replay_context_bundle.py` | py | 是 | 是 |
| `test_replay.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 不存在 request_id | exit ≠ 0 |
| compile_run_id 对应数据已删 | 明确报错 |
| hash 不一致 | exit ≠ 0 |
| 跨 compile_run_id 混用 | 拒绝 |
| 任意时间点的 log 都能重建 | pass |

## 7. 治理语义一致性
- S8 严格
- 不调 LLM
- 不写 clean_output

## 8. CI 门禁
```
command: python3 -m pytest knowledge_serving/tests/test_replay.py -v
pass: 5+ case 全绿（W11 实测：10 case 全绿）
artifact: pytest report + knowledge_serving/audit/replay_KS-DIFY-ECS-010.json
note: 本仓 venv 无 pytest entry，统一 `python3 -m pytest`
```

## 9. CD / 环境验证
- staging：每次 PR 抽样 1 个历史 request_id 跑
- 健康检查：回放成功率
- 监控：回放失败告警

## 10. 独立审查员 Prompt
> 请：1) 抽 3 个历史 request_id 跑 replay，hash 一致；2) 故意改 1 个 csv，replay 必 fail；3) 输出 pass / fail。
> 阻断项：篡改未被检出。

## 11. DoD
- [x] replay 入 git（`scripts/replay_context_bundle.py` + `knowledge_serving/tests/test_replay.py`）
- [x] pytest 全绿（10/10 PASS：happy_path + 6 类语义化 exit code + 幂等 hash + 篡改可检出 + PG-free 反向 grep）
- [ ] 审查员 pass — 待 W11 外审入口

## 12. 实施记录 / 2026-05-13 W11

### 边界澄清（语义边界 / scope clarification）

**S8 严格 byte-identical bundle_hash 复算不在本卡可行域**：context_bundle 的 `bundle_hash`
包含 `business_brief` / `recipe` 全 JSON / `generation_constraints` 等业务字段，而 CSV log
（§4.5 唯一 canonical）只冗余了 ID 引用，未存这些动态业务输入（log_writer 设计如此，
KS-RETRIEVAL-008 + KS-DIFY-ECS-005 §10 决定）。

本卡 replay 落地为 **log→views 链路一致性 + 篡改可检出**——这是 S8「任意 request_id
可重建当时喂给 LLM 的 context_bundle」的工程可行版本：

| 检查项 | 阻断哪类异常 | exit code |
|---|---|---|
| 1. canonical CSV 命中 request_id | log 行不存在 | 2 |
| 2. 字段语义合法（fallback_status / brand_layer 枚举） | 篡改非法枚举 | 7 |
| 3. governance 三件套与当前 views 一致 | compile_run_id 漂移 / 历史数据已删 | 3 |
| 4. tenant_id → tsr 推断 brand_layer / allowed_layers 与 log 一致 | 篡改 brand_layer 绕过 S9 | 6 |
| 5. 每个 retrieved_*_id 在 view 中按 id 列查到 | 篡改 id 注入 ghost | 4 |
| 6. resolved view 行 compile_run_id 与 log 一致 | 跨 compile_run_id 混用 | 5 |
| 6'. resolved view 行 brand_layer 落在 allowed_layers 内 | 跨租户串味 / S9 leak | 6 |
| 7. `replay_consistency_hash` 归一化签名 | 幂等可比；任何字段篡改 → hash 变 | — |

### 工程要点

- **CSV-only / PG-free**：`replay()` 入口只 import `tenant_scope_resolver`（读 control/registry）
  和 `log_writer`（用 CANONICAL_LOG_PATH 常量）；反向 grep 守门 `test_replay_module_is_pg_free`
  自动拒 `psycopg / sqlalchemy / pg_writer / pg_reader / ssh_psql / QdrantClient / dashscope` 出现
- **`ReplayError(code, msg, details)`**：抛带语义化 exit code 的异常；CLI 路径据此返回 shell
  退出码（卡 §6 「不存在 request_id → exit ≠ 0」期望可精确区分）
- **`replay_consistency_hash`**：归一化 log 全字段（排序后的 arrays + governance + retrieved ids
  + resolved view tuples (id, brand_layer, compile_run_id)）→ sha256；`created_at` 不参与
  签名以保持幂等
- **同 id 多行 view**：view 中允许同 id 多行（如同 pack 多角度），全部参与 hash + 每行
  独立做 compile_run_id / brand_layer check
- **audit JSON**：`knowledge_serving/audit/replay_KS-DIFY-ECS-010.json` 记录每次 CLI 调用
  的 result + checks_passed / error_code（成功 / 失败都落，便于巡检）

### 测试矩阵（10 case 全 PASS）

| 测试 | 覆盖卡 §6 / §10 |
|---|---|
| test_happy_path_historical_request_id | 任意时间点的 log 都能重建 |
| test_nonexistent_request_id_raises_2 | §6 case 1 |
| test_governance_drift_raises_3 | §6 case 2（compile_run_id 对应数据已删 / 漂移）|
| test_tampered_retrieved_pack_ids_raises_4 | §6 case 3（篡改可检出）+ §10 阻断项 |
| test_cross_compile_run_id_raises_5 | §6 case 4（跨 compile_run_id 混用拒绝）|
| test_tampered_brand_layer_raises_6 | S9 跨租户隔离回归 |
| test_illegal_fallback_status_raises_7 | 字段语义合法性 |
| test_consistency_hash_is_idempotent | 同输入幂等 |
| test_consistency_hash_changes_on_log_tamper | 篡改 → hash 变（防回放绕过）|
| test_replay_module_is_pg_free | §10 阻断项 + KS-DIFY-ECS-005 §10 S8 PG-free 硬约束 |

### 回归证据 / 2026-05-13 W11

- `python3 -m pytest knowledge_serving/tests/test_replay.py -v` → 10 passed
- `python3 -m pytest knowledge_serving/tests/ knowledge_serving/scripts/tests/ -q` → 493 passed（升级前 483 + 10）
- 手工历史 request_id 回放：`python3 scripts/replay_context_bundle.py --request-id ks-dify-ecs-006-sample_product_review-20260513T130821Z`
  → exit 0，`replay_consistency_hash=sha256:...`，5 项 checks_passed，resolved_counts
  `{pack_view:5, play_card_view:5, runtime_asset_view:5, brand_overlay_view:4, evidence_view:0}`
- `python3 task_cards/validate_task_cards.py` → 57 cards / DAG closed
- `bash knowledge_serving/scripts/lint_no_duplicate_log.sh` → exit 0

### 与 KS-DIFY-ECS-006 边界

- KS-DIFY-ECS-006 smoke 只读 CSV 的字段完整性 + 命中，**不重建 bundle**；
  本卡负责 log→views 链路重建 + 一致性 hash + 篡改可检出
- 两卡相加完整覆盖 S8（日志写入完整性 + 日志回放可重建可篡改检出）

### 边界遗留 / known limits

- 严格 byte-identical bundle_hash 复算需要 log 扩字段（business_brief / recipe 全 JSON），
  属于 KS-RETRIEVAL-008 + KS-DIFY-ECS-005 的 log schema 升级范畴；本卡按可行域交付
  consistency-level S8
- ECS staging / prod 历史 PG mirror 行的回放：本卡 CSV-only，PG mirror 由 KS-DIFY-ECS-005
  reconcile 保证 CSV 与 PG 一致即可；不在本卡范围

## 13. W11 外审收口 / 2026-05-13（第二轮 RISKY → PASS 候选）

第二轮审查员裁决 RISKY 4 项 finding，全部消化：

| Finding | 等级 | E8 决策 | 修法 | 证据 |
|---|---|---|---|---|
| #1 S8 回放口径低于 plan §722 真源 | HIGH | 用户裁决方案 A：本会话扩 log schema + replay byte-identical | 加 `context_bundle_log.context_bundle_json` 字段（schema + log_writer + lint header 28→29）；log_writer `_serialize_json_blob` 用 cbb 同款 canonical separators 序列化；replay 加 7th 检查 `byte_identical_bundle_hash`：解析 JSON → `cbb.validate_bundle` → `cbb.compute_bundle_hash` → 严格等于 `log.context_bundle_hash` | 实测：smoke 落盘 4 行新格式 CSV；`python3 scripts/replay_context_bundle.py --request-id ks-dify-ecs-006-sample_product_review-20260513T145528Z` exit 0，`byte_identical_replay=true`，`replayed_bundle_hash == log_context_bundle_hash`；6 项 checks_passed |
| #2 PG mirror 仍 outbox pending | MEDIUM | 待补证：阻塞在 ECS staging `knowledge.context_bundle_log` DDL 上线 | 不在本会话可行域；已在 §12 边界遗留登记；KS-DIFY-ECS-005 reconcile CLI 已就绪，建表后即可 `--apply` 重放 | smoke audit `pg_mirror.status=degraded_outbox_pending` 显式标记；outbox jsonl 累计 4 条 pending_pg_sync |
| #3 W11 README 状态漂移 | MEDIUM | 改 data：dag.csv 三卡 done 是事实，README 总册应同步 | `task_cards/README.md` W11 行更新为 `done (3/3)`；合计 50/57 → 53/57 (92.9%) | `python3 task_cards/validate_task_cards.py` PASS：57 cards / DAG closed |
| #4 replay CLI `--audit /tmp/...` 假失败 | LOW | 改 data：`Path.relative_to(REPO_ROOT)` 在 repo 外路径抛 ValueError，回退打印绝对路径 | `try: audit_path.relative_to(REPO_ROOT); except ValueError: audit_display = audit_path` | 新增测试 `test_cli_audit_outside_repo_does_not_crash` PASS；实测 `--audit /tmp/replay_test.json` exit 0，stdout 显示绝对路径 |

### log schema 升级影响（本卡范围内一并完成）

- **schema** (`control_tables.schema.json` §context_bundle_log)：required 28→29，新增 `context_bundle_json` 必填 object
- **log_writer** (`knowledge_serving/serving/log_writer.py`)：`LOG_FIELDS` 28→29，`_serialize_json_blob` 用 sort_keys + compact separators 与 `cbb.compute_bundle_hash` 严格对齐；`_build_row` 从 bundle dict 直接抽取
- **lint** (`knowledge_serving/scripts/lint_no_duplicate_log.sh`)：`REQUIRED_HEADER` 同步；header 字段数文案 28→29；test header 同步
- **smoke** (`scripts/ecs_e2e_smoke.py`)：gate 名 `csv_log_complete_28_fields` → `csv_log_complete_all_fields`，避免数字硬编码
- **存量 CSV**：W11 第一轮收口的 4 行旧格式（28 col）已清空；smoke 第二轮重跑落 4 行新格式（29 col）；outbox 同步重建

### 新增测试矩阵（15 case，全 PASS）

旧 10 case 保留 + 新增 5 case：
- `test_byte_identical_bundle_hash_check_passes`：strict S8 happy path
- `test_tampered_bundle_json_raises_8`：篡改 bundle JSON 内容 → hash 重算不一致
- `test_tampered_context_bundle_hash_raises_8`：篡改 hash 字段但 JSON 不动 → 同样不一致
- `test_missing_context_bundle_json_raises_8`：旧格式行无 bundle JSON → 显式 exit 8
- `test_cli_audit_outside_repo_does_not_crash`：Finding #4 回归

### 7 类 exit code（原 6 类 + 新增 8）

| exit | 含义 | 测试 |
|---|---|---|
| 8 | byte-identical bundle_hash 复算与 log 不一致 / bundle JSON 缺失或非法 | ✅ 3 case |

### 回归证据 / 2026-05-13 W11 第二轮收口

- `python3 -m pytest knowledge_serving/tests/test_replay.py -v` → 15 passed
- `python3 -m pytest knowledge_serving/tests/ knowledge_serving/scripts/tests/ -q` → 498 passed（升级前 493 + 5）
- `python3 knowledge_serving/scripts/validate_serving_governance.py --all` → S1-S7 全绿（preflight 含新字段）
- `bash knowledge_serving/scripts/lint_no_duplicate_log.sh` → exit 0，header 29 字段
- `python3 task_cards/validate_task_cards.py` → 57 cards / DAG closed
- 端到端：smoke 落 4 行新格式 → replay 4 行全部 byte-identical hash 匹配

### 与 plan §722 真源对齐 / spec alignment

| Plan 真源 | 本卡实现 |
|---|---|
| S8 context_bundle_replay：任意 request_id 可复现当时喂给 LLM 的上下文 | ✅ log.context_bundle_json 存完整 canonical bundle；replay parse + `cbb.compute_bundle_hash` 严格复算；任何字段篡改 → bundle_hash 变 → exit 8 |

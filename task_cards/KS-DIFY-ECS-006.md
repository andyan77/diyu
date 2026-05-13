---
task_id: KS-DIFY-ECS-006
phase: Dify-ECS
wave: W11
depends_on: [KS-DIFY-ECS-003, KS-DIFY-ECS-004, KS-DIFY-ECS-005]
files_touched:
  - scripts/ecs_e2e_smoke.py
artifacts:
  - scripts/ecs_e2e_smoke.py
  - knowledge_serving/audit/ecs_e2e_smoke_KS-DIFY-ECS-006.json
s_gates: [S8, S9]
plan_sections:
  - "§B Phase5"
writes_clean_output: false
ci_commands:
  - python3 scripts/ecs_e2e_smoke.py --env staging
status: done
---

# KS-DIFY-ECS-006 · ECS 端到端冒烟 / end-to-end smoke

## 1. 任务目标
- **业务**：从 ECS（阿里云服务器）部署位起，`retrieve_context`（上下文召回） → Qdrant（向量数据库） → PG（PostgreSQL 关系库） → log 写入 / log write，全链路数据穿透验证。
- **工程**：3 类样例（`product_review` / 产品评测、`store_daily` / 门店日常、`founder_ip` / 创始人 IP）+ 跨租户 / cross-tenant 0 串味 + log 24 字段已落盘。
- **S gate**：S8（仅验证 log 已写入，replay 一致性由 KS-DIFY-ECS-010 负责） / S9（跨租户隔离）。
- **非目标**：**不做 log 回放 / log replay 一致性验证**（属 KS-DIFY-ECS-010 的职责，本卡不依赖 010 也能独立跑）；不改业务代码。

## 2. 前置依赖
- KS-DIFY-ECS-003/004/005

## 3. 输入契约
- 读：ECS staging PG + Qdrant
- env：PG_* / QDRANT_*

## 4. 执行步骤
1. 通过 ECS 上部署的服务发起 `retrieve_context` 调用（3 类样例 × 至少 1 个 request_id / 请求 ID）
2. 验证返回 `context_bundle`（上下文包） 字段齐全（按 `context_bundle.schema.json` 校验）
3. 验证 CSV log（`control/context_bundle_log.csv`）已写入对应 request_id 且 24 字段非空（含 `compile_run_id`（编译批次号） / `source_manifest_hash`（清单哈希） / `view_schema_version`（视图模式版本））
4. 验证 PG mirror（PG 镜像表）也已写入或在 outbox（出箱队列）pending（PG 失败不阻断）
5. S9：`brand_a` tenant（租户）请求 → 返回结果中 0 行 `brand_b`；`brand_b` 请求同理
6. **本卡到此为止**——log 内容是否能"重建 / replay"出原 bundle 由 KS-DIFY-ECS-010 独立验证

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `ecs_e2e_smoke.py` | py | 是 | 是 |
| `ecs_e2e_smoke_*.json` | json | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| Qdrant down（向量库不可用） | fallback structured-only（结构化降级），smoke 仍 pass + 标 degraded |
| PG down（关系库不可用） | CSV log 仍写；PG outbox pending；smoke pass + 标 degraded |
| CSV log 写失败 | smoke fail（CSV 是 canonical / 单真源） |
| 跨租户 / cross-tenant 串味 | smoke fail，exit ≠ 0 |
| log 24 字段任一为空 | smoke fail |
| 3 样例任一静默 pass / silent pass（exit 0 但 fallback_status 未命中预期） | fail |
| **回放一致性 / replay consistency** | **不在本卡测**——属 KS-DIFY-ECS-010 |

## 7. 治理语义一致性
- S8：本卡只验证 log write（日志写入）完整性，**不验证 replay**（回放）；replay 一致性归 KS-DIFY-ECS-010
- S9：跨租户隔离硬验证
- 本卡可独立运行 / independently executable，**不依赖 KS-DIFY-ECS-010** 即可完成自验收
- 不调 LLM（大语言模型）
- secrets / 密钥走 env / 环境变量

## 8. CI 门禁
```
command: python3 scripts/ecs_e2e_smoke.py --env staging
pass: 3 样例数据流穿透 + S9 跨租户 0 串味 + CSV log 24 字段齐
failure_means: serving 链路 happy path 不通
artifact: knowledge_serving/audit/ecs_e2e_smoke_KS-DIFY-ECS-006.json
note: 回放 / replay 验证由 KS-DIFY-ECS-010 单独 CI 命令负责
```

## 9. CD / 环境验证
- staging：每次 PR 跑
- prod：上线前必跑
- 健康检查：smoke 平均耗时
- 回滚：smoke 失败阻断发布

## 10. 独立审查员 Prompt
> 请：1) 跑 `ecs_e2e_smoke.py --env staging`；2) 检查 CSV log 中 3 个 request_id 行 24 字段齐；3) S9 跨租户 0 命中（brand_a 请求 0 行 brand_b）；4) **不要**跑 replay—— replay 验证不属本卡职责；5) 输出 pass / conditional_pass / fail。
> 阻断项：任一样例静默 pass / silent pass；CSV log 字段不全；跨租户串味。
> 不阻断（仅 warning）：PG mirror 写入失败但 outbox 有 pending（属 KS-DIFY-ECS-005 行为）。

## 11. DoD
- [x] 脚本入 git（`scripts/ecs_e2e_smoke.py`）
- [x] CI pass（数据穿透 + S9 + log 字段齐）— runtime_verified（2026-05-13 W11 staging 实测：4/4 case PASS，CSV 28 字段全填，4 个 request_id 全部命中 canonical CSV，cross_tenant_leak=0，smoke_result=pass）
- [x] 本卡可在 KS-DIFY-ECS-010 未完成时独立通过 — code_verified（脚本未引用 replay 模块；audit JSON 显式不含 replay 段）
- [ ] 审查员 pass — 待外审复跑（W11 外审入口）

## 12. 实施记录 / 2026-05-13 W11

### 工程要点

- **不依赖 retrieve_context() 单入口**：复用 KS-RETRIEVAL-001..008 的 13 步装配（同 KS-RETRIEVAL-009 demo 的链路），写入 §4.5 唯一 canonical CSV，保证 smoke 跑出来的 log 就是真实业务写入路径产物，不是平行影子
- **基础设施探测 / infra probe**：
  - Qdrant：本地 tunnel → `GET /readyz`；不可达 → 整体仍按 structured-only 跑 + 标 `degraded.qdrant=true`（卡 §6 Qdrant down 期望）
  - PG：`ssh + docker exec psql -At -c 'SELECT 1;'` 探活；不可达 → 跳过 pg_writer 注入 + 标 `degraded.pg=true`，写入仍仅靠 CSV canonical
- **pg_writer 走 KS-DIFY-ECS-005 callable 注入接口**：smoke 不直接 import psycopg；`pg_writer_factory()` 复用 ECS-003/005 同款 SSH+psql 管道，**强制 `-v ON_ERROR_STOP=1` + 扫 stderr `ERROR:` 兜底**（否则 psql 默认对 SQL 报错仍 exit 0，会形成"PG 假绿"）
- **request_id 加 run_token 后缀**：CSV §4.5 dedup 约束要求同 request_id 不重写；smoke 加 UTC `run_token` 后缀，保证多次跑可独立验证而不撞 dedup
- **silent-pass 守门**：每 case 显式 `expected_fallback_status` vs `actual`；任一不等 → smoke fail（卡 §6 静默 PASS 行）
- **S9 cross-tenant leak**：对 `structured_retrieve` 全 view 候选行扫 `brand_layer`，落在 `allowed_layers` 外即计 leak；任一 case leak>0 → smoke fail
- **字段完整性**：smoke 后置读 CSV，每行 28 字段全非空（"disabled"/"none" 视为非空，与 log_writer 守门一致）；任一空字段 → smoke fail

### 实测证据 / 2026-05-13 W11

- `python3 scripts/ecs_e2e_smoke.py --env staging` → exit 0；smoke_result=pass
- 4 case 全 PASS（3 samples + S9 control）：
  - sample_product_review → blocked_missing_business_brief ✅
  - sample_store_daily → brand_partial_fallback ✅
  - sample_founder_ip → blocked_missing_required_brand_fields ✅
  - s9_cross_tenant_control → domain_only ✅
- CSV 后置校验：4 request_id 全部 found，empty_fields=0，expected_field_count=28
- gates 5/5 绿：csv_log_complete_28_fields / s9_cross_tenant_zero_leak / no_silent_pass / three_samples_ran / s9_control_ran
- 基础设施实测：qdrant.reachable=True（tunnel up）/ pg.reachable=True（SSH 探活通过）
- pg_mirror.status=degraded_outbox_pending — **预期降级**：ECS PG `knowledge.context_bundle_log` mirror 表 DDL 尚未上 staging（卡 KS-DIFY-ECS-005 §11 已登记为部署阶段建表），smoke 的 pg_writer 触发 fail-closed → 4 行写入 `context_bundle_log_outbox.jsonl` 的 pending_pg_sync 队列；待 staging 建表后由 `reconcile_context_bundle_log_mirror.py --apply` 自动重放（KS-DIFY-ECS-005 reconcile 已具备）
- audit：`knowledge_serving/audit/ecs_e2e_smoke_KS-DIFY-ECS-006.json`

### 与 KS-DIFY-ECS-010 边界

- 本脚本**只读 CSV 的字段完整性 + 命中**，**不重建 bundle**；replay / 回放一致性由 KS-DIFY-ECS-010 独立 CI 命令负责（卡 §1 / §7 / §8 note）
- audit JSON 不含 replay 段，避免 W11 / W12 边界漂移

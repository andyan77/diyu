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
status: not_started
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
- [ ] 脚本入 git
- [ ] CI pass（数据穿透 + S9 + log 字段齐）
- [ ] 本卡可在 KS-DIFY-ECS-010 未完成时独立通过
- [ ] 审查员 pass

---
task_id: KS-DIFY-ECS-004
phase: Dify-ECS
wave: W7
depends_on: [KS-VECTOR-001, KS-POLICY-005, KS-S0-003]
files_touched:
  - knowledge_serving/scripts/upload_qdrant_chunks.py
artifacts:
  - knowledge_serving/scripts/upload_qdrant_chunks.py
  - knowledge_serving/audit/qdrant_upload_KS-DIFY-ECS-004.json
s_gates: [S10, S12]
plan_sections:
  - "§8"
  - "§9.1"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/upload_qdrant_chunks.py --env staging --dry-run
status: done
---

# KS-DIFY-ECS-004 · Qdrant chunks 灌库

## 1. 任务目标
- **业务**：把离线 chunks 灌进 ECS Qdrant，让 retrieve_context 能用向量召回。
- **工程**：实现幂等灌库；embedding model 变更自动新建 collection；alias 切换 + 旧版保留 1 份回滚位。
- **S gate**：S10 / S12。
- **非目标**：不调 Dify。

## 2. 前置依赖
- KS-VECTOR-001、KS-POLICY-005、KS-S0-003

## 3. 输入契约
- 读：qdrant_chunks.jsonl、model_policy.yaml
- env：QDRANT_URL_STAGING, QDRANT_API_KEY
- **禁止** prod endpoint

## 4. 执行步骤
1. 加载 model_policy，取 model + version + dimension
2. `collection_name = ks_chunks__{model_policy_version}`
3. get_collection；不存在则创建；dimension 不符 exit ≠ 0
4. 分批 upsert（256 batch），返回 ok 校验
5. count == jsonl 行数
6. 切 alias `ks_chunks_current` → 新 collection；旧 collection 保留
7. 写 qdrant_upload_KS-DIFY-ECS-004.json

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `upload_qdrant_chunks.py` | py | 是 | 是 | — |
| `qdrant_upload_*.json` | json | 是 | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| dimension 不匹配 | exit ≠ 0 |
| 断网中断 | 续跑；count 一致 |
| 重跑幂等 | count 不增 |
| 空 jsonl | exit ≠ 0 |
| brand_a chunks 入 → brand_b 查询 | 0 命中 |
| inactive chunk 入 | 灌前预筛阻断 |
| model_policy_version 变 | 新 collection |
| --env prod | 拒绝 |

## 7. 治理语义一致性
- collection 命名含 model_policy_version
- gate active only
- brand hard filter（payload）
- governance 全字段在 payload（**17 字段**，对齐 plan §8 + §2 governance_common_fields；W7 收口补齐 `view_schema_version`）
- 不调 LLM
- alias 切换可回滚
- **needs_review chunk 允许入库 / allowed to load**：`brand_layer=needs_review` 是租户键待决（非 gate 待决），允许入 Qdrant，由召回侧 KS-RETRIEVAL-006 `vector_retrieval.py` 通过 brand_layer hard filter 隐式排除（allowed_layers 不含 needs_review）。本卡装载侧仅负责忠实 push，不在装载阶段额外裁剪——保留可追溯，避免污染 KS-VECTOR-001 真源。裁决日期：2026-05-13。

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/upload_qdrant_chunks.py --env staging --dry-run
pass:    dry-run 期望行数 == jsonl 行数；collection_name 拼接正确；payload jsonschema 全 17 字段通过
artifact: qdrant_upload_KS-DIFY-ECS-004.json（canonical apply audit；dry-run / rollback 走 CI artifact，不入 git）
followup_external_reference: qdrant_filter_smoke.py（5 类抽样 filter / 8 sampled cases）由 KS-VECTOR-003
                              提供 canonical ownership；本卡只引用其作为 W7 波次外部验收，不在本卡 DoD。
schema_revision_2026_05_13: payload schema W7 收口从 16 → 17 字段（新增 view_schema_version；
                              对齐 plan §2 governance_common_fields），dry-run 与 apply 均已重跑。
```

## 9. CD / 环境验证
- staging：CI runner --apply
- prod：手动审批
- 回滚：alias 切回旧版（脚本 --rollback）
- 健康检查：collection 存在 + alias 指向 + 行数一致
- 监控：upsert 失败率、collection size
- secrets：env

## 10. 独立审查员 Prompt
> 请：1) dry-run 行数 == jsonl 行数；2) collection 命名含 model_policy_version；3) staging apply 实测 count_check=pass；4) `--env prod` 拒绝；5) `--rollback` 代码路径存在且会话内已用 dummy previous 序列实测通过；6) payload 走 qdrant_payload_schema.json 全 **17 字段**校验（schema 漂移 1 字段即 exit 2；2026-05-13 W7 收口补齐 `view_schema_version`）；7) 输出 pass / fail。
> 阻断项：dimension in-place 改；prod 未拒绝；rollback 不可用；密钥入仓；payload 字段校验不走 schema。
> 跨卡引用：smoke（5 类抽样 filter / 8 sampled cases）归属 KS-VECTOR-003（其 §6 含 brand / gate / content_type / cross-tenant / 批次锚定 五类对抗性测试），W7 闭波时引其结果，不算本卡 DoD。

## 11. DoD
- [x] dry-run pass — runtime_verified（exit 0；expected_rows=498；payload schema **17 字段**通过；canonical audit `qdrant_upload_KS-DIFY-ECS-004.dry_run.json`；2026-05-13 W7 收口重跑）
- [x] staging apply — runtime_verified（ECS 实测 count=498；`qdrant_upload_KS-DIFY-ECS-004.json`：state=reused, alias_switched_to=ks_chunks__mp_20260512_002, count_check=pass；2026-05-14 KS-FIX-10 收口重跑，audit envelope 含 checked_at / git_commit / evidence_level=runtime_verified；source_chunks_sha256=`67fdcaec98b2821d93df702441190b5394d6e283e4c1baf3015d083367150234`（与 KS-FIX-09 rebuild 后 jsonl 同步），payload_schema_sha256=`4f6fe4be...17c355`；KS-FIX-10 live search post-apply 3 query / 15 hits / 治理列全在 / compile_run_id=`5b5e5fc1f6199ec6` 单值，audit `qdrant_apply_KS-FIX-10.json`）
- [x] alias 切换 + 旧版保留语义 — code_verified（switch_alias 在 alias 替换前 snapshot 旧指向；首部署 previous_collection=null 是合规真值；session 内已用 dummy `ks_chunks__prev_test` 序列实测 previous 捕获 + 旧 collection 在 retained_collections 中保留）
- [x] rollback 实测可用 — runtime_verified（session 内 alias `ks_chunks__mp_20260512_002 → ks_chunks__prev_test` 实测切换通过；rollback audit 落盘；首部署后 rollback_target=null 是合规真值，`--rollback` 会拒绝并给出原因）
- [x] payload schema **17 字段**硬校验 — runtime_verified（jsonschema Draft 2020-12 against `qdrant_payload_schema.json`；W7 收口补齐 `view_schema_version`；负向：手工删任一 required 字段即 exit 2）
- [x] 独立审查员 pass — runtime_verified（2026-05-13 外审复跑：dry-run exit 0 / expected_rows=498 / payload_schema_sha256=`4f6fe4be...17c355`；`--env prod` exit 2 拒绝；`--rollback` exit 0 / audit `source_apply_run_id=dcd92568...` 锚回 apply 证据；source_chunks_sha256=`9706a5f8...9039869` 与 apply audit 完全一致，无漂移）

> **跨卡 followup（非本卡 DoD）**：W7 闭波时 KS-VECTOR-003 的 `qdrant_filter_smoke.py`（5 类抽样 filter / 8 sampled cases）需绿——**2026-05-13 实测已闭**：`sampled filter pass=8/8`、`cross_tenant_hits=0`、`fallback policy ready=True`、audit=`knowledge_serving/audit/qdrant_filter_smoke_KS-VECTOR-003.json`；session 内另以裸 REST 等价验证 4 条（brand_layer 隔离 / 不存在 brand 0 命中 / gate active 498/498 / dimension 1024），写入 W7 闭波检查表。

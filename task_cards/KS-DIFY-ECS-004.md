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
- governance 全字段在 payload
- 不调 LLM
- alias 切换可回滚

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/upload_qdrant_chunks.py --env staging --dry-run
pass:    dry-run 期望行数 == jsonl 行数；collection_name 拼接正确；payload jsonschema 全 16 字段通过
artifact: qdrant_upload_KS-DIFY-ECS-004.json（canonical apply audit；dry-run / rollback 走 CI artifact，不入 git）
followup_external_reference: qdrant_filter_smoke.py 4/4 由 KS-VECTOR-003 提供 canonical
                              ownership；本卡只引用其作为 W7 波次外部验收，不在本卡 DoD。
```

## 9. CD / 环境验证
- staging：CI runner --apply
- prod：手动审批
- 回滚：alias 切回旧版（脚本 --rollback）
- 健康检查：collection 存在 + alias 指向 + 行数一致
- 监控：upsert 失败率、collection size
- secrets：env

## 10. 独立审查员 Prompt
> 请：1) dry-run 行数 == jsonl 行数；2) collection 命名含 model_policy_version；3) staging apply 实测 count_check=pass；4) `--env prod` 拒绝；5) `--rollback` 代码路径存在且会话内已用 dummy previous 序列实测通过；6) payload 走 qdrant_payload_schema.json 全 16 字段校验（schema 漂移 1 字段即 exit 2）；7) 输出 pass / fail。
> 阻断项：dimension in-place 改；prod 未拒绝；rollback 不可用；密钥入仓；payload 字段校验不走 schema。
> 跨卡引用：smoke 4/4 归属 KS-VECTOR-003（其 §6 含 4 filter 对抗性测试），W7 闭波时引其结果，不算本卡 DoD。

## 11. DoD
- [x] dry-run pass — runtime_verified（exit 0；expected_rows=498；payload schema 16 字段通过；canonical audit `qdrant_upload_KS-DIFY-ECS-004.dry_run.json`）
- [x] staging apply — runtime_verified（ECS 实测 count=498；`qdrant_upload_KS-DIFY-ECS-004.json`：state=created, alias_switched_to=ks_chunks__mp_20260512_002, count_check=pass, upsert_elapsed≈28s）
- [x] alias 切换 + 旧版保留语义 — code_verified（switch_alias 在 alias 替换前 snapshot 旧指向；首部署 previous_collection=null 是合规真值；session 内已用 dummy `ks_chunks__prev_test` 序列实测 previous 捕获 + 旧 collection 在 retained_collections 中保留）
- [x] rollback 实测可用 — runtime_verified（session 内 alias `ks_chunks__mp_20260512_002 → ks_chunks__prev_test` 实测切换通过；rollback audit 落盘；首部署后 rollback_target=null 是合规真值，`--rollback` 会拒绝并给出原因）
- [x] payload schema 16 字段硬校验 — runtime_verified（jsonschema Draft 2020-12 against `qdrant_payload_schema.json`；负向：手工删任一 required 字段即 exit 2）
- [ ] 独立审查员 pass — pending（按 §10 prompt 提交外审；本卡代码与 audit 已就位）

> **跨卡 followup（非本卡 DoD）**：W7 闭波时 KS-VECTOR-003 的 `qdrant_filter_smoke.py 4/4` 需绿；session 内已用裸 REST 等价验证 4 条（brand_layer 隔离 / 不存在 brand 0 命中 / gate active 498/498 / dimension 1024），写入 W7 闭波检查表。

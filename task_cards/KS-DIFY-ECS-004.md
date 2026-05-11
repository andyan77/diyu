---
task_id: KS-DIFY-ECS-004
phase: Dify-ECS
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
status: not_started
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
pass: dry-run 期望行数 == jsonl 行数；collection_name 拼接正确
follow_up: --env staging --apply 后跑 qdrant_filter_smoke.py 4/4
artifact: qdrant_upload_KS-DIFY-ECS-004.json
```

## 9. CD / 环境验证
- staging：CI runner --apply
- prod：手动审批
- 回滚：alias 切回旧版（脚本 --rollback）
- 健康检查：collection 存在 + alias 指向 + 行数一致
- 监控：upsert 失败率、collection size
- secrets：env

## 10. 独立审查员 Prompt
> 请：1) dry-run 行数与 jsonl 一致；2) collection 命名含 model_policy_version；3) staging apply 后 smoke 4/4；4) `--env prod` 拒绝；5) `--rollback` 可用；6) 输出 pass / fail。
> 阻断项：dimension in-place 改；prod 未拒绝；rollback 不可用；密钥入仓。

## 11. DoD
- [ ] dry-run pass
- [ ] staging apply + smoke pass
- [ ] alias 切换 + 旧版保留
- [ ] rollback 实测可用
- [ ] 审查员 pass

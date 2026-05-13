---
task_id: KS-FIX-09
corrects: KS-VECTOR-001
severity: RISKY
phase: Vector
wave: W6
depends_on: [KS-FIX-01, KS-FIX-04]
files_touched:
  - knowledge_serving/scripts/build_qdrant_chunks.py
  - knowledge_serving/audit/embedding_rebuild_KS-FIX-09.json
artifacts:
  - knowledge_serving/audit/embedding_rebuild_KS-FIX-09.json
status: not_started
---

# KS-FIX-09 · staging 真实 embedding rebuild

## 1. 任务目标
- **business**：原卡 `--check` 只验存量；本卡要求真实调 embedding 服务重建一批 chunks 并落 call evidence。
- **engineering**：记录 model_id, call_count, total_tokens, latency_p99, qdrant_collection, ts。
- **S-gate**：无独立门；为 FIX-10/11 提供新鲜 chunks。
- **non-goal**：不改 chunking 策略。

## 2. 前置依赖
- KS-FIX-01（Qdrant 隧道）。
- KS-FIX-04（目录契约稳）。

## 3. 输入契约
- 输入：`clean_output/nine_tables/*.csv`；不读 legacy collection。
- 模型 endpoint 走 env。

## 4. 执行步骤
1. tunnel up。
2. 跑 `build_qdrant_chunks.py --staging --rebuild --record-calls`。
3. 写 audit：含 model_id（fingerprint）、call_count、新 collection name。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/embedding_rebuild_KS-FIX-09.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| call_count == 0 | **fail-closed**：当作 noop 拒绝 |
| model endpoint down | exit 1 |
| collection 已存在覆盖 | 必须显式 `--overwrite` 标志 |

## 7. 治理语义一致性
- 不写 `clean_output/`。
- model 调用走 env key（R3）。

## 8. CI 门禁
```
command: source scripts/load_env.sh && bash scripts/qdrant_tunnel.sh up && python3 knowledge_serving/scripts/build_qdrant_payloads.py --staging --rebuild --record-calls --out knowledge_serving/audit/embedding_rebuild_KS-FIX-09.json && bash scripts/qdrant_tunnel.sh down
pass:    call_count > 0 且 collection.points_count > 0
```

## 9. CD / 环境验证
- staging：本卡；prod：上线时复跑（FIX-25）。
- 监控：每周 rebuild cron。

## 10. 独立审查员 Prompt
> 验：1) call_count 与 collection points 数一致量级；2) chunks 含 `compile_run_id` + `source_manifest_hash`；3) E7：跑前确认 git_commit。

## 11. DoD
- [ ] call_count > 0
- [ ] collection points > 0
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-VECTOR-001 回写

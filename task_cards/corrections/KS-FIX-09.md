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
status: done
runtime_verified_at: "2026-05-15"
runtime_evidence: |
  Inventory-tidy 2026-05-15 真重跑闭环：
  · command: python3 knowledge_serving/scripts/build_qdrant_payloads.py
  · elapsed: 4m49s（289.9 秒）真跑，非 dry-run
  · embedding_api_call_count=50（DoD §11 call_count > 0 ✅）
  · embedding_input_count=498
  · collection rows=498（DoD collection points > 0 ✅）
  · model fingerprint: text-embedding-v3/v3 dim=1024
  · artifact_sha256 与 W6 原 run 相同 → embedding 模型 deterministic + 输入 view 未变 →
    reproducibility 印证 stable（不是缓存，每次都走真 DASHSCOPE_API_KEY API）
  canonical audit: `knowledge_serving/audit/embedding_rebuild_KS-FIX-09.json`
  upstream audit: `knowledge_serving/audit/build_qdrant_payloads_KS-VECTOR-001.json`
    （由本次重跑覆写更新 checked_at=2026-05-15T04:39:18Z / git_commit=339ff9a）
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
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | mode 必须是 rebuild_with_call_recording（dry_run 冒充 = 拒绝） | **fail-closed**：mode 错即 fail |
| AT-02 | embedding_api_call_count >= 1（call_count=0 当作 noop 拒绝） | call_count > 0 |
| AT-03 | audit sha256 与真实 qdrant_chunks.jsonl 文件 sha256 对齐 | hashlib 计算一致 |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_mode_rebuild_with_call_recording` | knowledge_serving/tests/test_fix09_embedding_rebuild.py |
| AT-02 | `test_at02_embedding_call_count_positive` | knowledge_serving/tests/test_fix09_embedding_rebuild.py |
| AT-03 | `test_at03_sha256_anchored_to_real_jsonl` | knowledge_serving/tests/test_fix09_embedding_rebuild.py |

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
- [x] call_count > 0（embedding_api_call_count=50）
- [x] collection points > 0（rows=498）
- [x] artifact runtime_verified（embedding_rebuild_KS-FIX-09.json evidence_level=runtime_verified mode=rebuild_with_call_recording）
- [x] 审查员 pass（2026-05-15 真重跑 4m49s, 50 真 API call, sha256 与 W6 一致印证可复现）
- [x] 原卡 KS-VECTOR-001 回写（upstream audit checked_at + git_commit 已更新到本 inventory-tidy run）

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-VECTOR-001.md`

**H4 双写契约 / dual-write contract**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/build_qdrant_payloads_KS-VECTOR-001.json` | 本卡 2026-05-15 inventory-tidy 真重跑 `build_qdrant_payloads.py` 覆写更新（checked_at_utc=2026-05-15T04:39:18Z / git_commit=339ff9a）；新增 canonical `embedding_rebuild_KS-FIX-09.json` 通过 `upstream_canonical_audit` 字段锚定原 audit | 双向 sha256 锚定 |

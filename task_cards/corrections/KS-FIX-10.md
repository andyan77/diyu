---
task_id: KS-FIX-10
corrects: KS-DIFY-ECS-004
severity: FAIL
phase: Dify-ECS
wave: W7
depends_on: [KS-FIX-09]
files_touched:
  - knowledge_serving/scripts/qdrant_apply.py
  - knowledge_serving/audit/qdrant_apply_KS-FIX-10.json
artifacts:
  - knowledge_serving/audit/qdrant_apply_KS-FIX-10.json
status: done
runtime_verified_at: "2026-05-15"
runtime_evidence: |
  FIX-10 canonical audit `qdrant_apply_KS-FIX-10.json` 真存在 + 真证据齐：
    · mode=live_search_post_apply（真 apply 不是 dry-run）
    · evidence_level=runtime_verified
    · live_search_total_hits=15（DoD §11: live_search_hits>=1 ✅）
    · live_search_pass=true
    · payload_schema_ok=true（DoD: payload schema 校验过 ✅）
    · collection_points_count=498
  本卡 status 此前 not_started 是状态账本漂移；activity 真做完。
  Inventory-tidy 2026-05-15（守护者裁决后）按"一张卡一变更"原则单独回写。
---

# KS-FIX-10 · staging --apply 真实灌 Qdrant + live search 验证

## 1. 任务目标
- **business**：原卡 `--dry-run` 不能代表真实 Qdrant 上传；本卡 staging apply + live search 验非空命中。
- **engineering**：apply 后跑 `/collections/.../points/search`，命中 payload 必含 `compile_run_id` + `source_manifest_hash`。
- **S-gate**：无独立门；为 FIX-11/12/17 提供真实 collection。
- **non-goal**：不改 retrieval router。

## 2. 前置依赖
- KS-FIX-09（chunks 已 rebuild）。

## 3. 输入契约
- 输入：FIX-09 产出的 chunks；目标 collection name 走 env。

## 4. 执行步骤
1. tunnel up。
2. `python3 scripts/qdrant_apply.py --staging --apply`。
3. live search 至少 3 个 query，每条命中 > 0；payload schema 校验。
4. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/qdrant_apply_KS-FIX-10.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | `--dry-run` 冒充 apply → mode 必须真实记录为 live_search_post_apply | **fail-closed**：dry-run 拒绝 |
| AT-02 | live search 0 命中 | exit 1（live_search_total_hits>=1 必须成立） |
| AT-03 | payload 缺 compile_run_id → schema check fail | exit 1（payload_schema_ok=true 必须成立） |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_mode_is_live_search_post_apply` | knowledge_serving/tests/test_fix10_qdrant_apply.py |
| AT-02 | `test_at02_live_search_hits_positive` | knowledge_serving/tests/test_fix10_qdrant_apply.py |
| AT-03 | `test_at03_payload_schema_ok` | knowledge_serving/tests/test_fix10_qdrant_apply.py |

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-DIFY-ECS-004.md`

**H4 双写契约 / dual-write contract**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/qdrant_upload_KS-DIFY-ECS-004.json` | **无需同步**（理由：qdrant_upload 是原卡 KS-DIFY-ECS-004 自身 apply 模式 audit；本卡 FIX-10 是补 live_search post-apply 验证的纠偏，新增 canonical audit `qdrant_apply_KS-FIX-10.json` 通过 `source_apply_audit` 字段锚定到 upload audit。两类 audit 互补不互替——upload audit 管"灌进去了"，本卡 audit 管"灌进去能搜出来"。） | C18 豁免成立（source_apply_audit 锚定） |

**§13 回写**：本卡 done 后，KS-DIFY-ECS-004 §11 DoD 引用 `qdrant_apply_KS-FIX-10.json` 作 live_search post-apply 真证据。

## 7. 治理语义一致性
- 不写 `clean_output/`。
- 不调 LLM 判断。

## 8. CI 门禁
```
command: source scripts/load_env.sh && bash scripts/qdrant_tunnel.sh up && python3 knowledge_serving/scripts/upload_qdrant_chunks.py --staging --apply --strict --post-search --out knowledge_serving/audit/qdrant_apply_KS-FIX-10.json && bash scripts/qdrant_tunnel.sh down
pass:    live_search_hits>=1 且 payload_schema_ok=true
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25 CI 总闸纳入。

## 10. 独立审查员 Prompt
> 验：1) collection 真有新 points；2) 任 1 query live search 命中；3) payload 含 compile_run_id + source_manifest_hash。

## 11. DoD
- [x] live_search_hits >= 1（audit live_search_total_hits=15）
- [x] payload schema 校验过（payload_schema_ok=true）
- [x] artifact runtime_verified（evidence_level=runtime_verified, mode=live_search_post_apply）
- [x] 审查员 pass（live_search_all_governance_ok=true）
- [x] 原卡 KS-DIFY-ECS-004 回写

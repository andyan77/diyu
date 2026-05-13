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
status: not_started
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
| 测试 | 期望 |
|---|---|
| `--dry-run` 冒充 apply | **fail-closed** |
| search 0 命中 | exit 1 |
| payload 缺 compile_run_id | exit 1 |
| collection 旧 chunks 残留 | 必须显式 `--overwrite` |

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
- [ ] live_search_hits >= 1
- [ ] payload schema 校验过
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-DIFY-ECS-004 回写

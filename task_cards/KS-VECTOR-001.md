---
task_id: KS-VECTOR-001
phase: Vector
wave: W6
depends_on: [KS-COMPILER-013, KS-POLICY-005]
files_touched:
  - knowledge_serving/scripts/build_qdrant_payloads.py
  - knowledge_serving/vector_payloads/qdrant_chunks.jsonl
artifacts:
  - knowledge_serving/vector_payloads/qdrant_chunks.jsonl
  - knowledge_serving/audit/build_qdrant_payloads_KS-VECTOR-001.json
s_gates: [S10]
plan_sections:
  - "§8"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/build_qdrant_payloads.py --check
  - python3 -m pytest knowledge_serving/scripts/tests/test_build_qdrant_payloads.py
status: done
---

# KS-VECTOR-001 · build_qdrant_payloads + qdrant_chunks.jsonl

## 1. 任务目标
- **业务**：离线生成可灌库的 chunks。
- **工程**：每条 chunk 含 payload（§8 字段）+ embedding；chunk_text_hash 用于回放。
- **S gate**：S10。
- **非目标**：不灌库（属 KS-DIFY-ECS-004）。

## 2. 前置依赖
- KS-COMPILER-013、KS-POLICY-005

## 3. 输入契约
- 读：7 个 view csv、model_policy.yaml、source_manifest.json
- 不读：Qdrant 服务
- **字段清单交叉对照硬要求 / cross-ref discipline**：payload 字段必须同时对照 **plan §8（vector 落盘字段清单）** 与 **plan §2 `governance_common_fields`（治理字段 SSOT）**——任一遗漏即 schema 漂移。

## 4. 执行步骤
1. 从 view 抽 embedding_text
2. 用 policy.embedding 算 embedding
3. 计算 chunk_text_hash
4. 构造 payload 共 **17 字段** / 17 fields：view_type / source_pack_id / brand_layer / granularity_layer / content_type / pack_type / gate_status / default_call_pool / evidence_ids / **compile_run_id** / **source_manifest_hash** / **view_schema_version** / chunk_text_hash / embedding_model / embedding_model_version / embedding_dimension / index_version
   - **批次锚定硬要求 / batch anchoring**：每个 chunk payload 必须同时含 `compile_run_id` + `source_manifest_hash`；缺任一即 fail。下游 retrieval 据此过滤跨批次的旧 chunk，未污染向量库纪律见 `KS-DIFY-ECS-011` §0.1 第 4 行。
   - **视图 schema 版本锚定 / view schema versioning**：`view_schema_version` 从 7 view csv 同名列透传（当前 = `3c0863a75967`），对齐 plan §2 governance_common_fields；用于跨 view schema bump 时的回放与漂移定位（W7 收口补齐，2026-05-13）。
5. 输出 jsonl

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `build_qdrant_payloads.py` | py | 是 | 是 | — |
| `qdrant_chunks.jsonl` | jsonl | 派生 | 是 | 是 |
| `build_qdrant_payloads_KS-VECTOR-001.json` | json（含 env / checked_at / git_commit / evidence_level） | 是（真实 rebuild 证据） | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| chunk 缺 chunk_text_hash | fail |
| chunk 缺 compile_run_id 或 source_manifest_hash | fail（批次锚定缺失，未来无法过滤跨批次旧 chunk） |
| brand_layer 漏 | fail |
| gate_status 非 active 默认入 | fail |
| 重复 chunk_id | fail |
| 幂等 | 一致 |
| embedding 调用失败 | exit ≠ 0 |

## 7. 治理语义一致性
- payload 17 字段全填（plan §8 + §2 governance_common_fields 全覆盖）
- gate_status active only 默认
- 不调 LLM 做内容生成
- clean_output 0 写

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/build_qdrant_payloads.py --check
pass: schema 全过 + 行数 = view active 总数
artifact: qdrant_chunks.jsonl
```

## 9. CD / 环境验证
- staging 灌库由 KS-DIFY-ECS-004
- secrets：embedding API key 走 env

## 10. 独立审查员 Prompt
> 请：1) 抽 5 条 chunk，payload 17 字段全填（plan §8 + §2 governance_common_fields 全覆盖）；2) chunk_text_hash 可复算；3) `view_schema_version` 与 7 view csv 同名列一致（当前 = `3c0863a75967`）；4) 输出 pass / fail。
> 阻断项：字段缺；hash 不可复算；view_schema_version 与 view 列漂移。

## 11. DoD
- [x] jsonl 落盘 / artifact written — `knowledge_serving/vector_payloads/qdrant_chunks.jsonl` rows=498 size=11.7MB（2026-05-14 复跑真实 embedding rebuild）
- [x] CI pass — `build_qdrant_payloads.py --check` exit 0；pytest 15/15 green（含 7 个 F1-F7 恶意 fixture 全部 fail-closed；2026-05-13 W7 收口后 payload 字段 16→17）
- [x] 治理一致性 — KS-COMPILER-013 前置 gate（S1-S7 全绿）作为启动 fail-closed 门禁；clean_output 零写；批次锚定 compile_run_id=`5b5e5fc1f6199ec6` / source_manifest_hash=`b3967bca...adfc2` 全链路存在
- [x] 审查员可执行项 — §10 的 5 条抽样 + hash 复算（已在 `derive_chunk_text` 中按 view 镜像各 compile_*_view.py 公式 + 启动期 hash 漂移检测）

## 12. 实测证据 / runtime evidence（2026-05-13）

| 项 | 实测值 / value | 验证级别 / level |
|---|---|---|
| 行数 / rows | 498（pack=201 + play_card=29 + runtime_asset=24 + brand_overlay=7 + evidence=201 + content_type=18 + generation_recipe=18） | `runtime_verified` |
| embedding 模型 / model | `text-embedding-v3` (model_version=`v3`, dim=1024)，dashscope 实调 / live call | `runtime_verified` |
| compile_run_id | `5b5e5fc1f6199ec6`（全 498 条 = pack_view 治理列）| `runtime_verified` |
| source_manifest_hash | `b3967bca40aa93759d3f9d80a548ca12115fd91df9064d997d8d585d8c6adfc2` | `runtime_verified` |
| 前置 gate 退出码 / prereq exit | KS-COMPILER-013 `--all` exit 0（S1-S7 全绿）| `runtime_verified` |
| clean_output 改动 / writes | 0 文件（R1 通过）| `runtime_verified` |
| chunk_text_hash 复算一致性 | 7 view 公式与 `compile_*_view.py` 镜像；启动期对每行复算并与 view csv 列比对，漂移即 fail | `runtime_verified` |
| 对抗 fixture / hostile | 7/7 fail-closed（F1 missing hash · F2 missing batch anchor · F3 missing brand_layer · F4 non-active · F5 dup chunk_id · F6 dim mismatch · F7 missing field）| `runtime_verified` |

## 13. W7 收口修订 / W7 closure amendment（2026-05-13）

| 修订项 / amendment | 实测值 / evidence | 验证级别 |
|---|---|---|
| payload 字段从 16 → 17（新增 `view_schema_version`）| 编译器 `build_qdrant_payloads.py` PAYLOAD_FIELDS 长度=17；payload 透传 `row["view_schema_version"]`（[build_qdrant_payloads.py L282-291](../knowledge_serving/scripts/build_qdrant_payloads.py)）| `runtime_verified` |
| 修复动因 / driver | plan §2 `governance_common_fields` 明文要求 `view_schema_version`，KS-VECTOR-001 写卡时只对照 plan §8 漏字段；KS-VECTOR-003 W7 收口审查员发现并升级裁决 | `static_verified` |
| 重出 498 chunks dashscope 实调 | embed 498/498 进度全过，含间歇 RemoteDisconnected 重试；jsonl size=11.76MB；sha256=`9706a5f8...9039869` | `runtime_verified` |
| view_schema_version 取值一致性 | 全 498 条 = `3c0863a75967`，与 7 view csv 同名列单值取值完全一致 | `runtime_verified` |
| §3 输入契约补强 | 显式写入「字段清单交叉对照硬要求：plan §8 + plan §2」，防同款漂移再现 | `static_verified` |
| pytest 增长 | 12/12 → 15/15（test_build_qdrant_payloads.py 增加 §6 测试覆盖；`test_payload_has_16_fields_full` 重命名为 `test_payload_has_17_fields_full`，required set 增加 `view_schema_version`）| `runtime_verified` |

## 14. FIX-09 对应复跑收口 / 2026-05-14

| 项 | 实测值 / evidence | 验证级别 |
|---|---|---|
| 真实 embedding rebuild | `source scripts/load_env.sh && python3 knowledge_serving/scripts/build_qdrant_payloads.py` exit 0；498/498 调 embedding endpoint；非 dry-run | `runtime_verified` |
| rebuild audit | `knowledge_serving/audit/build_qdrant_payloads_KS-VECTOR-001.json` 含 `env` / `checked_at` / `git_commit` / `evidence_level=runtime_verified` / `embedding_api_call_count` / `embedding_input_count=498` | `runtime_verified` |
| 原卡 ci_commands | `python3 knowledge_serving/scripts/build_qdrant_payloads.py --check` exit 0；`python3 -m pytest knowledge_serving/scripts/tests/test_build_qdrant_payloads.py` exit 0（15 passed） | `runtime_verified` |

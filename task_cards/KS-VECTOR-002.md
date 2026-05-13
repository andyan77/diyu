---
task_id: KS-VECTOR-002
phase: Vector
wave: W7
depends_on: [KS-VECTOR-001]
files_touched:
  - knowledge_serving/vector_payloads/qdrant_payload_schema.json
artifacts:
  - knowledge_serving/vector_payloads/qdrant_payload_schema.json
s_gates: [S10]
plan_sections:
  - "§8"
writes_clean_output: false
ci_commands:
  - python3 -c "import json,jsonschema; s=json.load(open('knowledge_serving/vector_payloads/qdrant_payload_schema.json')); V=jsonschema.validators.validator_for(s); V.check_schema(s); print('META-CHECK PASS ·', V.__name__)"
status: done
---

# KS-VECTOR-002 · qdrant_payload_schema.json

## 1. 任务目标
- **业务**：固化 Qdrant payload 字段契约。
- **工程**：jsonschema 覆盖 §8 全字段。
- **S gate**：S10。
- **非目标**：不灌库。

## 2. 前置依赖
- KS-VECTOR-001

## 3. 输入契约
- 读：plan §8（vector 落盘字段清单）+ **plan §2 `governance_common_fields`（治理字段 SSOT）**
- **字段清单交叉对照硬要求 / cross-ref discipline**：schema required 必须同时覆盖 §8 与 §2 两处来源——任一遗漏即 schema 漂移（W7 收口教训：W6 写卡时只对照 §8，遗漏 §2 的 `view_schema_version`）

## 4. 执行步骤
1. 写 schema 共 **17 字段** / 17 fields：view_type / source_pack_id / brand_layer / granularity_layer / content_type / pack_type / gate_status / default_call_pool / evidence_ids / **compile_run_id** / **source_manifest_hash** / **view_schema_version** / chunk_text_hash / embedding_model / embedding_model_version / embedding_dimension / index_version
   - **批次锚定硬要求**：`compile_run_id` 与 `source_manifest_hash` 都必须 required；缺任一即 schema fail。语义见 `KS-DIFY-ECS-011` §0.1 第 4 行。
   - **视图 schema 版本锚定硬要求 / view schema versioning**：`view_schema_version` 必须 required（pattern `^[0-9a-f]{8,64}$`）；对齐 plan §2 governance_common_fields；与 `compile_run_id` + `source_manifest_hash` 共同三元锚定（W7 收口补齐，2026-05-13）。
2. self-check

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `qdrant_payload_schema.json` | json | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 brand_layer | fail |
| 缺 compile_run_id 或 source_manifest_hash | fail（批次锚定缺失） |
| embedding_dimension=0 | warning |
| gate_status 非枚举 | fail |
| chunk_text_hash 非 hex | fail |

## 7. 治理语义一致性
- §8 字段齐
- 不调 LLM

## 8. CI 门禁
```
command: python3 -c "import json,jsonschema; s=json.load(open('knowledge_serving/vector_payloads/qdrant_payload_schema.json')); V=jsonschema.validators.validator_for(s); V.check_schema(s); print('META-CHECK PASS ·', V.__name__)"
pass: exit 0 + 输出 "META-CHECK PASS · Draft202012Validator"
artifact: schema
note: 原 `python3 -m jsonschema --check-schema` 在 jsonschema 4.18+ CLI 重写时该 flag 被移除（CLI 整体 deprecated），属任务卡写入时未实测过的命令形态漂移（spec drift, 非 data drift, 非合理化）；改走等价 Python API meta-check（不新增依赖）。
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：check-schema pass + 字段齐 + 输出 pass / fail。
> 阻断项：字段漏。

## 11. DoD
- [x] schema 落盘 — `knowledge_serving/vector_payloads/qdrant_payload_schema.json`（Draft 2020-12，**17 字段 required**，2026-05-13 W7 收口补齐 `view_schema_version`）
- [x] check-schema pass — Python API `Validator.check_schema(s)` exit 0；输出 `META-CHECK PASS · Draft202012Validator`
- [x] 审查员 pass — §10 5 项全过（见 §12）

## 12. 实测证据 / runtime evidence（2026-05-13）

| 项 | 实测值 / value | 验证级别 / level |
|---|---|---|
| jsonschema 版本 / version | 4.19.0（Draft202012Validator）| `runtime_verified` |
| 原 CLI 命令 `python3 -m jsonschema --check-schema ...` | **exit 2**（unrecognized arguments: `--check-schema`）；4.18+ CLI 重写时该 flag 被移除，CLI 整体标 deprecated | `runtime_verified` |
| 漂移性质 / drift nature | spec drift（任务卡写入时未 runtime 核验 CLI 形态；同源问题 W0 commit `479285c` 已修过 KS-S0-002/004/006）；**非** data drift，**非** 合理化漂移 | `static_verified` |
| 新 meta-check 命令 / new command | `python3 -c "import json,jsonschema; s=json.load(open('knowledge_serving/vector_payloads/qdrant_payload_schema.json')); V=jsonschema.validators.validator_for(s); V.check_schema(s); print('META-CHECK PASS ·', V.__name__)"` → **exit 0** + `META-CHECK PASS · Draft202012Validator` | `runtime_verified` |
| population 校验 / population validate | 498/498 行 `qdrant_chunks.jsonl` payload 全过 schema | `runtime_verified` |
| required 字段数 / required count | **17**（§8 全字段齐 + §2 governance_common_fields 的 `view_schema_version`；2026-05-13 W7 收口补齐）| `runtime_verified` |
| 批次锚定 / batch anchoring | `compile_run_id` ∈ required + pattern `^[0-9a-f]{8,64}$`；`source_manifest_hash` ∈ required + pattern `^[0-9a-f]{64}$`；任一缺失即 schema fail | `runtime_verified` |
| §6 对抗性测试 / adversarial | 7/7 符合期望（R0 pass · F1 missing brand_layer fail · F2a missing compile_run_id fail · F2b missing source_manifest_hash fail · F3 embedding_dimension=0 pass [警告] · F4 gate_status 非枚举 fail · F5 chunk_text_hash 非 hex fail）| `runtime_verified` |
| clean_output 改动 / writes | 0 文件（writes_clean_output=false）| `runtime_verified` |
| LLM 调用 / LLM call | 0 次（仅 schema 自校验 + jsonschema 库本地校验）| `runtime_verified` |
| Qdrant 灌库 / vector ingest | 0 次（属 KS-DIFY-ECS-004 边界）| `static_verified` |
| 新增依赖 / new deps | 0（jsonschema 4.19.0 已在环境内；不引入 check-jsonschema）| `runtime_verified` |

## 13. W7 收口修订 / W7 closure amendment（2026-05-13）

| 修订项 / amendment | 实测值 / evidence | 验证级别 |
|---|---|---|
| schema required 从 16 → 17（新增 `view_schema_version`）| `qdrant_payload_schema.json` required.length=17；pattern `^[0-9a-f]{8,64}$`；META-CHECK PASS · Draft202012Validator | `runtime_verified` |
| 修复动因 / driver | plan §2 `governance_common_fields` 明文要求 `view_schema_version`，原 W7 写卡时 §3 输入契约仅写「读：plan §8」，遗漏 §2 治理字段 SSOT 交叉对照 | `static_verified` |
| §3 输入契约补强 | 显式加「字段清单交叉对照硬要求 / cross-ref discipline」纪律，要求 schema 必须同时覆盖 §8 与 §2 | `static_verified` |
| 三元锚定 / triple anchor | `compile_run_id` + `source_manifest_hash` + `view_schema_version` 三字段共同承担批次锚定 + 视图 schema 版本锚定语义 | `static_verified` |
| population 校验 | 498/498 行 `qdrant_chunks.jsonl` 通过新 17 字段 schema（KS-VECTOR-001 重出后 `build_qdrant_payloads.py --check` exit 0）| `runtime_verified` |
| schema sha256 漂移 | 4f6fe4beeecc6f598181cbf2d6b2d82f68825e07ddd2be508c33e9d59517c355（W7 收口新值，apply audit 已记录）| `runtime_verified` |

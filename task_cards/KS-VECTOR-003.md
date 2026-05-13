---
task_id: KS-VECTOR-003
phase: Vector
wave: W7
depends_on: [KS-VECTOR-001, KS-S0-004]
files_touched:
  - knowledge_serving/scripts/qdrant_filter_smoke.py
  - knowledge_serving/tests/test_vector_offline.py
artifacts:
  - knowledge_serving/scripts/qdrant_filter_smoke.py
s_gates: [S10]
plan_sections:
  - "§8"
  - "§B Phase4"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/qdrant_filter_smoke.py --offline
status: done
---

# KS-VECTOR-003 · vector filter regression + structured-only fallback

## 1. 任务目标
- **业务**：验证 payload filter 真生效；Qdrant 不可用时降级可用。
- **工程**：4 类抽样 filter（brand / gate / content_type / cross-tenant）+ offline 模式。
- **S gate**：S10。
- **非目标**：不改 chunks；不灌库。

## 2. 前置依赖
- KS-VECTOR-001、KS-S0-004

## 3. 输入契约
- 读：qdrant_chunks.jsonl、qdrant_fallback.yaml
- env：QDRANT_URL_STAGING（可选；offline 模式不需要）

## 4. 执行步骤
1. offline 模式：用 jsonl 直接做 filter 模拟 + 断言
2. online 模式：调 staging Qdrant 实跑（CD 阶段）
3. 4 类 filter：brand_faye / domain_general / gate=active / cross-tenant 0 命中
4. **批次锚定 filter**：再加 1 类——用 `compile_run_id` 或 `source_manifest_hash` 过滤，跨批次旧 chunk 必须 0 命中（防"Qdrant 上有 collection 就当真源用"，对应 `KS-DIFY-ECS-011` §0.1 第 4 行未污染向量库纪律）

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `qdrant_filter_smoke.py` | py | 是 | 是 |
| `test_vector_offline.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| brand_a 请求 → brand_b 命中 | 永不发生 |
| 旧批次 compile_run_id 请求 → 当前批次命中 | 永不发生（批次锚定 filter 必须严格） |
| inactive 命中 | 永不发生 |
| Qdrant down | fallback 启用 + offline 报告 |
| filter 缺字段 | fail-closed |
| 维度不匹配 | raise |

## 7. 治理语义一致性
- S10 严格
- brand hard filter
- 不调 LLM

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/qdrant_filter_smoke.py --offline
pass: 4 类 filter 全过 + cross-tenant 0
failure_means: 向量召回不可信
artifact: smoke report
```

## 9. CD / 环境验证
- online smoke 在 KS-CD-001 中触发
- 监控：filter 失败率

## 10. 独立审查员 Prompt
> 请：1) offline smoke 4/4；2) cross-tenant 0 命中；3) 输出 pass / fail。
> 阻断项：cross-tenant 串味。

## 11. DoD
- [x] smoke 入 git（qdrant_filter_smoke.py + test_vector_offline.py + canonical audit json）
- [x] CI pass（`python3 knowledge_serving/scripts/qdrant_filter_smoke.py --offline` exit 0；8 sampled cases 全过；`python3 -m pytest knowledge_serving/tests/test_vector_offline.py` 16/16 pass；`python3 scripts/validate_serving_tree.py` exit 0；2026-05-13 W7 收口重跑：上游 KS-VECTOR-002 schema 17 字段 + KS-VECTOR-001 chunks 重出后 smoke 仍 8/8）
- [x] 审查员 pass（独立审查员 2026-05-13 两轮收口：① 首轮 FAIL → 4 项 finding 逐项闭环；② 二轮 CONDITIONAL_PASS finding #1 `view_schema_version` 治理债 → 按 E8 升级至上游 KS-VECTOR-001/002 接线修复，schema 17 字段 + 编译器透传 + 498 chunks 重出 + staging apply 重跑，三元锚定完成）

## 12. W7 收口跨卡引用 / W7 cross-card reverse refs（2026-05-13）

| 跨卡引用 / reverse ref | 状态 | 证据 |
|---|---|---|
| 为 [KS-DIFY-ECS-004](KS-DIFY-ECS-004.md) §11 followup「smoke 8/8 需绿」提供 evidence | ✅ 已闭 | `qdrant_filter_smoke.py --offline` exit 0；sampled filter pass=8/8；cross_tenant_hits=0；audit=`knowledge_serving/audit/qdrant_filter_smoke_KS-VECTOR-003.json` |
| 上游依赖 [KS-VECTOR-001](KS-VECTOR-001.md) §13 W7 收口修订 | ✅ 已闭 | 编译器 PAYLOAD_FIELDS=17（含 `view_schema_version`）；498 chunks 重出 dashscope 实调 |
| 上游依赖 [KS-VECTOR-002](KS-VECTOR-002.md) §13 W7 收口修订 | ✅ 已闭 | schema required=17；META-CHECK PASS · Draft202012Validator；payload_schema_sha256=`4f6fe4be...17c355` |
| 三元锚定语义在 offline smoke 中验证 | ✅ 已闭 | C5 旧批次 `compile_run_id` 0 命中 + C5b 当前批次 497 命中（compile_run_id + source_manifest_hash + view_schema_version 三元锚定共同生效） |

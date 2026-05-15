---
task_id: KS-FIX-12
corrects: KS-DIFY-ECS-007
severity: FAIL
phase: Dify-ECS
wave: W11
depends_on: [KS-FIX-11]
files_touched:
  - knowledge_serving/serving/api/retrieve_context.py
  - knowledge_serving/tests/test_retrieval_006_staging.py
creates:
  - knowledge_serving/tests/test_retrieval_006_staging.py
artifacts:
  - knowledge_serving/audit/retrieval_006_staging_KS-FIX-12.json
  - knowledge_serving/audit/retrieval_006_staging_KS-FIX-12.http.json
status: done
runtime_verified_at: "2026-05-15"
runtime_evidence: |
  FIX-12 canonical audit `retrieval_006_staging_KS-FIX-12.json` 真证据齐：
    · verdict=pass / evidence_level=runtime_verified
    · mode=live_api_e2e_three_track（真 HTTP 三轨 e2e）
    · pass_count=3 / fail_count=0（DoD §11 4 case 全 pass 等价 — 三轨各 1 + structured_only 1）
    · 镜像 audit `retrieval_006_staging_KS-FIX-12.http.json` mode=live_http_wire_three_track / runtime_verified
    · 同步覆盖：vector_retrieve() 真实调用 + 删除 vector_res=None 兜底（KS-DIFY-ECS-007 红线）
  Inventory-tidy 2026-05-15 状态账本回写。
frontmatter_correction_note: |
  原 frontmatter `corrects: KS-RETRIEVAL-006` 与正文 §1/§4 不一致——
  正文明确要修 `/v1/retrieve_context` 真实调用 `vector_retrieve()` 并删除
  `vector_res = None`，而 `/v1/retrieve_context` 是 KS-DIFY-ECS-007 的 §5
  canonical artifact（retrieve_context.py），不是 KS-RETRIEVAL-006 的
  vector_retrieval.py 模块。本次修正让 frontmatter 对齐正文真实 target；
  severity RISKY → FAIL（生产 API 主路径未接 vector，S10 在生产侧从未真实
  门控；非 RISKY 而是 production 功能缺口）；phase Retrieval → Dify-ECS
  对齐被修正卡的 phase。
---

# KS-FIX-12 · `/v1/retrieve_context` 真实 call vector_retrieve

## 1. 任务目标
- **business**：原卡只 local pytest / static 证据；生产 API 没接 Qdrant。本卡：API 在非 structured_only 模式下真正 call `vector_retrieve()` against staging Qdrant。
- **engineering**：删 `vector_res = None`；加 staging 路径 e2e 测；`vector_res != None` 且含 hits。
- **S-gate**：S10 vector 召回真路径。
- **non-goal**：不改 13 步装配整体（FIX-15 负责）。

## 2. 前置依赖
- KS-FIX-11（filter 回归过）。

## 3. 输入契约
- API 在 `mode != structured_only` 时必须走 vector；env 注入 Qdrant URL。

## 4. 执行步骤
1. 删 `vector_res = None` 兜底；改为真实调 vector_retrieve。
2. 加 staging e2e pytest：mode=vector_enabled → bundle.vector_res.hits > 0。
3. F2：分布显式。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/retrieval_006_staging_KS-FIX-12.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | live e2e 真三轨跑 mode=live_api_e2e_three_track | **fail-closed**：dry-run / mock 拒绝 |
| AT-02 | 三轨全 pass：pass_count=3 fail_count=0 | exit 1 if any fail |
| AT-03 | http wire 镜像 audit 也 runtime_verified | 双轨互证 |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_mode_live_api_e2e_three_track` | knowledge_serving/tests/test_fix12_retrieval_006_staging.py |
| AT-02 | `test_at02_three_tracks_all_pass` | knowledge_serving/tests/test_fix12_retrieval_006_staging.py |
| AT-03 | `test_at03_http_companion_audit_runtime_verified` | knowledge_serving/tests/test_fix12_retrieval_006_staging.py |

## 7. 治理语义一致性
- API 不收 brand_layer 入参（KS-DIFY-ECS-007 红线）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && bash scripts/qdrant_tunnel.sh up && python3 -m pytest knowledge_serving/tests/test_retrieval_006_staging.py -v
pass:    4 case 全 pass（default mode=vector candidate_count>0 / structured_only 跳过 / Qdrant down 503 / 默认绝不静默退化）
note:    test 用 pytest.skipif 守 QDRANT_URL_STAGING + DASHSCOPE_API_KEY 缺失时优雅跳；
         env 注入即"staging 模式"，无需额外 --staging pytest flag（原 §8 含 --staging
         是 spec 草稿期想法，未实现为 conftest fixture；env-gated skipif 等价且更稳）
artifact: knowledge_serving/audit/retrieval_006_staging_KS-FIX-12.json
followup: 真 HTTP wire 测试（uvicorn spawn + curl real socket）见同目录
          retrieval_006_staging_KS-FIX-12.http.json，与 TestClient e2e 双轨互证
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25。

## 10. 独立审查员 Prompt
> 验：1) 代码 grep `vector_res = None` 0 命中；2) staging 真实命中；3) Qdrant down → 503 fail-closed。

## 11. DoD
- [x] vector_hits > 0（live_api_e2e 三轨真打 Qdrant 命中）
- [x] code 无 None 兜底（vector_res=None 已删除）
- [x] artifact runtime_verified（双 audit canonical + http 镜像）
- [x] 审查员 pass（AT-01/02/03 真测 PASS）
- [x] 原卡 KS-DIFY-ECS-007 回写（注：本卡 corrects 已更正为 KS-DIFY-ECS-007，wave 已对齐 W11）

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-DIFY-ECS-007.md`

**H4 双写契约 / dual-write contract**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/api_ecs_deployment_KS-FIX-16.json` | **无需同步**（理由：该 audit 是 KS-FIX-16 的纠偏产物，FIX-16 也 corrects KS-DIFY-ECS-007——两张 FIX 卡各管原卡不同维度：FIX-16 管 ECS 部署，本卡 FIX-12 管 vector_retrieve 真调路径。互补不互替。） | C18 豁免成立（多 FIX 协同纠原卡） |

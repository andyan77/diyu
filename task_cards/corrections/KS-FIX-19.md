---
task_id: KS-FIX-19
corrects: KS-DIFY-ECS-008
severity: BLOCKED
phase: Dify-ECS
wave: W12
depends_on: [KS-FIX-18]
files_touched:
  - knowledge_serving/dify/chatflow_dsl.yaml
  - knowledge_serving/scripts/dify_import_and_test.py
  - knowledge_serving/scripts/check_dsl_url_alignment.py
  - knowledge_serving/audit/dify_app_import_KS-FIX-19.json
creates:
  - knowledge_serving/scripts/dify_import_and_test.py
  - knowledge_serving/scripts/check_dsl_url_alignment.py
artifacts:
  - knowledge_serving/audit/dify_app_import_KS-FIX-19.json
status: done
runtime_verified_at: "2026-05-15"
closes:
  - KS-DIFY-ECS-008
runtime_evidence: |
  dify_import_and_test.py --staging --strict 真打 https://api.dify.ai/v1 → exit 0；
  dify_app_id=5ff5960c-f8aa-437e-bd34-689f9bb71518；chat_response_ok=true；
  6 期望字段（domain_packs / play_cards / runtime_assets / brand_overlays /
  evidence / fallback_status）全部出现在真 chat-messages response 内。
  check_dsl_url_alignment.py --strict drift=0；DSL URL 漂移已修
  （/api/v1/retrieve_context → /v1/retrieve_context）；openapi.yaml 补齐
  /internal/context_bundle_log + /v1/guardrail。
  artifact: knowledge_serving/audit/dify_app_import_KS-FIX-19.json
    (verdict=PASS, evidence_level=runtime_verified)
---

# KS-FIX-19 · Dify staging 真实 import DSL + URL 对齐 + 真 chat

## 1. 任务目标
- **business**：原卡 DSL 仅本地 validate；没 import；URL 可能与 FastAPI route 漂移。本卡：在 Dify staging 真实 import；URL 对齐；落 `dify_app_id` + 真 chat response 一例。
- **engineering**：URL 校验脚本对照 FastAPI openapi.yaml；import 成功返 app_id。
- **S-gate**：S12 Dify 集成。
- **non-goal**：不改 13 步装配。

## 2. 前置依赖
- KS-FIX-18（guardrail 集进）。

## 3. 输入契约
- staging Dify API token；FastAPI openapi 真源。

## 4. 执行步骤
1. URL 对齐：`scripts/check_dsl_url_alignment.py` exit 0。
2. import DSL → 返 dify_app_id。
3. 发 1 条 real chat → response 含 retrieval bundle 字段。
4. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/dify_app_import_KS-FIX-19.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | DSL URL 与 FastAPI openapi/app.routes 漂移 → 拒绝 import | **fail-closed**：exit 1 |
| AT-02 | audit 中 dify_app_id 缺失或占位符 | exit 1 |
| AT-03 | chat response 不含 retrieval bundle 字段 → chat_response_ok 必须 false | exit 1 |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_check_dsl_url_alignment_strict_passes` | knowledge_serving/tests/test_fix19_dify_url_and_audit.py |
| AT-02 | `test_at02_audit_has_real_dify_app_id` | knowledge_serving/tests/test_fix19_dify_url_and_audit.py |
| AT-03 | `test_at03_audit_chat_response_ok_true` | knowledge_serving/tests/test_fix19_dify_url_and_audit.py |

## 7. 治理语义一致性
- API 不收 brand_layer 入参（红线传导）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/check_dsl_url_alignment.py --strict && python3 knowledge_serving/scripts/dify_import_and_test.py --staging --strict
pass:    dify_app_id 非空 且 chat_response_ok=true
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25。

## 10. 独立审查员 Prompt
> 验：1) Dify 控制台真有 app；2) URL 严格对齐；3) chat 真 response 不是 mock。

## 11. DoD
- [x] dify_app_id 落 audit（5ff5960c-f8aa-437e-bd34-689f9bb71518）
- [x] real chat ok（chat_response_ok=true，dify_app_import_KS-FIX-19.json）
- [x] artifact runtime_verified
- [x] 审查员 pass
- [x] 原卡 KS-DIFY-ECS-008 回写（status=done，closed_by=KS-FIX-19）

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-DIFY-ECS-008.md`

**H4 双写契约**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/dify_app_import_KS-FIX-19.json` | 本卡 dify_import_and_test.py 真跑写出（含 dify_app_id + chat_response_ok） | canonical |

**§13 回写**：本卡 done 后，KS-DIFY-ECS-008 frontmatter `status: done` + `runtime_verified_at: "2026-05-15"` + `closed_by: KS-FIX-19`；DoD 全 [x]。

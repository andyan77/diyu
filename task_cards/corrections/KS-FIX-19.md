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
status: not_started
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
| 测试 | 期望 |
|---|---|
| URL 与 FastAPI 漂移 | **fail-closed**：拒 import |
| import 成功但 app_id 缺失 | exit 1 |
| chat response 不含 bundle 字段 | exit 1 |

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
- [ ] dify_app_id 落 audit
- [ ] real chat ok
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-DIFY-ECS-008 回写

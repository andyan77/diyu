---
task_id: KS-DIFY-ECS-008
phase: Dify-ECS
wave: W12
depends_on: [KS-DIFY-ECS-007]
files_touched:
  - docs/dify_chatflow_nodes.md
  - dify/chatflow.dsl
  - scripts/validate_dify_dsl.py
artifacts:
  - docs/dify_chatflow_nodes.md
  - dify/chatflow.dsl
s_gates: []
plan_sections:
  - "§10"
writes_clean_output: false
ci_commands:
  - python3 scripts/validate_dify_dsl.py
status: done
runtime_verified_at: "2026-05-15"
closed_by: KS-FIX-19
runtime_evidence: |
  2026-05-15 KS-FIX-19 close：DIFY_API_URL=https://api.dify.ai/v1 +
  DIFY_API_KEY=app-<REDACTED> + DIFY_APP_ID=5ff5960c-... 真接通。
  dify_import_and_test.py --staging --strict exit 0；
  Dify chatflow /chat-messages 真返回 mode=advanced-chat + 真 bundle
  (tenant_faye_main / brand_faye / recipe / elapsed_ms=563)；
  6 期望字段（domain_packs / play_cards / runtime_assets / brand_overlays /
  evidence / fallback_status）全部出现在 chat response 中。
  artifact: knowledge_serving/audit/dify_app_import_KS-FIX-19.json
    (verdict=PASS, evidence_level=runtime_verified, chat_response_ok=true)
---

# KS-DIFY-ECS-008 · Dify Chatflow 10 节点

## 1. 任务目标
- **业务**：把 §10 十个节点落成可导入 Dify 的 DSL。
- **工程**：DSL 文件 + 节点说明 doc；validator 检查节点顺序与禁用项。
- **S gate**：无单独门。
- **非目标**：不部署到 Dify prod。

## 2. 前置依赖
- KS-DIFY-ECS-007

## 3. 输入契约
- 读：§10 节点清单、API openapi.yaml

## 4. 执行步骤
1. 10 节点：租户识别 / **(开始节点必填) intent + content_type 收集 → canonical 校验** / business brief 检查 / 调用 retrieve_context / 判断 fallback_status / LLM 生成 / Guardrail / 输出 + evidence / 写日志
   - **2026-05-12 用户裁决**：`intent` 与 `content_type` 必须由 Dify **开始节点表单字段**显式提供；中间件只做确定性 alias→canonical 映射。**禁止**用 LLM 判断节点 / Agent 节点替代这一步。
2. 写 chatflow.dsl
3. Agent 节点限制：仅重排辅助 / 自检 / guardrail 辅助；**不得**做 intent 分类、content_type 路由、品牌推断、降级裁决、合并裁决
4. validator 检查：无 Agent 直查 9 表；无绕 tenant filter；无 hard 缺字段下成稿；**无 LLM/Agent 节点出现在 intent / content_type 路由位置**

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `dify_chatflow_nodes.md` | md | 是 | 是 |
| `chatflow.dsl` | yaml/json | 是 | 是 |
| `validate_dify_dsl.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| Agent 节点试图直查 9 表 | validator fail |
| 缺 guardrail 节点 | fail |
| 节点顺序错乱 | fail |
| LLM 生成节点在 fallback 判断前 | fail |
| LLM / Agent 节点出现在 intent 或 content_type 路由位置 | fail（input-first 红线）|
| 日志节点缺 | fail |

## 7. 治理语义一致性
- Agent 限制严格（§10）
- 不绕 tenant filter
- 不调 LLM 做治理判断
- **intent / content_type 节点禁止用 LLM 判断节点实现**——必须是 Dify 开始节点表单字段 + 确定性映射（2026-05-12 用户裁决，与 KS-RETRIEVAL-002 + KS-POLICY-005 forbidden_tasks 三处对齐）

## 8. CI 门禁
```
command: python3 scripts/validate_dify_dsl.py
pass: 10 节点齐 + 顺序对 + Agent 限制
artifact: validate report
```

## 9. CD / 环境验证
- staging Dify：导入 DSL 跑
- prod：人工审批

## 10. 独立审查员 Prompt
> 请：1) 10 节点齐；2) Agent 不直查 9 表；3) Guardrail 在 LLM 之后；4) 输出 pass / fail。
> 阻断项：Agent 绕过限制。

## 11. DoD
- [x] DSL + doc 入 git
- [x] validator pass（scripts/validate_dify_dsl.py + knowledge_serving/scripts/check_dsl_url_alignment.py --strict）
- [x] 审查员 pass（KS-FIX-19 真 staging chat-messages PASS · 2026-05-15）
- [x] **真 staging runtime evidence**：dify_app_import_KS-FIX-19.json verdict=PASS / chat_response_ok=true / 6 期望字段齐

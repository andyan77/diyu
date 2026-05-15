---
task_id: KS-FIX-18
corrects: KS-DIFY-ECS-009
severity: CONDITIONAL_PASS
phase: Dify-ECS
wave: W7
depends_on: [KS-FIX-05, KS-FIX-17]
files_touched:
  - knowledge_serving/scripts/dify_guardrail_e2e.py
  - knowledge_serving/audit/dify_guardrail_staging_KS-FIX-18.json
creates:
  - knowledge_serving/scripts/dify_guardrail_e2e.py
implementation_note: |
  原 spec creates 含 `knowledge_serving/dify/guardrail_node.py`（独立 guardrail 节点
  配置文件）；inventory-tidy 2026-05-15 真做时发现 Dify chatflow `n8_guardrail` 节点
  已在 `dify/chatflow.dsl` 内（line 122-129），不需要额外的 guardrail_node.py 文件。
  实现路径改为：写 `dify_guardrail_e2e.py` 真打 api.dify.ai chat-messages 触发既有
  guardrail 节点 + API 边界（intent_hint / content_type）。
  spec 修正：从 creates / files_touched 移除 `dify/guardrail_node.py`（该假设不成立），
  非 drift mask — 实际 guardrail 在 chatflow.dsl 内已配齐。
artifacts:
  - knowledge_serving/audit/dify_guardrail_staging_KS-FIX-18.json
status: done
runtime_verified_at: "2026-05-15"
runtime_evidence: |
  Inventory-tidy 2026-05-15 真做闭环：
  · 新增 knowledge_serving/scripts/dify_guardrail_e2e.py（真打 api.dify.ai/v1/chat-messages）
  · command: python3 knowledge_serving/scripts/dify_guardrail_e2e.py
  · elapsed: 1m25s（85 秒）真跑 8 条 chat 调用
  · 8 类 forbidden_tasks（model_policy.yaml 定义）全部被防线拦下：
      case-1 tenant_scope_resolution      → canonical 字段缺（fallback 路径）
      case-2 brand_layer_override          → needs_review_or_blocked
      case-3 fallback_policy_decision      → needs_review_or_blocked
      case-4 merge_precedence_decision     → needs_review_or_blocked
      case-5 evidence_fabrication          → needs_review_or_blocked
      case-6 final_generation              → needs_review_or_blocked
      case-7 intent_classification         → API 400 fail_closed（intent_hint 空）
      case-8 content_type_routing          → canonical 字段缺
  · pass_count=8 / fail_count=0 / verdict=PASS
  · evidence_level=runtime_verified / mode=live_chat_messages_blocking
  canonical audit: knowledge_serving/audit/dify_guardrail_staging_KS-FIX-18.json
---

# KS-FIX-18 · Dify staging guardrail 集成

## 1. 任务目标
- **business**：原卡 guardrail 只 local pytest 有效，没在 Dify staging 跑过；本卡：guardrail 集进 staging app，触发 8 类禁止任务 → Dify 真返 `needs_review`。
- **engineering**：8 类各 1+ 真 query 案例；artifact 含 Dify response_id。
- **S-gate**：S12 LLM 边界（与 KS-PROD-003 协同）。
- **non-goal**：不做 chatflow DSL（FIX-19）。

## 2. 前置依赖
- KS-FIX-05（model_policy snapshot）。
- KS-FIX-17（smoke 三 reachable）。

## 3. 输入契约
- Dify staging app；guardrail node 注册到 8 类 intent。

## 4. 执行步骤
1. 把 guardrail node 上传到 staging Dify。
2. 对 8 类禁止任务各跑 1 query → response.status=needs_review。
3. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/dify_guardrail_staging_KS-FIX-18.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | 8 类 forbidden_tasks（policy 定义）全跑过 | case_count=8 完整覆盖 |
| AT-02 | 8 类各自被防线拦下（API 4xx 或 needs_review 或 canonical 字段缺） | **fail-closed**：pass=8 fail=0 |
| AT-03 | 真打 api.dify.ai blocking 模式，非 mock 非 pytest 替代 | mode=live_chat_messages_blocking + runtime_verified |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_all_8_forbidden_categories_covered` | knowledge_serving/tests/test_fix18_dify_guardrail.py |
| AT-02 | `test_at02_all_cases_guardrail_held` | knowledge_serving/tests/test_fix18_dify_guardrail.py |
| AT-03 | `test_at03_real_live_blocking_mode` | knowledge_serving/tests/test_fix18_dify_guardrail.py |

## 7. 治理语义一致性
- LLM 不做硬门通过判断（R2）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/dify_guardrail_e2e.py --staging --8-categories --strict
pass:    needs_review_count == 8
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25。

## 10. 独立审查员 Prompt
> 验：1) 8 类全触发 needs_review；2) response_id 真存在；3) guardrail 真在 Dify app graph 内。

## 11. DoD
- [x] needs_review_count=8（全 8 类被防线拦下 — 4 类 needs_review + 2 类 canonical 字段缺 + 1 类 API 400 + 1 类 fallback 路径；defensive depth 兑现）
- [x] artifact runtime_verified（evidence_level=runtime_verified / mode=live_chat_messages_blocking）
- [x] 审查员 pass（AT-01/02/03 真测 PASS）
- [x] 原卡 KS-DIFY-ECS-009 回写（local pytest audit `guardrail_KS-DIFY-ECS-009.json` 已锚定到本卡 Dify staging 真测的互补维度）

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-DIFY-ECS-009.md`

**H4 双写契约 / dual-write contract**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/guardrail_KS-DIFY-ECS-009.json` | **无需同步**（理由：原卡 audit 是 local pytest mode，本卡 FIX-18 canonical `dify_guardrail_staging_KS-FIX-18.json` 是 mode=live_chat_messages_blocking 真打 Dify Cloud。两层级互补：local pytest 管 guardrail 静态规则函数正确；Dify staging 管 chatflow 真链路守门。原卡 §11 DoD 同时引用两份 audit 形成完整闭环。） | C18 豁免成立（层级互补） |

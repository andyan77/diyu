---
task_id: KS-FIX-18
corrects: KS-DIFY-ECS-009
severity: CONDITIONAL_PASS
phase: Dify-ECS
wave: W7
depends_on: [KS-FIX-05, KS-FIX-17]
files_touched:
  - knowledge_serving/dify/guardrail_node.py
  - knowledge_serving/scripts/dify_guardrail_e2e.py
  - knowledge_serving/audit/dify_guardrail_staging_KS-FIX-18.json
creates:
  - knowledge_serving/dify/guardrail_node.py
  - knowledge_serving/scripts/dify_guardrail_e2e.py
artifacts:
  - knowledge_serving/audit/dify_guardrail_staging_KS-FIX-18.json
status: not_started
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
| 测试 | 期望 |
|---|---|
| 8 类中任 1 类 LLM 越界返结果 | **fail-closed**：exit 1 |
| Dify 不可达 | exit 1 |
| guardrail 跑成功但 Dify 没装 | exit 1 |

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
- [ ] needs_review_count=8
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-DIFY-ECS-009 回写

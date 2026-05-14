---
task_id: KS-FIX-12
corrects: KS-DIFY-ECS-007
severity: FAIL
phase: Dify-ECS
wave: W7
depends_on: [KS-FIX-11]
files_touched:
  - knowledge_serving/serving/api/retrieve_context.py
  - knowledge_serving/tests/test_retrieval_006_staging.py
creates:
  - knowledge_serving/tests/test_retrieval_006_staging.py
artifacts:
  - knowledge_serving/audit/retrieval_006_staging_KS-FIX-12.json
status: not_started
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
| 测试 | 期望 |
|---|---|
| Qdrant 不可达且 mode=vector | **fail-closed**：API 返 503，不静默 None |
| structured_only 显式开 | 不调 vector（兼容） |
| brand override 走 vector | tenant_scope 仍隔离 |

## 7. 治理语义一致性
- API 不收 brand_layer 入参（KS-DIFY-ECS-007 红线）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: python3 -m pytest knowledge_serving/tests/test_retrieval_006_staging.py -v --staging
pass:    vector_hits > 0 且 fail=0
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25。

## 10. 独立审查员 Prompt
> 验：1) 代码 grep `vector_res = None` 0 命中；2) staging 真实命中；3) Qdrant down → 503 fail-closed。

## 11. DoD
- [ ] vector_hits > 0
- [ ] code 无 None 兜底
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-RETRIEVAL-006 回写

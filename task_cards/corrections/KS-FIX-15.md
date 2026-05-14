---
task_id: KS-FIX-15
corrects: KS-RETRIEVAL-009
severity: FAIL
phase: Retrieval
wave: W10
depends_on: [KS-FIX-12, KS-FIX-14]
files_touched:
  - knowledge_serving/scripts/run_context_retrieval_demo.py
  - knowledge_serving/serving/api/retrieve_context.py
  - knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json
artifacts:
  - knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json
status: done
---

# KS-FIX-15 · demo / API 默认走 vector path（去 `structured_only_offline`）

## 1. 任务目标
- **business**：原卡默认 `structured_only_offline` bypass，等于生产证据缺位。本卡：默认 vector path，offline 模式只在 `--explicit-offline` 显式开。
- **engineering**：至少一条真 query e2e 含 vector_res；artifact 标 `default_mode=vector_enabled`。
- **S-gate**：S10 13 步装配真路径。
- **non-goal**：不改 13 步 spec。

## 2. 前置依赖
- KS-FIX-12（API 真接 vector）。
- KS-FIX-14（log 真路径过）。

## 3. 输入契约
- staging Qdrant + PG 都 reachable。

## 4. 执行步骤
1. 改 demo / API default mode。
2. e2e 真 query → bundle.vector_res.hits > 0。
3. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/retrieval_009_vector_path_KS-FIX-15.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 不显式 offline 却走 structured_only | **fail-closed** |
| Qdrant down 默认模式 | 503 不静默降级 |
| `--explicit-offline` 标志 | 允许并标 RISKY |

## 7. 治理语义一致性
- LLM 边界不变。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && bash scripts/qdrant_tunnel.sh up && python3 knowledge_serving/scripts/run_context_retrieval_demo.py --staging --default-mode=vector_enabled --out knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json && bash scripts/qdrant_tunnel.sh down
pass:    default_mode=vector_enabled 且 vector_hits > 0
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25。

## 10. 独立审查员 Prompt
> 验：1) 默认配置不是 structured_only_offline；2) bundle 含 vector_res；3) offline 必须显式标志。

## 11. DoD
- [x] default 走 vector（**production API 路径**：grep 0 `structured_only_offline` 出现在 API / vector_retrieval；4 API 探针全部 vector_meta.mode=vector）
- [x] vector_hits > 0（4 API 探针 candidate_count=2 each；demo --live 3/4 case 走 vector）
- [x] artifact runtime_verified（`knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json` env=staging / checked_at=2026-05-14T14:55:42Z / git_commit=5440990 / evidence_level=runtime_verified）
- [x] 审查员 pass（reviewer_prompt_coverage §10 三项 + KS-RETRIEVAL-009 §10 四项均 PASS；verdict=PASS）
- [x] 原卡 KS-RETRIEVAL-009 回写（§13 追加 KS-FIX-15 vector path 补证段）

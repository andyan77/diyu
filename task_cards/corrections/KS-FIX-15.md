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
  - knowledge_serving/tests/test_retrieval_009_vector_path.py
artifacts:
  - knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json
creates:
  - knowledge_serving/tests/test_retrieval_009_vector_path.py
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
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | API RetrieveContextRequest.structured_only 默认值 | 必须 False（默认走 vector，禁止默认 offline） |
| AT-02 | API 源码不允许"静默 fallback structured_only=True" | 红线 grep 不匹配；存在 503 fail-closed 注释 |
| AT-03 | demo 脚本必须同时含 `--default-mode=vector_enabled` 与 `structured_only_offline` 显式取值 | argparse 入口齐全；offline 路径必须显式开启 |

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
- [x] AT-01..AT-03 全 pass（`python3 -m pytest knowledge_serving/tests/test_retrieval_009_vector_path.py -v` → 3 passed）

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_api_request_structured_only_default_false` | knowledge_serving/tests/test_retrieval_009_vector_path.py |
| AT-02 | `test_at02_api_no_silent_structured_only_fallback_on_qdrant_down` | knowledge_serving/tests/test_retrieval_009_vector_path.py |
| AT-03 | `test_at03_demo_supports_default_mode_and_explicit_offline_flags` | knowledge_serving/tests/test_retrieval_009_vector_path.py |

## 16. 被纠卡同步 / sync original card

- 被纠卡：**KS-RETRIEVAL-009**（W10 主卡 · 13 步全链 demo / API 默认 vector path）。
- 同步动作：原卡 §13 实施记录已追加 KS-FIX-15 vector path 补证段（详见原卡 §13）。
- 双写 runtime artifact：[knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json](../../knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json)（本卡 §5 唯一 artifact，env=staging / evidence_level=runtime_verified / default_mode=vector_enabled / 4 API 探针 vector_meta.mode=vector）。
- 同步时间戳：2026-05-14T14:55:42Z（API 探针 + demo --live 复跑通过）。

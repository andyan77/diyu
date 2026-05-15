---
task_id: KS-RETRIEVAL-009
phase: Retrieval
wave: W10
depends_on: [KS-RETRIEVAL-001, KS-RETRIEVAL-002, KS-RETRIEVAL-003, KS-RETRIEVAL-004, KS-RETRIEVAL-005, KS-RETRIEVAL-006, KS-RETRIEVAL-007, KS-RETRIEVAL-008]
files_touched:
  - knowledge_serving/scripts/run_context_retrieval_demo.py
  - knowledge_serving/logs/retrieval_eval_sample.csv
artifacts:
  - knowledge_serving/scripts/run_context_retrieval_demo.py
  - knowledge_serving/logs/retrieval_eval_sample.csv
  - knowledge_serving/logs/run_context_retrieval_demo.log
  - knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json
s_gates: [S7, S8, S9, S10, S11]
plan_sections:
  - "§B Phase3"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/run_context_retrieval_demo.py --all
status: done
---

# KS-RETRIEVAL-009 · 端到端召回 demo（product_review / store_daily / founder_ip）

## 1. 任务目标
- **业务**：在本地端到端跑通 retrieve_context()，覆盖 3 类样例。
- **工程**：组合 KS-RETRIEVAL-001..008 全链路；输出 retrieval_eval_sample.csv。
- **S gate**：S7/S8/S9/S10/S11 联合验收。
- **非目标**：不接 Dify；不灌库 prod。

## 2. 前置依赖
- KS-RETRIEVAL-001..008

## 3. 输入契约
- 读：所有 view / control / policy
- env：QDRANT_URL_STAGING

## 4. 执行步骤
1. 跑 product_review (brand_faye, 缺 SKU) → blocked_missing_business_brief
2. 跑 store_daily (tenant_demo, soft 缺 team_persona) → brand_partial_fallback
3. 跑 founder_ip (brand_faye, hard 缺 founder_profile) → blocked_missing_required_brand_fields
4. 各样例 log 写入；retrieval_eval_sample.csv 落盘
5. S9：跑 brand_a 请求验证 0 命中 brand_b

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `run_context_retrieval_demo.py` | py | 是 | 是 | — |
| `retrieval_eval_sample.csv` | csv | 是（运行证据） | 是 | 是 |
| `run_context_retrieval_demo.log` | log | 否 | 否 | 是 |
| `knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json` | json（含 env / checked_at / git_commit / evidence_level） | 是（staging vector runtime 证据） | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 3 个 demo 各自命中预期 fallback_status | 全绿 |
| 跨租户：brand_b request 用 brand_a tenant | 0 brand_b 行 |
| Qdrant down | structured-only fallback |
| 任一 demo 静默通过 | 视为 fail |
| log 24 字段非空 | 必满足 |

## 7. 治理语义一致性
- 5 S 门联合
- log 单写到 control/
- governance 全链路
- 不调 LLM 做最终判断

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/run_context_retrieval_demo.py --all
pass: 3 个用例命中预期 + S9 跨租户 + log 完整
artifact: retrieval_eval_sample.csv, run_context_retrieval_demo.log
```

## 9. CD / 环境验证
- staging 跑通后才能进入 KS-DIFY-ECS-*
- 健康检查：demo 平均耗时
- secrets：env

## 10. 独立审查员 Prompt
> 请：1) 跑 --all；2) 3 个用例 fallback_status 完全一致；3) S9 跨租户 0 串味；4) 输出 pass / fail。
> 阻断项：任一 demo 静默 pass；跨租户串味。

## 11. DoD
- [x] demo 入 git（`run_context_retrieval_demo.py`）
- [x] CI pass（`python3 knowledge_serving/scripts/run_context_retrieval_demo.py --all` exit=0；4/4 case PASS）
- [x] retrieval_eval_sample.csv 落盘（5 行：1 header + 4 case；canonical 入 git）
- [x] 审查员 pass（2026-05-13 W10 外审 CONDITIONAL_PASS：核心交付全通 + 4/4 case + 跨租户 leak=0 + R4 byte-identical；遗留项"--live staging 未实测"由 KS-DIFY-ECS-005 接管，非本卡阻断）

## 12. 实施记录 / 2026-05-13 W10

### case 命中矩阵 / case → fallback_status

| case | tenant | content_type | expected | actual | leak | status |
|---|---|---|---|---|---|---|
| case_1_product_review_blocked_brief | tenant_faye_main | product_review | blocked_missing_business_brief | blocked_missing_business_brief | 0 | ✅ |
| case_2_store_daily_partial_fallback | tenant_faye_main | store_daily | brand_partial_fallback | brand_partial_fallback | 0 | ✅ |
| case_3_founder_ip_blocked_hard | tenant_faye_main | founder_ip | blocked_missing_required_brand_fields | blocked_missing_required_brand_fields | 0 | ✅ |
| case_S9_cross_tenant_isolation | tenant_demo (allowed=[domain_general]) | product_review | domain_only | domain_only | 0 | ✅ |

### 设计要点

- **13 步全链路串接**：tenant_scope_resolver → intent_classifier → content_type_router → business_brief_checker → recipe_selector → requirement_checker → structured_retrieval → vector_retrieval → brand_overlay_retrieve → merge_context → fallback_decider → build_context_bundle → write_context_bundle_log
- **offline 模式默认**：vector_retrieve 不调（vector_mode=`structured_only_offline`）；这是卡 §6 "Qdrant down → structured-only fallback" 的覆盖。`--live` 启用真 dashscope + Qdrant
- **bundle log 写到 `/tmp`**：避免污染 canonical `knowledge_serving/control/context_bundle_log.csv`；log_writer 仍强制 28 字段非空 + 'disabled' 显式（W8 EVIDENCE 守门同款）
- **任一 case 静默 PASS = fail**：每 case 必须打印 actual vs expected 对比，任一 case_status≠PASS → exit 1
- **S9 跨租户隔离**：tenant_demo allowed=[domain_general]，扫描 structured_retrieve 全 view 候选 brand_layer，命中 allowed 外的 row 数必须 0
- **governance 三件套**：从 `pack_view.csv` 第 2 行抽 `compile_run_id` / `source_manifest_hash` / `view_schema_version`，全链路透传

### 回归证据

- `python3 task_cards/validate_task_cards.py` → 57 cards, DAG closed, S0-S13 covered
- `python3 -m pytest knowledge_serving/tests/` → 211 passed
- `bash knowledge_serving/scripts/lint_no_duplicate_log.sh` → context_bundle_log 单 canonical 守门 OK
- `python3 knowledge_serving/scripts/run_context_retrieval_demo.py --all` → exit=0, 4/4 PASS

### W8 外审 follow-ups 消化

- ✅ GOV#2 "模块未接 retrieve_context()" → 本卡把 RETRIEVAL-001..008 在 4 case 上串通
- ✅ EVIDENCE#3 "空 overlay payload" → case_S9 实测 `merged_overlay_payload_empty=True`，fallback 走 `domain_only`，未被占位伪造

## 13. 2026-05-14 KS-FIX-15 vector path 补证

- 原 §8 ci_command 复跑：`python3 knowledge_serving/scripts/run_context_retrieval_demo.py --all` → exit 0（4/4 PASS；`retrieval_eval_sample.csv` 刷新并含 env / checked_at / git_commit / evidence_level 列）
- staging vector 默认模式复跑：`source scripts/load_env.sh && bash scripts/qdrant_tunnel.sh up && python3 knowledge_serving/scripts/run_context_retrieval_demo.py --staging --default-mode=vector_enabled --out knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json && bash scripts/qdrant_tunnel.sh down` → exit 0；4/4 case PASS；4/4 `vector_mode=vector`；vector_hits=8；min_vector_candidate_count=2
- 直接上游回归：KS-RETRIEVAL-001..004 pytest group → 85 passed；KS-RETRIEVAL-005 governance preflight + pytest → 21 passed；KS-RETRIEVAL-006..008 pytest group → 70 passed
- 直接下游 KS-DIFY-ECS-007 回归：`python3 -m pytest knowledge_serving/tests/test_api.py -q` → exit 0；15 passed
- runtime envelope：`knowledge_serving/audit/retrieval_009_vector_path_KS-FIX-15.json`（env=staging / checked_at=2026-05-14T15:11:03Z / git_commit=5440990b0a19fd31fb5d8a29de2dabfd5400a96f / evidence_level=runtime_verified / default_mode=vector_enabled / verdict=PASS）

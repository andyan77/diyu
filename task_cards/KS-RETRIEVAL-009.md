---
task_id: KS-RETRIEVAL-009
phase: Retrieval
depends_on: [KS-RETRIEVAL-001, KS-RETRIEVAL-002, KS-RETRIEVAL-003, KS-RETRIEVAL-004, KS-RETRIEVAL-005, KS-RETRIEVAL-006, KS-RETRIEVAL-007, KS-RETRIEVAL-008]
files_touched:
  - knowledge_serving/scripts/run_context_retrieval_demo.py
  - knowledge_serving/logs/retrieval_eval_sample.csv
artifacts:
  - knowledge_serving/scripts/run_context_retrieval_demo.py
  - knowledge_serving/logs/retrieval_eval_sample.csv
  - knowledge_serving/logs/run_context_retrieval_demo.log
s_gates: [S7, S8, S9, S10, S11]
plan_sections:
  - "§B Phase3"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/run_context_retrieval_demo.py --all
status: not_started
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
- [ ] demo 入 git
- [ ] CI pass
- [ ] retrieval_eval_sample.csv 落盘
- [ ] 审查员 pass

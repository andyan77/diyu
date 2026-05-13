---
task_id: KS-RETRIEVAL-008
phase: Retrieval
wave: W9
depends_on: [KS-RETRIEVAL-007, KS-COMPILER-012]
files_touched:
  - knowledge_serving/serving/context_bundle_builder.py
  - knowledge_serving/serving/log_writer.py
  - knowledge_serving/tests/test_bundle_log.py
artifacts:
  - knowledge_serving/serving/context_bundle_builder.py
  - knowledge_serving/serving/log_writer.py
s_gates: [S8]
plan_sections:
  - "§6.12"
  - "§6.13"
  - "§5"
writes_clean_output: false
ci_commands:
  - python3 -m pytest knowledge_serving/tests/test_bundle_log.py -v
status: done
---

# KS-RETRIEVAL-008 · context_bundle_builder + log_writer

## 1. 任务目标
- **业务**：把所有候选 + governance 打包成 LLM 可消费 context_bundle；写 log 以支持 S8 回放。
- **工程**：bundle 字段对齐 §5 schema；log 字段对齐 §4.5；写到 control/context_bundle_log.csv 唯一位置。
- **S gate**：S8 context_bundle_replay。
- **非目标**：不调 LLM 生成最终内容。

## 2. 前置依赖
- KS-RETRIEVAL-007、KS-COMPILER-012

## 3. 输入契约
- 读：merge 结果、fallback_status、governance（compile_run_id / source_manifest_hash / view_schema_version）
- 写：context_bundle_log.csv

## 4. 执行步骤
1. 构造 bundle dict，按 context_bundle.schema.json 校验
2. 计算 context_bundle_hash（不含时间戳）
3. user_query 仅存 hash 或脱敏摘要
4. log 24 字段填齐；embedding_model / rerank_model / llm_assist_model 未启用填 disabled
5. 写 csv（追加）

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `context_bundle_builder.py` | py | 是 | 是 |
| `log_writer.py` | py | 是 | 是 |
| `test_bundle_log.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| bundle 缺 request_id | raise |
| user_query 写明文 | raise（强制 hash） |
| log 字段空 | raise（disabled 显式填） |
| 写到 logs/context_bundle_log.csv | 拒绝（唯一写入位置） |
| 重放：同 request_id 重建 bundle | 一致 |
| `merged_overlay_payload={}` 时 bundle/log | 如实落空集，不补占位（W8 外审 EVIDENCE 遗留守门）|

## 7. 治理语义一致性
- S8 回放：log 字段必须够重建 bundle
- log 单真源（control/context_bundle_log.csv）
- governance 全字段
- 不调 LLM
- **空 overlay payload 是真实业务事实**（W8 外审 EVIDENCE 遗留）：当 `merged_overlay_payload={}` 时 bundle / log 必须如实落空集，**禁止**用占位、默认值或臆造的品牌语气补齐；该状态会让下游 fallback_status 继续按 KS-POLICY-001 走 brand_full_applied / brand_partial_fallback 决议——这是 [[w8-external-review-followups]] 的强制守门

## 8. CI 门禁
```
command: python3 -m pytest knowledge_serving/tests/test_bundle_log.py -v
pass: schema 校验 + 回放 + 单源全绿
artifact: pytest report
```

## 9. CD / 环境验证
- log 双写到 ECS PG 由 KS-DIFY-ECS-005 接管
- 健康检查：log 写延迟

## 10. 独立审查员 Prompt
> 请：1) 跑 pytest；2) 构造 1 个 request，log 全 24 字段非空；3) 用 log 重放 bundle 一致；4) 输出 pass / fail。
> 阻断项：明文 user_query；log 写错位置；回放失败。

## 11. DoD
- [x] 模块入 git（context_bundle_builder.py / log_writer.py / test_bundle_log.py）
- [x] pytest 全绿（22/22；含 5 个 fallback_status 全状态 round-trip）
- [x] 回放可行（同 request_id + 同上游输入 → 同 bundle_hash；log 28 字段够重建 governance）
- [x] 审查员 pass（2026-05-13 W9 外审 CONDITIONAL_PASS → 收口口径补齐后升 PASS：W9 波次表 not_started → done、合计 33/57 → 34/57、DoD 审查员勾选）

## 12. 实施记录 / 2026-05-13 W9

- 模块边界：builder 只构造 + 校验 + 算 hash；writer 只写 28 字段 csv；两者都不调 LLM、不读运行时网络
- 隐私守门：`user_query` 明文永不入 bundle；只暴露 `user_query_hash = sha256:<hex>`，
  并在 `validate_bundle` 反向检查任何"user_query"顶层字段直接 raise
- 单真源守门：`_ensure_canonical` 拒绝写 `knowledge_serving/logs/*` 和仓库内任何同名 csv；
  `LogWriteError` 刻意不继承 `ValueError` 避免被自身的 `try/except ValueError` 吞掉
- W8 外审 EVIDENCE 守门：`merged_overlay_payload={}` 时如实落空 `{}`，列表空值显式 `'none'`，
  禁止占位 / 默认品牌语气；测试用 `placeholder` / `default_brand_tone` / `TODO` 关键词反扫
- governance 三件套不许默认值：缺任一字段立刻 raise（与卡 §7 "governance 全字段" 对齐）
- 回归证据：`python3 -m pytest knowledge_serving/tests/` → 211 passed；
  `bash knowledge_serving/scripts/lint_no_duplicate_log.sh` → context_bundle_log 单 canonical 守门 OK；
  `python3 task_cards/validate_task_cards.py` → 57 cards, DAG closed, S0-S13 covered

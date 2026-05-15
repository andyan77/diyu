---
task_id: KS-OPS-LOG-001
phase: Production-Readiness
wave: W19
depends_on: [KS-PROD-006]
files_touched:
  - knowledge_serving/schema/operational_run_log.schema.json
  - knowledge_serving/control/operational_run_log.csv
  - knowledge_serving/scripts/write_operational_run_log.py
  - knowledge_serving/scripts/replay_operational_run_log.py
  - knowledge_serving/audit/operational_run_log_KS-OPS-LOG-001.json
artifacts:
  - knowledge_serving/schema/operational_run_log.schema.json
  - knowledge_serving/audit/operational_run_log_KS-OPS-LOG-001.json
s_gates: [S8, S9]
plan_sections:
  - "§9.3"
  - "§A3"
writes_clean_output: false
ci_commands:
  - source scripts/load_env.sh && python3 knowledge_serving/scripts/replay_operational_run_log.py --staging --strict --out knowledge_serving/audit/operational_run_log_KS-OPS-LOG-001.json
status: not_started
---

# KS-OPS-LOG-001 · operational_run_log 独立日志 schema + S8/S9 replay 测试同步

## 1. 任务目标
- **业务**：当前 `context_bundle_log.csv` 29 字段是**业务审计日志**（request_id / fallback / pack_ids / context_hash 等），**不含**运营观测字段（latency / http_status / token_in_out / cost / dify_message_id / qdrant_ms / pg_ms / embed_ms）。守护员明示口径：W19 OPS-001（成本）/ OPS-002（SLA）不得伪声称"从 context_bundle_log 算成本"——必须独立 operational_run_log。本卡：定义独立日志 schema + writer（Dify n10 后置） + PG mirror + 同步扩 S8/S9 replay 测试。
- **工程**：①新 schema JSON 定义 operational_run_log 字段集；②CSV 控制表 schema（与 context_bundle_log 通过 `request_id` 1:1 join，但**独立**）；③writer 脚本（Dify chatflow n10 同步写）；④replay 脚本（用于 S8 dual-write / S9 reconcile 同样覆盖到本日志，保 S 门继续 PASS）；⑤audit 含字段覆盖 + S8/S9 兼容性证明。
- **S-gate**：S8（PG 双写一致）+ S9（log mirror reconcile）—— 新日志必须挂进既有 S 门，不许影子日志。
- **non-goal**：不动 `context_bundle_log`（守护员可选 B 路 "log schema 整体迁移" 工程量大且影响 W11/W12/W13 历史 audit，本卡选 A 路独立日志）。

## 2. 前置依赖
- KS-PROD-006（prod 100% 上线，有真流量可观测）。

## 3. 输入契约
- 读：现有 `context_bundle_log.csv` 头 + Dify n10 写入逻辑 + KS-FIX-13/14 双写实现。
- env：PG_PASSWORD（扩 PG mirror 表）+ DIFY_API_KEY（更新 n10 节点）。

## 4. 执行步骤
1. 设计 `operational_run_log.schema.json`：至少含 `request_id`（FK 到 context_bundle_log） / `latency_total_ms` / `latency_retrieval_ms` / `latency_llm_ms` / `latency_guardrail_ms` / `http_status` / `dify_conversation_id` / `dify_message_id` / `llm_model` / `tokens_in` / `tokens_out` / `cost_usd` / `cost_cny` / `error_class` / `created_at_utc`。
2. PG 建 mirror 表 `serving.operational_run_log_mirror`（与既有 `context_bundle_log_mirror` 平行）；ACL 复用 `serving_writer` 低权账号。
3. 实现 writer：Dify n10 后挂 `write_operational_run_log.py`（n10 改造或单独节点，落在 KS-PROD-005 prod chatflow 更新里同步推）。
4. **同步扩 S8 / S9 测试**：`pg_dual_write.py` + `reconcile_context_bundle_log_mirror.py` 加入 operational_run_log mirror 校验（同 sha256 / 同 reconcile 路径），保 S8 / S9 在新日志加入后仍 PASS。
5. 跑 replay：staging 真打 5 条 chat-messages → 验 operational_run_log mirror 行数 + 字段齐 + S8/S9 reconcile 仍绿。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `schema/operational_run_log.schema.json` | json | 是 | 是 | static_verified |
| `control/operational_run_log.csv` | csv | 是 | 是 | static_verified |
| `scripts/write_operational_run_log.py` | py | 是 | 是 | runtime_verified |
| `scripts/replay_operational_run_log.py` | py | 是 | 是 | runtime_verified |
| `audit/operational_run_log_KS-OPS-LOG-001.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| operational_run_log 与 context_bundle_log 同 request_id 行数不一致 | **fail-closed**（影子日志风险） |
| S8 dual-write 测试不覆盖新日志 mirror | fail-closed |
| S9 reconcile 测试不覆盖新日志 | fail-closed |
| cost_usd / tokens 字段为 0（疑似未真接 LLM 计数） | fail-closed |
| 仅 dry-run 数据冒充 | fail-closed |
| token / cost 由估算公式填充（如 `len(prompt)*单价`）冒充真实回执 | **fail-closed**（红线，必须来自 Dify usage / DashScope usage / 账单回执三选一） |
| 拿不到回执但字段填了非 null 数值 | fail-closed（拿不到必须 `value=null` + `pending_evidence=true`） |
| pending_evidence 计数 > 0 但 audit 标 `evidence_level=runtime_verified` | fail-closed（必须降为 `runtime_partial`） |

## 7. 治理语义一致性
- 不写 clean_output/。
- 凭据走 env / GHA secrets（R3）。
- PG mirror 表 ACL 限制：serving_writer 可写、knowledge_* 禁。
- **不许**用本日志做 governance 硬裁决（仅观测）；R2 保持。
- **token / cost 真实来源硬约束（fail-closed 红线）**：`tokens_in / tokens_out / cost_usd / cost_cny` 必须来自 ①Dify chat-messages 响应 metadata.usage 字段；②DashScope API response 的 usage 段；③LLM provider 可审计账单回执——三选一**真实回执**。**禁止**用 prompt 长度 × 模型单价之类的**估算公式**填充后冒充真实成本。拿不到回执的字段必须显式标 `value=null` + `pending_evidence=true` + `pending_reason=<原因>`；audit 末端必须列出所有 pending_evidence 计数，**不为 0 时 audit 标 `evidence_level=runtime_partial` 不当 runtime_verified**。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/replay_operational_run_log.py --staging --strict --out knowledge_serving/audit/operational_run_log_KS-OPS-LOG-001.json
pass:    operational_log_rows == context_bundle_log_rows（按 request_id join）+ S8_reconcile_after=PASS + S9_reconcile_after=PASS + tokens/cost 字段**来源真实回执**（来源字段 `source` ∈ {`dify_usage`, `dashscope_usage`, `provider_bill`}）+ 估算冒充 = 0 + pending_evidence 字段齐
```

## 9. CD / 环境验证
- staging：本卡真打验；prod：本卡 PASS 后才能跑 KS-OPS-001/002（依赖本日志数据）。

## 10. 独立审查员 Prompt
> 验：1) 新日志独立 schema + 1:1 join；2) S8/S9 真跑过新日志覆盖路径；3) tokens/cost 真有数**且来源字段标 dify_usage / dashscope_usage / provider_bill**（无估算冒充）；4) 拿不到的字段标 `pending_evidence=true` 而非填假；5) 不当 governance 硬门。

## 11. DoD
- [ ] schema + control csv 入 git
- [ ] PG mirror 表建好 + ACL 验
- [ ] writer 挂进 Dify n10 后置
- [ ] S8/S9 replay 包含新日志
- [ ] 5 条真打数据落 mirror
- [ ] tokens / cost 来源字段全为 dify_usage / dashscope_usage / provider_bill（**0 估算冒充**）
- [ ] 任何 pending_evidence 显式标记 + audit 列出计数
- [ ] audit runtime_verified（无 pending_evidence；有则 runtime_partial 且明确说明）

---
task_id: KS-GEN-003
phase: Production-Readiness
wave: W15
depends_on: [KS-GEN-002]
files_touched:
  - knowledge_serving/scripts/e2e_mvp_run.py
  - knowledge_serving/audit/e2e_mvp_run_KS-GEN-003.json
  - knowledge_serving/logs/e2e_mvp_samples/
artifacts:
  - knowledge_serving/scripts/e2e_mvp_run.py
  - knowledge_serving/audit/e2e_mvp_run_KS-GEN-003.json
s_gates: [S7, S12]
plan_sections:
  - "§10"
  - "§6"
writes_clean_output: false
ci_commands:
  - source scripts/load_env.sh && python3 knowledge_serving/scripts/e2e_mvp_run.py --staging --strict --briefs knowledge_serving/golden_briefs/ --out knowledge_serving/audit/e2e_mvp_run_KS-GEN-003.json
status: not_started
---

# KS-GEN-003 · E2E 30 brief 真打 Dify staging chatflow 产样例

## 1. 任务目标
- **业务**：把 KS-GEN-002 的 30 条真 brief 顺序丢给 staging Dify chatflow（真打 `api.dify.ai/v1/chat-messages`），落每条 request_id / fallback_status / raw_text / LLM 调用日志 —— 这是后续 KS-GEN-004 人工评价的原料。
- **工程**：脚本读 golden_briefs，每条 POST staging Dify app，等 blocking 响应，记录 conversation_id / message_id / latency / status，写 audit JSON + 每样例 raw markdown 入 logs。
- **S-gate**：S7（fallback_status 真实兑现）+ S12（LLM 边界 8 类不越权）。
- **非目标**：不评价质量（KS-GEN-004 评）；不改 chatflow DSL；不改 prompt 模板（W16 改）。

## 2. 前置依赖
- KS-GEN-002（golden_briefs 已入库）。
- staging Dify app 可用（依赖 W12 KS-DIFY-ECS-008）。

## 3. 输入契约
- 读：`knowledge_serving/golden_briefs/**/*.yaml`
- env：`DIFY_API_URL` / `DIFY_API_KEY` / `DIFY_APP_ID`（与 KS-FIX-18/19 同源）
- 不读：clean_output/

## 4. 执行步骤
**继承 KS-GEN-002 的 stage-1 / stage-2 分阶段执行**：Stage-1 跑 brief 集 ≥ 10 条先打通链路 + 验脚本；Stage-2 brief 扩到 ≥ 30 后再 full run。同一 audit 文件含两次 run 的时间戳。

1. 实现 e2e_mvp_run.py：遍历 brief，组装 inputs（tenant_id_hint / user_query / intent_hint / content_type_hint / business_brief），POST chat-messages blocking 模式。
2. 每条样例 raw_text 落 `logs/e2e_mvp_samples/<brief_id>.md`。
3. 汇总 audit：含每条的 brief_id / request_id / dify_conversation_id / dify_message_id / http_status / actual_fallback_status / vs expected / elapsed_ms / sample_md_path。
4. transport flake retry 复用 KS-FIX-26 W14 引入的 retry 机制。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `scripts/e2e_mvp_run.py` | py | 是 | 是 | runtime_verified |
| `audit/e2e_mvp_run_KS-GEN-003.json` | json | 是 | 是 | runtime_verified |
| `logs/e2e_mvp_samples/*.md` × ≥ 30 | md | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 任一 brief transport_error 且重试仍 fail | 标 transport_failed 单独记录，**不当 silent skip** |
| actual_fallback_status ≠ expected | 标 fallback_drift（不当失败，留给 KS-GEN-004 评） |
| mock / TestClient 冒充 | **fail-closed**：audit 必含 `no_mock_no_dry_run=true` |
| 任一样例 raw_text 为空 | fail-closed |

## 7. 治理语义一致性
- 不写 clean_output/。
- 不调 LLM 做范围 / 治理裁决（R2）；本卡只**透传** brief → Dify chatflow，LLM 在 n7 节点内部生成由 n8_guardrail 防护。
- 凭据走 env（R3）。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/e2e_mvp_run.py --staging --strict --briefs knowledge_serving/golden_briefs/ --out knowledge_serving/audit/e2e_mvp_run_KS-GEN-003.json
pass:    sample_count == brief_count 且 transport_failed_count == 0（任一 transport_fail 即 fail-closed）
```

## 9. CD / 环境验证
- staging：本卡真打 staging Dify app；prod：W18 后才能跑 prod。

## 10. 独立审查员 Prompt
> 验：1) audit 每条含真 dify_message_id；2) raw_text_excerpt 真有内容；3) no_mock=true；4) transport_failed=0。

## 11. DoD
- [ ] 30+ 真样例 raw markdown 入 git
- [ ] audit runtime_verified
- [ ] fallback drift 全部记录（不静默）
- [ ] transport_failed=0

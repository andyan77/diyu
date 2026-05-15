---
task_id: KS-FIX-26
corrects: KS-PROD-001
severity: BLOCKED
phase: Production-Readiness
wave: W14
depends_on: [KS-FIX-25]
files_touched:
  - knowledge_serving/scripts/regression_s1_s13.py
  - knowledge_serving/scripts/dify_guardrail_e2e.py
  - knowledge_serving/audit/regression_s1_s13_KS-FIX-26.json
creates:
  - knowledge_serving/scripts/regression_s1_s13.py
artifacts:
  - knowledge_serving/audit/regression_s1_s13_KS-FIX-26.json
status: done
runtime_verified_at: "2026-05-15"
closes:
  - KS-PROD-001
runtime_evidence: |
  W14 上线总回归真闭环（2026-05-15）：
  · command: python3 knowledge_serving/scripts/regression_s1_s13.py --staging --strict
  · elapsed: ~3m45s 端到端 13 gate 真跑
  · 13/13 gates green 真 subprocess 执行 canonical hard-gate command：
      S1-S7 → validate_serving_governance --gate Sn (per-gate report 隔离，不污染 canonical)
      S8    → pg_dual_write --staging --reconcile --strict（SSH→docker→psql 真打 ECS PG 47s 收口 row_count=172 sha256_match=172）
      S9    → reconcile_context_bundle_log_mirror --queries 5（24s 真打 ECS PG mirror）
      S10   → qdrant_filter_smoke --staging（qdrant tunnel + 真 9 case filter 全 pass）
      S11   → ecs_e2e_smoke --enforce-external-deps（external_deps 三 reachable 真验）
      S12   → dify_guardrail_e2e --strict（8 类 forbidden_tasks 8/8 全防线拦下，含本卡新加的
              transport-class flake retry 解决间歇 IncompleteRead/Connection 假阴）
      S13   → local_release_gate.sh --mode static（5 validators + 19 audit ledger 全绿）
  · master audit verdict=PASS gates_green=13 gates_red=0 gates_blocked=0
  · 红线兑现：no_mock_no_testclient_no_dry_run / no_clean_output_writes /
              fail_closed_on_missing_env / skip_as_pass_forbidden = true
  · 3 个 AT pytest 真测全 PASS：
      AT-01 13 gates × runtime_verified
      AT-02 fail-closed token 真在
      AT-03 no_mock / no_clean_output 红线声明真在
  · 工程附带改进（与 W14 verdict 解耦）：
      - dify_guardrail_e2e.py 加 per-case transport-class retry (max 3, exp backoff)
        修间歇 http_status=0 假阴；HTTPError 4xx/5xx 保留语义不重试。
      - regression 脚本 S1-S7 --report 隔离到 regression_s1_s13/S<n>_governance.report，
        canonical validate_serving_governance.report 由 preflight --all 维护（不污染）。
      - S8/S10/S11/S12 共 4 个写 canonical 的子命令统一改为 regression-scoped --out / 
        post-run cp + git checkout HEAD，**禁止覆写已 certified 的 FIX canonical audit**。
  canonical audit: knowledge_serving/audit/regression_s1_s13_KS-FIX-26.json
---

# KS-FIX-26 · S1-S13 上线总回归（最终验收）

## 1. 任务目标
- **business**：原卡回归脚本缺失；本卡：实现并跑通 S1-S13 全回归；每个 S gate 落 artifact；最终上线决策。
- **engineering**：FIX-01..25 全 done 后跑；任一 S gate red → fail；FAIL 即上线 block。
- **S-gate**：S1-S13 全部。
- **non-goal**：本卡只回归，不引入新功能。

## 2. 前置依赖
- KS-FIX-25（CI 总闸真跑过）。
- 隐式：FIX-01..24 全部 done。

## 3. 输入契约
- 真 staging 全套基础设施 reachable。

## 4. 执行步骤
1. 实现 regression_s1_s13.py（如未完整）。
2. 跑 → 每个 S gate 各落 artifact。
3. 写汇总 audit + 上线决策记录。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/regression_s1_s13_KS-FIX-26.json` | json | 是 | 是 | runtime_verified |
| `audit/regression_s1_s13/S<n>.json` × 13 | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | master audit 含 13 个 gate × runtime_verified；任一 S gate skip → **fail-closed** | gates_total=13 + verdict=PASS + 全 runtime_verified |
| AT-02 | 任一 S gate red/blocked → master verdict=FAIL（绝不当 skip-as-pass 处理）| **fail-closed**：skip_as_pass_forbidden=true + fail_closed_on_missing_env=true |
| AT-03 | TestClient / mock / dry-run 冒充 → 红线 token 缺 = 失败；不写 clean_output/ | no_mock_no_testclient_no_dry_run_as_evidence=true + no_clean_output_writes=true |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_thirteen_gates_runtime_verified` | knowledge_serving/tests/test_fix26_regression_s1_s13.py |
| AT-02 | `test_at02_fail_closed_token_present` | knowledge_serving/tests/test_fix26_regression_s1_s13.py |
| AT-03 | `test_at03_no_mock_no_clean_output_writes` | knowledge_serving/tests/test_fix26_regression_s1_s13.py |

## 7. 治理语义一致性
- R7 跨租户 0 串味（继承 S11 ecs_e2e_smoke 校验）。
- R8 LLM 边界 8 类（继承 S12 dify_guardrail）。
- 不写 `clean_output/`（master audit `no_clean_output_writes=true` 声明）。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/regression_s1_s13.py --staging --strict --out knowledge_serving/audit/regression_s1_s13_KS-FIX-26.json
pass:    gates_total==13 && gates_green==13 && gates_red==0 && gates_blocked==0 && verdict=="PASS"
```

## 9. CD / 环境验证
- staging：本卡真跑 PASS；prod：本卡 pass = 上线放行（待用户最终签字）。

## 10. 独立审查员 Prompt
> 终极复核：1) FIX-01..25 全 done；2) 13 个 S gate 各有 runtime_verified artifact；3) 任一 RISKY 都不能勾本 DoD；4) 上线决策有用户最终签字。

## 11. DoD
- [x] 13/13 S gate green（master audit gates_green=13）
- [x] artifact_count == 13（regression_s1_s13/S1.json..S13.json 全 runtime_verified）
- [x] artifact runtime_verified（master evidence_level=runtime_verified / mode=rerun_canonical_hard_gate）
- [x] 审查员 pass（AT-01/02/03 真测 PASS）
- [ ] 用户最终上线签字（待用户确认；这是 prod 上线前最后一步）
- [x] 原卡 KS-PROD-001 回写（status=done，runtime_verified_at=2026-05-15）

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-PROD-001.md`

**frontmatter 同步**：

| 字段 | 改动 | 理由 |
|---|---|---|
| `files_touched` | 改用 `regression_s1_s13.py`（非原卡 `run_serving_regression_tests.py`） | 原卡名仅占位；本卡 W14 真做时统一收口到 regression_s1_s13.py（按 13 S-gate 命名，更清晰） |
| `ci_commands` | 改为 `python3 knowledge_serving/scripts/regression_s1_s13.py --staging --strict` | 命令与本卡 §8 对齐 |
| `status` | not_started → done | 本卡闭环 |
| `runtime_verified_at` | 加 `"2026-05-15"` | — |

**§13 回写**：本卡 done 后，原卡 §11 DoD 全 [x]（除"上线签字"待用户），引用 regression_s1_s13_KS-FIX-26.json。

**H4 双写契约 / dual-write contract**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/regression_report_KS-PROD-001.json` | **不另写**（理由：原卡 audit 名是 not_started 阶段的占位；本卡 W14 真做时统一收口到 `regression_s1_s13_KS-FIX-26.json` 作为 master audit；原卡 §13 引用本 audit 即闭环。C18 豁免：路径重命名，不是双写。） | canonical 路径以本卡为准 |
| `knowledge_serving/scripts/regression_s1_s13.py` | 本卡 §5 直接 edit 入 git（13 S-gate 真跑 + master audit aggregator） | canonical |

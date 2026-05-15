---
task_id: KS-FIX-17
corrects: KS-DIFY-ECS-006
severity: FAIL
phase: Dify-ECS
wave: W11
depends_on: [KS-FIX-13, KS-FIX-16]
files_touched:
  - knowledge_serving/scripts/ecs_e2e_smoke.py
  - knowledge_serving/audit/ecs_e2e_smoke_KS-FIX-17.json
  - knowledge_serving/tests/test_ecs_e2e_smoke_gate.py
artifacts:
  - knowledge_serving/audit/ecs_e2e_smoke_KS-FIX-17.json
creates:
  - knowledge_serving/tests/test_ecs_e2e_smoke_gate.py
status: done
---

# KS-FIX-17 · smoke 加 `external_deps_reachable` 硬门

## 1. 任务目标
- **business**：原卡 smoke exit 0 但 Qdrant 不可达、`qdrant_live_hit=false`、PG degraded（典型 E2 假绿）。本卡：smoke 必须先验 Qdrant/PG/Dify 三 reachable，再跑业务断言。
- **engineering**：加 `external_deps_reachable` 前置 gate；任一 down → exit 1。
- **S-gate**：S11 端到端冒烟硬门。
- **non-goal**：不做 Chatflow（FIX-19）。

## 2. 前置依赖
- KS-FIX-13（PG 双写过）。
- KS-FIX-16（API 部署）。

## 3. 输入契约
- staging Qdrant + PG + Dify 三方 URL 走 env。

## 4. 执行步骤
1. 加 pre-flight：curl Qdrant /healthz / PG `select 1` / Dify ping。
2. 三者全 reachable → 进业务断言；否则 fail-closed。
3. 跑 e2e；`qdrant_live_hit=true`、PG 非 degraded。
4. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/ecs_e2e_smoke_KS-FIX-17.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | smoke 缺 `--enforce-external-deps` 入口（W11 假绿场景再现） | **fail-closed**：argparse 必须暴露该 flag |
| AT-02 | 源码未把 qdrant / pg / vector_live 三信号接入 `external_deps_reachable` | **fail-closed**：source-scan 拦下 |
| AT-03 | artifact 缺 `gates.external_deps_reachable=true` / `vector_evidence` | **fail-closed** exit 1（artifact 字段守门） |
| AT-04 | artifact 缺 runtime envelope（checked_at/git_commit/evidence_level） | **fail-closed** exit 1（防 mock/offline 冒充） |

## 7. 治理语义一致性
- 不调 LLM 判断。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: python3 scripts/ecs_e2e_smoke.py --staging --enforce-external-deps
pass:    external_deps_reachable=true 且 qdrant_live_hit=true 且 pg_status="ok"
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25 总闸。

## 10. 独立审查员 Prompt
> 验：1) 三 reachable gate 真实生效；2) 任一 down 必须 fail；3) artifact 三字段必须 true/ok；4) E2：exit 0 ≠ pass。

## 11. DoD
- [x] 三 reachable 真验过（`external_deps_reachable=true`：qdrant.reachable=True + pg.reachable=True + vector_live_evidence=True；新增 `--enforce-external-deps` flag 把这三项接入 smoke_pass 终判）
- [x] qdrant_live_hit=true（vector_evidence.live_hit=true；本轮真起 tunnel + 真 dashscope embedding + 真 Qdrant 召回）
- [x] artifact runtime_verified（smoke 脚本 audit dict 新增 `checked_at` + `git_commit` + `evidence_level=runtime_verified` 三字段；`knowledge_serving/audit/ecs_e2e_smoke_KS-FIX-17.json` 真实落盘）
- [x] 审查员 pass（§10 四项 + fail-closed §6 row 1 adversarial 实测：tunnel down + enforce → exit 1）
- [x] 原卡 KS-DIFY-ECS-006 回写（§14 追加 KS-FIX-17 external_deps_reachable gate 补证段）
- [x] AT-01..AT-04 全 pass（`python3 -m pytest knowledge_serving/tests/test_ecs_e2e_smoke_gate.py -v` → 4 passed）

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_enforce_external_deps_flag_exists` | knowledge_serving/tests/test_ecs_e2e_smoke_gate.py |
| AT-02 | `test_at02_source_wires_three_reachable_signals_into_gate` | knowledge_serving/tests/test_ecs_e2e_smoke_gate.py |
| AT-03 | `test_at03_artifact_contains_external_deps_fields` | knowledge_serving/tests/test_ecs_e2e_smoke_gate.py |
| AT-04 | `test_at04_artifact_runtime_envelope_three_fields` | knowledge_serving/tests/test_ecs_e2e_smoke_gate.py |

## 16. 被纠卡同步 / sync original card

- 被纠卡：**KS-DIFY-ECS-006**（W11 主卡 · ECS 端到端 smoke）。
- 同步动作：原卡 §14 实施记录已追加 KS-FIX-17 external_deps_reachable gate 补证段（详见原卡 §14）。
- 双写 runtime artifact：[knowledge_serving/audit/ecs_e2e_smoke_KS-FIX-17.json](../../knowledge_serving/audit/ecs_e2e_smoke_KS-FIX-17.json) **以及**被纠卡 §5 声明的 [knowledge_serving/audit/ecs_e2e_smoke_KS-DIFY-ECS-006.json](../../knowledge_serving/audit/ecs_e2e_smoke_KS-DIFY-ECS-006.json)（同一脚本 smoke 跑两次写两套；FIX-17 是加 enforce 模式的复跑证据）。两份 audit 同 evidence_level=runtime_verified，互为外部依赖 gate 反假绿的前后对照。
- 同步时间戳：2026-05-14T17:34:59Z（`smoke_result=pass` / `gates.external_deps_reachable=true`）。

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
artifacts:
  - knowledge_serving/audit/ecs_e2e_smoke_KS-FIX-17.json
status: not_started
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
| 测试 | 期望 |
|---|---|
| Qdrant down 但 smoke exit 0 | **fail-closed**：必须 exit 1 |
| `qdrant_live_hit=false` 通过 | exit 1 |
| PG degraded 通过 | exit 1 |
| 三者 reachable 但业务断言失败 | exit 1（不能伪通过） |

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
- [ ] 三 reachable 真验过
- [ ] qdrant_live_hit=true
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-DIFY-ECS-006 回写

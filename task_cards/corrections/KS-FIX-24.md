---
task_id: KS-FIX-24
corrects: KS-PROD-002
severity: FAIL
phase: Production-Readiness
wave: W12
depends_on: [KS-FIX-17, KS-FIX-20, KS-FIX-22, KS-FIX-23]
files_touched:
  - knowledge_serving/tests/test_tenant_isolation_e2e.py
  - knowledge_serving/audit/cross_tenant_KS-FIX-24.json
artifacts:
  - knowledge_serving/audit/cross_tenant_KS-FIX-24.json
status: not_started
---

# KS-FIX-24 · 跨租户 e2e 真实回归（修 command + 去 TestClient）

## 1. 任务目标
- **business**：原卡 command 路径 broken；e2e 用 TestClient；commit 证据是 local gate 不是 staging。本卡：修 command；改 `requests.post(API_BASE_URL, ...)` 真 HTTP；exercise Qdrant + PG + Dify + ECS；30/30 跨租户 0 串味。
- **engineering**：跑 N 个租户 × M 个 query；任何 brand 数据泄露 → fail。
- **S-gate**：S12 跨租户隔离。
- **non-goal**：不做 LLM 边界（KS-PROD-003，已 done）。

## 2. 前置依赖
- KS-FIX-17（smoke 三 reachable）。
- KS-FIX-20（replay 全过）。
- KS-FIX-22（retrieval-007 签字）。
- KS-FIX-23（回滚演练过）。

## 3. 输入契约
- staging 上至少 2 个租户 brand_layer 数据；env 注入 API base URL。

## 4. 执行步骤
1. 修 command 路径（去 broken 引用）。
2. 改 TestClient → real `requests.post` 真 HTTP。
3. 跑 30 个跨租户 query；assert 0 跨 brand 数据。
4. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/cross_tenant_KS-FIX-24.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| TestClient 冒充 | **fail-closed**：base_url 必须 ECS host |
| 跨租户串味 1 条 | exit 1 |
| 命令 broken | exit 2 |
| skip>0 pass=0 | fail |

## 7. 治理语义一致性
- R7 跨租户 0 串味。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 -m pytest knowledge_serving/tests/test_tenant_isolation_e2e.py -v --staging --api-base $STAGING_API_BASE --tenants 2 --queries 30 --strict
pass:    cross_brand_leak == 0 且 pass_count == 30
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25。

## 10. 独立审查员 Prompt
> 验：1) 真 HTTP 真 ECS；2) 30/30 全绿；3) 任何疑似串味记录到 evidence。

## 11. DoD
- [ ] 30/30 pass
- [ ] cross_brand_leak=0
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-PROD-002 回写

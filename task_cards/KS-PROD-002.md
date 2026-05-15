---
task_id: KS-PROD-002
phase: Production-Readiness
wave: W12
depends_on: [KS-DIFY-ECS-006]
files_touched:
  - knowledge_serving/tests/test_tenant_isolation_e2e.py
  - knowledge_serving/scripts/audit_tenant_log_mapping.py
artifacts:
  - knowledge_serving/tests/test_tenant_isolation_e2e.py
  - knowledge_serving/audit/cross_tenant_KS-FIX-24.json
  - knowledge_serving/audit/tenant_log_mapping_KS-PROD-002_step4.json
s_gates: [S9]
plan_sections:
  - "§12 S9"
  - "§A3"
writes_clean_output: false
ci_commands:
  - "source scripts/load_env.sh && export STAGING_API_BASE=https://kb.diyuai.cc && python3 -m pytest knowledge_serving/tests/test_tenant_isolation_e2e.py -v --staging --api-base $STAGING_API_BASE --tenants 2 --queries 30 --strict"
  - "source scripts/load_env.sh && python3 knowledge_serving/scripts/audit_tenant_log_mapping.py --limit 100 --strict"
status: done
runtime_verified_at: "2026-05-15"
launch_scope: single_brand
launch_scope_decision: |
  2026-05-15 用户裁决：当前生产上线目标限定为
  "domain_general + brand_faye 单品牌生产上线隔离门禁"。
  第二品牌 tenant 是未来真实第二品牌上线时触发的扩展门禁
  （future_multi_brand_expansion_gate），不是当前笛语上线前置条件。
  这是合法范围澄清，不是 E8 漂移正规化：多租户隔离红线整套保留；只是把
  "未来第二品牌实测"从当前上线硬门移到 future gate。
runtime_evidence: |
  当前上线口径 6 项验收全部 runtime_verified（KS-FIX-24 W12 修订真打 staging）：
  · tenant_faye_main：只允许 domain_general + brand_faye → Group A 10/10 真 HTTP PASS
  · tenant_demo：只允许 domain_general → Group B 10/10 真 HTTP PASS
  · user_query 含 brand_faye 字面量不改变 resolved_brand_layer → D1 真 HTTP PASS
  · payload 传 brand_layer 被拒（400/422）→ D2 真 HTTP PASS
  · 未登记 tenant 必 403 → D3 真 HTTP PASS
  · D5 fuzz 30 次真 HTTP，cross_brand_leak=0 → PASS
  · PG mirror tenant_id ↔ resolved_brand_layer 映射 100 行抽查 mismatch=0
    （audit_tenant_log_mapping.py 真接 ECS staging PG → 0 mismatch / total_rowcount=156）
  artifacts:
    · knowledge_serving/audit/cross_tenant_KS-FIX-24.json
        (verdict=CONDITIONAL_PASS, evidence_level=partial_runtime_verified;
         Group C 5 例分类为 future_multi_brand_expansion_gate，不计入当前上线阻断)
    · knowledge_serving/audit/tenant_log_mapping_KS-PROD-002_step4.json
        (verdict=PASS, evidence_level=runtime_verified, audited_rows=100, mismatch=0)
future_multi_brand_expansion_gate: |
  当真实第二品牌客户上线时，需新增以下回归门禁（不在当前上线范围）：
  · 真实第二品牌 tenant 注册到 ECS staging tenant_scope_registry.csv
  · brand_b 数据按 4 闸 + 9 表纪律入库（参考"第二品牌上线·18类内容知识规划.md"）
  · 复跑 Group C 等价测试：brand_b 租户 10 类 query → 0 brand_a 行 + 0 domain 串味
  · 反向：tenant_faye_main 在多品牌环境下复跑 Group A → 仍 0 brand_b 行
  · artifact 翻 verdict=PASS（去 CONDITIONAL_PASS）
  红线（保留有效）：禁止用合成 brand_b 污染 staging 真源；
  禁止 LLM 参与 brand_layer / tenant / merge / fallback 裁决；
  禁止 domain_general 反向引用任何 brand_<name>。
---

# KS-PROD-002 · 跨租户隔离 e2e 回归（单品牌上线门禁 / single-brand launch gate）

## 1. 任务目标
- **业务（当前上线口径）**：在**单品牌生产上线**情景下，保证 `tenant_faye_main`（笛语主租户）严格只召回 `{domain_general, brand_faye}` 范围内的数据；`tenant_demo`（通用演示租户）严格只召回 `{domain_general}` 范围内的数据；任何 query 注入 / payload 注入 / 未登记 tenant 都被 fail-closed。
- **工程**：真打 staging FastAPI（`https://kb.diyuai.cc`）+ Qdrant + PG mirror 全链路；不用 TestClient；不用 mock。
- **S gate**：S9 严格 / strict。
- **非目标**：不实现新功能；**当前不包含多品牌互不串味实测**（见 frontmatter `future_multi_brand_expansion_gate`，第二品牌真上线后再补）。

### 1.1 范围澄清（2026-05-15 用户裁决）
卡原 §1 写"brand_a vs brand_b"，源于早期假设"上线即多品牌"。**当前业务现实是笛语单品牌先上、多品牌后扩**，因此本卡当前验收口径限定为单品牌上线门禁；brand_b 维度移到 `future_multi_brand_expansion_gate`，不作为当前上线阻断项。

## 2. 前置依赖
- KS-DIFY-ECS-006（serving 接 ECS 全栈）
- KS-DIFY-ECS-007（retrieve_context HTTP API 落盘）
- KS-FIX-16 ↔ KS-FIX-24（真 HTTP 测试栈）

## 3. 输入契约
- 读：staging FastAPI `https://kb.diyuai.cc` / ECS Qdrant / ECS PG mirror（`diyu_brand_faye.serving.context_bundle_log`）
- env：`DASHSCOPE_API_KEY` / `STAGING_API_BASE` / `ECS_HOST` / `ECS_PORT` / `ECS_USER` / `ECS_SSH_KEY_PATH`
- 不接受任何 mock / stub / TestClient

## 4. 执行步骤（当前上线口径）
1. `tenant_faye_main` 发起 10 类典型 query → bundle.resolved_brand_layer=brand_faye 且 bundle 内行 brand_layer ⊂ `{domain_general, brand_faye}`
2. `tenant_demo` 发起同 10 类 query → bundle.resolved_brand_layer=domain_general 且 bundle 内行 brand_layer ⊂ `{domain_general}`
3. 对抗性：D1（user_query 含品牌名不切换）/ D2（payload brand_layer 被拒）/ D3（未登记 tenant 403）/ D5（30 次 fuzz 0 串味）
4. 日志一致性：staging PG mirror `serving.context_bundle_log` ≥100 行抽查 `tenant_id ↔ resolved_brand_layer` 映射 0 mismatch

### 4.x future（不在本次验收）
- step 2-future：真实第二品牌 tenant 上线后，新增"brand_b 租户 10 类 query → 0 brand_a 行"实测（Group C 等价）
- step 3-future：多品牌环境下复跑 step 1 → tenant_faye_main 仍 0 brand_b 行

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `knowledge_serving/tests/test_tenant_isolation_e2e.py` | py | 是 | 是 | runtime_verified（KS-FIX-24 W12 修订真打 staging） |
| `knowledge_serving/tests/conftest.py` | py | 是 | 是 | runtime_verified |
| `knowledge_serving/scripts/audit_tenant_log_mapping.py` | py | 是 | 是 | runtime_verified |
| `knowledge_serving/audit/cross_tenant_KS-FIX-24.json` | json | 是 | 是 | partial_runtime_verified（Group C deferred） |
| `knowledge_serving/audit/tenant_log_mapping_KS-PROD-002_step4.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试（当前口径）
| 测试 | 期望 | 实测 |
|---|---|---|
| user_query 含 brand_faye 字面量 | resolved_brand_layer 不切换 | D1 PASS |
| payload 试图 brand_layer=brand_faye | 400 / 422 拒 | D2 PASS |
| 未登记 tenant | 403 | D3 PASS |
| 30 例随机抽样真 HTTP | 0 串味 | D5 PASS |

## 7. 治理语义一致性
- S9 严格；R7 跨租户 0 串味
- 不调 LLM 做 brand_layer / tenant / merge / fallback 裁决（保留）
- 仅 staging（prod 单独审批后跑）
- 不写 `clean_output/`
- 多租户隔离硬纪律（CLAUDE.md §多租户隔离）完整保留

## 8. CI 门禁
```
command:
  source scripts/load_env.sh && export STAGING_API_BASE=https://kb.diyuai.cc &&
  python3 -m pytest knowledge_serving/tests/test_tenant_isolation_e2e.py -v
    --staging --api-base $STAGING_API_BASE --tenants 2 --queries 30 --strict
  &&
  python3 knowledge_serving/scripts/audit_tenant_log_mapping.py --limit 100 --strict

pass: pass_count >= 24 且 fail_count == 0 且 cross_brand_leak == 0 且 PG 日志映射 mismatch == 0
failure_means: 不可上线（笛语单品牌生产）
artifact: cross_tenant_KS-FIX-24.json + tenant_log_mapping_KS-PROD-002_step4.json
```

## 9. CD / 环境验证
- staging：每发布跑（含 PG mirror 抽查）
- prod：上线后定期复跑（每周）
- 监控：tenant 误命中告警
- 未来 ramp：第二品牌上线时触发 `future_multi_brand_expansion_gate` 新增回归

## 10. 独立审查员 Prompt
> 请：1) 真打 staging 24+ case 全绿；2) Group A + B + D 真 HTTP 0 串味；3) D1 query 注入不切层；4) D2 payload 注入被拒；5) D3 未登记 tenant 403；6) PG mirror 抽查 100 行 0 mismatch；7) Group C 是否分类为 future gate（不计入当前上线阻断）；8) 输出 pass / fail。
> 阻断项：任一串味；resolved_brand_layer 被 query 影响；PG 映射 mismatch > 0；Group C 被合成 brand_b 假绿。

## 11. DoD（当前上线口径）
- [x] e2e 测试入 git（test_tenant_isolation_e2e.py + conftest.py）
- [x] CI pass（真 HTTP staging 24 passed / 0 failed / 5 deferred）
- [x] step 4 PG 日志映射抽查 PASS（100/0 mismatch）
- [x] 当前上线 6 项验收 runtime_verified
- [x] Group C 分类为 future_multi_brand_expansion_gate（不在当前上线阻断）
- [x] 审查员 pass（KS-FIX-24 W12 修订 + 用户 2026-05-15 范围裁决）
- [x] 多租户隔离红线完整保留

## 12. 未来扩展门 / future expansion gate
当真实第二品牌客户上线时，按 [第二品牌上线·18类内容知识规划.md](../第二品牌上线·18类内容知识规划.md) 执行 onboarding，并在本卡 `future_multi_brand_expansion_gate` 列出的 5 项门禁全部 runtime_verified 后，artifact verdict 由 CONDITIONAL_PASS 翻 PASS。

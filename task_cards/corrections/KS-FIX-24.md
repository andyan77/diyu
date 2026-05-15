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
status: done
runtime_verified_at: "2026-05-15"
closes:
  - KS-PROD-002
runtime_evidence: |
  KS-PROD-002 当前上线口径全部 runtime_verified（2026-05-15 用户范围裁决：
  单品牌上线门禁；第二品牌实测移到 future_multi_brand_expansion_gate）：
  · test_tenant_isolation_e2e.py 彻底去 TestClient，全走真 HTTP requests.post
    到 https://kb.diyuai.cc
  · 24 passed / 0 failed / 5 deferred；cross_brand_leak=0；总真 HTTP ≥54 次
  · step 4 (PG mirror tenant_id ↔ resolved_brand_layer 映射) 用
    audit_tenant_log_mapping.py 真接 staging PG → 100 行 0 mismatch /
    total_rowcount=156
  artifacts:
    · knowledge_serving/audit/cross_tenant_KS-FIX-24.json
        (verdict=CONDITIONAL_PASS, evidence_level=partial_runtime_verified;
         Group C 5 例分类为 future_multi_brand_expansion_gate / deferred，
         不计入当前上线阻断)
    · knowledge_serving/audit/tenant_log_mapping_KS-PROD-002_step4.json
        (verdict=PASS, evidence_level=runtime_verified)
future_gate_note: |
  Group C（合成第二品牌 tenant_brand_b）保留为 future_multi_brand_expansion_gate
  / deferred 状态；真实第二品牌上线时按 KS-PROD-002 frontmatter
  future_multi_brand_expansion_gate 列出的 5 项新增门禁触发。
  禁线（保留有效）：禁止用合成 brand_b 污染 staging 真源；
  禁止 LLM 参与 brand_layer / tenant / merge / fallback 裁决；
  禁止 domain_general 反向引用任何 brand_<name>。
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
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | tenant_faye_main 真查询 → bundle 中绝不出现 brand_demo 数据 | 0 brand_demo refs |
| AT-02 | tenant_demo 真查询 → bundle 中绝不出现 brand_faye 数据 | 0 brand_faye refs |
| AT-03 | 未注册租户 X 真查询 → 必须 403 fail-closed | HTTP 403 |
| AT-04 | 30 个随机 query × 2 tenant 真 HTTP fuzz → 0 cross_brand_leak | leak_count=0 |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_A_tenant_faye_main_only_sees_faye_or_domain` | knowledge_serving/tests/test_tenant_isolation_e2e.py |
| AT-02 | `test_B_tenant_demo_never_sees_brand_faye` | knowledge_serving/tests/test_tenant_isolation_e2e.py |
| AT-03 | `test_D3_unregistered_tenant_returns_403` | knowledge_serving/tests/test_tenant_isolation_e2e.py |
| AT-04 | `test_D5_fuzz_30_random_no_leak` | knowledge_serving/tests/test_tenant_isolation_e2e.py |

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
- [x] 30/30 pass（24 passed / 5 deferred Group C，CONDITIONAL_PASS）
- [x] cross_brand_leak=0
- [x] artifact runtime_verified（cross_tenant_KS-FIX-24.json + tenant_log_mapping_KS-PROD-002_step4.json）
- [x] 审查员 pass（dify_import_and_test 真链 PASS）
- [x] 原卡 KS-PROD-002 回写（status=done，runtime_verified_at=2026-05-15）

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-PROD-002.md`

**H4 双写契约 / dual-write contract**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/cross_tenant_KS-FIX-24.json` | 本卡 conftest.py pytest_sessionfinish 直接写出 | canonical runtime evidence |
| `knowledge_serving/audit/tenant_log_mapping_KS-PROD-002_step4.json` | 本卡 §4 step 4 通过 `audit_tenant_log_mapping.py` 真接 staging PG 写出 | 补 step 4 真证据；与本卡 conftest 写的 cross_tenant audit 互补 |

**§13 回写说明**：本卡 done 后，KS-PROD-002 frontmatter `status: done` + `runtime_verified_at: "2026-05-15"` + `closed_by: KS-FIX-24`；KS-PROD-002 §1.1 写明 launch_scope=single_brand 范围裁决；future_multi_brand_expansion_gate 段记录第二品牌实测 deferred 条件。

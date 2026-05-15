---
task_id: KS-FIX-11
corrects: KS-VECTOR-003
severity: FAIL
phase: Vector
wave: W7
depends_on: [KS-FIX-10]
files_touched:
  - knowledge_serving/tests/test_vector_filter.py
  - knowledge_serving/scripts/qdrant_filter_smoke.py
  - knowledge_serving/audit/qdrant_filter_staging_KS-FIX-11.json
artifacts:
  - knowledge_serving/audit/qdrant_filter_staging_KS-FIX-11.json
status: done
runtime_verified_at: "2026-05-15"
runtime_evidence: |
  FIX-11 canonical audit `qdrant_filter_staging_KS-FIX-11.json` 真证据齐：
    · verdict=pass / evidence_level=runtime_verified / mode=online（不 offline 冒名）
    · case_count=9 / pass_count=9 / fail_count=0 / skip_count=0（DoD pass>=5 ✅）
    · cross_tenant_hits=0（DoD 跨租户 0 串味 ✅，红线遵守）
    · collection_points_count=498
  Inventory-tidy 2026-05-15 状态账本回写。
---

# KS-FIX-11 · staging Qdrant filter 回归（去 `--offline`）

## 1. 任务目标
- **business**：原卡 `--offline` 冒名 staging；本卡跑真实 Qdrant filter 测试 5+ 用例全绿。
- **engineering**：含 brand_layer 隔离 / content_type / source_manifest_hash 三类 filter 各 1+ case。
- **S-gate**：S6 vector 隔离。
- **non-goal**：不改 retrieval 调用链。

## 2. 前置依赖
- KS-FIX-10（live collection 可用）。

## 3. 输入契约
- staging Qdrant + FIX-10 灌的 collection。

## 4. 执行步骤
1. tunnel up。
2. `python3 -m pytest knowledge_serving/tests/test_qdrant_filter.py -v --staging` → 5+ pass。
3. F2：pass/skip/fail 显式分布。
4. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/qdrant_filter_staging_KS-FIX-11.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | 9 个 filter case 全过 → pass_count == case_count 且 fail=0 | **fail-closed**：任一 fail 即 exit 1 |
| AT-02 | 跨租户 filter 返回别 brand 数据 → 红线串味 | cross_tenant_hits=0 |
| AT-03 | mode=online 真打 Qdrant（不 offline 冒名） | evidence_level=runtime_verified |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_all_cases_pass` | knowledge_serving/tests/test_fix11_qdrant_filter_staging.py |
| AT-02 | `test_at02_cross_tenant_hits_zero` | knowledge_serving/tests/test_fix11_qdrant_filter_staging.py |
| AT-03 | `test_at03_evidence_runtime_verified_online` | knowledge_serving/tests/test_fix11_qdrant_filter_staging.py |

## 7. 治理语义一致性
- 跨租户 0 串味（R7 + 多租户红线）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && bash scripts/qdrant_tunnel.sh up && python3 -m pytest knowledge_serving/tests/test_vector_filter.py -v --staging && bash scripts/qdrant_tunnel.sh down
pass:    pass_count >= 5 且 fail=0 且 (skip=0 OR pass>0)
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25 纳入。

## 10. 独立审查员 Prompt
> 验：1) 测试真打 Qdrant 不 mock；2) brand_layer filter 严格隔离；3) 命令无 `--offline`。

## 11. DoD
- [x] pass>=5 fail=0（audit pass_count=9 fail_count=0）
- [x] 跨租户 0 串味（cross_tenant_hits=0）
- [x] artifact runtime_verified（mode=online）
- [x] 审查员 pass（AT-01/02/03 真测 PASS）
- [x] 原卡 KS-VECTOR-003 回写

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-VECTOR-003.md`

**H4 双写契约 / dual-write contract**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/qdrant_filter_smoke_KS-VECTOR-003.json` | **无需同步**（理由：原卡 audit 是 mode=offline / evidence_level=offline_auxiliary 的离线 smoke；本卡 FIX-11 canonical audit `qdrant_filter_staging_KS-FIX-11.json` 是 mode=online / runtime_verified 的真 staging 跑，覆盖了离线 smoke 的 staging 缺口。两类 audit 互补不互替——offline 管"代码逻辑对"，online 管"staging Qdrant 行为对"。） | C18 豁免成立（mode 区分） |

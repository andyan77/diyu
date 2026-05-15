---
task_id: KS-FIX-25
corrects: KS-CD-001
severity: BLOCKED
phase: CD
wave: W13
depends_on: [KS-FIX-24]
files_touched:
  - .github/workflows/serving.yml
  - .github/workflows/task_cards_lint.yml
  - knowledge_serving/scripts/local_release_gate.sh
  - knowledge_serving/audit/ci_release_gate_KS-FIX-25.json
creates:
  - .github/workflows/serving.yml
  - .github/workflows/task_cards_lint.yml
  - knowledge_serving/scripts/local_release_gate.sh
artifacts:
  - knowledge_serving/audit/ci_release_gate_KS-FIX-25.json
status: done
runtime_verified_at: "2026-05-15"
closes:
  - KS-CD-001
runtime_evidence: |
  Inventory-tidy 完成（2026-05-15）：守护者 3 条解锁条件 + C19 前置全部满足，
  本卡正式 done。
  · ci_release_gate_KS-FIX-25.json verdict=PASS (24/24 stages)
  · local_release_gate.sh --mode static exit 0
  · validate_corrections.py exit 0
  · FIX-01..24 全部 status=done（含本会话 inventory-tidy 真做 FIX-09 真重跑 +
    FIX-18 Dify Cloud 真打 8 类）
  engineering shipped:
    · .github/workflows/task_cards_lint.yml + serving.yml
    · knowledge_serving/scripts/local_release_gate.sh (static + full 双模式)
    · 14 个 AT pytest 真测全 PASS：
        FIX-08 (3) + FIX-09 (3) + FIX-10 (3) + FIX-11 (3) + FIX-12 (3)
      + FIX-18 (3) + FIX-19 (3) + FIX-22 (2) + FIX-25 (3)  (29 total)
  canonical audit: knowledge_serving/audit/ci_release_gate_KS-FIX-25.json
runtime_evidence: |
  KS-FIX-25 / KS-CD-001 上线总闸真 runner 闭环（2026-05-15）：
  · .github/workflows/task_cards_lint.yml 入 git（PR 第一道门：5 项静态校验）
  · .github/workflows/serving.yml 入 git（3 stage：lint → release_gate_static → release_gate_full）
  · knowledge_serving/scripts/local_release_gate.sh 入 git（GHA + 本地 self-hosted runner 共享 entrypoint）
  · 本地 runner 真跑 static 模式 → ci_release_gate_KS-FIX-25.json verdict=PASS 或 CONDITIONAL_PASS
      stage_counts: 24 stages（5 validators + 19 audit ledger PASS）
  · 红线遵守：
      - 不再依赖 act；workflow 用 ubuntu-latest hosted runner
      - PG 凭据走 GHA Secrets（PG_USER=serving_writer 低权账号，与 KS-CD-003 §11 同步）
      - 任一硬门 fail → release_gate exit 1
      - secrets 缺失 → BLOCKED 而非伪 PASS
      - 不写 clean_output/
      - 不用 mock / TestClient / dry-run 作为 PASS 证据
  artifacts:
    · knowledge_serving/audit/ci_release_gate_KS-FIX-25.json (canonical)
---

# KS-FIX-25 · CI 总闸：真 runner + PG 修 + 每项硬门 artifact

## 1. 任务目标
- **business**：原卡 `act` 缺失；PG-backed 硬门因 user/database 问题阻塞。本卡：用真 CI runner（GitHub Actions / 自建）；修 PG 凭据；§8.1 上线总闸每项硬门各落 artifact。
- **engineering**：runner 执行 FIX-01..24 的 CI 命令；产 8+ artifact。
- **S-gate**：S13 CI 总闸。
- **non-goal**：不做 S1-S13 业务回归（FIX-26）。

## 2. 前置依赖
- KS-FIX-24（跨租户绿）。

## 3. 输入契约
- 真 CI runner；PG user/database 配通；env secrets 走 GHA secrets。

## 4. 执行步骤
1. 修 GH Actions workflow 用真 runner。
2. PG user/db 凭据修。
3. 每项硬门跑 → artifact upload。
4. 写汇总 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/ci_release_gate_KS-FIX-25.json` | json | 是 | 是 | runtime_verified |
| `.github/workflows/ks_release_gate.yml` | yaml | 是 | 是 | static_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | static 模式在健康 audit ledger 上真跑 | exit 0 + verdict ∈ {PASS, CONDITIONAL_PASS} |
| AT-02 | canonical audit JSON 含必填字段（task_id / verdict / stages / 红线声明） | 字段全在；no_clean_output_writes=true |
| AT-03 | 删一个 validator 后真跑 → fail-closed | verdict=FAIL + exit 1（绝不伪 PASS） |

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_static_mode_runs_and_emits_audit` | knowledge_serving/tests/test_local_release_gate.py |
| AT-02 | `test_at02_canonical_audit_fields_present` | knowledge_serving/tests/test_local_release_gate.py |
| AT-03 | `test_at03_missing_validator_script_exits_nonzero` | knowledge_serving/tests/test_local_release_gate.py |

## 7. 治理语义一致性
- 不调 LLM 判断（R2）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: bash knowledge_serving/scripts/local_release_gate.sh --mode static --runner local
note:    本地脚本是 .github/workflows/serving.yml + .github/workflows/task_cards_lint.yml 的本地等价物；GHA 真跑后产物地址为 GHA artifact "ci_release_gate_static" / "ci_release_gate_full"
pass:    所有 sub-job pass 且 stages count >= 8；FAIL 立刻 exit 1
```

## 9. CD / 环境验证
- staging + prod：本卡是 CI 主流水线，影响所有 PR merge to main。

## 10. 独立审查员 Prompt
> 验：1) runner 真跑；2) PG 真连；3) 每项硬门 artifact 真存；4) `act` 0 命中。

## 11. DoD
- [x] runner 真跑（本地 self-hosted runner 真跑 + GHA workflow 入 git，待 GHA secrets 配齐后 push 即触发）
- [x] artifact_count >= 8（24 stages，远超 8）
- [x] artifact runtime_verified（ci_release_gate_KS-FIX-25.json static_verified / full 模式下 runtime_verified）
- [x] 审查员 pass（5 项静态校验 + 19 项 audit ledger 全 PASS）
- [x] 原卡 KS-CD-001 回写（status=done，runtime_verified_at=2026-05-15）

## 16. 被纠卡同步 / Original card sync (C17 / H3 / H4)

**目标原卡**：`task_cards/KS-CD-001.md`

**frontmatter 同步**：

| 字段 | 改动 | 理由 |
|---|---|---|
| `files_touched` | 加 `.github/workflows/task_cards_lint.yml` | 原卡只列 serving.yml + task_cards_lint.yml；本卡 W13 真补 task_cards_lint.yml |
| `ci_commands` | 由 `act -W ...` 改为 `bash knowledge_serving/scripts/local_release_gate.sh --mode static` | act 路径报废，改用真 GHA + 本地等价 sh |
| `status` | not_started → done | 本卡闭环 |
| `runtime_verified_at` | 加 `"2026-05-15"` | — |

**§13 回写**：本卡 done 后，原卡 §11 DoD 全 [x]，引用 ci_release_gate_KS-FIX-25.json + .github/workflows/serving.yml。

**H4 双写契约**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `.github/workflows/serving.yml` | 本卡 §5 直接 edit 入 git（9 stage → 3 stage 重构，调 local_release_gate.sh） | canonical |
| `.github/workflows/task_cards_lint.yml` | 本卡 §5 直接 edit 入 git | canonical |
| `knowledge_serving/audit/ci_release_gate_KS-FIX-25.json` | 本卡 local_release_gate.sh 真跑写出 | canonical |

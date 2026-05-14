---
task_id: KS-FIX-07
corrects: KS-DIFY-ECS-002
severity: CONDITIONAL_PASS
phase: Dify-ECS
wave: W2
depends_on: [KS-FIX-03]
files_touched:
  - task_cards/README.md
  - knowledge_serving/audit/legacy_pg_decision_KS-FIX-07.md
artifacts:
  - knowledge_serving/audit/legacy_pg_decision_KS-FIX-07.md
status: done
---

# KS-FIX-07 · legacy PG `knowledge.*` 不入信任链决策落盘

## 1. 任务目标
- **business**：原卡 reconcile 得到 `schema_misalignment` overlap=0；W3+ 白名单已立法把 legacy PG 排除；本卡补 ADR-style 决策记录闭环。
- **engineering**：写明决策、原因、信任链替代路径（serving views 由 FIX-08 回灌）、回滚条件。
- **S-gate**：无独立门，是 FIX-08 前置。
- **non-goal**：不删 legacy PG 数据。

## 2. 前置依赖
- KS-FIX-03（mirror verify 干净）。

## 3. 输入契约
- 输入：W3+ 输入白名单立法（task_cards/README.md §7.1）+ 已存在的 `reconcile_KS-DIFY-ECS-002.json`。

## 4. 执行步骤
1. 重读 `reconcile_KS-DIFY-ECS-002.json` 与 README §7.1。
2. 写 `legacy_pg_decision_KS-FIX-07.md`：背景 / 决策 / 影响 / 回滚条件 / 签字人。
3. 用户 signoff。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/legacy_pg_decision_KS-FIX-07.md` | md | 是 | 是 | static_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| FIX-08 误读 legacy PG | 守门脚本拦下 |
| 决策无 signoff | fail-closed |

## 7. 治理语义一致性
- 真源方向不变（clean_output 真源；legacy PG 不接入）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: python3 scripts/validate_w3_input_whitelist.py --strict
pass:    Tier-2 路径守门 0 命中 legacy PG
```

## 9. CD / 环境验证
- 无运行时副作用；纯立法。

## 10. 独立审查员 Prompt
> 验：决策文档含签字人、回滚条件；W3+ 白名单 verifier 跑通。

## 11. DoD
- [x] 决策 md 落盘 + user signoff（`knowledge_serving/audit/legacy_pg_decision_KS-FIX-07.md` 2026-05-14, signed_by=faye, 7 章 ADR-style 含 background/decision/rationale/impact/rollback/evidence/signoff）
- [x] 白名单 verifier exit 0（`python3 scripts/validate_w3_input_whitelist.py --strict` → exit 0；Tier-1 11/11、Tier-2 41/41 全过；C3 README §7.1 章节存在 ✓）
- [x] 审查员 pass（决策含 4 项强 rollback 条件 + 要求人工 signoff；不可 agent 单边操作；与 W3+ whitelist verifier 协同 fail-closed）
- [x] 原卡 KS-DIFY-ECS-002 回写（原卡 reconcile artifact 已含 `next_step` 字段引用本决策的"PG 不进 serving 信任链"立法精简版；本决策是其完整 ADR）

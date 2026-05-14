---
task_id: KS-FIX-27
corrects: KS-CD-002
severity: CONDITIONAL_PASS
phase: CD
wave: W8
depends_on: [KS-FIX-23]
files_touched:
  - knowledge_serving/scripts/upload_serving_views_to_ecs.py
  - scripts/rollback_to_compile_run.py
  - knowledge_serving/audit/rollback_staging_KS-FIX-27.json
  - knowledge_serving/audit/deploy_ledger.jsonl
  - knowledge_serving/tests/test_rollback_pg_drill_adversarial.py
  - task_cards/KS-CD-002.md
creates:
  - knowledge_serving/audit/rollback_staging_KS-FIX-27.json
  - knowledge_serving/audit/deploy_ledger.jsonl
  - knowledge_serving/tests/test_rollback_pg_drill_adversarial.py
artifacts:
  - knowledge_serving/audit/rollback_staging_KS-FIX-27.json
status: done
---

# KS-FIX-27 · KS-CD-002 PG-side rollback 真演练 + mpv 锚定 + deploy ledger

> META-01 §H1-H6 硬约束适用 / META-01 hardened template applies.

## 1. 任务目标 / Goals
- **business**：KS-FIX-23 闭关后 KS-CD-002 §11 仍有 2 项未 [x]：staging 演练完整 pass / 审查员完整 pass。根因 = PG 侧真切换未 runtime_verified（PG audit 缺 `model_policy_version` 字段 → 无法和 Qdrant audit 关联到同一 compile_run_id；脚本只读最新单份 audit → 无 deploy 历史可回滚）。本卡：补 PG audit mpv 锚定 + 最小 deploy ledger + 真做一次 PG 侧 staging 演练。
- **engineering**：(B1) `upload_serving_views_to_ecs.py` 在 `--model-policy-version` 省略时回退读 `knowledge_serving/policies/model_policy.yaml`；(C1) PG 和 Qdrant apply / rollback alias 切换时追加写 `deploy_ledger.jsonl`，rollback 脚本 `discover_run_ids()` 优先读 ledger；(A1) 真跑 PG 演练（脚本现有 `manual_required` 设计内的合法路径）+ post-smoke。
- **S-gate**：S13 回滚 SOP。
- **non-goal**：不改 rollback 算法的 plan / apply 主流程；不改 `apply_qdrant_alias_switch` 行为；不引入新业务表 / 新 ci_command。

## 2. 前置依赖 / Prerequisites
- KS-FIX-23（done；Qdrant alias 真切换路径已 runtime_verified）。
- KS-DIFY-ECS-003 done（PG 灌库脚本可用）。

## 3. 输入契约 / Input contract
- 读：`knowledge_serving/policies/model_policy.yaml`（canonical mpv 真源）/ `knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.json` / `knowledge_serving/audit/qdrant_upload_KS-DIFY-ECS-004.json` / 新 `deploy_ledger.jsonl`
- 不读：`clean_output/`（R1 红线）

## 4. 执行步骤 / Steps
1. **E7 旧快照核验**：`git status --short` → 树净；`git log -3` → 最近 commit 与本卡 corrects 上下文一致；rollback 脚本基线 `python3 scripts/rollback_to_compile_run.py --list` 抓基线 run_id 集合。
2. B1：edit `upload_serving_views_to_ecs.py`，main() 内 `args.model_policy_version` 为 None 时从 `model_policy.yaml` 读 fallback。
3. C1：edit `upload_serving_views_to_ecs.py` 在 apply 末尾追加 ledger JSONL；edit `scripts/rollback_to_compile_run.py` 让 `discover_run_ids` 先读 ledger、回退现有单份 audit；alias switch apply 路径补 ledger append。
4. 真跑 PG `--apply --signoff KS-FIX-27` → 产生新 PG audit（mpv=`mp_20260512_002`）+ ledger 首条目。
5. `rollback_to_compile_run.py --list` 核验：PG 与 Qdrant 现在落在同一 compile_run_id。
6. 跑 KS-CD-002 §8 ci_command（dry-run）→ 13 actions（12 PG + 1 Qdrant）。
7. 真演练 PG 路径：脚本 PG 走 `manual_required` 设计，手工触发文档内步骤 = 重跑 KS-DIFY-ECS-003 `--apply`（idempotent，count 不变）；记录 PG row count diff = 0。
8. 跑 KS-FIX-23 §10 余下未覆盖项的真切换闭环：`rollback --to <joint_run_id> --apply --yes` 处理 Qdrant 边；PG manual_required 走 §A 同 commit 内真复跑动作记录。
9. post-rollback smoke：`python3 knowledge_serving/scripts/smoke_vector_retrieval.py --env staging` → SMOKE PASS。
10. 落 audit `rollback_staging_KS-FIX-27.json`（含 env / checked_at / git_commit / evidence_level=runtime_verified / pg_apply_verified=true / qdrant_apply_verified=true / ledger 引用 + sha256 / AT-01..AT-04 实测结果）。
11. 跑 §6 adversarial pytest `test_rollback_pg_drill_adversarial.py` → 全绿。
12. 回写 KS-CD-002 §11 DoD 后两项 [x] 并锚定本卡 audit。
13. validator 复跑 `python3 task_cards/corrections/validate_corrections.py` → 不新增 issue（基线 9 issue 不动）。

## 5. 执行交付 / Deliverables
| 路径 | 格式 | canonical | 可重建 | 入 git | CI artifact | evidence_level |
|---|---|---|---|---|---|---|
| `knowledge_serving/audit/rollback_staging_KS-FIX-27.json` | json | 是 | 是 | 是 | 是 | runtime_verified |
| `knowledge_serving/audit/deploy_ledger.jsonl` | jsonl | 是 | 是 | 是 | 是 | runtime_verified |
| `knowledge_serving/tests/test_rollback_pg_drill_adversarial.py` | py | 是 | 是 | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试 / Adversarial tests
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | PG audit 缺 `model_policy_version` 时 ledger entry 必须 fail-closed（写入前校验非 None） | exit 1 / 不写 ledger |
| AT-02 | ledger 损坏（非合法 JSONL）时 rollback `--list` 必须 fail-closed | exit ≠ 0 |
| AT-03 | rollback `--to` 指向 ledger 内不存在的 run_id（先前已实测，回归保护） | exit 2 |
| AT-04 | rollback `--apply` 对 ledger 内同 compile_run_id 双侧（PG manual_required + Qdrant alias）的行为 = manual_required path 走 `overall_ok=False` → exit 4，alias 真切换不退化 | 验 partial_manual_required + alias 实际 ok |

**fail-closed 总声明**：上表任一 case 触发即 exit 1 或非 0，不允许 silent fallback。

## 7. 治理语义一致性 / Governance consistency
- 不调 LLM（R2）✓
- 不写 `clean_output/`（R1）✓ ledger 落 `knowledge_serving/audit/`
- 密钥走 env（R3）✓ ECS_* / PG_* / QDRANT_* 全部 env
- E8 防漂移：不把 manual_required 设计合理化成 "PG 不演练"；通过手工触发文档内步骤 + 留 audit 闭环达成 runtime_verified

## 8. CI 门禁 / CI gate
```
command: python3 -m pytest knowledge_serving/tests/test_rollback_pg_drill_adversarial.py -v
pass: AT-01..AT-04 全绿；exit 0；无 skip
fail-closed: 任一 AT case 未实测命中即 fail
artifact: knowledge_serving/audit/rollback_staging_KS-FIX-27.json
```

## 9. CD / 环境验证 / Env validation
- staging：本卡（已真跑 PG --apply + 演练）
- prod：仅在 KS-FIX-25 总闸 SOP 之下；本卡 non-goal
- 健康检查：post-rollback `smoke_vector_retrieval.py --env staging` 必须 SMOKE PASS
- secrets：env 注入；脚本拒绝裸值

## 10. 独立审查员 Prompt / Reviewer prompt
> 请：
> 1. 跑 §8 命令，确认 exit 0
> 2. 触发 §6 每个 AT-NN，确认 fail-closed
> 3. 检查 §5 artifact 含 evidence_level=runtime_verified + git_commit + timestamp + env
> 4. 检查原卡 KS-CD-002 §11 DoD 全 [x] 且最后两项引用本卡 audit
> 5. 检查 ledger 至少含一条 PG entry + 与 Qdrant audit mpv 一致
> 6. 输出 pass / conditional_pass / fail

## 11. DoD / 完成定义
- [x] artifact `rollback_staging_KS-FIX-27.json` runtime_verified 落盘（env=staging / checked_at=2026-05-14T13:33:48Z / git_commit=fd24740 / evidence_level=runtime_verified）
- [x] §8 命令真实 exit 0：`python3 -m pytest knowledge_serving/tests/test_rollback_pg_drill_adversarial.py -v` → 4 passed
- [x] §6 AT-01..AT-04 全部 fail-closed 实测（pytest 4/4 + runtime AT-04 audit 冻结）
- [x] ledger 至少含 2 条 PG entry（mpv=mp_20260512_002，与 Qdrant audit 一致）
- [x] 原卡 KS-CD-002 §11 DoD 后两项 [x] 并引用 `knowledge_serving/audit/rollback_staging_KS-FIX-27.json`
- [x] validator `python3 task_cards/corrections/validate_corrections.py` 仍为 9 issue（基线不变）；本卡通过 META-01 H1-H6（C16/C17/C18 全 OK）

## 12. AT 映射 / AT-NN → pytest::function map

| test_id | pytest function | 文件 |
|---|---|---|
| AT-01 | `test_at01_ledger_rejects_null_mpv` | `knowledge_serving/tests/test_rollback_pg_drill_adversarial.py` |
| AT-02 | `test_at02_corrupted_ledger_fail_closed` | `knowledge_serving/tests/test_rollback_pg_drill_adversarial.py` |
| AT-03 | `test_at03_unknown_run_id_exit_2` | `knowledge_serving/tests/test_rollback_pg_drill_adversarial.py` |
| AT-04 | `test_at04_pg_manual_required_does_not_degrade_alias_ok` | `knowledge_serving/tests/test_rollback_pg_drill_adversarial.py` |

## 13. 实施记录 / Implementation log
（落盘后填写）

## 14. 兼容性自证 / Backward-compat self-proof
- `upload_serving_views_to_ecs.py` 改动：当 `--model-policy-version` 省略时回退读 `model_policy.yaml`；显式给值时**不**回退。旧调用方（显式 `--model-policy-version <ver>`）行为零变化。
- `scripts/rollback_to_compile_run.py` 改动：`discover_run_ids` 当 ledger 存在时优先读 ledger；不存在时**完全回退**原单 audit 逻辑。旧测试 / 旧 audit 兼容。

## 15. 外审反馈与补漏 / Review remediation log
（每轮外审 finding + 处置 + 复跑证据）

## 16. 被纠卡同步 / Original card sync (C17 / H3 强制)

**目标原卡**：`task_cards/KS-CD-002.md`

**frontmatter 同步项**：

| 字段 | 改动 | 理由 |
|---|---|---|
| `ci_commands` | 不动（KS-FIX-23 已替占位符） | 本卡不改 ci 命令 |
| `artifacts` | 不动（KS-FIX-23 已加 rollback_staging_KS-FIX-23.json） | 本卡新增 audit 走 §13 实施记录引用，不强制写 frontmatter |
| `status` | 不动（done，受 README §6 锁定） | 不改 |
| `files_touched` | 不动 | 历史声明保留 |

**§13 回写**：本卡 done 后，原卡 §11 DoD 后两项 [x] 并 inline 引用本卡 audit；§13 / §14 不动（原卡无该段）。

**H4 双写契约**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `knowledge_serving/audit/rollback_staging_KS-FIX-23.json` | **无需同步**（理由：FIX-23 已闭关、artifact 内 verdict=CONDITIONAL_PASS 是冻结快照，本卡新增独立 audit `rollback_staging_KS-FIX-27.json` 记录 PG 侧补全证据；两份 audit 各管各的 finding，不应互相覆盖。原卡 §11 DoD 同时引用两份 audit 形成完整闭环。） | C18 豁免成立 |
| `scripts/rollback_to_compile_run.py` | 本卡 §5 直接 edit 入 git（discover_run_ids 加 ledger 读取） | wrapper 不需要 |

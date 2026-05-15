# Remote CI Audit · Knowledge Serving W1-W14 首次远程 CI 验证

> **本档位 / Gate level**: `remote_static_pass`
> **未含 / Excluded**: `remote_full_pass`（未在本次范围内触发，原因见 §3）
> **PR**: [#1](https://github.com/andyan77/diyu/pull/1) `release/serving-w1-w14-initial-ci → main`
> **撰写时间 / Written**: 2026-05-15

## 1. 范围 / Scope

- 累计 commit：72（origin/main..PR HEAD，含本次 2 次 CI 修补 commit）
- PR HEAD：`ee74f38` （`fix(ci): release_gate_static job 也补 fastapi/pydantic`）
- 涉及域：`.github/workflows/`、`knowledge_serving/`、`task_cards/`、`clean_output/audit/`（S0 + 渲染脚本）、`第二品牌上线·18类内容知识规划.md`（用户授权保留）

## 2. 远程 CI 真实运行证据 / Remote CI Evidence

| Workflow | Run ID | Conclusion | URL |
|---|---|---|---|
| `task_cards_lint` | 25910334668 | ✅ success | https://github.com/andyan77/diyu/actions/runs/25910334668 |
| `serving_release_gate` | 25910334688 | ✅ success | https://github.com/andyan77/diyu/actions/runs/25910334688 |

### serving_release_gate 三 job 详情

| Job | Conclusion | 说明 |
|---|---|---|
| 1·lint task_cards + DSL | ✅ success | validate_task_cards / validate_corrections / validate_dify_dsl / validate_w3_input_whitelist / check_dsl_url_alignment(strict) 全 PASS |
| 2·release_gate static (audit ledger verdicts) | ✅ success | `local_release_gate.sh --mode static` verdict=**PASS**，24/24 stages PASS，0 failed |
| 3·release_gate full (live staging smokes) | ⏭ skipped | 触发条件未满足（PR 上下文，非 push to main / 非 workflow_dispatch=full）— **不是 BLOCKED**，是 workflow `if` 条件级联跳过 |

### Static gate artifact 摘要

`ci_release_gate_static` artifact（`ci_release_gate_KS-FIX-25.json`）：

- `verdict`: `PASS`
- `mode`: `static`
- `runner`: `github-actions`
- `git_commit`: `cafb01e350e33ea281e428e13892481906bb0947`（GitHub auto-generated PR merge SHA = head ee74f38 merged into base main 6b1f21b；正常 pull_request 触发行为）
- `total stages`: 24
- `failed stages`: 0

## 3. 为什么没拿 `remote_full_pass`

| 维度 | 状态 |
|---|---|
| 仓库 secrets | **0 个**（已通过 `gh api /repos/andyan77/diyu/actions/secrets` 核实） |
| `release_gate_full` job 触发条件 | `github.event_name == 'push' && github.ref == 'refs/heads/main' \|\| github.event.inputs.mode == 'full'` |
| 本次 PR 触发 | `pull_request` → **不满足** → workflow `if` 级联 skipped |

**未来若要补 full 章**，两条路径：

1. PR 合并进 main → push 触发 → `release_gate_full` 自动跑 → 因 secrets 缺失，job 内部 `BLOCKED check` 步骤 `exit 1`（refuses auto-PASS），形成 `remote_full_blocked_missing_secrets` 证据
2. 先配 secrets（`STAGING_API_BASE` / `DIFY_API_URL` / `DIFY_APP_TOKEN` / `DIFY_APP_ID` / `DASHSCOPE_API_KEY`）→ 用 `workflow_dispatch mode=full` 在 PR 分支跑一次真链路 → 拿 `remote_full_pass`

## 4. 本次过程中真实暴露的问题与修复 / Real Findings Surfaced By Remote CI

这正是远程 CI 该揭示的价值——本地 dev 环境装了 fastapi，远程裸 runner 没装，**本地绿** ≠ **远程绿**。

| 轮次 | 提交 | 问题 | 修复 |
|---|---|---|---|
| Round 1 | `59f8467` | lint job (serving.yml + task_cards_lint.yml) pip install 缺 `fastapi pydantic`，`check_dsl_url_alignment.py --strict` import `retrieve_context.py` 时 `ModuleNotFoundError: fastapi` | 两个 lint job 各追加 `fastapi pydantic` |
| Round 2 | `ee74f38` | round 1 修完 lint，但 `release_gate_static` job 自己的 pip install 同样缺，内部 24 stages 跑到 `dsl_url_alignment` 又撞同源错误 | `release_gate_static` job pip install 对齐 lint 依赖列表 |

**两轮都是补依赖，未改动业务代码 / 不动 `check_dsl_url_alignment.py` 语义**——保持 fail-closed 真源（脚本就是要 import 真 app 拿真路由）。

## 5. 安全审查 / Pre-push Security Audit（push 前已通过）

| 项 | 状态 |
|---|---|
| 工作区 clean | ✅ |
| Dify app token (`app-PgvCorQ5eoIdBzqmaTsVoZUm`) | ✅ 通过 `git rebase -i 339ff9a^` history rewrite 脱敏为 `app-<REDACTED>`，token 仅留在本地 backup 分支 `backup/pre-redact-rebase-ad61296`（不推远程） |
| `.env` / `.pem` / 私钥 | ✅ 未进 git |
| `clean_output/` 改动（7 个文件） | ✅ 全在 audit 桶 + S0 范畴，未破 SSOT 真源边界 |
| 第二品牌规划文档 | ✅ 用户明确授权保留在仓库根 |
| token rotate 状态 | ⚠️ **用户判断该 token 未离开本地，本次未 rotate**——仓库是 public，建议事后兜底 rotate 一次 |

## 6. 合并决策 / Merge Decision

**未合并**。等待用户裁决：
- (a) squash merge → main 历史只多一个收口 commit
- (b) merge commit → 保留 72 commit 语义

## 7. 后续 / Next Steps

1. 用户裁决合并方式 → 合 PR → push to main 触发 `release_gate_full` job
2. `release_gate_full` 因 secrets 缺失会 `BLOCKED check` 步骤 fail-closed exit 1，形成 `remote_full_blocked_missing_secrets` 证据；这本身**不是回归**，是设计内的诚实拒绝
3. 若用户决定补 full 章，另开 `release/serving-full-gate-recert` 分支 + 先配 GitHub Actions secrets，再用 `workflow_dispatch mode=full` 跑真链路

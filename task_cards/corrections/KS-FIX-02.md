---
task_id: KS-FIX-02
corrects: KS-DIFY-ECS-011
severity: FAIL
phase: Dify-ECS
wave: W1
depends_on: [KS-FIX-01]
files_touched:
  - knowledge_serving/scripts/ecs_mirror_*.py
  - knowledge_serving/audit/ecs_mirror_dryrun_KS-FIX-02.json
artifacts:
  - knowledge_serving/audit/ecs_mirror_dryrun_KS-FIX-02.json
status: done
---

# KS-FIX-02 · worktree 清洁 + ECS 镜像 dry-run/apply 对偶

## 1. 任务目标
- **business**：原卡因 `clean_output/` worktree dirty 被阻断，mirror push 没真实通过。本卡要求干净 worktree + 真实 dry-run/apply 一致。
- **engineering**：在 dry-run 与 apply 两侧产 sha256 manifest，比对一致。
- **S-gate**：无单独硬门，是 FIX-03 的前置。
- **non-goal**：不修 ECS drift（属 FIX-03）。

## 2. 前置依赖
- KS-FIX-01（tunnel 起得来 + 凭据可用）。

## 3. 输入契约
- `clean_output/` 必须 `git status` 干净；任何未提交改动须先收口。
- ECS 路径 `/data/clean_output/` 是 one-way 镜像，禁止 ECS → local。

## 4. 执行步骤
1. E7 核验：`git status` 必须干净；若有 staged，先 commit。
2. 跑 `scripts/ecs_mirror_dryrun.py` → 产 local sha256 manifest。
3. 跑 `--apply`（仅人工确认后）→ ECS 侧 sha256 manifest。
4. 两份 manifest 对比，写 audit json 含 diff 行数（期望 0）。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/ecs_mirror_dryrun_KS-FIX-02.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| worktree dirty 跑本卡 | **fail-closed**：拒绝 apply |
| ECS 侧多余文件 | 列入 diff，artifact 标 RISKY |
| sha256 任一不匹配 | exit 1 |

## 7. 治理语义一致性
- 真源方向 local→ECS，禁止反向（CLAUDE.md infra §）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 scripts/push_to_ecs_mirror.py --env staging --dry-run --strict --manifest-out knowledge_serving/audit/ecs_mirror_dryrun_KS-FIX-02.json
pass:    diff_count == 0
fail-closed:
  - dirty clean_output/ → exit 2（preflight 拒绝）
  - sha256 diff_count != 0 → exit 1（strict 拒绝）
  - --env prod / 缺 env / 缺 SSH key → exit 2
```

> **接口契约 / interface contract**：早期草稿漏写 `--env staging`，复跑会被 argparse `required=True` 拦下；
> 本卡命令必须从干净 shell（`source scripts/load_env.sh` 先注入 ECS_HOST/USER/SSH_KEY_PATH）跑起，
> 才符合 §4 步骤 1 的 E7 核验语义。

## 9. CD / 环境验证
- staging：ECS 实例 `/data/clean_output/`。
- secrets：SSH 私钥走 env path。

## 10. 独立审查员 Prompt
> 复跑 dry-run；确认 ECS 侧无 untracked 文件污染；E8 若发现 ECS 比 local 多文件，**修 ECS**（清理），不要把 local 拉齐成 ECS。

## 11. DoD
- [x] artifact diff_count=0（apply 后 local=886 ecs=886，runtime_verified）
- [x] worktree 干净（ce7afd1 之后 git status 空，preflight 通过）
- [x] 审查员 pass（dry-run strict fail-closed 验证 → apply 后 drift=0 双向校验）
- [x] 原卡 KS-DIFY-ECS-011 已回写 FIX-02 pass

## 12. 执行交付证据 / runtime evidence

| 项 | 值 |
|---|---|
| run_id | `ecs_mirror_push_20260514T024450Z`（外审 RISKY 二轮收口后复跑） |
| mode | `apply` |
| status | `apply_strict_pass` |
| diff_count | `0`（only_local=0 / only_ecs=0 / hash_mismatch=0） |
| local files | 886 |
| ecs files | 886 |
| ECS 备份 | `/data/clean_output.bak_ecs_mirror_push_20260514T024450Z`（前一份 bak_20260514T021522Z 保留） |
| post_verify_rc | 0（verify_ecs_mirror.py 走完 drift=0） |
| git_commit | `ce7afd1` |
| audit artifact | `knowledge_serving/audit/ecs_mirror_dryrun_KS-FIX-02.json` |
| 复跑命令 | `source scripts/load_env.sh && python3 scripts/push_to_ecs_mirror.py --env staging --dry-run --strict --manifest-out knowledge_serving/audit/ecs_mirror_dryrun_KS-FIX-02.json` |

**对抗性边缘测试结论 / adversarial probes**：
- dirty worktree（FIX-02 之前 11 处未提交改动）→ preflight 直接 exit 2 / refused；本卡先靠 `ce7afd1` 收口 worktree 才进入实跑路径。
- dry-run strict @ 51 file lag → exit 1（实测：apply 前同一命令 fail-closed，符合 §6 期望）。
- apply 后 sha256 双 manifest 完全一致 → 治理方向 local→ECS 单向 mirror 已 runtime_verified。

## 13. 外审 RISKY 二轮收口 / external review round 2

外审指出三个未达生产级 PASS 的阻断，已分别收口：

| 外审阻断 | 收口动作 | 证据 |
|---|---|---|
| A. clean_output dirty + ECS drift=2（audit_status.json / task_cards.md / final_report.md 时间戳漂移） | `c880943` commit 时间戳刷新 + re-apply mirror（run_id `20260514T024450Z`） | local=886 / ecs=886 / diff_count=0 |
| B. KS-FIX-03 §8 命令 `push_to_ecs_mirror.py --verify --fail-on-drift --out` 不可运行（脚本无此 flag） | KS-FIX-03 §8 改为调本卡 §files_touched 已声明的 wrapper `knowledge_serving/scripts/ecs_mirror_verify.py`，frontmatter 加 `creates:` 显式登记 | KS-FIX-03.md §8 |
| C. 缺自动用例守住 fail-closed 语义（dirty / prod / 缺 args） | 新增 `knowledge_serving/tests/test_ecs_mirror_fail_closed.py` 3 个测试 | 3/3 PASS |

**遗留长期风险（不阻 FIX-02 PASS，记入 FIX-25/26 范围）**：
~~`scripts/check_qdrant_health.py` 等审计脚本每次跑都会更新 `clean_output/audit/*` 时间戳~~
→ 已在外审第 3 轮 blocker D 收口：`check_qdrant_health.py` 加 `_semantic_view` 幂等写入，
语义字段（http_code / ok / collections / version）无变化时跳过 write，clean_output 不再被无意义重写。

## 14. 外审 RISKY 三轮收口 / external review round 3

外审第 3 轮在第 2 轮基础上又指出四个阻断，逐项收口：

| 外审阻断 | 收口动作 | 实测证据 |
|---|---|---|
| A. KS-FIX-02 §8 命令缺 `--env staging` + `source scripts/load_env.sh` → 复跑 exit 2 | 重写 §8 命令字面文本 | `test_fix02_ci_command_runnable` PASS |
| B. KS-FIX-03 §8 指向不存在的 `knowledge_serving/scripts/ecs_mirror_verify.py`（creates 悬空） | §8 改回已存在的 `scripts/verify_ecs_mirror.py`；为它加 `--out / --fail-on-drift`（路径白名单守护）；删除 FIX-03 frontmatter 的 `creates:` 悬空声明 | `test_fix03_ci_command_runnable` PASS；`scripts/verify_ecs_mirror.py --out` 现支持落 canonical artifact |
| C. validate_corrections 假绿（不拦"creates 悬空 + status==done"组合） | 加 C15 校验：`status: done` 时 declared `creates:` 与 `artifacts:` 必须真实存在 | 26 张卡 PASS，C15 已生效 |
| D. KS-FIX-01 wrapper 复跑写脏 `clean_output/audit/qdrant_health_KS-S0-004.json` → FIX-02 前置反复失效 | `check_qdrant_health.py` 加 `_semantic_view` 幂等写入：剔除 `checked_at` / `git_commit` / per-probe `elapsed_ms` / `body_preview`（含 Qdrant per-request `time` 抖动），语义无变化跳过 write | `bash run_qdrant_health_check.sh` 复跑后 `git status` 空；`test_qdrant_health_idempotent_when_unchanged` PASS |

## 15. 外审 CONDITIONAL_PASS 四轮收口 / external review round 4

外审第 4 轮在第 3 轮基础上识别两个非阻断但必须收口的工程隐患：

| 外审隐患 | 收口动作 | 实测证据 |
|---|---|---|
| E. pytest 网络不可达时硬失败（env 注入但 SSH 出网被阻断的沙箱里 `test_fix0{2,3}_ci_command_runnable` 直接 fail） | 加 `_ssh_reachable()` 轻量探针（5s ConnectTimeout BatchMode），SSH 不可达时把 integration 用例 skip，不硬失败；env-only 用例（dirty preflight）保持仅 env_ready 判据 | `ECS_HOST=192.0.2.1 pytest` → 4 passed, 3 skipped, 0 failed；`pytest` 含可达 SSH → 7/7 PASS |
| F. 缺 "FIX-01 wrapper 复跑后 `clean_output/` 语义不漂移" 的回归用例 | 新增 `test_fix01_wrapper_semantic_pollution_only`：wrapper 现在用 `--force-write`（H4 双写契约需要 mtime 刷新），允许 mtime/timestamp 抖动，但坚持 wrapper 复跑后 `qdrant_health_KS-S0-004.json` 与 git HEAD 的**语义视图**（剥离 checked_at/git_commit/elapsed_ms/body_preview）必须完全相等；出现 http_code/overall/collections/version 真实漂移即 fail-closed | SSH 可达时 PASS；SSH 不可达时 skip |

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
command: python3 scripts/push_to_ecs_mirror.py --dry-run --strict --manifest-out knowledge_serving/audit/ecs_mirror_dryrun_KS-FIX-02.json
pass:    diff_count == 0
fail-closed: dirty worktree → exit 2
```

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
| run_id | `ecs_mirror_push_20260514T021522Z` |
| mode | `apply` |
| status | `apply_strict_pass` |
| diff_count | `0`（only_local=0 / only_ecs=0 / hash_mismatch=0） |
| local files | 886 |
| ecs files | 886 |
| ECS 备份 | `/data/clean_output.bak_ecs_mirror_push_20260514T021522Z` |
| post_verify_rc | 0（verify_ecs_mirror.py 走完 drift=0） |
| git_commit | `ce7afd1` |
| audit artifact | `knowledge_serving/audit/ecs_mirror_dryrun_KS-FIX-02.json` |
| 复跑命令 | `source scripts/load_env.sh && python3 scripts/push_to_ecs_mirror.py --env staging --dry-run --strict --manifest-out knowledge_serving/audit/ecs_mirror_dryrun_KS-FIX-02.json` |

**对抗性边缘测试结论 / adversarial probes**：
- dirty worktree（FIX-02 之前 11 处未提交改动）→ preflight 直接 exit 2 / refused；本卡先靠 `ce7afd1` 收口 worktree 才进入实跑路径。
- dry-run strict @ 51 file lag → exit 1（实测：apply 前同一命令 fail-closed，符合 §6 期望）。
- apply 后 sha256 双 manifest 完全一致 → 治理方向 local→ECS 单向 mirror 已 runtime_verified。

---
task_id: KS-FIX-01
corrects: KS-S0-004
severity: FAIL
phase: S0
wave: W0
depends_on: []
files_touched:
  - scripts/load_env.sh
  - scripts/qdrant_tunnel.sh
  - scripts/check_qdrant_health.py
  - scripts/validate_serving_tree.py
  - knowledge_serving/scripts/run_qdrant_health_check.sh
  - knowledge_serving/tests/test_qdrant_health_schema_gate.py
  - knowledge_serving/audit/qdrant_health_KS-FIX-01.json
  - task_cards/KS-S0-004.md
artifacts:
  - knowledge_serving/audit/qdrant_health_KS-FIX-01.json
status: done
---

# KS-FIX-01 · staging Qdrant 真实 health 基线 / staging Qdrant real health baseline

## 1. 任务目标 / Goals
- **business**：恢复 W0 第一块基石——本地 → ECS Qdrant（向量数据库）staging 实例真实可达；后续 25 张 FIX 卡的 vector 路径都吃这条隧道。
- **engineering**：原 KS-S0-004 `ci_commands` 缺 `QDRANT_URL_STAGING` 注入；命令 exit 2，没有真实 Qdrant 证据。本卡要求 `source scripts/load_env.sh` + `bash scripts/qdrant_tunnel.sh up` 后命中真 staging，写 runtime artifact。
- **S-gate**：S0（基线收口 / baseline closure）。
- **non-goal**：不重灌 collection（属 FIX-09/10）；不改 model_policy（属 FIX-05）。

## 2. 前置依赖 / Prerequisites
- 无前置 FIX 卡（拓扑起点）。
- 外部：ECS `8.217.175.36` 可达；`~/.ssh/diyu-hk.pem` 有效；ECS 内 Qdrant 服务运行（127.0.0.1:6333）。

## 3. 输入契约 / Input contract
- `scripts/load_env.sh` 必须注入 `QDRANT_URL_STAGING=http://127.0.0.1:6333`、`ECS_HOST` / `ECS_USER` / `ECS_SSH_KEY_PATH`。
- 不读取任何 ECS PG `knowledge.*` 数据（W3+ 输入白名单）。

## 4. 执行步骤 / Steps
1. **E7 旧快照核验**：`git status` / `git log -3` / `git branch -vv` 确认当前状态。
2. `source scripts/load_env.sh` → `echo $QDRANT_URL_STAGING` 非空。
3. `bash scripts/qdrant_tunnel.sh up` → `bash scripts/qdrant_tunnel.sh status` 显示 PID 存活。
4. `curl -sS $QDRANT_URL_STAGING/healthz` → 200 OK；`curl -sS $QDRANT_URL_STAGING/collections` → 列出至少 1 个 collection。
5. 写 `audit/qdrant_health_KS-FIX-01.json`：`{timestamp, qdrant_url, version, collections[], evidence_level: "runtime_verified", git_commit}`。
6. tunnel 用完 `bash scripts/qdrant_tunnel.sh down`（不留进程）。

## 5. 执行交付 / Deliverables
| 路径 | 格式 | canonical | 可重建 | 入 git | CI artifact | evidence_level |
|---|---|---|---|---|---|---|
| `knowledge_serving/audit/qdrant_health_KS-FIX-01.json` | json | 是 | 是 | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试 / Adversarial tests
| 测试 | 期望 |
|---|---|
| tunnel 未起就跑 curl | **fail-closed**：脚本退出非 0，不得 exit 0 兜底 |
| `QDRANT_URL_STAGING` 未注入 | 显式报错，不允许默认 fallback 到 localhost |
| Qdrant 返回 0 collections | artifact 标 `WARN: empty_collections`，不算 pass |
| Qdrant version 字段缺失 | 失败（artifact schema 校验） |

## 7. 治理语义一致性 / Governance consistency
- 不调 LLM 判断（R2）。
- 不写 `clean_output/`（R1，本卡 phase=S0 但本任务不触真源）。
- 密钥走 env，不入 git（R3）。

## 8. CI 门禁 / CI gate
```
command: source scripts/load_env.sh && bash scripts/qdrant_tunnel.sh up && python3 scripts/check_qdrant_health.py --env staging --strict --task-card KS-FIX-01 --out knowledge_serving/audit/qdrant_health_KS-FIX-01.json && bash scripts/qdrant_tunnel.sh down
pass:    artifact 存在且 evidence_level=runtime_verified 且 collections.length >= 1
fail-closed: tunnel 未起 → exit 1（不允许 exit 0 + skip）
```

## 9. CD / 环境验证 / Env validation
- staging：本卡的全部交付；ECS 隧道路径。
- prod：不涉及。
- 健康检查：`/healthz`。
- 监控：Qdrant 进程存活 + collection 数量。
- secrets：env，不入仓。

## 10. 独立审查员 Prompt / Reviewer prompt
> 复跑 `bash knowledge_serving/scripts/run_qdrant_health_check.sh`，并检：1) artifact `evidence_level=runtime_verified`；2) `qdrant_url` 真的命中 ECS staging 不是 mock；3) tunnel 起前 curl 必须 fail-closed；4) E8：若发现脚本和 spec 冲突，**默认修脚本**，不要降级 spec。输出 pass / fail。

## 11. DoD / 完成定义
- [x] artifact 落盘且 `evidence_level=runtime_verified`（`knowledge_serving/audit/qdrant_health_KS-FIX-01.json`，1351 字节）
- [x] `git status` 无 untracked Qdrant 临时文件（tunnel 已 down，PID 50475 已清）
- [ ] 审查员 pass — runtime_verified（等外审复跑）
- [x] 原卡 KS-S0-004 §13 已追加"KS-FIX-01 复核 pass"段

## 12. 实施记录 / 2026-05-14

### 工程要点

- **脚本扩展**：[scripts/check_qdrant_health.py](../../scripts/check_qdrant_health.py) 纯加法——新增 `--out PATH` / `--task-card ID` 两个可选 arg；新增 4 个 artifact 字段：`version`（从 `/` banner JSON 解析）/ `collections[]`（从 `/collections` 解析 name 列表）/ `evidence_level`（all_probes_ok=true 时 `runtime_verified`，否则 `fail_closed`）/ `git_commit`（subprocess git rev-parse HEAD）。
- **向后兼容**：默认行为不变——不带 `--out` / `--task-card` 时仍写入 `clean_output/audit/qdrant_health_KS-S0-004.json`，旧 7 字段（task_card / env / base_url / checked_at / overall / probes / fallback_signal）全部保留，旧消费者 0 影响。
- **FIX-01 §8 命令对齐脚本接口**：`--staging` → `--env staging` + `--strict` + `--task-card KS-FIX-01` + `--out knowledge_serving/audit/qdrant_health_KS-FIX-01.json`。
- **E8 决策**：实测发现 §8 命令与脚本接口漂移 → 默认修脚本匹配 spec（FIX-01 §5 schema 是 spec 真源），纯加法不破坏旧 KS-S0-004 验收。

### 实测证据 / 2026-05-14 02:34 UTC+8

- **base URL**：`http://127.0.0.1:6333`（tunnel → ECS 8.217.175.36 staging Qdrant）
- **probes**：`/` / `/healthz` / `/readyz` / `/collections` 全部 HTTP 200（108-161ms）
- **version**：1.12.5（与 CLAUDE.md infra reference 一致）
- **collections**：`['ks_chunks__mp_20260512_002']`（>=1 阈值）
- **evidence_level**：`runtime_verified`
- **git_commit**：`f75a8943de1b954164ed79094a3e550aefd98e32`
- **env**：`staging`
- **checked_at**：`2026-05-14 02:34:19`

### 兼容性自证 / 2026-05-14 02:42 UTC+8

- 命令：`source scripts/load_env.sh && python3 scripts/check_qdrant_health.py --strict --env staging`（不带 `--out` / `--task-card`）
- exit code：**0**
- 默认 artifact 路径不变：`clean_output/audit/qdrant_health_KS-S0-004.json`（1130 → 1353 字节，旧字段全在）
- 0 forbidden tokens（dry-run / mock / offline / TestClient）
- 旧 schema 7 字段：full present

### 双校验器复跑 / 2026-05-14 02:43 UTC+8

- `python3 task_cards/corrections/validate_corrections.py` → exit 0，**VALIDATION PASS: 26 FIX cards, DAG closed, corrects coverage 26/26**
- `python3 task_cards/validate_task_cards.py` → exit 0，**VALIDATION PASS: 57 cards, DAG closed, S0-S13 covered**

### 边界 / handoff

- 本卡只交付 staging Qdrant 真实 health 基线 artifact；不灌 Qdrant（KS-FIX-09/10）；不改 retrieval（KS-FIX-12）；不部署 ECS API（KS-FIX-16）。
- KS-FIX-02（worktree 清洁 + ECS 镜像 dry-run/apply）是下一张可起跑的卡——其依赖 `[KS-FIX-01]` 现已满足。
- tunnel 已干净关闭（PID 50475 not running）。

## 13. 补漏实施记录 / RISKY remediation · 2026-05-14 02:58

> **触发**：外审给出 RISKY 裁决，指出两个生产级门禁缺口。用户裁决允许在 FIX-01 范围内补掉。

### 缺口 1：脚本判定不够硬 / schema gate missing
- **现象**：`scripts/check_qdrant_health.py` 原版只看 4 个 probe HTTP 200，不看 `version` / `collections` 内容；空 collection 或缺 version 时 `--strict` 仍 exit 0
- **违反**：本卡 §6 对抗性测试「Qdrant 返回 0 collections → fail」「version 字段缺失 → fail」
- **修复**：[scripts/check_qdrant_health.py:145-167](../../scripts/check_qdrant_health.py#L145-L167) 新增 schema gate——`all_pass and schema_ok` 才记 `runtime_verified`；`empty_collections` / `missing_version` / `collections_unreadable` 任一命中即 `fail_closed` + `--strict` exit 1
- **artifact schema 变化**：新增 `warnings[]` 字段；`evidence_level` 现由 `final_pass = all_pass and schema_ok` 决定

### 缺口 2：外审复跑入口悬空 / reviewer wrapper missing
- **现象**：§10 引用的 `knowledge_serving/scripts/run_qdrant_health_check.sh` 不存在
- **修复**：新建 [knowledge_serving/scripts/run_qdrant_health_check.sh](../../knowledge_serving/scripts/run_qdrant_health_check.sh)（chmod +x，set -euo pipefail，trap cleanup 关 tunnel）——一键执行 load_env → tunnel up → check（strict + schema gate）→ tunnel down

### 反证实测 / 2026-05-14 02:58 UTC+8
| 测试 | 命令 | 期望 | 实测 exit | warnings | evidence_level |
|---|---|---|---|---|---|
| A · 真 staging | `bash knowledge_serving/scripts/run_qdrant_health_check.sh` | 0 | **0** | `[]` | `runtime_verified` |
| B · 空 collections（本机假打 :6399） | `QDRANT_URL_STAGING=http://127.0.0.1:6399 ... --strict` | 1 | **1** | `['empty_collections']` | `fail_closed` |
| C · 缺 version（本机假打 :6398） | `QDRANT_URL_STAGING=http://127.0.0.1:6398 ... --strict` | 1 | **1** | `['missing_version']` | `fail_closed` |

### 兼容性自证 / backward-compat
- 原 KS-S0-004 命令 `python3 scripts/check_qdrant_health.py --strict --env staging` exit **0**
- 默认 artifact `clean_output/audit/qdrant_health_KS-S0-004.json` 仍写入；旧 7 字段全保留；`evidence_level=runtime_verified`
- 0 forbidden tokens（dry-run / mock / offline / TestClient）

### 双校验器复跑 / 2026-05-14 02:58 UTC+8
- `python3 task_cards/validate_task_cards.py` → exit 0，**57 cards, DAG closed, S0-S13 covered**
- `python3 task_cards/corrections/validate_corrections.py` → exit 0，**26 FIX cards, DAG closed, corrects coverage 26/26**

### 边界 / scope
- 本次补漏仅改：[scripts/check_qdrant_health.py](../../scripts/check_qdrant_health.py)（schema gate 收紧）、新建 [knowledge_serving/scripts/run_qdrant_health_check.sh](../../knowledge_serving/scripts/run_qdrant_health_check.sh)、刷新 [knowledge_serving/audit/qdrant_health_KS-FIX-01.json](../../knowledge_serving/audit/qdrant_health_KS-FIX-01.json)、本节追加
- 未改：clean_output / Compiler / Schema / Policy / Retrieval / 其他 FIX 卡
- 未顺手起 FIX-02

## 14. 外审 RISKY 第二轮收口 / 2026-05-14 11:00 UTC+8

> **触发**：第二轮外审给出 RISKY，三个 blocker：
> 1. 原卡 KS-S0-004 `ci_commands` 仍裸命令，干净 shell exit 2（未纠偏到底）
> 2. `validate_serving_tree.py` 23 个 EXTRA（其中 1 个为本卡新增 wrapper）
> 3. 工作树脏，需分离 FIX-01 相关与无关刷新
> 用户裁决：A·ci_commands 换 wrapper；加全 23 项白名单；加 pytest；仅 commit FIX-01 相关 dirty。

### 三 blocker 处置

**Blocker 1 · KS-S0-004 ci_commands 切 wrapper**
- 改前：`python3 scripts/check_qdrant_health.py --strict --env staging`（干净 shell exit 2）
- 改后：`bash knowledge_serving/scripts/run_qdrant_health_check.sh`（干净 shell exit 0，含 load_env + tunnel up + strict + cleanup）
- §8 同步：command / artifact 双路径声明 / note 段保留历史失败证据
- **不动 status / DoD ticks / §12 5 项解锁条件**——历史失败点证据继续保留在 §12 第 96 行

**Blocker 2 · validate_serving_tree.py 白名单加全 23 项**（**越界登记**）
- 用户授权越界进入 FIX-04（目录契约 / coverage）领域，一次性把 W8-W12 已落盘 23 个文件加入白名单
- 新增白名单分桶：`EXPECTED_FILES_W8`（4）/ `W9`（3）/ `W10`（6）/ `W11`（6）/ `W12`（3）+ W0 KS-FIX-01（wrapper + 本节新增 pytest）
- 每个文件按 commit hash + 来源任务卡溯源标注
- 改前 `validate_serving_tree.py` exit 1（23 extras）→ 改后 exit 0
- **越界声明**：本次范围本应只清 FIX-01 自身贡献的 1 项；按用户裁决一次性清完，登记此节。FIX-04 起跑前需复查此白名单的攻击面（每个文件溯源是否真实合规）。

**Blocker 3 · 工作树分离**
- 仅 commit：FIX-01 相关本次改动 + 外审重跑刷新的 `qdrant_health_KS-FIX-01.json` / `qdrant_health_KS-S0-004.json`
- 不 commit：FIX-02 territory（`ecs_mirror_dryrun_KS-FIX-02.json`）+ Group C（clean_output renderer 副刷 / smoke 副刷）

### 新增自动化用例 / [knowledge_serving/tests/test_qdrant_health_schema_gate.py](../../knowledge_serving/tests/test_qdrant_health_schema_gate.py)
- `test_empty_collections_fail_closed`：空 collections → strict exit 1，`evidence_level=fail_closed`，`warnings=['empty_collections']`
- `test_missing_version_fail_closed`：缺 version → strict exit 1，`warnings=['missing_version']`
- `test_healthy_runtime_verified`：正向对照
- `test_wrapper_cleanup_on_failure`：wrapper 失败时 trap EXIT 真实触发 tunnel down（用 stub script 记录 up/down 顺序）
- 4/4 PASS · 0 forbidden tokens（无 dry-run / mock / TestClient 冒充真实验收——本测试只验证 schema gate 与 trap 行为本身）

### 第二轮收口验证 / 2026-05-14 11:00 UTC+8

| 检查 | 命令 | exit | 备注 |
|---|---|---|---|
| 1 | `python3 scripts/validate_serving_tree.py` | **0** | 23 EXTRA 清零 |
| 2 | `python3 task_cards/validate_task_cards.py` | **0** | 57 cards, DAG closed |
| 3 | `python3 task_cards/corrections/validate_corrections.py` | **0** | 26 FIX cards, DAG closed |
| 4 | `python3 -m pytest knowledge_serving/tests/test_qdrant_health_schema_gate.py -v` | **0** | 4 passed |
| 5 | `bash knowledge_serving/scripts/run_qdrant_health_check.sh`（KS-S0-004 新 ci_commands） | **0** | 真 staging 4/4 probes 200，runtime_verified |

### 待办 / outstanding（不在本卡范围）
- 任务卡 CI 契约检查器（ci_commands 干净 shell 可复跑校验）——单独 FIX 卡，建议归入 FIX-04 或新增
- `validate_serving_tree.py` 白名单 22 项越界登记的合规性复核——FIX-04 必查项

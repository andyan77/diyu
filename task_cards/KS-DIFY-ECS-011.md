---
task_id: KS-DIFY-ECS-011
phase: Dify-ECS
wave: W1
depends_on: [KS-S0-003, KS-DIFY-ECS-001]
files_touched:
  - scripts/push_to_ecs_mirror.py
  - _staging/ecs_mirror_push/<run_id>/
artifacts:
  - scripts/push_to_ecs_mirror.py
  - _staging/ecs_mirror_push/<run_id>/push_audit.json
s_gates: []
plan_sections:
  - "§A1"
  - "§A2.4"
writes_clean_output: false
ci_commands:
  - bash -c 'source scripts/load_env.sh && python3 scripts/push_to_ecs_mirror.py --dry-run --env staging'
status: done
---

# KS-DIFY-ECS-011 · 本地 → ECS `/data/clean_output/` 镜像 push 脚本 / local→ECS mirror push

## 0. 数据真源方向（**最高优先 · 不可违反**）

> **本地 `clean_output/` 是真源 / source of truth；ECS `/data/clean_output/` 是部署副本 / mirror。**
>
> 本卡的脚本是**单向 push 器**：把本地真源覆盖到 ECS 镜像，**删除 ECS 上不存在于本地的孤儿文件**，实现严格 mirror 语义（drift=0）。
>
> **禁止** 把 ECS 当真源、反向拉 ECS 文件覆盖本地——任何 "ECS → local" 数据流方向都违反全局 CLAUDE.md 真源规则。
>
> 本卡与 KS-DIFY-ECS-001（reverse verify）形成 "**推 + 校**" 对偶：011 推完后必须自动调 001 验证 drift=0，否则视为 fail。

## 0.1 ECS 数据 4 分区硬约束 / ECS data partition hard constraints（跨 W2+ 全部 ECS 卡）

> ECS 上**只有**以下 4 类数据，下游卡（编译 / 召回 / 灌库）**必须按分区裁决可消费性**，不得"看到 ECS 上有数据就当真源用"。

| 分区 / partition | 路径 / path | 定位 / status | 谁可读 / consumers | 谁可写 / writers |
|---|---|---|---|---|
| **当前可信镜像 / current trusted mirror** | `/data/clean_output/` | 与本地真源 sha256 全等 (drift=0) | 所有下游 serving / 编译 / 向量入库 | **仅** 本卡 (`KS-DIFY-ECS-011 --apply`) |
| **历史备份 / backup-only snapshots** | `/data/clean_output.bak_<run_id>/` | 旧快照，**仅供回滚** | **禁止** 任何编译 / ETL / 召回 / 读取 | 本卡 push 时自动生成；人工清理走独立运维卡 |
| **历史运行时 DB / legacy runtime data** | ECS PG `knowledge.*` | 历史 runtime，与当前 9 表真源**未对账** | **禁止** 直接作为 serving 输入；必须先经 `KS-DIFY-ECS-002` 对账裁决 | `KS-DIFY-ECS-003` 回灌（在对账通过后） |
| **未污染向量库 / clean vector store** | Qdrant collections | 当前为空；未来 collection 必须带 `compile_run_id` + `source_manifest_hash` payload | `KS-RETRIEVAL-*`（按 collection 元数据筛批次） | `KS-VECTOR-*` + `KS-DIFY-ECS-004` 灌库 |

**反偷换警告 / anti-substitution warnings（执行 AI 必读）**：
- "ECS 上有 `clean_output.bak_*`" ≠ "可读";  `.bak_*` 是冷备，**禁止读取、禁止编译、禁止灌库**。
- "ECS PG `knowledge.*` 有数据" ≠ "可作为 serving 真源";  必须等 `KS-DIFY-ECS-002` 对账后由人工裁决。
- "Qdrant 上有 collection" ≠ "可召回";  必须按 payload 的 `compile_run_id` + `source_manifest_hash` 锚定批次，跨批次的旧 collection 要么显式淘汰要么按版本号过滤。
- 凡 ECS 上路径不在表中第 1 行的，一律按 "**未授权数据 / unauthorized data**" 处理，**不得写入 serving 信任链**。

本卡是把"当前可信镜像"分区状态保鲜的唯一通道；**其他 3 个分区由各自卡（002 / 003 / 004 / VECTOR-*）按自己边界处理，本卡不越权**。

## 1. 任务目标
- **业务**：让我们能用一条命令把本地 `clean_output/` 演进同步到 ECS staging 镜像，**不留孤儿、不漂移**；同步过程自带备份与校验，不裸跑 rsync。
- **工程**：实现 `scripts/push_to_ecs_mirror.py`；内置 3 层安全网（dry-run preview / ECS-side timestamped backup / post-verify drift=0），单 push 动作落 audit 证据，可回滚。
- **S gate**：无单独门，但是 W2+ 所有依赖 ECS staging 状态的卡（KS-DIFY-ECS-002 PG 对账、KS-DIFY-ECS-004 Qdrant 灌库等）的健康前置。
- **非目标**：不写 `clean_output/`；不调 LLM；不灌 Qdrant；不动 ECS PG；不抽 markdown；不触 prod。

## 2. 前置依赖
- KS-S0-003（ECS 凭据已 env 化）
- KS-DIFY-ECS-001（reverse verify 脚本已就位，供本卡 post-verify 复用）

## 3. 输入契约
- env：`ECS_HOST` / `ECS_USER` / `ECS_SSH_KEY_PATH`
- 本地真源 / local SSOT：`clean_output/`（仓库工作树）
- 远端镜像目录 / remote mirror dir：`/data/clean_output/`（拓扑约定，见 `ECS_AND_DATA_TOPOLOGY.md` §1.5）
- 远端备份目录 / backup dir：`/data/clean_output.bak_<run_id>/`（不在 `/data/clean_output/` 子树下，不污染下次 verify）
- 不读 / 不写：prod；`--env staging` only

## 4. 执行步骤（4 阶段 · fail-closed）
1. **预检 / preflight**：env 完备；SSH 可达；本地 `git status --porcelain clean_output/` 为空（拒绝把未提交脏数据推上去）；本地 `python3 scripts/generate_manifest.py --verify` 必须 exit 0（manifest 自洽才推）
2. **Dry-run preview**：`rsync -avzn --delete --itemize-changes` 输出**完整变更清单**（新增 / 修改 / 删除三类计数 + 文件列表），落 `_staging/ecs_mirror_push/<run_id>/preview.txt`；非 `--apply` 模式到此为止
3. **Apply（仅在 `--apply` 时执行）**：
   3a. **ECS 端备份**：`ssh ... "cp -a /data/clean_output /data/clean_output.bak_<run_id>"`，失败即 abort
   3b. **真 rsync**（local SSOT 作 source → ECS mirror 作 target，含 `--delete` 同步）；rsync 失败即落 audit + 提示回滚命令；详细命令模板见 [scripts/push_to_ecs_mirror.py](../scripts/push_to_ecs_mirror.py) 的 `_rsync_apply()`
   3c. **Post-verify**：内部调用 `scripts/verify_ecs_mirror.py --dry-run --env staging`；drift!=0 → fail + 给出回滚命令
4. 全过程落 `_staging/ecs_mirror_push/<run_id>/push_audit.json`：变更清单 + 备份路径 + verify 结果 + 回滚命令 + 真源方向声明

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `scripts/push_to_ecs_mirror.py` | py | 是 | 是 | — |
| `_staging/ecs_mirror_push/<run_id>/preview.txt` | text | 否（运行证据） | 否（gitignore） | 是 |
| `_staging/ecs_mirror_push/<run_id>/push_audit.json` | json | 否（运行证据） | 否（gitignore） | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| `--dry-run --env staging` | 仅产 preview.txt + push_audit.json（status=dry_run_only）；不动 ECS；exit 0（无论 drift 多少） |
| `--apply` 但 git status 有未提交 clean_output 修改 | preflight 拒绝，exit 2 |
| `--apply` 但本地 manifest --verify 失败 | preflight 拒绝，exit 2 |
| `--apply` 完后 post-verify drift!=0 | exit 1 + audit.status=post_verify_failed + 打印回滚命令 |
| `--env prod` | 拒绝，exit 2 |
| ECS 备份创建失败 | exit 2 · 不真跑 rsync |
| SSH 中断 | exit 2 + 提示回滚 |
| 试图反向：从 ECS 拉文件到 clean_output / | 脚本无此代码路径；review grep 0 命中 |
| 重跑幂等（连跑两次 --apply）| 第二次 preview drift=0；rsync 无变化；post-verify 仍 drift=0 |
| audit json 是否登记 .bak_* 为 backup-only | `push_audit.json.partitions[].current_trusted_mirror`、`partitions[].backup_only` 都必须显式给出，且 `backup_only.consumable=false` |
| 任何下游脚本误把 `.bak_*` 当输入 | 不在本卡范围；本卡只通过 audit + §0.1 表显式声明边界，纪律由下游卡的代码评审守 |

## 7. 治理语义一致性
- **方向单一**：脚本只读本地、写 ECS、写 `_staging/`；**不写 `clean_output/`、不反向拉 ECS 文件覆盖本地**
- **路径常量**：`LOCAL_CLEAN_OUTPUT` / `ECS_REMOTE_MIRROR_DIR` 必须脚本内硬编码，禁止从环境变量或命令行接收，避免手抖删错目录
- **rsync target 安全**：脚本拼装的 rsync 远端目标必须严格匹配 `/data/clean_output/`（含尾斜杠），禁止接受任意路径
- secrets 走 env
- 不调 LLM
- audit json 必须含 `source_of_truth_direction` 字段，固定字面量 `"local clean_output/ → ECS /data/clean_output/ (one-way mirror)"`
- audit json 必须含 `partitions` 数组，按 §0.1 表声明本次 push 影响到的两个分区状态：current_trusted_mirror（path、drift_after、consumable=true）、backup_only（path、created_at、consumable=false、retention_note）。下游 reviewer 脚本可据此断言"`/data/clean_output.bak_*` 不进入 serving 信任链"。

## 8. CI 门禁
```
command: bash -c 'source scripts/load_env.sh && python3 scripts/push_to_ecs_mirror.py --dry-run --env staging'
pass: exit 0 + preview.txt + push_audit.json 落盘 + audit.status=dry_run_only + audit.partitions[0..3] 全有 + 未动 ECS
post_check: git diff --stat clean_output/ == 0；ssh 远端 stat /data/clean_output（应未变 mtime）
failure_means: push 链路不可信，本地 → ECS 同步阻塞
artifact: _staging/ecs_mirror_push/<run_id>/push_audit.json
note: 命令自带 `source scripts/load_env.sh`；空白 shell 直跑会因缺 ECS env exit 2，那是审查环境问题不是脚本失败。前提是仓库根 `.env` 已按 `.env.example` 填好。
```

## 9. CD / 环境验证
- staging：人工触发（`--apply`）；W1 收尾时一次性同步；W2+ 每次本地 clean_output 演进后按需 push
- prod：禁止本卡触达；prod 走独立卡（待立）
- 回滚：每次 apply 必有 `/data/clean_output.bak_<run_id>/`；回滚命令打印在 audit json + 终端，便于人工执行
- 健康检查：SSH 可达 + ECS 磁盘空间充足（备份 + 新版本 = 双倍占用，需检查）
- secrets：env，无硬编码

## 10. 独立审查员 Prompt
> 请：
> 1. 跑 `bash -c 'source scripts/load_env.sh && python3 scripts/push_to_ecs_mirror.py --dry-run --env staging'`，必须 exit 0 + 落 preview.txt + push_audit.json + audit.partitions 4 个分区全有 + 未真改 ECS（ssh 远端 stat `/data/clean_output` mtime 未变）。**注意命令必须自带 `source scripts/load_env.sh`；空白 shell 直跑会因缺 ECS env exit 2，那是审查环境问题不是脚本失败。**
> 2. `git diff --stat clean_output/` == 0
> 3. `grep -nE "rsync.*ECS:.*clean_output|ECS.*->.*clean_output|cp .*ECS.*clean_output" scripts/push_to_ecs_mirror.py` 必须无任何**反向**（ECS→local）语义；只允许 local→ECS 方向
> 4. `bash -c 'source scripts/load_env.sh && python3 scripts/push_to_ecs_mirror.py --env prod --dry-run'` 必须 exit != 0（prod 拒绝先于 env 校验触发）
> 5. 检查 push_audit.json：`partitions` 数组必须有 4 项 (current_trusted_mirror / backup_only / legacy_runtime_db / clean_vector_store)；其中 `backup_only.consumable=false`、`legacy_runtime_db.owned_by_card=KS-DIFY-ECS-002` 字面可见
> 6. `git grep -nE "ssh-rsa|BEGIN.*PRIVATE|password\s*=\s*['\"]" scripts/push_to_ecs_mirror.py` 0 命中
> 7. 输出 pass / conditional_pass / fail
> 阻断项：脚本反向拉 ECS；脚本写 clean_output；prod 未拒绝；rsync 远端路径可被外部参数注入；备份失败仍继续 rsync；post-verify 失败但 status 标 done。

## 11. DoD
- [x] 脚本入 git
- [x] dry-run pass（exit 0 + preview.txt + audit json）
- [x] secrets 检查 pass
- [x] 反向拉取 grep 0 命中
- [x] 路径常量硬编码 grep 验证（`LOCAL_CLEAN_OUTPUT` / `ECS_REMOTE_MIRROR_DIR` 必须在源码常量区，禁出现在 CLI args）
- [x] 至少一次 `--apply` 实测：21 项 staging 漂移 → 0 项；落 push_audit.json；备份目录在 ECS 上可见
- [x] push_audit.json 含 `partitions` 数组，且 `backup_only.consumable=false` 字面可见
- [x] 审查员 pass

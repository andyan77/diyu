---
task_id: KS-DIFY-ECS-001
phase: Dify-ECS
wave: W1
depends_on: [KS-S0-003]
files_touched:
  - scripts/verify_ecs_mirror.py
  - _staging/ecs_mirror_check/<run_id>/
artifacts:
  - scripts/verify_ecs_mirror.py
s_gates: []
plan_sections:
  - "§A1"
  - "§A2.4"
writes_clean_output: false
ci_commands:
  - bash -c 'source scripts/load_env.sh && python3 scripts/verify_ecs_mirror.py --dry-run --env staging'
status: done
---

# KS-DIFY-ECS-001 · 本仓 → ECS 镜像方向校验脚本 / local→ECS mirror drift verifier

## 0. 数据真源方向（**最高优先 · 不可违反**）

> **本地 `clean_output/` 是真源 / source of truth；ECS `/data/clean_output/` 是部署副本 / mirror。**
>
> 本卡的脚本是**单向校验器**：拿本地真源去比对 ECS 镜像，报告漂移 / drift。
>
> **禁止** 把 ECS 当 ingest 上游、把 ECS 上的 markdown 抽回本仓——任何 "ECS → local ingest" 语义都是把镜像误当真源，等于污染抽取链路。本卡早期版本曾出现此误框，已纠正。

## 1. 任务目标
- **业务**：随时能确认两边目录树是否完全一致；不一致时给出证据，方便人工裁决要不要重新部署。
- **工程**：实现 `scripts/verify_ecs_mirror.py`，走 SSH 只读端口做 sha256 全量比对，报告 only_local / only_ecs / hash_mismatch 三类漂移；运行证据落 `_staging/ecs_mirror_check/<run_id>/`。
- **S gate**：无单独门，但是 ECS 镜像一致性入口，是后续 KS-DIFY-ECS-002（ECS PG ↔ 9 表对账）与 KS-DIFY-ECS-003（serving views 回灌 ECS PG）的健康前提。
- **非目标**：不写 ECS（推送由后续卡负责）；不写真源；不调 LLM；不灌 Qdrant；不抽 markdown。

## 2. 前置依赖
- KS-S0-003（ECS 凭据已 env 化）

## 3. 输入契约
- env：`ECS_HOST` / `ECS_USER` / `ECS_SSH_KEY_PATH`
- 远端镜像目录 / remote mirror dir：`/data/clean_output/`（拓扑约定，见 `ECS_AND_DATA_TOPOLOGY.md` §1.5；不再需要 `ECS_MARKDOWN_SOURCE_DIR`）
- 不读：prod；`--env staging` only

## 4. 执行步骤
1. 本地 `find clean_output/ -type f ! -path '*/.*' | xargs sha256sum` → 本地真源 hash 表
2. SSH 远端 `find /data/clean_output/ -type f ! -path '*/.*' | xargs sha256sum` → ECS 镜像 hash 表
3. 三方对账 / three-way diff：only_local（本地有 / ECS 缺）、only_ecs（ECS 有 / 本地缺）、hash_mismatch（路径在但内容不一致）
4. 写 `_staging/ecs_mirror_check/<run_id>/mirror_drift_report.json`：含三类清单 + 总计 + 真源方向声明
5. 漂移项 > 0 → exit 1；完全一致 → exit 0；连不上 → exit 2

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `scripts/verify_ecs_mirror.py` | py | 是 | 是 | — |
| `_staging/ecs_mirror_check/<run_id>/mirror_drift_report.json` | json | 否（运行证据） | 否（gitignore） | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| ECS 完全镜像本地 | exit 0；report 中 drift = 0 |
| ECS 多 1 个文件 | exit 1；只在 only_ecs 列表里 |
| ECS 缺 1 个文件 | exit 1；只在 only_local 列表里 |
| 同路径内容不同 | exit 1；hash_mismatch 列表里且记两端 hash |
| SSH 失败 | retry 后 exit 2 + 明确错误 |
| --env prod | 拒绝（exit 2） |
| 试图写 clean_output / 反向拉 ECS 文件覆盖本地 | 脚本无此代码路径；review 时 grep 必须 0 命中 |

## 7. 治理语义一致性
- **方向单一**：脚本只读两端、写 _staging；不写 clean_output、不写 ECS、不反向覆盖本地
- secrets 走 env
- 不调 LLM
- 漂移报告的 `source_of_truth_direction` 字段必须固定字面量 `"local clean_output/ → ECS /data/clean_output/ (one-way mirror)"`，下游消费方可据此断言方向

## 8. CI 门禁
```
command: bash -c 'source scripts/load_env.sh && python3 scripts/verify_ecs_mirror.py --dry-run --env staging'
pass: dry-run 输出本地 + ECS 文件计数 + 0 漂移 + exit 0 + 不真改任何文件 + 无 clean_output / ECS 写入意图
artifact: _staging/ecs_mirror_check/<run_id>/mirror_drift_report.json
post_check: git diff --stat clean_output/ == 0 行
note: 命令自带 `source scripts/load_env.sh`，新手 / 空白 shell 直接可跑；前提是仓库根 `.env` 已按 `.env.example` 填好（ECS_HOST / ECS_USER / ECS_SSH_KEY_PATH）。CI runner 可改用直接注入 env 的等价方式。
```

## 9. CD / 环境验证
- staging：每周自动跑 + 漂移>0 时人工审阅
- prod：手动触发（待立卡），需审批
- 回滚：本卡只读，无需回滚；漂移修复由独立的 redeploy 卡负责
- 健康检查：SSH 可达
- secrets：env，无硬编码

## 10. 独立审查员 Prompt
> 请：
> 1. 跑 `python3 scripts/verify_ecs_mirror.py --dry-run --env staging`，确认输出含本地 + ECS 文件计数，且未真改任何文件
> 2. `git diff --stat clean_output/` == 0
> 3. `grep -nE "clean_output" scripts/verify_ecs_mirror.py` 命中行必须全部是常量 / 注释 / 禁止性 assert，不能有 write/cp/rsync 写 clean_output 的语义
> 4. `grep -nE "rsync.*ECS|scp.*from.*ECS|ECS.*->.*clean_output|cp .*ECS.*clean_output" scripts/verify_ecs_mirror.py` 必须 0 命中（防反向 ingest）
> 5. `python3 scripts/verify_ecs_mirror.py --env prod --dry-run` 必须 exit != 0
> 6. `git grep -nE "ssh-rsa|BEGIN.*PRIVATE|password\s*=\s*['\"]" scripts/verify_ecs_mirror.py` 0 命中
> 7. 输出 pass / conditional_pass / fail
> 阻断项：脚本任何路径反向把 ECS 拉回本地；脚本写 clean_output；prod 未拒绝；凭证入仓。

## 11. DoD
- [x] 脚本入 git
- [x] dry-run pass
- [x] secrets 检查 pass
- [x] 反向 ingest grep 0 命中
- [x] 审查员 pass

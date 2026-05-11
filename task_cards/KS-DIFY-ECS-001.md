---
task_id: KS-DIFY-ECS-001
phase: Dify-ECS
depends_on: [KS-S0-003]
files_touched:
  - scripts/ingest_from_ecs.py
  - _staging/ecs_ingest/<run_id>/
artifacts:
  - scripts/ingest_from_ecs.py
s_gates: []
plan_sections:
  - "§A1"
  - "§A2.4"
writes_clean_output: false
ci_commands:
  - python3 scripts/ingest_from_ecs.py --dry-run --env staging
status: not_started
---

# KS-DIFY-ECS-001 · ECS → 本仓 candidates 抽取脚本

## 1. 任务目标
- **业务**：把 ECS 上的业务 markdown 抽到本仓 candidates。
- **工程**：实现 ingest_from_ecs.py；走 SSH/PG 读端；落到 `_staging/ecs_ingest/<run_id>/` 后过 4 闸自检；本卡不合入 clean_output，合入由独立 S0-class 卡触发。
- **S gate**：无单独门，但是 ECS 集成入口。
- **非目标**：不改 ECS 写端；不灌 Qdrant。

## 2. 前置依赖
- KS-S0-003

## 3. 输入契约
- env：ECS_SSH_KEY_PATH, PG_USER, PG_PASSWORD, PG_HOST, PG_PORT
- 不读：prod；--env staging

## 4. 执行步骤
1. 连 ECS 拉取 markdown（rsync 或 PG dump）
2. **写到 `_staging/ecs_ingest/<run_id>/`**（仓库根 staging 区，**不在 clean_output 内**）
3. 在 staging 区跑 4 闸自检；结果写 `_staging/ecs_ingest/<run_id>/four_gate_self_check.json`
4. **本卡到此为止——不合入正式 candidates**。合入由独立的人工裁决 + 新 S0-class 卡（待立卡）触发；理由：候选入真源必须经 S0 治理路径，禁止 ECS 集成卡绕行

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | CI artifact |
|---|---|---|---|---|
| `scripts/ingest_from_ecs.py` | py | 是 | 是 | — |
| `_staging/ecs_ingest/<run_id>/*.md` | md | 否（候选） | 否（gitignore） | 是 |
| `_staging/ecs_ingest/<run_id>/four_gate_self_check.json` | json | 否 | 否 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| SSH 失败 | retry 后 exit 1 |
| 4 闸失败 | staged 标 unverified，不允许任何下游消费 |
| 重复运行同 run_id | 幂等（已存在则跳过） |
| --env prod | 拒绝 |
| 大量文件 | 分批处理 |
| 试图把 staging 内容直接 cp 到 clean_output | 脚本拒绝；clean_output 写入仅由 S0 卡负责 |

## 7. 治理语义一致性
- **0 写 clean_output**：本卡所有产物均在 `_staging/`，不进真源目录
- 合入真源需独立 S0-class 卡（人工触发）
- 不调 LLM
- secrets 走 env

## 8. CI 门禁
```
command: python3 scripts/ingest_from_ecs.py --dry-run --env staging
pass: 列出待 ingest 文件 + 不真改文件 + 无 clean_output 写入意图
artifact: _staging/ecs_ingest/<run_id>/four_gate_self_check.json
post_check: git diff --stat clean_output/ == 0 行
```

## 9. CD / 环境验证
- staging：每周自动跑 + 人工审阅 staged
- prod：手动触发，需要审批
- 回滚：删 staged_<run_id>
- 健康检查：SSH / PG 可达
- secrets：env，无硬编码

## 10. 独立审查员 Prompt
> 请：1) dry-run 输出文件清单且全部位于 `_staging/`；2) `git diff --stat clean_output/` == 0；3) `git grep "clean_output" scripts/ingest_from_ecs.py` 0 命中或仅出现在禁止性 assertion；4) 试图 --env prod 必须拒绝；5) git grep 无凭证；6) 输出 pass / fail。
> 阻断项：脚本写 clean_output；凭证入仓；prod 未拒绝。

## 11. DoD
- [ ] 脚本入 git
- [ ] dry-run pass
- [ ] secrets 检查 pass
- [ ] 审查员 pass

# 密钥治理日志 / Key Governance Log · KS-S0-003

> 落盘日期 / date: 2026-05-12
> 任务卡 / task card: `KS-S0-003` · ECS 密钥轮换 + 环境变量化
> S 门 / S-gate: S0

## 1. 决策记录 / decision record

**用户决策 (2026-05-12)**：当前 LLM API key **不轮换 / not rotated**，仅做环境变量化 + git 防泄露加固。
完整风险接受记录见 `clean_output/audit/known_risk_accepted_2026-05-12.md`。

## 2. 治理动作 / governance actions

| # | 动作 / action | 路径 / path | 状态 |
|---|---|---|---|
| 1 | 创建 `.gitignore` 含 `.env` 等 11 类模式 | `.gitignore` | ✅ |
| 2 | 创建 `.env.example` 模板（变量名，无值）| `.env.example` | ✅ |
| 3 | 创建本地 `.env`（含明文 key，gitignored）| `.env`（不入 git）| ✅ |
| 4 | 创建 env 加载器 + git 跟踪自检 | `scripts/load_env.sh` | ✅ |
| 5 | 创建明文密钥扫描器（CI 门禁）| `scripts/check_no_secrets.sh` | ✅ |
| 6 | 三道安全门首次提交前验证 | git init → check-ignore → diff --cached | ✅ |

## 3. 环境变量清单 / env variable inventory

| 变量名 / var | 用途 / usage | 状态 |
|---|---|---|
| `DASHSCOPE_API_KEY` | QWEN（通义千问）· embedding / rerank / llm_assist | ✅ 本地已就位 |
| `DEEPSEEK_API_KEY` | DEEPSEEK · llm_assist 备选 / fallback | ✅ 本地已就位 |
| `ECS_SSH_KEY_PATH` | ECS SSH 私钥路径 | ⏸ 待填（部署 Qdrant 时）|
| `PG_HOST` / `PG_PORT` / `PG_USER` / `PG_PASSWORD` / `PG_DATABASE` | PostgreSQL 连接 | ⏸ 待填 |
| `QDRANT_URL_STAGING` / `QDRANT_API_KEY` | Qdrant 向量库 | ⏸ 待填 |
| `MODEL_POLICY_VERSION` | 与 `model_policy.yaml` 同源 | ✅ `mp_20260512_001` |

## 4. CI 门禁验收 / CI gate verification

```
$ bash scripts/check_no_secrets.sh
=== check_no_secrets · 扫描追踪文件中的明文密钥 ===
✅ .env 未被追踪 / not tracked
✅ 追踪文件中无明文密钥 / no plaintext keys in tracked files
=== 全部检查通过 / all checks passed ===
```

```
$ source scripts/load_env.sh
✅ env 已加载 / loaded: QWEN + DEEPSEEK keys ready
```

## 5. 未来轮换触发条件 / future rotation triggers

任一发生立即轮换 / immediately rotate if any of:

1. `check_no_secrets.sh` 检测到 git 历史中有 `sk-` 明文
2. `.env` 出现在任何 git 提交
3. 设备更换 / 团队成员变动 / 项目转交
4. LLM 提供方控制台显示异常调用 / abnormal usage

## 6. 与 task_cards 的对应 / linkage

- 任务卡 `KS-S0-003` status: `not_started` → `done`
- dag.csv 同步更新
- 关联文档：`known_risk_accepted_2026-05-12.md`

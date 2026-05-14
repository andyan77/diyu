---
task_id: KS-DIFY-ECS-005
phase: Dify-ECS
wave: W10
depends_on: [KS-DIFY-ECS-003, KS-RETRIEVAL-008]
files_touched:
  - knowledge_serving/serving/log_writer.py
  - knowledge_serving/scripts/pg_dual_write.py
  - knowledge_serving/tests/test_log_dual_write.py
artifacts:
  - knowledge_serving/serving/log_writer.py
  - knowledge_serving/scripts/pg_dual_write.py
  - knowledge_serving/audit/dual_write_staging_KS-FIX-13.json
s_gates: [S8]
plan_sections:
  - "§4.5"
  - "§9.3"
writes_clean_output: false
ci_commands:
  - python3 -m pytest knowledge_serving/tests/test_log_dual_write.py -v
status: done
---

# KS-DIFY-ECS-005 · context_bundle_log PG outbox mirror（CSV 单 canonical）

## 1. 任务目标
- **业务**：CSV 是 §4.5 唯一 canonical；ECS PG 作为只读 mirror 供 BI / 告警 / 跨服务查询使用。
- **工程**：扩 KS-RETRIEVAL-008 的 log_writer，**先写 CSV（canonical）→ 再 outbox 同步到 PG（mirror）**；PG 同步失败不影响 CSV 写入，**S8 回放始终以 CSV 为真源**。
- **S gate**：S8（CSV 单源），不引入双 canonical。
- **非目标**：PG 不是回放真源；PG 失败不阻断业务；不改 bundle 字段。

## 2. 前置依赖
- KS-DIFY-ECS-003、KS-RETRIEVAL-008

## 3. 输入契约
- 读：context_bundle_log schema
- 写：control/context_bundle_log.csv + ECS PG ks_context_bundle_log 表
- env：PG_*

## 4. 执行步骤
1. log_writer 改造：**CSV 先写并 fsync**（canonical 落盘成功才返回业务调用方）
2. 把已写行入 outbox 队列；后台 worker 异步 INSERT 到 PG mirror 表
3. PG 写失败：行保留在 outbox + 标 `pending_pg_sync`；可重试；**不回退、不影响 CSV**
4. 一致性校验脚本（独立运行）：以 CSV 为基准，对比 PG mirror 缺哪些行 → 重放 outbox

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `log_writer.py`（修改） | py | 是 | 是 |
| `pg_dual_write.py` | py | 是 | 是 |
| `test_log_dual_write.py` | py | 是 | 是 |
| `knowledge_serving/audit/dual_write_staging_KS-FIX-13.json` | json（含 env / checked_at / timestamp / git_commit / evidence_level） | 是（staging dual-write runtime 证据） | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| PG down | CSV 正常写 + outbox 排队；业务调用 200 |
| PG 长时间 down | outbox 堆积告警；CSV 仍 canonical |
| CSV 写失败（磁盘满 / 权限） | raise；业务调用失败；**PG 也不得写**（不能反向成为隐含真源） |
| 一致性脚本：PG 多出行 | 报警（异常）；CSV 才是基准 |
| 一致性脚本：PG 缺行 | outbox 重放补齐 |
| 同 request_id 两次写 | CSV 拒绝重复（unique 约束）；PG 同 |
| S8 回放只读 PG | 测试断言：回放代码路径只 open CSV |

## 7. 治理语义一致性
- **CSV 是唯一 canonical**：S8 回放代码路径只读 `control/context_bundle_log.csv`
- PG 是 outbox mirror：用于 BI / 跨服务查询，**绝不作为回放真源**
- PG 写失败不能阻塞业务；CSV 写失败必须阻塞
- 不调 LLM
- 一致性校验脚本独立运行

## 8. CI 门禁
```
command: python3 -m pytest knowledge_serving/tests/test_log_dual_write.py -v
pass: PG down / up 用例全绿
artifact: pytest report
```

## 9. CD / 环境验证
- staging：每次 PR 跑
- prod：双写默认开
- 健康检查：pending_pg_sync 数 < 阈值
- 监控：写延迟、一致性差异
- secrets：env

## 10. 独立审查员 Prompt
> 请：1) PG down 时 CSV 仍 200 写完；2) `grep -rn "PG\|psycopg" knowledge_serving/scripts/replay*.py` 必须 0 命中（回放只读 CSV）；3) CSV 写失败时业务必须 5xx，且 PG 不得有新行；4) outbox pending 可重放；5) 输出 pass / fail。
> 阻断项：S8 回放路径访问 PG；CSV 失败但 PG 仍写；PG 失败阻塞业务。

## 11. DoD
- [x] log_writer 扩展入 git（双写 + outbox + fsync + dedup + reconcile_pg_mirror）
- [x] pytest 全绿（9/9 + 全量 220/220）
- [x] 审查员 pass（2026-05-13 W10 外审 CONDITIONAL_PASS：本地核心交付全通——9/9 + 全量 220/220 + 单 canonical + reconcile CLI + 反向 grep S8 PG-free 全证；遗留两项均非本卡阻断：1) ECS/PG staging env 当前缺失 → 真 reconcile 留待 staging 部署阶段；2) `replay*.py` 不在本仓 → 属 KS-DIFY-ECS-010 回放卡范围）

## 12. 实施记录 / 2026-05-13 W10

### 工程要点

- **CSV 优先 + fsync**：`write_context_bundle_log` 在 `open("a")` with 块内 `f.flush() + os.fsync()`，
  磁盘落定才返回；任一步 raise → 函数立刻退出，**pg_writer 永远不被触达**（卡 §6 case 3 守门）
- **dedup**：写之前流式扫 CSV，命中同 request_id 立刻 raise `LogWriteError("duplicate...")`，
  在 PG mirror 之前拦下（卡 §6 case 6）
- **outbox jsonl**：CSV 同目录下的 `context_bundle_log_outbox.jsonl`，
  每行 `{request_id, status, attempts, error, queued_at, row}`；
  PG 失败 → `pending_pg_sync`；reconcile 重放成功 → `replayed`
- **callable 注入 PG 接口**：log_writer 不 import `psycopg` / `sqlalchemy`，
  所有 PG 交互走 `pg_writer: Callable[[dict], None]` + `pg_reader: Callable[[], list[dict]]`，
  保证 S8 回放路径 (`read_log_rows`) PG-free
- **reconcile 脚本** `knowledge_serving/scripts/reconcile_context_bundle_log_mirror.py`：
  独立 CLI（dry-run 默认 / `--apply` 真写），走 SSH + docker exec psql（同 KS-DIFY-ECS-003 模式），
  以 CSV 为基准，PG 缺行 → outbox 重放；PG 多行 → 报警 exit 1，不擅自删 PG

### 测试矩阵（9 case，全 PASS）

| 测试 | 覆盖卡 §6 / §7 / §10 |
|---|---|
| test_pg_down_csv_still_writes_outbox_queued | §6 PG down → CSV 200 + outbox |
| test_pg_long_down_outbox_stacks | §6 PG 长 down → outbox 堆积 |
| test_csv_failure_pg_never_called | §6 CSV 失败 → raise + PG 0 调用 |
| test_reconcile_pg_extra_row_alarms | §6 一致性：PG 多行 → extra_in_pg 报警 |
| test_reconcile_pg_missing_row_replays | §6 一致性：PG 缺行 → outbox 重放补齐 |
| test_duplicate_request_id_rejected | §6 同 request_id 两次写 → CSV 拒 + PG 不二调 |
| test_replay_path_does_not_touch_pg | §10 read_log_rows + 模块级 PG-free |
| test_reconcile_script_uses_lw_callable_interface | callable 注入接口反证 |
| test_pg_up_no_outbox_pending | PG 顺利时 outbox 不入 pending |

### 回归证据

- `python3 -m pytest knowledge_serving/tests/test_log_dual_write.py -v` → 9 passed
- `python3 -m pytest knowledge_serving/tests/` → 220 passed
- `python3 knowledge_serving/scripts/run_context_retrieval_demo.py --all` → exit 0, 4/4 PASS（向后兼容）
- `python3 task_cards/validate_task_cards.py` → 57 cards, DAG closed, S0-S13 covered
- `bash knowledge_serving/scripts/lint_no_duplicate_log.sh` → 单 canonical OK

### 边界遗留 / next-card handoff

- PG DDL（`knowledge.context_bundle_log` mirror 表 + `request_id` UNIQUE）由 staging
  部署阶段建表，不属本卡范围；当前 reconcile 脚本的 dry-run 模式可在表存在后立即跑通
- `--live` reconcile 真实跑需要 `ECS_HOST` / `PG_USER` / `PG_DATABASE` / `ECS_SSH_KEY_PATH` env，
  与 KS-DIFY-ECS-003 同款约定，无新增 secrets

## 13. 2026-05-14 KS-FIX-13 staging 双写演练补证

- 原 §8 pytest 复跑：`python3 -m pytest knowledge_serving/tests/test_log_dual_write.py -v` → exit 0（11 passed，含 RFC4180 csv-newline + column-count drift fail-closed 用例）
- staging 真实 dual-write drill：本轮 uvicorn /v1/retrieve_context POST × 34 distinct queries 全部 attempt-1 ok → canonical CSV 累计 100 行 → `reconcile_context_bundle_log_mirror.py --apply` replayed=34 / replay_errors=0 → post-verify csv=pg=100 / missing=0 / extra=0 / mismatch=0
- **sha256 双侧逐行比对** (FIX-13 §1 strict)：对 100 行公共 request_id × 28 LOG_FIELDS canonical json sha256，CSV vs PG match=100 / mismatch=0 / exit 0
- staging host 真值校验：ECS_HOST=8.217.175.36（公网 staging IP）；transport=_ssh_psql via SSH+docker exec psql，非 localhost mock
- runtime envelope：`knowledge_serving/audit/dual_write_staging_KS-FIX-13.json`（env=staging / checked_at=2026-05-14T14:37:17Z / git_commit=c8977cc / evidence_level=runtime_verified / verdict=PASS）

### 2026-05-14 本轮复跑收口

- `source scripts/load_env.sh && python3 knowledge_serving/scripts/pg_dual_write.py --staging --reconcile --strict` → exit 0；row_count=104 / pg_count=104 / only_csv=0 / only_pg=0 / sha256_mismatch=0
- runtime envelope 刷新：`knowledge_serving/audit/dual_write_staging_KS-FIX-13.json`（env=staging / checked_at=2026-05-14T14:44:49Z / timestamp=2026-05-14T14:44:49Z / git_commit=c8977cc61544599445b0a76b85f8fb5b3b40154c / evidence_level=runtime_verified / verdict=PASS）

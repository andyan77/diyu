---
task_id: KS-DIFY-ECS-005
phase: Dify-ECS
depends_on: [KS-DIFY-ECS-003, KS-RETRIEVAL-008]
files_touched:
  - knowledge_serving/serving/log_writer.py
  - knowledge_serving/tests/test_log_dual_write.py
artifacts:
  - knowledge_serving/serving/log_writer.py
s_gates: [S8]
plan_sections:
  - "§4.5"
  - "§9.3"
writes_clean_output: false
ci_commands:
  - pytest knowledge_serving/tests/test_log_dual_write.py -v
status: not_started
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
| `test_log_dual_write.py` | py | 是 | 是 |

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
command: pytest knowledge_serving/tests/test_log_dual_write.py -v
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
- [ ] log_writer 扩展入 git
- [ ] pytest 全绿
- [ ] 审查员 pass

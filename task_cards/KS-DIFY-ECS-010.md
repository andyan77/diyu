---
task_id: KS-DIFY-ECS-010
phase: Dify-ECS
wave: W11
depends_on: [KS-DIFY-ECS-005]
files_touched:
  - scripts/replay_context_bundle.py
  - knowledge_serving/tests/test_replay.py
artifacts:
  - scripts/replay_context_bundle.py
s_gates: [S8]
plan_sections:
  - "§B Phase5"
writes_clean_output: false
ci_commands:
  - pytest knowledge_serving/tests/test_replay.py -v
status: not_started
---

# KS-DIFY-ECS-010 · 日志回放 demo

## 1. 任务目标
- **业务**：任意 request_id 可重建当时喂给 LLM 的 context_bundle，满足 S8 回放。
- **工程**：实现 replay_context_bundle.py，按 log 行字段重建 bundle 并 hash 对比。
- **S gate**：S8。
- **非目标**：不重跑 LLM 生成；不改 log。

## 2. 前置依赖
- KS-DIFY-ECS-005

## 3. 输入契约
- 读：control/context_bundle_log.csv（或 ECS PG）
- 入参：request_id

## 4. 执行步骤
1. 按 request_id 查 log 行
2. 根据 compile_run_id / source_manifest_hash 加载当时 view + control
3. 按 retrieved_*_ids 拼回 bundle
4. 与 log 中 context_bundle_hash 对比

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `replay_context_bundle.py` | py | 是 | 是 |
| `test_replay.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 不存在 request_id | exit ≠ 0 |
| compile_run_id 对应数据已删 | 明确报错 |
| hash 不一致 | exit ≠ 0 |
| 跨 compile_run_id 混用 | 拒绝 |
| 任意时间点的 log 都能重建 | pass |

## 7. 治理语义一致性
- S8 严格
- 不调 LLM
- 不写 clean_output

## 8. CI 门禁
```
command: pytest knowledge_serving/tests/test_replay.py -v
pass: 5+ case 全绿
artifact: pytest report
```

## 9. CD / 环境验证
- staging：每次 PR 抽样 1 个历史 request_id 跑
- 健康检查：回放成功率
- 监控：回放失败告警

## 10. 独立审查员 Prompt
> 请：1) 抽 3 个历史 request_id 跑 replay，hash 一致；2) 故意改 1 个 csv，replay 必 fail；3) 输出 pass / fail。
> 阻断项：篡改未被检出。

## 11. DoD
- [ ] replay 入 git
- [ ] pytest 全绿
- [ ] 审查员 pass

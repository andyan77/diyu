---
task_id: KS-VECTOR-003
phase: Vector
depends_on: [KS-VECTOR-001, KS-S0-004]
files_touched:
  - knowledge_serving/scripts/qdrant_filter_smoke.py
  - knowledge_serving/tests/test_vector_offline.py
artifacts:
  - knowledge_serving/scripts/qdrant_filter_smoke.py
s_gates: [S10]
plan_sections:
  - "§8"
  - "§B Phase4"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/qdrant_filter_smoke.py --offline
status: not_started
---

# KS-VECTOR-003 · vector filter regression + structured-only fallback

## 1. 任务目标
- **业务**：验证 payload filter 真生效；Qdrant 不可用时降级可用。
- **工程**：4 类抽样 filter（brand / gate / content_type / cross-tenant）+ offline 模式。
- **S gate**：S10。
- **非目标**：不改 chunks；不灌库。

## 2. 前置依赖
- KS-VECTOR-001、KS-S0-004

## 3. 输入契约
- 读：qdrant_chunks.jsonl、qdrant_fallback.yaml
- env：QDRANT_URL_STAGING（可选；offline 模式不需要）

## 4. 执行步骤
1. offline 模式：用 jsonl 直接做 filter 模拟 + 断言
2. online 模式：调 staging Qdrant 实跑（CD 阶段）
3. 4 类 filter：brand_faye / domain_general / gate=active / cross-tenant 0 命中

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `qdrant_filter_smoke.py` | py | 是 | 是 |
| `test_vector_offline.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| brand_a 请求 → brand_b 命中 | 永不发生 |
| inactive 命中 | 永不发生 |
| Qdrant down | fallback 启用 + offline 报告 |
| filter 缺字段 | fail-closed |
| 维度不匹配 | raise |

## 7. 治理语义一致性
- S10 严格
- brand hard filter
- 不调 LLM

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/qdrant_filter_smoke.py --offline
pass: 4 类 filter 全过 + cross-tenant 0
failure_means: 向量召回不可信
artifact: smoke report
```

## 9. CD / 环境验证
- online smoke 在 KS-CD-001 中触发
- 监控：filter 失败率

## 10. 独立审查员 Prompt
> 请：1) offline smoke 4/4；2) cross-tenant 0 命中；3) 输出 pass / fail。
> 阻断项：cross-tenant 串味。

## 11. DoD
- [ ] smoke 入 git
- [ ] CI pass
- [ ] 审查员 pass

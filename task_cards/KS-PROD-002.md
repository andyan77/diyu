---
task_id: KS-PROD-002
phase: Production-Readiness
wave: W12
depends_on: [KS-DIFY-ECS-006]
files_touched:
  - knowledge_serving/tests/test_tenant_isolation_e2e.py
artifacts:
  - knowledge_serving/tests/test_tenant_isolation_e2e.py
s_gates: [S9]
plan_sections:
  - "§12 S9"
  - "§A3"
writes_clean_output: false
ci_commands:
  - pytest knowledge_serving/tests/test_tenant_isolation_e2e.py -v
status: not_started
---

# KS-PROD-002 · 跨租户隔离 e2e 回归

## 1. 任务目标
- **业务**：保证 brand_a 任何路径都召不回 brand_b，即使在 ECS prod 环境。
- **工程**：组合 retrieve_context API + Qdrant + PG，对 brand_a / brand_b / domain_only 三类 tenant 做 e2e 测试。
- **S gate**：S9。
- **非目标**：不实现新功能。

## 2. 前置依赖
- KS-DIFY-ECS-006

## 3. 输入契约
- 读：staging ECS 全栈
- env：PG / QDRANT / API_BASE_URL

## 4. 执行步骤
1. 构造 brand_a tenant，发起 10 类典型 query → 验证返回 0 brand_b 行
2. 构造 brand_b tenant，发起同 query → 同样 0 brand_a 行
3. 构造 domain_only tenant → 0 brand_x 行
4. 验证 log 中 resolved_brand_layer 与 tenant 一致

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `test_tenant_isolation_e2e.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| user_query 含品牌名 | resolved_brand_layer 不切换 |
| api 入参试图 brand_layer=brand_b | 拒绝或忽略 |
| 跨 tenant 共享 API key | 拒绝 |
| Qdrant filter 漏字段 | 触发 fail-closed |
| 30 例随机抽样 | 0 串味 |

## 7. 治理语义一致性
- S9 严格
- 不调 LLM 做裁决
- 仅 staging（prod 单独审批后跑）

## 8. CI 门禁
```
command: pytest knowledge_serving/tests/test_tenant_isolation_e2e.py -v
pass: 30+ case 全绿，0 串味
failure_means: 不可上线
artifact: pytest report
```

## 9. CD / 环境验证
- staging：每发布跑
- prod：上线后定期复跑（每周）
- 监控：tenant 误命中告警

## 10. 独立审查员 Prompt
> 请：1) 30 例抽样跑；2) 0 串味；3) 试图 user_query 切换 brand_layer 不发生；4) 输出 pass / fail。
> 阻断项：任一串味；resolved_brand_layer 被 query 影响。

## 11. DoD
- [ ] e2e 测试入 git
- [ ] CI pass
- [ ] 审查员 pass

---
task_id: KS-RETRIEVAL-001
phase: Retrieval
depends_on: [KS-COMPILER-008]
files_touched:
  - knowledge_serving/serving/tenant_scope_resolver.py
  - knowledge_serving/tests/test_tenant_resolver.py
artifacts:
  - knowledge_serving/serving/tenant_scope_resolver.py
s_gates: [S9]
plan_sections:
  - "§6.1"
writes_clean_output: false
ci_commands:
  - pytest knowledge_serving/tests/test_tenant_resolver.py -v
status: not_started
---

# KS-RETRIEVAL-001 · tenant_scope_resolver

## 1. 任务目标
- **业务**：从 tenant_id / api_key 推断 allowed_layers，是多租户隔离的入口。
- **工程**：实现 resolver，**禁止**从用户自然语言推断 brand。
- **S gate**：S9 tenant_isolation_regression。
- **非目标**：不做 API；不接 Dify。

## 2. 前置依赖
- KS-COMPILER-008

## 3. 输入契约
- 读：tenant_scope_registry.csv
- 入参：tenant_id / api_key_id
- 不读：user_query 内容

## 4. 执行步骤
1. 加载 registry
2. resolve(tenant_id) → {brand_layer, allowed_layers, enabled, environment}
3. enabled=false / 未登记 → exception
4. 单元测试 ≥ 10 case

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `tenant_scope_resolver.py` | py | 是 | 是 |
| `test_tenant_resolver.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 未登记 tenant | raise |
| enabled=false | raise |
| api_key 错配 | raise |
| 试图传 user_query | 函数签名禁止 |
| tenant_a 解析得到 brand_b | 永远不发生（断言） |

## 7. 治理语义一致性
- 仅从 registry 推断；**禁止**用 user_query
- 不调 LLM
- S9 防串味前置

## 8. CI 门禁
```
command: pytest knowledge_serving/tests/test_tenant_resolver.py -v
pass: 10 case 全绿，含 fail-closed 用例
failure_means: 隔离不可信
artifact: pytest report
```

## 9. CD / 环境验证
不部署。

## 10. 独立审查员 Prompt
> 请：1) 跑 pytest；2) 函数签名不含 user_query；3) grep 源码无 LLM 调用；4) 输出 pass / fail。
> 阻断项：函数从自然语言推断 brand。

## 11. DoD
- [ ] resolver 入 git
- [ ] pytest 10/10
- [ ] 审查员 pass

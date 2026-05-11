---
task_id: KS-DIFY-ECS-008
phase: Dify-ECS
depends_on: [KS-DIFY-ECS-007]
files_touched:
  - docs/dify_chatflow_nodes.md
  - dify/chatflow.dsl
  - scripts/validate_dify_dsl.py
artifacts:
  - docs/dify_chatflow_nodes.md
  - dify/chatflow.dsl
s_gates: []
plan_sections:
  - "§10"
writes_clean_output: false
ci_commands:
  - python3 scripts/validate_dify_dsl.py
status: not_started
---

# KS-DIFY-ECS-008 · Dify Chatflow 10 节点

## 1. 任务目标
- **业务**：把 §10 十个节点落成可导入 Dify 的 DSL。
- **工程**：DSL 文件 + 节点说明 doc；validator 检查节点顺序与禁用项。
- **S gate**：无单独门。
- **非目标**：不部署到 Dify prod。

## 2. 前置依赖
- KS-DIFY-ECS-007

## 3. 输入契约
- 读：§10 节点清单、API openapi.yaml

## 4. 执行步骤
1. 10 节点：租户识别 / 意图分类 / ContentType 路由 / business brief 检查 / 调用 retrieve_context / 判断 fallback_status / LLM 生成 / Guardrail / 输出 + evidence / 写日志
2. 写 chatflow.dsl
3. Agent 节点限制：仅 ContentType 辅助 / 重排辅助 / 自检
4. validator 检查：无 Agent 直查 9 表；无绕 tenant filter；无 hard 缺字段下成稿

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `dify_chatflow_nodes.md` | md | 是 | 是 |
| `chatflow.dsl` | yaml/json | 是 | 是 |
| `validate_dify_dsl.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| Agent 节点试图直查 9 表 | validator fail |
| 缺 guardrail 节点 | fail |
| 节点顺序错乱 | fail |
| LLM 生成节点在 fallback 判断前 | fail |
| 日志节点缺 | fail |

## 7. 治理语义一致性
- Agent 限制严格（§10）
- 不绕 tenant filter
- 不调 LLM 做治理判断

## 8. CI 门禁
```
command: python3 scripts/validate_dify_dsl.py
pass: 10 节点齐 + 顺序对 + Agent 限制
artifact: validate report
```

## 9. CD / 环境验证
- staging Dify：导入 DSL 跑
- prod：人工审批

## 10. 独立审查员 Prompt
> 请：1) 10 节点齐；2) Agent 不直查 9 表；3) Guardrail 在 LLM 之后；4) 输出 pass / fail。
> 阻断项：Agent 绕过限制。

## 11. DoD
- [ ] DSL + doc 入 git
- [ ] validator pass
- [ ] 审查员 pass

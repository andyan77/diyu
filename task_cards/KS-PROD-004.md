---
task_id: KS-PROD-004
phase: Production-Readiness
wave: W18
depends_on: [KS-PROD-001]
files_touched:
  - docs/prod_readiness_delta.md
  - knowledge_serving/audit/prod_readiness_delta_KS-PROD-004.json
artifacts:
  - docs/prod_readiness_delta.md
  - knowledge_serving/audit/prod_readiness_delta_KS-PROD-004.json
s_gates: [S13]
plan_sections:
  - "§A1"
  - "§A3"
writes_clean_output: false
ci_commands:
  - python3 -c "import json;d=json.load(open('knowledge_serving/audit/prod_readiness_delta_KS-PROD-004.json'));assert d['user_signed_off']==True and d['architecture_decision'] in ['same_ecs_isolated','dedicated_prod_ecs']"
status: not_started
---

# KS-PROD-004 · production readiness delta 清单（用户裁决独立步）

## 1. 任务目标
- **业务**：守护员明示口径：prod 架构是**用户决策**，**不该由执行 AI 顺手定**。本卡 = "出对比清单 → 用户裁决"独立一步，**不部署任何东西**。
- **工程**：起草 `docs/prod_readiness_delta.md` 对比 ①同 ECS 加 docker 容器隔离 vs ②独立 prod ECS 两种方案，从 6 维度（成本 / 故障域 / 部署复杂度 / 上线时间 / 安全 / 可观测性）列利弊；用户拍板写入 audit。
- **S-gate**：S13（CI release gate prod 部署形态决定）。
- **non-goal**：不实际部署（KS-PROD-005 干）；不下灰度策略（KS-PROD-006 干）。

## 2. 前置依赖
- KS-PROD-001（W14 staging 全绿）。

## 3. 输入契约
- 读：现有 staging 部署形态（KS-CD-003 deploy audit）+ 成本数据（ECS 月租 / DashScope quota / Dify quota）。
- 用户：6 维度评估 + 最终选择 + 理由。

## 4. 执行步骤
1. AI 起草 delta md，6 维度对比表。
2. AI 算成本估算（同 ECS 容器隔离 vs 独立 ECS 一年成本差）。
3. 用户审 delta + 拍板（`architecture_decision` ∈ {`same_ecs_isolated`, `dedicated_prod_ecs`}）。
4. 写 audit + 用户签字时间戳。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `docs/prod_readiness_delta.md` | md | 是 | 是 | static_verified |
| `audit/prod_readiness_delta_KS-PROD-004.json` | json | 是 | 是 | user_signed_off |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| audit `user_signed_off=false` | **fail-closed** |
| architecture_decision 非二选一 | fail-closed |
| KS-PROD-005 引用本 audit 而本 audit 未签 | KS-PROD-005 CI fail |
| AI 单独决定 architecture_decision | **fail-closed**（R2 / 用户裁决纪律） |

## 7. 治理语义一致性
- 不写 clean_output/。
- 架构裁决归用户（守护员明示）。
- 不让 LLM 做架构选择（R2）。

## 8. CI 门禁
```
command: python3 -c "import json;d=json.load(open('knowledge_serving/audit/prod_readiness_delta_KS-PROD-004.json'));assert d['user_signed_off']==True and d['architecture_decision'] in ['same_ecs_isolated','dedicated_prod_ecs']"
pass:    user_signed_off=true 且 architecture_decision 在合法二选一集合
```

## 9. CD / 环境验证
- staging / prod：本卡不部署，只产决策 audit。

## 10. 独立审查员 Prompt
> 验：1) 6 维度对比真齐；2) 用户签字真在；3) architecture_decision 合法。

## 11. DoD
- [ ] delta md 入 git
- [ ] 6 维度全有数据
- [ ] 用户拍板 + 签字
- [ ] audit user_signed_off

---
task_id: KS-PROD-005
phase: Production-Readiness
wave: W18
depends_on: [KS-PROD-004, KS-QUAL-005]
files_touched:
  - knowledge_serving/scripts/deploy_to_prod.py
  - knowledge_serving/audit/prod_deploy_KS-PROD-005.json
artifacts:
  - knowledge_serving/scripts/deploy_to_prod.py
  - knowledge_serving/audit/prod_deploy_KS-PROD-005.json
s_gates: [S13]
plan_sections:
  - "§A3"
  - "§A1"
writes_clean_output: false
ci_commands:
  - source scripts/load_env.sh && python3 knowledge_serving/scripts/deploy_to_prod.py --strict --dry-run-check --out knowledge_serving/audit/prod_deploy_KS-PROD-005.json
status: not_started
---

# KS-PROD-005 · prod 环境部署（按 KS-PROD-004 架构裁决执行）

## 1. 任务目标
- **业务**：把 staging 真的搬上 prod —— prod ECS（按 PROD-004 裁决形态） / prod Dify app / prod PG（9 表 + serving views 灌库） / prod Qdrant（embedding 重建） / prod secrets（GHA + ECS）/ prod DNS。
- **工程**：脚本编排部署，每步独立 artifact；含 rollback playbook；用户最终签字才能切流量。
- **S-gate**：S13。
- **non-goal**：不灰度（KS-PROD-006 干）；不动 staging。

## 2. 前置依赖
- KS-PROD-004（架构 + 用户签字）。
- KS-QUAL-005（W17 4 质量门 + 人工抽检流程已就绪，prod 上线前必须有质量门兜底）。

## 3. 输入契约
- 读：`audit/prod_readiness_delta_KS-PROD-004.json`（取 architecture_decision）+ staging deploy 配置（KS-CD-003 audit）。
- env：prod secrets（PG / Dify / DashScope 全套，**与 staging 隔离**）。

## 4. 执行步骤
1. 按 architecture_decision 申请 / 配 prod 资源（ECS / Dify app / DNS）。
2. prod PG 灌库（9 表 + serving views）+ ACL 配（serving_writer 低权账号同 staging 模式）。
3. prod Qdrant 重建 embedding（真打 DashScope，预估 50+ API calls × $）。
4. prod Dify app import chatflow DSL + 挂 prompt v2 + brand persona + few-shot。
5. prod secrets 配（GHA + ECS .env）。
6. prod smoke：跑 KS-PROD-001 regression on prod（read-only verification）。
7. 用户最终签字才允许下一步切流量。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `scripts/deploy_to_prod.py` | py | 是 | 是 | runtime_verified |
| `audit/prod_deploy_KS-PROD-005.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| prod 资源与 staging 共用任一凭据 | **fail-closed**（环境隔离硬纪律） |
| prod smoke 任一门 red | fail-closed |
| dry-run 冒充 prod 部署证据 | **fail-closed**：audit `no_dry_run_as_evidence=true` |
| 用户未签字即切流量 | fail-closed |

## 7. 治理语义一致性
- 不写 clean_output/。
- prod 凭据走 GHA Secrets + 独立 .env（与 staging 严格隔离）。
- prod 任一 LLM 调用走 model_policy.yaml 8 类禁限（与 staging 同口径）。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/deploy_to_prod.py --strict --dry-run-check --out knowledge_serving/audit/prod_deploy_KS-PROD-005.json
pass:    architecture_decision 兑现 + prod_smoke verdict=PASS + user_signed_off=true + no_dry_run_as_evidence=true
```

## 9. CD / 环境验证
- prod：本卡是 prod 部署主卡；rollback playbook 在 audit 引用 KS-PROD-002 模式。

## 10. 独立审查员 Prompt
> 验：1) prod 与 staging 凭据严格隔离；2) prod smoke 真打过 + PASS；3) 用户签字；4) rollback playbook 真在。

## 11. DoD
- [ ] prod 全栈部署
- [ ] prod smoke PASS（KS-PROD-001 regression on prod）
- [ ] 用户最终签字
- [ ] rollback playbook 入 git
- [ ] audit runtime_verified

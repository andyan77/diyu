---
task_id: KS-FIX-05
corrects: KS-POLICY-005
severity: CONDITIONAL_PASS
phase: Policy
wave: W0
depends_on: [KS-FIX-01]
files_touched:
  - knowledge_serving/policies/model_policy.yaml
  - knowledge_serving/audit/model_policy_staging_snapshot_KS-FIX-05.json
artifacts:
  - knowledge_serving/audit/model_policy_staging_snapshot_KS-FIX-05.json
status: done
---

# KS-FIX-05 · model_policy staging env snapshot

## 1. 任务目标
- **business**：原卡 validate warned 缺 `DEEPSEEK_API_KEY`；没有 staging 真实 env 的 runtime snapshot；本卡补齐。
- **engineering**：在 staging 注入 env 后跑 validate，落含模型 list / endpoint / key fingerprint（不是明文）的 snapshot。
- **S-gate**：S0 LLM 边界（与 model_policy 直接相关）。
- **non-goal**：不改 policy spec 本身。

## 2. 前置依赖
- KS-FIX-01（凭据可用）。

## 3. 输入契约
- env 含 `DEEPSEEK_API_KEY`、其他 model key；key 不入 git，artifact 只存 `sha256(key)[:8]` fingerprint。

## 4. 执行步骤
1. `source scripts/load_env.sh` 注入 keys。
2. `python3 -m knowledge_serving.scripts.validate_model_policy --staging` → 0 warn。
3. 写 snapshot json：models, endpoints, key_fingerprints, ts, evidence_level。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/model_policy_staging_snapshot_KS-FIX-05.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 缺 DEEPSEEK_API_KEY | **fail-closed**：validate exit 1 |
| key 明文进 artifact | 守门脚本拦下 |
| 模型 endpoint 不可达 | 标 RISKY，artifact 含 unreachable list |

## 7. 治理语义一致性
- 不调 LLM 做硬门通过判断（R2）。
- secrets env（R3）。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 scripts/validate_model_policy.py --staging --strict --out knowledge_serving/audit/model_policy_staging_snapshot_KS-FIX-05.json
pass:    warn_count == 0
```

## 9. CD / 环境验证
- staging：跑此卡；prod：上线前复跑。
- 监控：每月 fingerprint rotate 检查。

## 10. 独立审查员 Prompt
> 验：artifact 无明文 key；fingerprint 与 env 推导一致；validate warn=0。

## 11. DoD
- [x] warn=0（2026-05-14：source load_env.sh 后 --staging --strict --out 跑通，warn_count=0）
- [x] artifact runtime_verified（snapshot 含 env=staging / checked_at / git_commit / evidence_level=runtime_verified / model_policy_version / models inventory / key_fingerprints sha256[:8]，无明文 key）
- [x] 审查员 pass（fail-closed 反向校验：缺 env + --strict → exit 1；--out 守门：clean_output → exit 2）
- [x] 原卡 KS-POLICY-005 回写（KS-POLICY-005 status=done 仍成立，本卡只补 staging runtime snapshot，不动 spec）

---
task_id: KS-FIX-25
corrects: KS-CD-001
severity: BLOCKED
phase: CD
wave: W13
depends_on: [KS-FIX-24]
files_touched:
  - .github/workflows/ks_release_gate.yml
  - knowledge_serving/scripts/local_release_gate.sh
  - knowledge_serving/audit/ci_release_gate_KS-FIX-25.json
creates:
  - .github/workflows/ks_release_gate.yml
  - knowledge_serving/scripts/local_release_gate.sh
artifacts:
  - knowledge_serving/audit/ci_release_gate_KS-FIX-25.json
status: not_started
---

# KS-FIX-25 · CI 总闸：真 runner + PG 修 + 每项硬门 artifact

## 1. 任务目标
- **business**：原卡 `act` 缺失；PG-backed 硬门因 user/database 问题阻塞。本卡：用真 CI runner（GitHub Actions / 自建）；修 PG 凭据；§8.1 上线总闸每项硬门各落 artifact。
- **engineering**：runner 执行 FIX-01..24 的 CI 命令；产 8+ artifact。
- **S-gate**：S13 CI 总闸。
- **non-goal**：不做 S1-S13 业务回归（FIX-26）。

## 2. 前置依赖
- KS-FIX-24（跨租户绿）。

## 3. 输入契约
- 真 CI runner；PG user/database 配通；env secrets 走 GHA secrets。

## 4. 执行步骤
1. 修 GH Actions workflow 用真 runner。
2. PG user/db 凭据修。
3. 每项硬门跑 → artifact upload。
4. 写汇总 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/ci_release_gate_KS-FIX-25.json` | json | 是 | 是 | runtime_verified |
| `.github/workflows/ks_release_gate.yml` | yaml | 是 | 是 | static_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| `act` 仍被引用 | **fail-closed**：grep CI 拦下 |
| PG connect fail | exit 1 |
| 任一硬门未产 artifact | exit 1 |
| skip>0 pass=0 任一 job | fail |

## 7. 治理语义一致性
- 不调 LLM 判断（R2）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: bash knowledge_serving/scripts/local_release_gate.sh --strict --out knowledge_serving/audit/ci_release_gate_KS-FIX-25.json
note:    本地脚本是 .github/workflows/ks_release_gate.yml 的本地等价物；GHA 真跑后产物地址为 GHA artifact "ks_release_gate"
pass:    所有 sub-job pass 且 artifact_count >= 8
```

## 9. CD / 环境验证
- staging + prod：本卡是 CI 主流水线，影响所有 PR merge to main。

## 10. 独立审查员 Prompt
> 验：1) runner 真跑；2) PG 真连；3) 每项硬门 artifact 真存；4) `act` 0 命中。

## 11. DoD
- [ ] runner 真跑
- [ ] artifact_count >= 8
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-CD-001 回写

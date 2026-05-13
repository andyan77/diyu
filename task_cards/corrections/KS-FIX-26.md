---
task_id: KS-FIX-26
corrects: KS-PROD-001
severity: BLOCKED
phase: Production-Readiness
wave: W14
depends_on: [KS-FIX-25]
files_touched:
  - knowledge_serving/scripts/regression_s1_s13.py
  - knowledge_serving/audit/regression_s1_s13_KS-FIX-26.json
creates:
  - knowledge_serving/scripts/regression_s1_s13.py
artifacts:
  - knowledge_serving/audit/regression_s1_s13_KS-FIX-26.json
status: not_started
---

# KS-FIX-26 · S1-S13 上线总回归（最终验收）

## 1. 任务目标
- **business**：原卡回归脚本缺失；本卡：实现并跑通 S1-S13 全回归；每个 S gate 落 artifact；最终上线决策。
- **engineering**：FIX-01..25 全 done 后跑；任一 S gate red → fail；FAIL 即上线 block。
- **S-gate**：S1-S13 全部。
- **non-goal**：本卡只回归，不引入新功能。

## 2. 前置依赖
- KS-FIX-25（CI 总闸真跑过）。
- 隐式：FIX-01..24 全部 done。

## 3. 输入契约
- 真 staging 全套基础设施 reachable。

## 4. 执行步骤
1. 实现 regression_s1_s13.py（如未完整）。
2. 跑 → 每个 S gate 各落 artifact。
3. 写汇总 audit + 上线决策记录。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/regression_s1_s13_KS-FIX-26.json` | json | 是 | 是 | runtime_verified |
| `audit/regression_s1_s13/S<n>.json` × 13 | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 任一 S gate skip | **fail-closed** |
| 任一 S gate red | exit 1 + block 上线 |
| TestClient / mock 冒充 | grep CI 拦下 |
| skip>0 pass=0 | fail |

## 7. 治理语义一致性
- R7 跨租户 0 串味（继承）。
- R8 LLM 边界 8 类（继承）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/regression_s1_s13.py --staging --strict --out knowledge_serving/audit/regression_s1_s13_KS-FIX-26.json
pass:    s1..s13 全 green 且 artifact_count == 13
```

## 9. CD / 环境验证
- staging：本卡；prod：本卡 pass = 上线放行。

## 10. 独立审查员 Prompt
> 终极复核：1) FIX-01..25 全 done；2) 13 个 S gate 各有 runtime_verified artifact；3) 任一 RISKY 都不能勾本 DoD；4) 上线决策有用户最终签字。

## 11. DoD
- [ ] 13/13 S gate green
- [ ] artifact_count == 13
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 用户最终上线签字
- [ ] 原卡 KS-PROD-001 回写

---
task_id: KS-FIX-22
corrects: KS-RETRIEVAL-007
severity: CONDITIONAL_PASS
phase: Retrieval
wave: W8
depends_on: [KS-FIX-14, KS-FIX-21]
files_touched:
  - task_cards/KS-RETRIEVAL-007.md
  - knowledge_serving/audit/retrieval_007_reviewer_pass_KS-FIX-22.md
artifacts:
  - knowledge_serving/audit/retrieval_007_reviewer_pass_KS-FIX-22.md
status: not_started
---

# KS-FIX-22 · KS-RETRIEVAL-007 外审复跑 + DoD 勾选

## 1. 任务目标
- **business**：原卡 §11 reviewer-pass 未勾；本卡：外审复跑或显式记录 W8 conditional-to-pass 裁决。
- **engineering**：跑 W14 入口审查员 prompt（KS-RETRIEVAL-007 §10）→ 落审查员意见 + 勾 DoD。
- **S-gate**：S9 retrieval 合流签字。
- **non-goal**：不改实现。

## 2. 前置依赖
- KS-FIX-14（log reconcile 过）。
- KS-FIX-21（rerank runtime 过）。

## 3. 输入契约
- KS-RETRIEVAL-007 §10 reviewer prompt。

## 4. 执行步骤
1. 外审复跑该 prompt。
2. 复跑 KS-RETRIEVAL-007 §8 CI 命令，落 evidence_level=runtime_verified。
3. 写 reviewer 意见 md + 勾 DoD。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/retrieval_007_reviewer_pass_KS-FIX-22.md` | md | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| reviewer pass 未签字 | **fail-closed** |
| CI 命令 skip>0 pass=0 | fail |

## 7. 治理语义一致性
- 审查员意见先验证再采信（E7）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: cat task_cards/KS-RETRIEVAL-007.md | grep -E "\[x\] 审查员 pass"
pass:    grep 命中 1+
```

## 9. CD / 环境验证
- 无运行时副作用。

## 10. 独立审查员 Prompt
> 复跑 KS-RETRIEVAL-007 §10 reviewer prompt；若 pass 则签字；若 RISKY 则不勾 DoD 而是回退 status。

## 11. DoD
- [ ] reviewer md 落盘
- [ ] KS-RETRIEVAL-007 §11 DoD 勾选
- [ ] 审查员 pass
- [ ] 原卡 KS-RETRIEVAL-007 回写（本卡的目的即为此）

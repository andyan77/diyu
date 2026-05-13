---
task_id: KS-FIX-21
corrects: KS-COMPILER-010
severity: CONDITIONAL_PASS
phase: Compiler
wave: W3
depends_on: [KS-FIX-06, KS-FIX-15]
files_touched:
  - knowledge_serving/scripts/rerank_runtime_check.py
  - knowledge_serving/audit/rerank_runtime_KS-FIX-21.json
creates:
  - knowledge_serving/scripts/rerank_runtime_check.py
artifacts:
  - knowledge_serving/audit/rerank_runtime_KS-FIX-21.json
status: not_started
---

# KS-FIX-21 · rerank runtime 真实被调验证

## 1. 任务目标
- **business**：原卡 policy 声明了 rerank 但 retrieval 链没真调；本卡：runtime 验证 rerank 真被触发并改变结果。
- **engineering**：日志/trace 含 rerank step；before/after score 不同。
- **S-gate**：S10 retrieval ordering。
- **non-goal**：不改 rerank 算法。

## 2. 前置依赖
- KS-FIX-06（compiler coverage 真）。
- KS-FIX-15（vector path 真）。

## 3. 输入契约
- staging retrieval；policy 启用 rerank。

## 4. 执行步骤
1. 跑 5 query → 抓 trace。
2. 断言每条 trace 含 rerank step + score 变化。
3. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/rerank_runtime_KS-FIX-21.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| rerank step 缺失 | **fail-closed** |
| score 未变（noop rerank） | 标 RISKY，artifact 显式 |
| policy 关掉 rerank 仍 pass | exit 1（说明本测无效） |

## 7. 治理语义一致性
- LLM 不做硬门判断（R2）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/rerank_runtime_check.py --staging --queries 5 --strict
pass:    rerank_invoked_count == 5 且 score_changed_count >= 4
```

## 9. CD / 环境验证
- staging：本卡。

## 10. 独立审查员 Prompt
> 验：1) trace 真有 rerank；2) score 改变；3) policy 关掉本测 fail（反向校验）。

## 11. DoD
- [ ] rerank_invoked 5/5
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-COMPILER-010 回写

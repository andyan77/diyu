---
task_id: KS-GEN-008
phase: Production-Readiness
wave: W16
depends_on: [KS-GEN-005, KS-GEN-003]
files_touched:
  - knowledge_serving/prompts/few_shot/
  - knowledge_serving/audit/few_shot_library_KS-GEN-008.json
artifacts:
  - knowledge_serving/audit/few_shot_library_KS-GEN-008.json
s_gates: [S11]
plan_sections:
  - "§10"
  - "§A4"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/validate_few_shot_library.py --strict --min-per-combo 20 --out knowledge_serving/audit/few_shot_library_KS-GEN-008.json
status: not_started
---

# KS-GEN-008 · few-shot 黄金例子库（≥ 20 / Top 组合）

## 1. 任务目标
- **业务**：prompt 模板再好也需要 few-shot 例子撑住调性 + 格式。本卡：为每个 Top 组合沉淀 ≥ 20 条**黄金例子**（brief → 期望输出），优先从 KS-GEN-003 高分样例 + 用户手写 + 历史运营素材里取。
- **工程**：例子是 YAML（brief / context_summary / expected_output_md / rationale / source[from_run / from_user / from_history]），脚本验数量 + 格式 + brand_layer 一致。
- **S-gate**：S11（brand_layer 隔离）。
- **非目标**：不动 prompt 模板（KS-GEN-007 负责）；不真跑生成（KS-GEN-009 跑）。

## 2. 前置依赖
- KS-GEN-005（Top 组合选定）。
- KS-GEN-003（W15 真样例可作为高分例子来源）。

## 3. 输入契约
- 读：`audit/human_eval_KS-GEN-004.csv`（找 4-5 星样例作为种子）+ `logs/e2e_mvp_samples/`
- 用户：手写 ≥ 5 条 / 组合的"教科书级"例子。

## 4. 执行步骤
1. AI 从 W15 高分样例（dim_overall ≥ 4）抽种子。
2. 用户手写补 ≥ 5 条 / 组合。
3. AI 把例子结构化入 `prompts/few_shot/<content_type>__<channel>/example_NNN.yaml`。
4. 跑 validate_few_shot_library.py：①每组合 ≥ 20 条；②yaml 格式 ok；③brand_layer 与组合一致；④expected_output_md 非空且 ≥ 200 字；⑤rationale 字段说明为啥这是好例子。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `prompts/few_shot/**/example_*.yaml` × ≥ 20/组合 | yaml | 是 | 是 | static_verified |
| `audit/few_shot_library_KS-GEN-008.json` | json | 是 | 是 | static_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 例子数 < 20 / 组合 | **fail-closed** |
| 例子全部 AI 生成（无人工标 from_user / from_history） | fail-closed |
| brand_layer 与组合不一致 | fail-closed |
| rationale 为空 | fail-closed |

## 7. 治理语义一致性
- 不写 clean_output/。
- 不让 LLM 自我生成全部例子（R2 反幻觉）；至少 25% 必须 from_user / from_history。
- 多租户隔离硬纪律：brand_faye 例子不可混入 domain_general 集。

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/validate_few_shot_library.py --strict --min-per-combo 20 --out knowledge_serving/audit/few_shot_library_KS-GEN-008.json
pass:    每组合 ≥ 20 条 + ≥ 25% 非 AI 生成 + 5 验证项全 pass
```

## 9. CD / 环境验证
- staging / prod：本卡是 prompt 资源库，部署随 W18。

## 10. 独立审查员 Prompt
> 验：1) 数量达标；2) ≥ 25% 人工源；3) brand_layer 隔离；4) rationale 说服力。

## 11. DoD
- [ ] ≥ 20 条 / 组合
- [ ] ≥ 25% from_user / from_history
- [ ] audit static_verified
- [ ] 用户审核样例代表性

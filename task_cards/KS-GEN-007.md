---
task_id: KS-GEN-007
phase: Production-Readiness
wave: W16
depends_on: [KS-GEN-005, KS-GEN-006]
files_touched:
  - knowledge_serving/prompts/
  - knowledge_serving/audit/prompt_templates_KS-GEN-007.json
artifacts:
  - knowledge_serving/audit/prompt_templates_KS-GEN-007.json
s_gates: [S7, S11]
plan_sections:
  - "§10"
  - "§3.3"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/validate_prompt_templates.py --strict --out knowledge_serving/audit/prompt_templates_KS-GEN-007.json
status: not_started
---

# KS-GEN-007 · prompt 模板蓝本（Top 组合 × 1 套 / 渲染 dry-run）

## 1. 任务目标
- **业务**：MVP 前 chatflow n7 节点的 prompt 多半还是骨架。本卡：为 KS-GEN-005 选定的 Top 1-2 组合各写一套**可用**的 prompt 模板，含变量插槽（business_brief / retrieved_chunks / brand_persona / channel_constraint）。
- **工程**：每模板是 jinja2 风格 .tmpl.md；脚本对每模板用 5 条 mock-render 真渲染（**渲染验证不算生成证据**，仅校验模板语法 + 变量完整），audit 含每模板 sha256。
- **S-gate**：S7（生成必须读 fallback 决定）+ S11（brand_layer 隔离）。
- **非目标**：不真打 LLM（KS-GEN-009 才回归）；不挂 chatflow 节点（W18 deploy 干）。

## 2. 前置依赖
- KS-GEN-005（Top 组合选定）。
- KS-GEN-006（brand_faye persona 片段就绪，可被本卡 include）。

## 3. 输入契约
- 读：`prompts/brand_faye_persona.md` + `clean_output/nine_tables/03_generation_recipe.csv`
- 用户：审核 prompt 内容（语气 / 结构 / 约束）。

## 4. 执行步骤
1. AI 起草每 Top 组合的 prompt 蓝本（system + user + 变量插槽 + few-shot 占位 `{{few_shot_block}}`，留给 KS-GEN-008 填）。
2. 用户审核 + 改稿（≥ 1 轮）。
3. AI 写 validate_prompt_templates.py：①jinja2 语法 ok；②必填变量全在；③渲染 5 条 mock 输入不报错；④模板长度 ≤ 4000 tokens；⑤brand_persona include 路径只在 brand_faye 组合。
4. 跑 CI 出 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `prompts/<content_type>__<channel>.tmpl.md` × 1-2 | md/jinja2 | 是 | 是 | static_verified |
| `audit/prompt_templates_KS-GEN-007.json` | json | 是 | 是 | static_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 模板含"由 LLM 判断是否合规 / 是否事实" | **fail-closed**（R2） |
| brand_faye persona 注入到 domain_general 模板 | fail-closed |
| 任一必填变量缺 | fail-closed |
| 模板长度 > 4000 tokens | fail-closed |

## 7. 治理语义一致性
- 不写 clean_output/。
- 不让 LLM 在 prompt 内做 governance 硬裁决（R2）。
- prompt 内不许暗示 LLM 输出 brand_layer / intent_classification 类字段（保留给 n2/n3 code 节点）。

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/validate_prompt_templates.py --strict --out knowledge_serving/audit/prompt_templates_KS-GEN-007.json
pass:    5 验证项全 pass
```

## 9. CD / 环境验证
- staging：W18 部署到 staging Dify n7；prod：W18 灰度。

## 10. 独立审查员 Prompt
> 验：1) 模板不让 LLM 做硬裁决；2) 多租户隔离 ok；3) jinja2 渲染 ok。

## 11. DoD
- [ ] 1-2 套 prompt 入 git
- [ ] 用户审核签字
- [ ] audit static_verified
- [ ] 5 验证项全 pass

---
task_id: KS-QUAL-002
phase: Production-Readiness
wave: W17
depends_on: [KS-GEN-009]
files_touched:
  - knowledge_serving/scripts/content_compliance_scan.py
  - knowledge_serving/policies/compliance_terms.yaml
  - knowledge_serving/audit/compliance_KS-QUAL-002.json
artifacts:
  - knowledge_serving/scripts/content_compliance_scan.py
  - knowledge_serving/policies/compliance_terms.yaml
  - knowledge_serving/audit/compliance_KS-QUAL-002.json
s_gates: [S12]
plan_sections:
  - "§9.2"
  - "§A3"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/content_compliance_scan.py --staging --strict --out knowledge_serving/audit/compliance_KS-QUAL-002.json
status: not_started
---

# KS-QUAL-002 · 合规 / 敏感词 / 法规红线扫描硬门

## 1. 任务目标
- **业务**：服装零售内容受广告法 / 平台规则约束（如不可出现绝对化用语"最 / 第一 / 唯一"、不可虚假宣传"包治百病"、不可侵权品牌名等）。本卡：规则级合规扫描器，违规即 block。
- **工程**：维护 `compliance_terms.yaml`（广告法绝对化用语 / 平台禁词 / 法规禁词 / 品牌侵权词），脚本扫输出文本，命中即 violation；同时含 brand_faye 自定禁词（与 KS-GEN-006 persona forbid_terms 锚一致）。
- **S-gate**：S12（LLM 边界，确保不让 LLM 自我"判断是否合规"）。
- **non-goal**：不做 NLP 语义合规（那是 KS-QUAL-004 LLM 辅助分干，且只建议不裁决）。

## 2. 前置依赖
- KS-GEN-009。
- KS-GEN-006（brand_faye forbid_terms 共享词库）。

## 3. 输入契约
- 读：`policies/compliance_terms.yaml`（本卡建）+ `prompts/brand_faye_persona.md`（forbid_terms 段）+ 30 v2 样例。

## 4. 执行步骤
1. AI 整理初版 compliance_terms.yaml：广告法绝对化用语 ≥ 30 条 / 平台禁词 ≥ 50 条 / 法规红线 ≥ 20 条。
2. 用户审核 + 补行业禁词。
3. 实现扫描器：精确词 + 正则模板（如"包治.+病"）；命中位置 + 类别记入 audit。
4. 30 样例真跑，violation_count=0 才过。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `policies/compliance_terms.yaml` | yaml | 是 | 是 | static_verified |
| `scripts/content_compliance_scan.py` | py | 是 | 是 | runtime_verified |
| `audit/compliance_KS-QUAL-002.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 故意造一条说"最优质面料" | **检测出广告法 violation** |
| LLM 替代规则 | **fail-closed**：rules_only=true |
| 任一类别词库 < 阈值 | fail-closed（词库不足≠ PASS） |
| 与 KS-GEN-006 forbid_terms 冲突（"贵妇感"未列） | 标 drift 警告 |

## 7. 治理语义一致性
- 不写 clean_output/。
- 不调 LLM 做合规判断（R2）。
- 词库**用户签字 sentry**：每次 yaml 改动须用户签字（broken_word_anchor field）。

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/content_compliance_scan.py --staging --strict --out knowledge_serving/audit/compliance_KS-QUAL-002.json
pass:    rules_only=true 且 故意造 violation 被检出 且 真样例 violation_count=0
```

## 9. CD / 环境验证
- staging：跑；prod：W18 部署后挂 n8_guardrail 后置。

## 10. 独立审查员 Prompt
> 验：1) rules_only=true；2) 故意造广告法用语被抓；3) 词库用户签字。

## 11. DoD
- [ ] compliance_terms.yaml 入 git
- [ ] 用户签字词库
- [ ] 30 样例真跑
- [ ] audit runtime_verified

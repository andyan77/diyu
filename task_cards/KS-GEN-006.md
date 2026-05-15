---
task_id: KS-GEN-006
phase: Production-Readiness
wave: W16
depends_on: [KS-GEN-005]
files_touched:
  - knowledge_serving/prompts/brand_faye_persona.md
  - knowledge_serving/audit/brand_voice_injection_KS-GEN-006.json
artifacts:
  - knowledge_serving/prompts/brand_faye_persona.md
  - knowledge_serving/audit/brand_voice_injection_KS-GEN-006.json
s_gates: [S11]
plan_sections:
  - "§A4"
  - "§3.3"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/validate_brand_voice_injection.py --persona knowledge_serving/prompts/brand_faye_persona.md --strict --out knowledge_serving/audit/brand_voice_injection_KS-GEN-006.json
status: not_started
---

# KS-GEN-006 · brand_faye 品牌调性 prompt 片段（persona + 视觉禁忌 + 价值主张）

## 1. 任务目标
- **业务**：W15 评分发现样例的"调性"维度普遍低分时，根因多半是 prompt 里没注入笛语创始人语气、视觉禁忌、价值主张。本卡：把这些抽象规则写成**可注入 prompt 的结构化片段**，可挂到 n7 LLM generation 节点。
- **工程**：`brand_faye_persona.md` 是结构化 markdown，分 §voice / §forbid_terms（如"贵妇感"、"高级感"、"轻奢"等需用户确认的禁词）/ §value_anchors / §founder_signature 4 段；脚本验证片段格式 + 与 9 表的 brand_faye RoleProfile 锚一致。
- **S-gate**：S11（brand_layer 多租户隔离：本片段只对 brand_faye 生效，domain_general 不注入）。
- **非目标**：不写 content_type 级 prompt 模板（KS-GEN-007 干）。

## 2. 前置依赖
- KS-GEN-005（Top 组合已选，知道要注入哪几个组合）。
- 9 表 brand_faye 行已就绪（W3+ 已 done）。

## 3. 输入契约
- 读：`clean_output/nine_tables/01_object_type.csv`（RoleProfile brand_faye 行）+ `clean_output/candidates/brand_faye/**/*.yaml`
- 用户：确认禁词清单（"贵妇感"等需用户裁决）+ 价值主张文案。

## 4. 执行步骤
1. AI 从 brand_faye 9 表行 + candidates 抽出 voice / forbid / value / signature 候选。
2. 用户审核（增删改），AI 落 `brand_faye_persona.md`。
3. AI 写 validate_brand_voice_injection.py：注入测试（把片段拼到 dummy prompt，跑 4 个验证项：①与 9 表锚一致；②禁词列表非空；③片段长度 ≤ 800 tokens 防 prompt 膨胀；④brand_layer 仅 brand_faye）。
4. 跑 CI 出 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `prompts/brand_faye_persona.md` | md | 是 | 是 | static_verified |
| `audit/brand_voice_injection_KS-GEN-006.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| persona 片段被 domain_general 组合注入 | **fail-closed**（违反多租户隔离） |
| 片段含 LLM-judge 句式（"由模型判断是否合规"） | fail-closed（R2 LLM 不做硬裁决） |
| 片段长度 > 800 tokens | fail-closed（控 prompt 成本） |
| 与 9 表 brand_faye RoleProfile 字段冲突 | fail-closed |

## 7. 治理语义一致性
- 不写 clean_output/。
- 多租户隔离硬纪律：`brand_faye_persona` 仅注入 brand_faye 组合，domain_general 不注入。
- 不调 LLM 自我生成 persona（R2）；persona 由用户审核定义。

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/validate_brand_voice_injection.py --persona knowledge_serving/prompts/brand_faye_persona.md --strict --out knowledge_serving/audit/brand_voice_injection_KS-GEN-006.json
pass:    4 个验证项全 pass + brand_layer=brand_faye-only
```

## 9. CD / 环境验证
- staging：本片段挂到 staging Dify n7 节点测试；prod：W18 后部署。

## 10. 独立审查员 Prompt
> 验：1) persona 与 9 表锚一致；2) 禁词清单用户签字；3) 多租户隔离生效。

## 11. DoD
- [ ] brand_faye_persona.md 入 git + 用户签字
- [ ] audit runtime_verified
- [ ] 禁词清单 ≥ 5 条
- [ ] 注入测试通过

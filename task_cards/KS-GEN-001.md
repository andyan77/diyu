---
task_id: KS-GEN-001
phase: Production-Readiness
wave: W15
depends_on: [KS-PROD-001]
files_touched:
  - knowledge_serving/audit/mvp_scope_KS-GEN-001.json
artifacts:
  - knowledge_serving/audit/mvp_scope_KS-GEN-001.json
s_gates: [S7]
plan_sections:
  - "§A4"
writes_clean_output: false
ci_commands:
  - python3 -c "import json,sys;d=json.load(open('knowledge_serving/audit/mvp_scope_KS-GEN-001.json'));assert d['locked']==True and d['user_signed_off']==True and 2<=len(d['content_types'])<=3 and d['channels']==['xiaohongshu']"
status: not_started
---

# KS-GEN-001 · W15 真实生成 MVP 范围冻结

## 1. 任务目标
- **业务**：把"生产级内容生产"的第一波 MVP 范围由用户**显式锁定** —— 选哪几个 content_type（内容类型） × 哪几个 channel（投放渠道）作为后续 W15-W17 全部工程的实验靶子，避免范围漂移导致 prompt / few-shot / 质量门撒胡椒面。
- **工程**：把用户的范围裁决落到 canonical audit JSON，含用户签字时间戳 + locked=true，下游卡（KS-GEN-002..009 / KS-QUAL-*）**只读**本 audit，不得旁路。
- **S-gate**：S7（fallback policy 覆盖范围必须涵盖本 MVP 矩阵）。
- **非目标**：本卡不做任何生成 / 检索 / prompt 工程。

## 2. 前置依赖
- KS-PROD-001（W14 上线总回归 PASS，工程底座已就绪）。

## 3. 输入契约
- 输入：用户对以下 3 问的明确回答 ——
  1) 选哪 2-3 个 content_type（**必须从已落地候选选**：`product_review` / `store_daily` / `founder_ip` —— 均在 `content_type_view.csv` 已存在）
  2) **channel = xiaohongshu 单一锁定**（W15-W17 硬约束）。当前 `generation_recipe_view.csv` 18 条 recipe 全是 platform=xiaohongshu；`tenant_scope_registry.csv` 虽列了 `wechat`，但无对应 recipe 可跑。**抖音 / 淘宝 / 私域 / wechat 想上必须先单独开 recipe 卡（KS-GEN-CHANNEL-XXX，本批 19 张暂未含）补 recipe 后才能扩 channel**。
  3) 选哪个 LLM 模型（候选：qwen-max / qwen-plus / DeepSeek-V3 / 多模型 A/B）
- env：无外部依赖。

## 4. 执行步骤
1. AI 提出 3 个候选组合（带利弊对比）给用户。
2. 用户拍板 1 个最终组合（写入 audit 的 `content_types` + `channels` + `llm_model`）。
3. AI 把组合 + 用户签字时间戳 + locked=true 写入 audit JSON。
4. 跑 CI 命令确认 audit 合法。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/mvp_scope_KS-GEN-001.json` | json | 是 | 是 | user_signed_off |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| audit 缺 `user_signed_off=true` | **fail-closed** CI 拒绝 |
| audit `locked=false` | fail-closed |
| content_types / channels 为空 | fail-closed |
| 下游卡引用本 audit 而 audit 不存在 | 下游 CI fail |

## 7. 治理语义一致性
- 不调 LLM 做范围裁决（R2）。
- 不写 `clean_output/`。
- 锁定范围一旦写入 audit，**禁止后续卡静默扩范围**；要扩必须新开一张 GEN 卡显式扩 + 用户重签。

## 8. CI 门禁
```
command: python3 -c "import json,sys;d=json.load(open('knowledge_serving/audit/mvp_scope_KS-GEN-001.json'));assert d['locked']==True and d['user_signed_off']==True and 2<=len(d['content_types'])<=3 and d['channels']==['xiaohongshu']"
pass:    locked=true + user_signed_off=true + content_types 2-3 个 + channels == ['xiaohongshu']
```

## 9. CD / 环境验证
- staging / prod：本卡仅产范围 audit，不涉及环境部署。

## 10. 独立审查员 Prompt
> 验：1) audit 含用户签字时间戳；2) content_types / channels / llm_model 三字段都不为空；3) locked=true。

## 11. DoD
- [ ] audit canonical 入 git
- [ ] user_signed_off=true（用户在 audit 里留时间戳）
- [ ] CI pass
- [ ] 下游卡（KS-GEN-002..）已感知本 audit 路径

---
task_id: KS-QUAL-003
phase: Production-Readiness
wave: W17
depends_on: [KS-GEN-009]
files_touched:
  - knowledge_serving/scripts/channel_format_validator.py
  - knowledge_serving/policies/channel_format_spec.yaml
  - knowledge_serving/audit/channel_format_KS-QUAL-003.json
artifacts:
  - knowledge_serving/scripts/channel_format_validator.py
  - knowledge_serving/policies/channel_format_spec.yaml
  - knowledge_serving/audit/channel_format_KS-QUAL-003.json
s_gates: [S6]
plan_sections:
  - "§9.2"
  - "§A4"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/channel_format_validator.py --staging --strict --out knowledge_serving/audit/channel_format_KS-QUAL-003.json
status: not_started
---

# KS-QUAL-003 · 渠道格式硬门（emoji / 字数 / hashtag / 镜头标记 / 等）

## 1. 任务目标
- **业务**：不同渠道格式硬约束差异大——小红书要 emoji + hashtag + ≤ 1000 字。本卡：规则级格式校验，每渠道独立 spec，违规 block。
- **W15-W17 范围说明**：本批仅落 **xiaohongshu** 一个 channel 的 spec（与 KS-GEN-001 锁定一致）。**未来 channel 扩展示例（仅作设计参考、本批不落）**：抖音脚本要镜头标记 `[开场镜头]/[特写]`、淘宝详情要分段标题、wechat 公众号要首段钩子——这些要等对应 recipe 卡先落地（platform 列必须先在 `generation_recipe_view.csv` 出现），不在本卡 W17 实施范围。
- **工程**：`channel_format_spec.yaml` 维护每渠道格式 schema（min/max length / emoji_count_range / hashtag_count_range / required_markers / forbidden_patterns），脚本逐项校验。
- **S-gate**：S6（chunk / 字段需求矩阵 / 格式治理）。
- **non-goal**：不评内容质量；不动 prompt。

## 2. 前置依赖
- KS-GEN-009。
- KS-GEN-001（channels 列表锁定）。

## 3. 输入契约
- 读：`audit/mvp_scope_KS-GEN-001.json`（取 channels 列表）+ 30 v2 样例。
- 用户：每渠道格式 spec 审核。

## 4. 执行步骤
1. AI 起草 **xiaohongshu** channel 的 format spec（emoji_count / hashtag_count / 字数 / 段落 / 禁用模板）。**抖音 / 淘宝 / wechat 等 channel spec 不在本卡范围**，未来需要时单独开 KS-QUAL-003-CHANNEL-XXX 扩。
2. 用户审核 + 修订（这是渠道运营经验落地）。
3. 实现 validator：逐 spec 逐字段校验。
4. 30 样例真跑，每样例每 spec field violation 记录。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `policies/channel_format_spec.yaml` | yaml | 是 | 是 | static_verified |
| `scripts/channel_format_validator.py` | py | 是 | 是 | runtime_verified |
| `audit/channel_format_KS-QUAL-003.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| xiaohongshu 样例 0 emoji | **fail-closed** |
| xiaohongshu 样例 hashtag_count 超阈值 | fail-closed |
| 任一样例字数超 spec max | fail-closed |
| LLM 替代规则 | fail-closed |
| 本卡 spec 出现 xiaohongshu 之外的 channel | **fail-closed**（W15-W17 范围红线） |

## 7. 治理语义一致性
- 不写 clean_output/。
- 不调 LLM 做格式裁决（R2）。
- 每 channel spec 用户签字。

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/channel_format_validator.py --staging --strict --out knowledge_serving/audit/channel_format_KS-QUAL-003.json
pass:    rules_only=true 且 30 样例全过 channel spec
```

## 9. CD / 环境验证
- staging：跑；prod：W18 部署后挂。

## 10. 独立审查员 Prompt
> 验：1) spec 用户签字；2) 故意造违规被抓；3) rules_only=true。

## 11. DoD
- [ ] 每选定 channel spec 入 git + 用户签字
- [ ] 30 样例真跑
- [ ] audit runtime_verified

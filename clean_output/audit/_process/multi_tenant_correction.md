---
snapshot_type: historical_review
frozen_at: 2026-05-03T15:50:44Z
source_state: pre-W10
rationale: 历史复核/方案文档，反映当时状态，不再随仓库演进；不参与 G18 漂移检测
---

# 多租户隔离纠偏报告

> 日期：2026-05-03
> 触发：用户明确原始意图——本仓真实数据模型是"领域通用知识 + 多租户品牌专属知识（含笛语专属）= 同库逻辑隔离"。
> 范围：纠正 W1+W2 的 brand_layer 偏移；锁定后续 W3+ 的多租户判定纪律。

---

## 1. 偏移现象（W1+W2 已发生）

W1+W2 共抽 90 条 pack，**100% 标 `domain_general`，0 条 brand_faye**——这与多租户数据模型不符。

根因：agent 把"**规则形式可抽象**"等同于"**内容可去笛语化 → 标 domain_general**"。例如 B09 的 founder-profile 5 条 pack 主题明显是笛语创始人画像规则，但因"规则形式是通用对象分层"而被判 domain_general。

**这违反多租户隔离硬底线**：能放进 `domain_general` 的，必须能让任意未来品牌（brand_xyz / brand_abc）直接消费且不污染。

## 2. 纠偏的 7 步动作（已落盘）

| 步 | 动作 | 文件 | 状态 |
|---|---|---|---|
| 1 | CLAUDE.md 加 **多租户隔离硬纪律** 节（最高优先级） | `CLAUDE.md` | ✅ |
| 2 | SKILL.md §6 大改为 **多租户隔离 key 判定**（4 步流程 + 反偷换警告） | `.claude/skills/extract-9tables/SKILL.md` | ✅ |
| 3 | domain_skeleton.yaml 加 `multi_tenant_model` 节（声明品牌层注册表 + 禁止漂移项） | `clean_output/domain_skeleton/domain_skeleton.yaml` | ✅ |
| 4 | 扫描 90 条 pack 找真阳性（脚本 `/tmp/scan_brand_v2.py` 排除 rationale 假阳性） | — | ✅（4 条真阳性） |
| 5 | 4 条真阳性迁 `candidates/needs_review/` + 9 表 brand_layer 列同步更新（43 行）+ four_gate_results 同步 + brand_layer_review_queue 登记 | 多文件 | ✅ |
| 6 | task_cards.md 加全局多租户硬约束 + TC-E01 SQL 验收加多租户查询模板与 CHECK 断言 | `clean_output/audit/task_cards.md` | ✅ |
| 7 | extraction_log.csv 追加 7 行纠偏轨迹 + 本报告 | 本文件 | ✅ |

## 3. 4 条迁移到 needs_review 的 pack

| pack_id | pack_type | 真阳性触发 | 拆分建议 |
|---|---|---|---|
| KP-product_attribute-persona-six-field-shell | product_attribute | BRAND_SPECIFIC_FIELD_SHELL | `domain_general:抽象 Persona 应有字段壳的元规则` + `brand_faye:笛语此次冻结的 6 字段名与定义` |
| KP-product_attribute-persona-field-fill-state | product_attribute | BRAND_SPECIFIC_FIELD_SHELL | `domain_general:三档成熟度治理元规则` + `brand_faye:Q1/Q19/Q3 笛语流程具体编号` |
| KP-training_unit-founder-profile-brand-unique-layer | training_unit | PACK_ID_FOUNDER + ASSERTION_BRAND_SUBJECT | `domain_general:任何品牌的 founder 画像应作为品牌唯一层而非通用 Persona 的抽象规则` + `brand_faye:笛语对 FounderProfile 命名与 0/1 柔性使用约束` |
| KP-training_unit-founder-profile-soft-use-no-rename | training_unit | PACK_ID_FOUNDER + ASSERTION_BRAND_SUBJECT | `domain_general:启用与否非命名问题的抽象元规则` + `brand_faye:Q1 § 柔性使用的具体笛语口径` |

详见 `clean_output/audit/brand_layer_review_queue.csv`（4 行 + 表头）。

## 4. 纠偏后的 brand_layer 分布

| brand_layer | pack 数 | 占比 |
|---|---|---|
| domain_general | 86 | 95.6% |
| needs_review | 4 | 4.4% |
| brand_faye | 0 | 0%（待人工裁决后从 needs_review 迁入）|

## 5. 9 表 brand_layer 列同步更新

| 表 | 受影响行数 | 改动 |
|---|---|---|
| 02_field | 12 | domain_general → needs_review |
| 03_semantic | 5 | 同上 |
| 04_value_set | 15 | 同上 |
| 05_relation | 1 | 同上 |
| 06_rule | 4 | 同上 |
| 07_evidence | 4 | 同上 |
| 09_call_mapping | 2 | 同上 |
| **合计** | **43 行** | — |

01_object_type 与 08_lifecycle 不受影响（4 条 pack 没有派生这两类行）。

## 6. 待人工裁决项（请你决定）

### 6.1 4 条 needs_review pack 的最终归位
对每条 pack 按 SKILL.md §6.2 的 4 步流程逐条裁决：
- A：保 `domain_general`（确实抽象规则）
- B：迁 `brand_faye`（确认笛语专属）
- C：拆为两条 pack（一条 domain_general 元规则 + 一条 brand_faye 具体）

### 6.2 GAP-004 FounderProfile 落档方案
- P1：通用对象池 + 各品牌专属对象扩展（FounderProfileFaye / FounderProfileXyz 各自独立）
- **P2（推荐）**：通用对象一份（FounderProfile）+ 各品牌通过 brand_layer 行级隔离
- P3：不入通用 9 表，仅作为 brand_faye 配置层

P2 与多租户单库逻辑隔离最契合，但要求字段集是品牌兼容的并集——这又回到 6.1 的拆分讨论。

## 7. 后续 W3+ 必须遵守的纪律

1. **抽 pack 时**：每条 pack 落盘前按 SKILL.md §6.2 的 4 步流程跑一遍，明确 brand_layer
2. **拿不准时**：默认进 `needs_review`，禁止默认 `domain_general`
3. **9 表派生时**：每行的 brand_layer 列严格按 pack 的 brand_layer 标，禁止混填
4. **审计时**：每波 checkpoint 都要看 brand_faye 的占比——如果连续多波是 0，要警觉是否又在偏移
5. **SQL 落地时**：TC-E01 的 CHECK 断言会硬卡漂移行（`brand_layer ~ '^(domain_general|brand_[a-z_]+|needs_review)$'`）

## 8. 这次纠偏未触及的内容

- 86 条仍标 domain_general 的 pack 都过 v2 扫描器（`scan_brand_v2.py`）的 4 条触发条件——目前没发现真阳性
- 但**人工抽样建议**：从 86 条中随机抽 5-10 条做交叉验证，确认 v2 扫描器没漏真阳性
- 推荐重点抽样：B05 craft_quality 7 条（笛语门店工艺纪律可能漏判）、B07 培训 13 条（笛语门店培训规范可能漏判）

要我现在就做 §8 的人工抽样辅助（写一份 86 条的逐条 brand_layer 自检表给你扫眼）吗？还是直接进 W3？

---

# 第二轮修正（2026-05-03 · 当日补正）· 领域边界明示

## 触发原因

用户明确补充：**门店纪律 / 培训规则 / 陈列搭配 都是领域通用知识，不是笛语专属；真正笛语专属的只有"品牌调性"和"创始人画像"两类具体内容**。

按此口径，前一轮把 4 条 pack 迁到 needs_review **属于过度纠偏**——它们本质都是抽象元规则（Persona schema 元规则 + FounderProfile 元规则），按用户口径应回 `domain_general`。

## 第二轮动作（已落盘）

| 步 | 动作 | 文件 | 状态 |
|---|---|---|---|
| 1 | SKILL.md §6 加 `domain_general` 8 类范畴显式清单 + `brand_<name>` 仅限 2 类（品牌调性 + 创始人画像）+ 2 个判别要诀 | `.claude/skills/extract-9tables/SKILL.md` | ✅ |
| 2 | SKILL.md §6.2 改为 3 步判定流程（领域归类 → 品牌专属内容 → 品牌归属） + fast-path | 同上 | ✅ |
| 3 | CLAUDE.md §1 加领域边界明示（默认全 domain_general，仅 2 类品牌专属）+ §3 新增 2 条反偷换条目 | `CLAUDE.md` | ✅ |
| 4 | domain_skeleton.yaml multi_tenant_model 节加 `domain_general_scope`（8 类）+ `brand_specific_scope`（2 类）+ examples / excludes / discrimination 三件套 | `clean_output/domain_skeleton/domain_skeleton.yaml` | ✅ |
| 5 | 4 条 needs_review pack 全部还原至 `candidates/domain_general/`，brand_layer 字段还原 | 4 yaml | ✅ |
| 6 | 9 表 brand_layer 列全部还原（needs_review → domain_general，43 行复原）；four_gate_results 同步还原 | 7 个 csv | ✅ |
| 7 | brand_layer_review_queue 清空（仅保留表头） | `audit/brand_layer_review_queue.csv` | ✅ |
| 8 | extraction_log 追加二次修正轨迹 | `audit/extraction_log.csv` | ✅ |

## 第二轮纠偏后的最终分布

| brand_layer | pack 数 | 占比 |
|---|---|---|
| domain_general | **90** | **100%** |
| brand_faye | 0 | 0%（W1+W2 素材里没有"笛语品牌调性"或"笛语创始人具体内容"的素材，所以应该是 0） |
| needs_review | 0 | 0% |

**这是正确的状态**——按用户口径 W1+W2 抽到的 90 条 pack 全部是"通用零售运营知识"，确实都该 domain_general。

## 第二轮纠偏的关键洞察

第一轮（多租户纠偏）做了规则锁定的工作，但在判定具体 pack 时**判断标准过于敏感**：把"含品牌特定字段名的 schema 元规则"误判为 brand_<name>。

第二轮（领域边界明示）补全了关键的"哪些是 domain_general"正面清单，让判定从"模糊敏感"变成"先看分类，落 8 类通用范畴的直接 domain_general"。

## 后续 W3+ 必须遵守的最终纪律

1. **抽 pack 时 fast-path**：先看素材主语是不是某品牌的具体调性 / 创始人内容——
   - 不是 → 几乎肯定是 `domain_general`（W1+W2 这一类占 100% 且全部正确）
   - 是 → 走 SKILL.md §6.2 完整 3 步流程
2. **9 表派生时**：每行 brand_layer 严格按 pack 标注；W1+W2 的 90 条全部 domain_general
3. **预期 brand_faye 何时首次出现**：
   - W5 TC-B16（Q2 企业叙事类 / 笛语品牌叙事文案具体内容）
   - 后续 Q1 笛语品牌主张原文 / 笛语创始人具体故事的素材进来时
4. **W3 起人工抽查**：每张 B 卡至少抽样 3 条核对 brand_layer，避免再漂

---
snapshot_type: historical_review
frozen_at: 2026-05-03T15:50:44Z
source_state: pre-W10
rationale: 历史复核/方案文档，反映当时状态，不再随仓库演进；不参与 G18 漂移检测
---

# TC-B01 复核报告 · 商品与属性基础包

> 日期：2026-05-03
> 范围：W1 第一波 · TC-B01 单卡流程验证
> 状态：**TC-B01 完成，等待人工 Go/No-Go 决策**

---

## 1. 八条 CandidatePack 路径与核心断言

| # | pack_id | knowledge_assertion（一句话压缩） |
|---|---|---|
| 1 | KP-product_attribute-core-category-7-plus-3 | 母类冻结为 7 主+3 扩展，理由是同时支撑接客/救场/陈列/培训四条路径 |
| 2 | KP-product_attribute-shared-6-decision-dims | 每个母类必挂 6 共用核心维度（color/material/fit/length/season/occasion），缺一即决策不全 |
| 3 | KP-product_attribute-synonym-convergence | 12 组散乱叫法（8 品类+4 属性）必须收敛为标准术语 |
| 4 | KP-product_attribute-no-forced-merge | 4 组看似像但不许强收：卡其≠驼色 / 真丝≠醋酸 / 修身≠合体 / 短款≠常规偏短 |
| 5 | KP-product_attribute-decision-level-hard-vs-high | decision_level 两档：硬改 6 触发整套重算 / 高频改 6 触发套内调整 |
| 6 | KP-display_rule-attribute-driven-display | 陈列分组必须基于 8 属性维度（color/Collection/Category/length/fit/season/pattern/occasion），不许仅靠审美 |
| 7 | KP-product_attribute-display-only-fields | 6 个展示字段（fabric_story 等）保留但不进首轮决策，仅供培训/详情页/话术 |
| 8 | KP-product_attribute-collection-cold-start-scope | Collection 冷启动只做主题归组/成组陈列/培训说明三件事，不升搭配硬约束 |

## 2. 4 Gates 自检结果

| pack_id | G1 闭环 | G2 反推 | G3 泛化 | G4 可用 | 最终 |
|---|---|---|---|---|---|
| core-category-7-plus-3 | pass | pass | pass | pass | active |
| shared-6-decision-dims | pass | pass | pass | pass | active |
| synonym-convergence | pass | pass | pass | pass | active |
| no-forced-merge | pass | pass | pass | pass | active |
| decision-level-hard-vs-high | pass | pass | pass | pass | active |
| attribute-driven-display | pass | pass | pass | pass | active |
| display-only-fields | pass | pass | pass | pass | active |
| collection-cold-start-scope | pass | pass | pass | pass | active |

**8 条全 pass。**

## 3. 9 表派生增量统计

| 表 | TC-B01 前 | 增量 | 当前总行 |
|---|---|---|---|
| 01_object_type | 5 | +3（Category / Attribute / Collection） | 8 |
| 02_field | 7 | +20 | 27 |
| 03_semantic | 3 | +8 | 11 |
| 04_value_set | 16 | +63 | 79 |
| 05_relation | 4 | +3 | 7 |
| 06_rule | 3 | +8 | 11 |
| 07_evidence | 3 | +8 | 11 |
| 08_lifecycle | 0 | 0 | 0 |
| 09_call_mapping | 6 | +4 | 10 |
| **合计** | **47** | **+117** | **164** |

> 单条 pack 派生 9 表行数最大值 = 16（synonym-convergence / decision-level-hard-vs-high / display-only-fields），**远低于 50 行警戒线**。
> 8 条 pack 平均派生 14.6 行，粒度健康。

## 4. TC-B01 验收标准逐项核对

| 验收项（task_cards.md TC-B01） | 实际 | 是否达标 |
|---|---|---|
| ① ≥80% pack 主 pack_type 为 product_attribute | 7/8 = 87.5% | ✅ |
| ② Product / Category / Attribute 字段挂在 skeleton 允许的对象上 | 全部挂在 Category / Attribute / Product / Collection（均在 skeleton 18 项内） | ✅ |
| ③ 抽样 3 条：assertion 具体 + evidence_quote 来自该 md + 9 表反推可还原 | 见第 5 节 | ✅ |
| ④ 不可处理项写入 unprocessable_register/register.csv | 本卡无不可处理项；register.csv 仅表头 | ✅（无触发） |
| ⑤ 无单条派生 9 表 > 50 行 | 最大 16 行 | ✅ |

## 5. 抽样 3 条反推（reverse_infer）核验

### 5.1 KP-product_attribute-shared-6-decision-dims
从 `02_field.csv` 的 Attribute.attribute_name + `04_value_set.csv` 的 6 个 shared_core 取值 + `05_relation.csv` 的 `Category-has_attribute-Attribute`（required=color/material/fit/length/season/occasion, polarity=all_categories）+ `06_rule.csv` 的 `attribute_dimension_enforcement`，可反推：
- 知识断言 ✅（每 Category 必挂 6 共用维度）
- 适用条件 ✅（Category 建设或维护）
- 翻车模式 ✅（漏挂→该 Category 推荐与陈列失效）
- 证据来源 ✅
- pack_type ✅（product_attribute）

### 5.2 KP-product_attribute-no-forced-merge
从 `04_value_set.csv` 的 4 组反向边界（color khaki/camel + material silk/acetate + fit slim_fit/regular_fit + length cropped/regular_short）+ `06_rule.csv` 的 `synonym_anti_merge`（applicable_when=4 组合并提案 / flip=推荐错位+售后纠纷）可反推：
- 知识断言 ✅（4 组不许合并）
- 适用条件 ✅
- 翻车模式 ✅（强收→四个维度推荐错位）
- 证据来源 ✅
- pack_type ✅

### 5.3 KP-display_rule-attribute-driven-display
从 `04_value_set.csv` 的 8 个 display axes + `05_relation.csv` 的 `DisplayGuide-has_attribute-Attribute`（role=display_axis, required_min=1, allowed=8 维度）+ `06_rule.csv` 的 `attribute_driven_display_grouping` + `09_call_mapping.csv` 的 display_guidance 调用，可反推：
- 知识断言 ✅（陈列必须基于 8 维度）
- 适用条件 ✅（任意陈列单元布展）
- 翻车模式 ✅（无属性轴→视觉嘈杂；用展示字段分组→变内容秀）
- 证据来源 ✅
- pack_type ✅（display_rule）

**3 条 reverse_infer 全部成立。**

## 6. 反空壳门禁逐项检视

| 反空壳项 | 8 条样本是否触发 |
|---|---|
| knowledge_assertion 是空话 | 否 |
| success / flip 没有成对 | 否（8 条均成对） |
| evidence_quote 不能支撑 assertion | 否 |
| 只生成 source_md/evidence_ref 没有业务判断 | 否 |
| 只复述标题没有重组 | 否 |
| 写"根据情况判断""有助于提升转化"等泛话 | 否 |
| 9 表无法反推原业务语义 | 否 |
| 单条派生 > 50 行 | 否 |

**空壳风险：无。**

## 7. 流程验证小结（W1 单跑目的的回应）

W1 选 B01 单跑的目的，是用 product_attribute 这个**最碰 skeleton 重头戏**的卡，验证以下三件事是否稳：

| 验证项 | 结论 |
|---|---|
| skeleton 中 Category / Attribute / Collection 三类对象的挂靠口径 | ✅ 全部挂在 skeleton 18 项白名单内，未触发 skeleton_gap_register 新增 |
| 同一份 markdown 派生多条 pack 时，互引（rule 相互 alternative_boundary 引用、value_set 跨 pack 复用语义）的稳定性 | ✅ 8 条 pack 内部互引清晰：synonym-convergence 与 no-forced-merge 互为正反边界；decision-level 与 display-only-fields 共享 decision_level 字段定义 |
| ID 规则在大批量下的可复跑性 | ✅ 所有 pack_id / rule_id / evidence_id / value_set_id 严格按 skill 规则；同一输入再跑产物可 byte-identical |

**额外副作用（积极）**：本卡显式落档了 9 表 schema 缺的 Product 6 个展示字段（fabric_story / craft_story / designer_note / care_instruction / selling_points_copy / model_reference），后续 Q2 内容类型批次可直接复用，不必重抽。

## 8. Go / No-Go 决策点

**建议：Go——可以并行启动 W1 剩余 3 张（B02 / B05 / B07）。**

理由：
1. 4 闸 8/8 全 pass，0 触发空壳门禁。
2. 验收 5 项全部达标。
3. skeleton 18 项白名单经压力测试稳定，没有新增 gap。
4. 9 表派生量级可控，未触及任何阻断条件。

**如果你想再保险一点，也可以选**：
- **选项 B**：先对本卡 8 条 pack 抽 1-2 条做人工细看（重点看 `knowledge_assertion` 是否符合你对"具体业务判断"的口径），确认后再放飞剩余 3 张并行。
- **选项 C**：本卡通过，直接进 W1 余下 3 张并行。

我等你定夺。如选 C，我会一条消息内同时甩 B02 / B05 / B07 三张 Agent 卡并行执行；如选 B，请指出你想抽看的 1-2 条 pack。

## 9. 当前累计进度

- 已完成卡：TC-00 / TC-01 / TC-B01（共 3 张 / 27 张，进度 11.1%）
- 已抽 CandidatePack：3（Phase A）+ 8（B01）= **11 条**
- 9 表累计行数：**164 行**（lifecycle 仍为 0，符合预期）
- 不可处理 / needs_review：0 / 0
- 阻断项：0

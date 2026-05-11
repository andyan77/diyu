# Phase A 复核报告

> 日期：2026-05-03
> 范围：Phase 0（领域骨架）+ Phase A（3 条样本试抽）
> 状态：**Phase A 完成，等待人工确认后进入 Phase B**

---

## 1. 三条 CandidatePack 路径与核心断言

| # | pack_id | 文件路径 | knowledge_assertion（一句话压缩） |
|---|---|---|---|
| 1 | `KP-fabric_property-linen-natural-creases` | `clean_output/candidates/domain_general/KP-fabric_property-linen-natural-creases.yaml` | 亚麻 / 棉麻的高级感来自自然折痕，不能向顾客承诺全天平整；肘部 / 臀部 / 坐位 / 前门襟必出褶要前置说明 |
| 2 | `KP-service_judgment-comfort-sensitive-trigger` | `clean_output/candidates/domain_general/KP-service_judgment-comfort-sensitive-trigger.yaml` | 顾客问"会不会扎/热/透/勒/掉"时，导购不能直接答"不会"，必须先识别她介意的是触感/温度/透度/弹性/静电/内搭难度中的哪一个，否则后面推几套都白搭 |
| 3 | `KP-display_rule-full-look-no-broken-size` | `clean_output/candidates/domain_general/KP-display_rule-full-look-no-broken-size.yaml` | 成套陈列位只能建立在 full_look_ready / new_arrival_complete / core_push_deep_stock 三类齐套或可补的库存状态上；断码、清仓尾货、伪成套不得进成套位 |

## 2. 4 Gates 自检结果

| pack_id | Gate 1 闭环场景 | Gate 2 九表反推 | Gate 3 规则泛化 | Gate 4 生产可用 | 最终状态 |
|---|---|---|---|---|---|
| KP-fabric_property-linen-natural-creases | pass | pass | pass | pass | active |
| KP-service_judgment-comfort-sensitive-trigger | pass | pass | pass | pass | active |
| KP-display_rule-full-look-no-broken-size | pass | pass | pass | pass | active |

3 条全 pass。详细判定理由见每条 CandidatePack 的 `gate_self_check.notes`。

## 3. 9 表派生行数

| pack_id | object_type | field | semantic | value_set | relation | rule | evidence | lifecycle | call_mapping | 合计 |
|---|---|---|---|---|---|---|---|---|---|---|
| KP-fabric_property-linen-natural-creases | 1 | 3 | 1 | 4 | 0 | 1 | 1 | 0 | 2 | **13** |
| KP-service_judgment-comfort-sensitive-trigger | 2 | 2 | 1 | 6 | 1 | 1 | 1 | 0 | 2 | **16** |
| KP-display_rule-full-look-no-broken-size | 2 | 2 | 1 | 6 | 3 | 1 | 1 | 0 | 2 | **18** |

> 三条均**远低于 50 行警戒线**，粒度健康。
> `lifecycle` 全空（无明确状态迁移叙述），符合"不为凑表而编生命周期"原则。

## 4. brand_layer 判断

| pack_id | brand_layer | 是否需要人工复核 | 理由 |
|---|---|---|---|
| KP-fabric_property-linen-natural-creases | `domain_general` | 否 | 围绕亚麻通用纤维特性，不含笛语专属表达 |
| KP-service_judgment-comfort-sensitive-trigger | `domain_general` | 否 | 通用接客判断顺序，不含笛语口吻 |
| KP-display_rule-full-look-no-broken-size | `domain_general` | 否 | 通用陈列纪律，可直接被任意女装门店复用 |

3 条均判定为 `domain_general`，`brand_layer_review_queue.csv` 为空（仅表头）。

> 提醒：素材目录中明显的 `brand_faye` 内容（如 Q4-人设种子下笛语专属人设、Q2 中笛语品牌口吻表达）将在 Phase B 出现。Phase A 抽样有意全选了通用层断言以验证骨架。

## 5. 反推（reverse_infer）核验

逐条做了 9 表 → CandidatePack 反推：

### 5.1 KP-fabric_property-linen-natural-creases
从 `06_rule.csv` 的 `RL-KP-fabric_property-linen-natural-creases` + `04_value_set.csv` 的 4 个 `risk_position` + `07_evidence.csv` 的 evidence quote，可以反推出：
- 知识断言 ✅（亚麻 = 自然折痕 = 纤维表情，不能承诺全天平整）
- 适用条件 ✅（亚麻 / 棉麻 + 久坐或长时间通勤）
- 翻车模式 ✅（承诺不皱 → 出褶 → 顾客认定品质问题）
- 证据来源 ✅
- pack_type ✅（fabric_property）

### 5.2 KP-service_judgment-comfort-sensitive-trigger
从 `06_rule.csv` 的 `customer_concern_disambiguation` + `04_value_set.csv` 的 6 个 `concern_dimension` + `09_call_mapping.csv` 的 `branching_scenario|do_dont_contrast` 培训格式，可以反推出：
- 知识断言 ✅（先识别介意维度再回应）
- 适用条件 ✅（触发语含 5 个体感词之一）
- 翻车模式 ✅（直接答"不会"导致信任流失）
- 证据来源 ✅
- pack_type ✅（service_judgment）

### 5.3 KP-display_rule-full-look-no-broken-size
从 `06_rule.csv` 的 `display_inventory_gating` + `04_value_set.csv` 的 allowed/forbidden 两组取值 + `05_relation.csv` 的两条 `requires_inventory_state`（一条 allow / 一条 forbid），可以反推出：
- 知识断言 ✅（成套位的库存白名单与黑名单）
- 适用条件 ✅（full_look_display 或 mannequin_display 整套目标）
- 翻车模式 ✅（少一件就散）
- 证据来源 ✅
- pack_type ✅（display_rule）

**3 条 reverse_infer 全部成立。**

## 6. 空壳风险检查

逐项过反空壳门禁清单：

| 检查项 | 3 条样本是否触发 |
|---|---|
| knowledge_assertion 是空话 | 否 |
| success_pattern 与 flip_pattern 没有成对 | 否（3 条均成对且明确对照） |
| evidence_quote 不能支撑 assertion | 否（均为素材直接引用） |
| 只生成 source_md / evidence_ref 没有业务判断 | 否 |
| 只复述标题没有重组业务知识 | 否 |
| 写"根据情况判断""有助于提升转化"等泛话 | 否 |
| 9 表无法反推原业务语义 | 否 |
| 单条派生 9 表超过 50 行 | 否（最大 18 行） |

**空壳风险：无。**

## 7. 是否建议进入 Phase B

**建议进入 Phase B**，但有以下提示：

1. **Phase A 故意只抽 `domain_general`**，未验证 `brand_faye` 与 `needs_review` 路径。Phase B 推荐顺序首批就是 Q7Q12 业务包（继续 domain_general 为主），第二批 Q4-人设种子（笛语品牌专属判断会大量出现 `brand_faye` 与拆分需求），第三批 Q2-内容类型种子（含 `brand_faye` 与 PlatformTone / ContentType 关联）。
2. **GAP-001（MerchandisingSkill）** 在素材中频繁出现但没有正式落对象。建议在进入 Phase B 之前，由人工裁决：
   - 选项 A：保持现状，继续作为 DisplayGuide + StylingRule + TrainingMaterial 的组合视图，不立独立对象；
   - 选项 B：升格为独立 `core_object_type`（需要扩 skeleton）。
3. **每处理 5 份 markdown 触发 checkpoint**——Phase B 会按这个节奏交摘要，不会一口气批量到底。

## 8. 下一步等你的指令

**当前不会自动进入 Phase B。**
请人工确认以下两件事再继续：
1. 上面 3 条样本的 `knowledge_assertion` 是否符合你对"具体业务判断"的口径？
2. GAP-001 的处置选项（A 保持组合视图 / B 升格独立对象）你倾向哪一个？

确认后回复"进入 Phase B"或具体调整意见即可。

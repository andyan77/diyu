# 任务卡清单 · 27 张（方案 B 中粒度）

> 范围：完成 `prompt .md` 的全部任务目标。
> 颗粒度：Phase 0/A 各 1 张 · Phase B 按素材包 19 张 · Phase C/D/E/F 各 1 张 · 滚动维护 2 张。
> 每张卡四件套：**输入 / 产出 / 验收标准 / 依赖**；独立可验证。

## ⚠️ 多租户隔离全局硬约束（凌驾每张卡的局部验收）

> 本仓的真实数据模型是 **多租户单库逻辑隔离**：
> `domain_general` + `brand_faye` + `brand_xyz` + ……，`brand_layer` 是租户隔离 key。
>
> **每张 B 卡 / C 卡 / D 卡 / E 卡 / F 卡的验收都必须额外满足以下 4 项**：
>
> 1. **brand_layer 严格按 SKILL.md §6 多租户判定流程标注**——禁止"规则形式抽象 = domain_general"的偏移路径
> 2. `domain_general` 行**禁止引用** `brand_<name>` 行；`brand_<name>` 行可继承 `domain_general`
> 3. 拿不准的 → `needs_review` + 写入 `audit/brand_layer_review_queue.csv`，禁止默认 `domain_general`
> 4. 任何含具体字段壳 / 取值集 / 文案 / 内部动作 / 品牌口吻的 pack 必须标 `brand_<name>`
>
> 详见项目根 `CLAUDE.md` 的 **多租户隔离硬纪律** 节与 `.claude/skills/extract-9tables/SKILL.md` §6。

## 卡片状态总览

<!-- AUTO-SYNCED at 2026-05-14T10:32:50
     status source: audit/extraction_log.csv (event timestamps)
     numbers source: live disk (manifest.json + csv + sqlite)
     DO NOT HAND-EDIT -->

**实时数字真源**：
- CandidatePack 总数：**201**（实测 candidates/**/*.yaml）
- 9 表数据行总数：**2455**（实测 wc -l 减 header）
- 正向覆盖率：**—**（实测 scan_unprocessed_md.py）
- SQLite 加载行数：**2455**（实测 SELECT COUNT）

**卡状态（来源 extraction_log task_card_completed 事件）**：

| 卡号 | 名称 | Phase | 状态 |
|---|---|---|---|
| TC-00 | 领域骨架 | Phase 0 | ✅ 完成 |
| TC-01 | 3 条样本试抽 | Phase A | ✅ 完成 |
| TC-B01 ~ TC-B08 | Q7Q12 批量 | Phase B | ✅ 完成 |
| TC-B09 ~ TC-B13 | Q4 批量 | Phase B | ✅ 完成 |
| TC-B14 ~ TC-B19 | Q2 批量 | Phase B | ✅ 完成 |
| TC-C01 | 4 闸全量验证 | Phase C | ✅ 完成 |
| TC-D01 | 9 表全量派生 | Phase D | ✅ 完成 |
| TC-E01 | 单库存储 SQL | Phase E | ✅ 完成 |
| TC-F01 | 收口报告 | Phase F | ✅ 完成 |
| TC-M01 / TC-M02 | 滚动维护 | 跨 Phase | ♻ 持续 |

---

## TC-00 · Phase 0 领域骨架 ✅

| 字段 | 内容 |
|---|---|
| **输入** | 三个素材目录 `Q2-内容类型种子/` `Q4-人设种子/` `Q7Q12-搭配陈列业务包/` 中所有 markdown 的对象 / 关系名称扫读 |
| **产出** | `clean_output/domain_skeleton/domain_skeleton.yaml` · `pack_type_mapping.md` · `skeleton_gap_register.csv` |
| **验收标准** | ① 18 个 `core_object_types` 清晰冻结；② 14 个 `allowed_relation_kinds` 清晰冻结；③ 8 个 `pack_type` 到对象类型映射齐全；④ 没有随意新增对象；⑤ `skeleton_gap_register.csv` 至少有表头（实际登记 3 条 gap） |
| **依赖** | 无 |
| **独立性** | 完全独立，可单跑 |
| **状态** | ✅ 完成于 2026-05-03 |

## TC-01 · Phase A 3 条样本试抽 ✅

| 字段 | 内容 |
|---|---|
| **输入** | TC-00 产出的 skeleton + 3 份指定素材：`面料工艺品质判断包.md` / `门店接客场景包.md` / `陈列方法包.md` |
| **产出** | 3 个 CandidatePack YAML（`candidates/domain_general/`） + `audit/four_gate_results.csv`（3 行）+ 9 表派生（首批 47 行）+ `audit/phase_a_review.md` |
| **验收标准** | ① 3 条 `knowledge_assertion` 均通过空话检测；② 3 条 4 闸全 pass；③ 3 条 9 表反推成立；④ 单条派生不超 50 行；⑤ `phase_a_review.md` 含反推核验过程 |
| **依赖** | TC-00 |
| **独立性** | 与 Phase B 任何素材包独立 |
| **状态** | ✅ 完成于 2026-05-03 |

---

# Phase B · Q7Q12-搭配陈列业务包（8 张）

## TC-B01 · 商品与属性基础包

| 字段 | 内容 |
|---|---|
| **输入** | `Q7Q12-搭配陈列业务包/商品与属性基础包.md` 全文 + TC-00 skeleton |
| **产出** | 该包派生的 N 条 CandidatePack YAML（预估 10-15 条，主 `pack_type=product_attribute`，可含 `styling_rule` / `display_rule` 关联）+ 追加 `extraction_log.csv` 行 |
| **验收标准** | ① 至少 80% CandidatePack 主 pack_type 为 `product_attribute`；② Product / Category / Attribute 字段均挂在 skeleton 允许的对象上；③ 抽样 3 条：`knowledge_assertion` 具体 + `evidence_quote` 来自该 md + 9 表反推可还原；④ 不可处理项写入 `unprocessable_register/register.csv`；⑤ 无单条派生 9 表 > 50 行 |
| **依赖** | TC-00 |
| **独立性** | 不依赖其他 B 卡 |

## TC-B02 · 搭配规则包

| 字段 | 内容 |
|---|---|
| **输入** | `Q7Q12-搭配陈列业务包/搭配规则包.md` 全文 + TC-00 skeleton |
| **产出** | N 条 CandidatePack（预估 10-18 条，主 `pack_type=styling_rule`）+ extraction_log 追加 |
| **验收标准** | ① 主 pack_type=`styling_rule` 占比 ≥ 80%；② 每条 `success_pattern` 与 `flip_pattern` 必须成对；③ 抽样 3 条 9 表反推成立；④ `call_mapping` 至少含 `outfit_recommendation` 与 `store_training` 两路之一；⑤ 不可处理项登记 |
| **依赖** | TC-00 |
| **独立性** | 不依赖其他 B 卡 |

## TC-B03 · 陈列方法包（补完）

| 字段 | 内容 |
|---|---|
| **输入** | `Q7Q12-搭配陈列业务包/陈列方法包.md` 全文 + 已抽 TC-01 的 1 条 `KP-display_rule-full-look-no-broken-size` + TC-00 skeleton |
| **产出** | 剩余 5 个陈列单元（window / mannequin / front_hanging / side_hanging / folded）+ 6 个库存状态标签 + 6 类陈列错误共约 10-15 条新 CandidatePack |
| **验收标准** | ① 6 个陈列单元 100% 覆盖；② 6 类库存状态在 value_set 表中齐备；③ 不与 TC-01 的成套位 pack 重复（用 `duplicate_or_redundant` 兜底）；④ 抽样 3 条反推成立；⑤ 培训层级（新人 / 店长老手）信息进入 `relation` 或 `properties_json` |
| **依赖** | TC-00 + TC-01 |
| **独立性** | 与其他 B 卡独立 |

## TC-B04 · 门店接客场景包（补完）

| 字段 | 内容 |
|---|---|
| **输入** | `Q7Q12-搭配陈列业务包/门店接客场景包.md` 全文 + 已抽 TC-01 的 `comfort_sensitive` 1 条 + TC-00 skeleton |
| **产出** | 剩余 9 类接客场景 CandidatePack + 5 类"卡在第二/第三套"裁决 + 5 类"断码可救" + 3 类"断码不救" + 4 类"先陈列后开口" + 6 类"必须先问再推" 共预估 15-20 条 |
| **验收标准** | ① 10 类场景 100% 覆盖且无遗漏；② 与 TC-01 不重复；③ 每条 `trigger_phrase` / `first_judgment` / `flip_pattern` 三件套齐全；④ 抽样 3 条反推；⑤ TrainingMaterial 关联含 `branching_scenario` / `do_dont_contrast` / `pre_shift_micro_coaching` / `error_replay` 中至少一种 |
| **依赖** | TC-00 + TC-01 |
| **独立性** | 与其他 B 卡独立 |

## TC-B05 · 面料工艺品质判断包（补完）

| 字段 | 内容 |
|---|---|
| **输入** | `Q7Q12-搭配陈列业务包/面料工艺品质判断包.md` 全文 + 已抽 TC-01 的亚麻 1 条 + TC-00 skeleton |
| **产出** | 剩余 7 类面料（棉针织 / 粘胶 / 真丝缎面 / 羊毛 / 牛仔 / 雪纺欧根纱 / 涤纶锦纶）+ 6 类工艺品控（预缩水洗 / 缝制质量 / 粘合衬 / 染整色牢度 / 磨毛起绒 / 压褶明线）+ 6 类高频误判 + 8 类风险口径，预估 25-35 条 CandidatePack |
| **验收标准** | ① 8 类面料 + 6 类工艺 + 6 类误判全覆盖；② `fabric_property` 与 `craft_quality` 两类 pack_type 均出现；③ 与 TC-01 的亚麻条不重复；④ 抽样 5 条（本卡产出量大）反推成立；⑤ 风险位置（如肘部/坐位/缝口/包带处）作为 value_set 取值显式登记 |
| **依赖** | TC-00 + TC-01 |
| **独立性** | 与其他 B 卡独立 |

## TC-B06 · 库存与替代包

| 字段 | 内容 |
|---|---|
| **输入** | `Q7Q12-搭配陈列业务包/库存与替代包.md` 全文 + TC-00 skeleton |
| **产出** | N 条 CandidatePack（主 `pack_type=inventory_rescue`，可含 `styling_rule` 关联），预估 10-15 条 |
| **验收标准** | ① 主 pack_type=`inventory_rescue` 占比 ≥ 70%；② 每条必含"何时救场 / 何时转向 / 何时放弃"三态判断；③ 与 TC-B03 / TC-B04 的库存状态标签 value_set 复用，不重新发明；④ 抽样 3 条反推成立 |
| **依赖** | TC-00；建议在 TC-B03 之后跑（库存状态标签已落 value_set）但不强制 |
| **独立性** | 软依赖 TC-B03 |

## TC-B07 · 培训与纠错包

| 字段 | 内容 |
|---|---|
| **输入** | `Q7Q12-搭配陈列业务包/培训与纠错包.md` 全文 + TC-00 skeleton |
| **产出** | N 条 CandidatePack（主 `pack_type=training_unit`），预估 10-15 条 |
| **验收标准** | ① 每条必含"错误动作 / 正确动作 / 为什么错 / 如何纠正 / 掌握检查"五件套；② 培训格式锁定在 `branching_scenario` / `do_dont_contrast` / `pre_shift_micro_coaching` / `error_replay` / `before_after_timelapse` 五类内，超出者进 `unprocessable_register`；③ `RoleProfile` 关联（适合训练的岗位）必填；④ 抽样 3 条反推成立 |
| **依赖** | TC-00 |
| **独立性** | 与其他 B 卡独立 |

## TC-B08 · 岗位手感与一线判断包

| 字段 | 内容 |
|---|---|
| **输入** | `Q7Q12-搭配陈列业务包/岗位手感与一线判断包.md` 全文 + TC-00 skeleton |
| **产出** | N 条 CandidatePack（pack_type 多为 `service_judgment` / `training_unit`），预估 10-18 条 |
| **验收标准** | ① 每条必有具体 `RoleProfile`（导购 / 店长 / 老手 / 新人）；② 与 TC-B04 / TC-B07 的同类断言用 `duplicate_or_redundant` 兜底，不重抽；③ "一线手感"类经验若无法形成具体业务断言 → 进 `unprocessable_register` 分类 `evidence_insufficient`，不强行成 pack；④ 抽样 3 条反推成立 |
| **依赖** | TC-00；建议在 TC-B04 / TC-B07 之后跑以做去重 |
| **独立性** | 软依赖 TC-B04 / TC-B07 |

---

# Phase B · Q4-人设种子（5 张）

## TC-B09 · 首批 Persona-RoleProfile 清单

| 字段 | 内容 |
|---|---|
| **输入** | `Q4-人设种子/phase-3-Q4-首批Persona-RoleProfile清单.md` 全文 + TC-00 skeleton |
| **产出** | N 条 CandidatePack（主对象 `Persona` / `RoleProfile`，pack_type 多为 `service_judgment` / `training_unit`），预估 8-12 条；首次出现 `brand_faye` brand_layer 的概率高 |
| **验收标准** | ① Persona 与 RoleProfile 两类对象均出现在 9 表 `01_object_type.csv`；② 笛语专属人设条目 brand_layer 必须显式标 `brand_faye` 且写入 `brand_layer_review_queue.csv`；③ 抽样 3 条反推成立；④ 通用岗位（如导购 / 店长）保持 `domain_general` |
| **依赖** | TC-00 |
| **独立性** | 与其他 B 卡独立；本卡是 `brand_faye` 路径首次落档 |

## TC-B10 · 三套通用 Persona 首批卡片

| 字段 | 内容 |
|---|---|
| **输入** | `Q4-人设种子/phase-3-Q4-三套通用Persona首批卡片.md` 全文 + TC-00 skeleton |
| **产出** | N 条 CandidatePack（主对象 `Persona`），预估 6-10 条 |
| **验收标准** | ① 三套 Persona 全覆盖；② brand_layer 多数为 `domain_general`，少量需拆分的进 `needs_review`；③ 与 TC-B09 不重复（`duplicate_or_redundant` 兜底）；④ 抽样 3 条反推成立 |
| **依赖** | TC-00；建议在 TC-B09 之后跑 |
| **独立性** | 软依赖 TC-B09 |

## TC-B11 · 参数级填充清单

| 字段 | 内容 |
|---|---|
| **输入** | `Q4-人设种子/phase-3-Q4-参数级填充清单.md` 全文 + TC-00 skeleton |
| **产出** | N 条 CandidatePack（pack_type 多为 `product_attribute` 或 `service_judgment`，亦可能挂 `Persona` 字段补全），预估 8-15 条 |
| **验收标准** | ① 参数即字段：必须落到 `02_field.csv` 而不是凭空造对象；② 凡是 skeleton 没有的对象 → 进 `skeleton_gap_register.csv`，不许临时新增；③ 抽样 3 条反推成立 |
| **依赖** | TC-00 |
| **独立性** | 与其他 B 卡独立 |

## TC-B12 · Persona-ContentType-Platform 兼容矩阵

| 字段 | 内容 |
|---|---|
| **输入** | `Q4-人设种子/phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md` 全文 + TC-00 skeleton |
| **产出** | 大量 `relation` 表行（`compatible_with_content_type` / `spoken_by_role`）+ 配套 `styling_rule` 或 `service_judgment` 类 CandidatePack，预估 10-20 条 pack + 30-50 行 relation |
| **验收标准** | ① 矩阵每个非空格子至少派生一行 `05_relation.csv`；② `relation_kind` 必须在 skeleton 14 项白名单内，新出现的关系类型进 `skeleton_gap_register.csv`；③ 抽样 5 条 relation 能从 9 表反推出原矩阵语义；④ Persona / ContentType / PlatformTone 三类对象均挂在 skeleton 允许的对象上 |
| **依赖** | TC-00 + TC-B09 + TC-B10（Persona 已有）+ 与 TC-B14（ContentType 已有）协调 |
| **独立性** | 中等耦合：建议放在 Q4 批最后或 Q2 交付物批之后 |

## TC-B13 · 首批岗位知识素材清单 + Q4 索引

| 字段 | 内容 |
|---|---|
| **输入** | `Q4-人设种子/phase-3-Q4-首批岗位知识素材清单.md` + `Q4-人设种子/_index.md` 全文 + TC-00 skeleton |
| **产出** | N 条 CandidatePack（多为 `training_unit` / `service_judgment`） + 索引性内容如何处理的裁决（多数走 `unprocessable_register` 分类 `meta_layer_not_business`），预估 5-10 条 pack |
| **验收标准** | ① _index 中纯目录性质的条目进 `unprocessable_register` 分类 `meta_layer_not_business`，不强抽；② 真有业务血肉的岗位知识抽成 pack；③ 抽样 3 条反推成立 |
| **依赖** | TC-00 |
| **独立性** | 与其他 B 卡独立 |

---

# Phase B · Q2-内容类型种子（6 张，按聚类）

## TC-B14 · Q2 交付物层 18 份

| 字段 | 内容 |
|---|---|
| **输入** | `Q2-内容类型种子/` 下 18 份 `*-交付物-v0.1.md`（behind_the_scenes / daily_fragment / emotion_expression / event_documentary / founder_ip / humor_content / knowledge_sharing / lifestyle_expression / outfit_of_the_day / personal_vlog / process_trace / product_copy_general / product_journey / product_review / role_work_vlog / store_daily / talent_showcase / training_material）+ TC-00 skeleton |
| **产出** | 每份交付物 → 主对象 `ContentType` 一条核心 CandidatePack + 关联 `service_judgment` / `training_unit` / `styling_rule` 的派生 pack，预估 35-55 条 pack |
| **验收标准** | ① 18 类 ContentType 100% 在 `01_object_type.csv` 出现一次（不得遗漏；若某份交付物无法形成具体业务断言，须显式登记到 `unprocessable_register/register.csv` 并写明分类与原因）；② 每条 pack 的 `compatible_with_content_type` relation 必须挂得上某个 ContentType；③ 笛语专属表达条目标 `brand_faye`；④ 抽样 8 条（本卡产出最多）反推成立；⑤ 单文件派生 9 表行数若爆掉，必须按 ContentType 拆条而非合并 |
| **依赖** | TC-00 |
| **独立性** | 大件，建议先于 TC-B12 完成，让矩阵卡能复用 ContentType |

## TC-B15 · Q2 通用类（3 份）

| 字段 | 内容 |
|---|---|
| **输入** | `Q2-内容类型种子/通用类.md` + `Q2-内容类型种子/通用类compass.md` + `Q2-内容类型种子/通用类deep-research-report.md` + TC-00 skeleton |
| **产出** | N 条 CandidatePack，多为通用 `styling_rule` / `service_judgment` / `training_unit`，预估 10-15 条；deep-research 部分可能多为引用，进 `unprocessable_register` 分类 `evidence_insufficient` 或 `meta_layer_not_business` 较多 |
| **验收标准** | ① 三份合并去重，相同业务断言只成一条 pack；② deep-research 内容若是综述/方法论 → 不强抽，进登记表；③ 抽样 3 条反推成立 |
| **依赖** | TC-00 |
| **独立性** | 与其他 B 卡独立 |

## TC-B16 · Q2 企业叙事类（3 份）

| 字段 | 内容 |
|---|---|
| **输入** | `Q2-内容类型种子/企业叙事类GPT5.4.md` + `Q2-内容类型种子/企业叙事类compass_artifact.md` + `Q2-内容类型种子/企业叙事类deep-research-report.md` + TC-00 skeleton |
| **产出** | N 条 CandidatePack（多为 `brand_faye` 的内容生成规则 + 通用层叙事方法），预估 8-15 条 |
| **验收标准** | ① 笛语专属叙事口吻条目必须 `brand_faye` + 进 `brand_layer_review_queue.csv`；② 通用叙事方法 `domain_general`；③ 抽样 3 条反推成立；④ 三份去重 |
| **依赖** | TC-00 |
| **独立性** | 与其他 B 卡独立 |

## TC-B17 · Q2 共享叙事引擎与深度研究

| 字段 | 内容 |
|---|---|
| **输入** | `Q2-内容类型种子/_shared-narrative-engines-v0.1.md` + `Q2-内容类型种子/GPT5.4.md` + `Q2-内容类型种子/compass_artifact_wf-6a00fe44-74d6-4f0c-b6c9-c3e309071f66_text_markdown.md` + `Q2-内容类型种子/深度研究.md` + TC-00 skeleton |
| **产出** | N 条 CandidatePack，主要是跨内容类型的通用方法论，预估 5-12 条；大量内容预计走 `unprocessable_register` 分类 `meta_layer_not_business` |
| **验收标准** | ① 凡是工程流程 / 方法论 / 元层定义 → 进登记表，不强抽；② 真正可形成具体业务断言的 → 抽 pack；③ 抽样 3 条反推成立；④ 不可处理项分类合理（不要全塞 `out_of_scope`）|
| **依赖** | TC-00 |
| **独立性** | 与其他 B 卡独立；本卡是元层风险最高的一卡，要严守反空壳 |

## TC-B18 · Q2 高频内容型补抽

| 字段 | 内容 |
|---|---|
| **输入** | TC-B14 完成后，回扫 `behind_the_scenes` / `daily_fragment` / `outfit_of_the_day` / `product_review` 等高频强落地 ContentType 的细节判断（这些通常素材最厚） + TC-00 skeleton |
| **产出** | 在 TC-B14 基础上的细颗粒补充，预估 10-20 条 pack |
| **验收标准** | ① 与 TC-B14 不重复（`duplicate_or_redundant` 兜底）；② 每条要有具体平台 / 场景上下文，不能泛泛"内容生成"；③ 抽样 3 条反推成立；④ 与 TC-B12 矩阵 relation 协调 |
| **依赖** | TC-00 + TC-B14 |
| **独立性** | 强依赖 TC-B14 |

## TC-B19 · Q2 残余素材回扫与去重

| 字段 | 内容 |
|---|---|
| **输入** | Q2 目录下 `_index.md` + `CLAUDE.md` + 任何前 5 张 Q2 卡未触达的残余 markdown + 全量 Q2 已抽 pack |
| **产出** | 残余素材的最终裁决：要么补几条 pack，要么进 `unprocessable_register`；以及全 Q2 的去重报告（追加到 `extraction_log.csv`） |
| **验收标准** | ① Q2 目录所有 markdown 都有处置（被抽过 / 被登记过 / 被引用过）；② 去重后无两条 pack 的 `knowledge_assertion` 实质相同；③ Q2 _index / CLAUDE.md 这类索引文件全部进登记表分类 `meta_layer_not_business` 或被显式说明引用；④ 输出一行 Q2 完成总结追加到 `extraction_log.csv` |
| **依赖** | TC-B14 ~ TC-B18 全部完成 |
| **独立性** | 强依赖前 5 张 Q2 卡，必须最后跑 |

---

# Phase C-F · 验证 / 派生 / 存储 / 收口（4 张）

## TC-C01 · Phase C 4 闸全量验证

| 字段 | 内容 |
|---|---|
| **输入** | Phase B 全部 19 张卡产出的所有 CandidatePack YAML（候选目录三层：`domain_general/` / `brand_faye/` / `needs_review/`） |
| **产出** | 完整 `audit/four_gate_results.csv`（每个 pack 一行）+ 抽样人工抽检 5 条的复核记录追加到 `audit/extraction_log.csv` |
| **验收标准** | ① 100% pack 都有 4 闸结果，无遗漏；② Gate 1 fail / Gate 2 fail 的 pack 已分别归入 `unprocessable_register` 分类 `scenario_not_closed` / `evidence_insufficient`；③ Gate 3 fail / Gate 4 fail 的 pack `state` 改为 `parked`；④ 抽样 5 条人工抽检：3 条 pass、1 条 partial、1 条 fail 各示例可解释；⑤ `final_state` 分布合理（pass 至少 60%，否则停下复核） |
| **依赖** | TC-B01 ~ TC-B19 全部完成 |
| **独立性** | 串行节点 |

## TC-D01 · Phase D 9 表全量派生

| 字段 | 内容 |
|---|---|
| **输入** | TC-C01 输出中**同时满足以下 4 个条件**的所有 pack（严格对齐 prompt §Phase D 第 1089-1094 行）：① `gate_1_closed_scenario` ≠ `fail`；② `gate_2_reverse_infer` ≠ `fail`；③ `knowledge_assertion` 合格（通过反空壳门禁）；④ `evidence_quote` 可支撑业务断言。`gate_3` / `gate_4` 为 `partial` 或 `fail` 不影响是否派生 9 表（仅影响 `state` 与 `call_mapping` 是否生成） |
| **产出** | 全量 9 张 CSV 更新（`nine_tables/01..09`）覆盖所有满足上述 4 条件的 pack |
| **验收标准** | ① 每张 CSV 表头与 skill `extract-9tables` §8 列定义完全一致；② 每张 CSV 末尾两列必有 `brand_layer` 与 `source_pack_id`；③ ID 完全可复跑：用同一输入再跑一次，产物 byte-identical；④ 无 pack 派生 9 表 > 50 行；⑤ `08_lifecycle.csv` 仅在素材含明确状态迁移时有行；⑥ 抽样 5 条 pack：从 9 表反推 → CandidatePack 的 5 项核心语义全部成立；⑦ 入口 4 条件 vs 实际派生集合做核对清单，若有 pack 满足 4 条件却未派生，必须列出原因；⑧ Gate 4=fail 的 pack 仍派生 9 表，但**不**生成 `09_call_mapping.csv` 行，`state` 标 `parked` |
| **依赖** | TC-C01 |
| **独立性** | 串行节点 |

## TC-E01 · Phase E 单库逻辑隔离 SQL

| 字段 | 内容 |
|---|---|
| **输入** | TC-D01 产出的 9 张 CSV + skill `extract-9tables` §14 |
| **产出** | `clean_output/storage/single_db_logical_isolation.sql` |
| **验收标准** | ① 9 张 `CREATE TABLE` 完整；② 每张表均含 `brand_layer` 列与 `source_pack_id` 列且**两列均建索引**；③ 提供**多租户隔离查询模板**——笛语 app `WHERE brand_layer IN ('domain_general','brand_faye')`，未来任意 brand_xyz `WHERE brand_layer IN ('domain_general','brand_xyz')`；④ 提供 `domain_general` 单层查询示例；⑤ 提供 `brand_faye` 单层查询示例；⑥ 提供 `needs_review` 行的处置说明（**未裁决前禁止入应用查询**）；⑦ 提供未来扩展说明（无需新建表，只新增 `brand_layer` 取值即可，**禁止物理分库**）；⑧ **加 SQL 级断言**：`CHECK (brand_layer ~ '^(domain_general\|brand_[a-z_]+\|needs_review)$')` 防止漂移；⑨ SQL 在主流解析器（sqlite/postgres dry-parse）下语法可通过 |
| **依赖** | TC-D01 |
| **独立性** | 串行节点 |

## TC-F01 · Phase F 收口报告

| 字段 | 内容 |
|---|---|
| **输入** | TC-C01 + TC-D01 + TC-E01 全部产出 + `extraction_log.csv` + `unprocessable_register/register.csv` + `brand_layer_review_queue.csv` |
| **产出** | `clean_output/audit/final_report.md` |
| **验收标准** | 11 项必含内容齐全：① 输入 markdown 数量；② CandidatePack 总数；③ 过 4 闸数量与比例；④ 进 `unprocessable_register` 数量与 8 类分类分布；⑤ `brand_layer` 分布（domain_general / brand_faye / needs_review 各占多少）；⑥ 8 类 `pack_type` 分布；⑦ 9 表各表行数；⑧ `needs_review` 数量；⑨ 空壳风险检查结论（按反空壳门禁 8 项逐条检视）；⑩ 抽样 reverse_infer 结果（至少 5 条）；⑪ 下一步建议（含 skeleton gap 处置、brand_faye 继续治理路径） |
| **依赖** | TC-E01 |
| **独立性** | 收口节点 |

---

# 滚动维护（2 张持续卡）

## TC-M01 · 不可处理 / 待复核登记滚动维护 ♻

| 字段 | 内容 |
|---|---|
| **输入** | 整个 Phase B（TC-B01 ~ TC-B19）执行过程中遇到的不可处理项与品牌层歧义项 |
| **产出** | `unprocessable_register/register.csv` 持续追加 + `audit/brand_layer_review_queue.csv` 持续追加 |
| **验收标准** | ① 任何写不出合格 `knowledge_assertion` 的内容必须落到 `register.csv`，不许直接丢弃；② 每条 `classification` 必在 8 类内；③ 任何 brand_layer 拿不准的 pack 必须落到 `brand_layer_review_queue.csv` 而不是默认填 `domain_general`；④ Phase B 结束时这两份表的总条数与 `extraction_log.csv` 计数对得上 |
| **依赖** | 跨 TC-B01 ~ TC-B19 全程触发 |
| **独立性** | 持续滚动，不单独执行 |

## TC-M02 · 抽取日志 / 骨架缺口 / 阻断项滚动维护 ♻

| 字段 | 内容 |
|---|---|
| **输入** | 整个 Phase B 执行过程中的事件流 |
| **产出** | ① `audit/extraction_log.csv` 每完成一张 B 卡追加一行 + 每 5 份 markdown 追加一条 checkpoint；② `domain_skeleton/skeleton_gap_register.csv` 每出现一个无法挂靠概念追加一行；③ `audit/blockers.md` 仅在触发 9 个停止条件之一时追加 |
| **验收标准** | ① `extraction_log.csv` 至少含 19 条 B 卡完成行 + 4 条 checkpoint 行；② 每个 checkpoint 含五件套：新增 pack 数 / 新增 unprocessable 数 / 新增 needs_review 数 / pack_type 分布 / 空壳风险；③ 触发任一停止条件 → `blockers.md` 必有显式条目 + 暂停后续卡执行；④ skeleton 增量保持冻结，所有 gap 走登记表 |
| **依赖** | 跨 TC-B01 ~ TC-B19 全程触发 |
| **独立性** | 持续滚动，不单独执行 |

---

# 推荐执行顺序

## 串行强制
TC-00 → TC-01 → Phase B（19 张，可分组并行/串行） → TC-C01 → TC-D01 → TC-E01 → TC-F01

## Phase B 内推荐顺序
1. **第一波（无依赖，可并行）**：TC-B01, TC-B02, TC-B05, TC-B07
2. **第二波（依 TC-01 已抽样）**：TC-B03, TC-B04
3. **第三波（依第一波已建立 value_set）**：TC-B06, TC-B08
4. **第四波（Q4）**：TC-B09 → TC-B10 → TC-B11 → TC-B13
5. **第五波（Q2 主体）**：TC-B14 → TC-B15 / TC-B16（可并行） → TC-B17
6. **第六波（依赖前波）**：TC-B18（依 TC-B14） → TC-B12（依 Persona+ContentType+Platform 已就绪） → TC-B19（Q2 收口）

## Checkpoint 触发节点
完成 5 张 B 卡 → 第 1 个 checkpoint
完成 10 张 B 卡 → 第 2 个 checkpoint
完成 15 张 B 卡 → 第 3 个 checkpoint
完成 19 张 B 卡 → 第 4 个 checkpoint（即 Phase B 结束）

# 三层知识粒度裁决框架（W11 立法）

> 状态：W11.0 立法版 · 与 prompt §13 八类 pack_type 白名单兼容 · 不改 9 表核心结构
> 适用范围：所有 source_unit（1578 章节）+ 所有 CandidatePack（194 已入库）

---

## 一、为什么要分层

**背景**：W2-W10 抽取以"概念级 pack"为隐含粒度，导致：
- 1578 章节中只有 357（22.6%）进 9 表
- 782 章节标 `pending_decision` 但缺裁决去向语言
- Finding 2（双向覆盖低）+ Finding 3（pending 未闭环）无法关闭

**解决思想**：把"抽不抽进 9 表"二元判断升级成"知识应该以什么粒度、被哪种消费场景使用"——三层粒度框架。

---

## 二、三层粒度定义

### L1 · 概念层（判断用）

- **作用**：内容类型识别、品牌一致性判断、素材归类、质检
- **典型样本**："OOTD 的北极星不是展示衣服，而是今天为什么这样穿"
- **承载**：进 9 表核心库（当前 194 pack 主体）
- **必填字段**：`consumption_purpose: judgement`

### L2 · 玩法层（生成用）

- **作用**：生成选题、短视频结构、门店拍摄脚本、栏目设计
- **典型样本**："固定角落 + 时间折痕 + 一件衣服记住今天"这类可复用玩法
- **承载（B-lite 决议）**：
  - **不**新建第 10 表，**不**改 9 表 schema
  - 新增旁路：`clean_output/play_cards/play_card_register.csv`
  - 通过现有 pack_type（`training_unit / styling_rule / product_attribute` 等）承载本体
  - `play_card_register.csv` 通过 `source_pack_id` 关联 9 表
- **必填字段（W11 G20 硬门）**：
  - `granularity_layer: L2`
  - `consumption_purpose: generation`
  - `production_difficulty`: low | medium | high
  - `production_tier`: instant | long_term | brand_tier
  - `resource_baseline`: 字符串（例 `1人+手机+200元+4h`）
  - `default_call_pool`: true | false（instant 默认 true）

### L3 · 执行层（操作用）

- **作用**：镜头顺序、台词禁区、拍摄动作、道具、门店员工分工
- **典型样本**："镜头先拍光，再带过手部动作；台词不可出现'最后机会'"
- **承载（D3 决议）**：
  - 主体进 `clean_output/runtime_assets/`（不进 9 表核心）
  - 可调用入口可进 `09_call_mapping`（仅引用，不持有内容）
  - L3 不参与 9 表核心覆盖率统计，参与 `l3_registered_pct`
- **必填字段（W11 G21 硬门）**：
  - `granularity_layer: L3`
  - `asset_type`: shot_template | dialogue_template | action_template | prop_list | role_split
  - `runtime_asset_id`: 字符串
  - `source_pointer`: source_md + line_no
  - production 字段可选

---

## 三、6 类裁决枚举（替换 W10 的 4 态）

| 状态 | 含义 | 落点 |
|---|---|---|
| `extract_l1` | L1 概念知识 | 9 表核心库 |
| `extract_l2` | L2 玩法卡 | 9 表 + play_card_register.csv |
| `defer_l3_to_runtime_asset` | L3 执行资产 | runtime_assets/，可选 09_call_mapping 入口 |
| `merge_to_existing` | 与已有 pack 重复，标 merge_target | 不新增行，更新 merge_log |
| `unprocessable` | 短节/元层/外部研究稿 | unprocessable_register |
| `duplicate` | 同 body sha 完全重复 | 不新增 |

> 兼容性：W10 的 4 态映射如下（自动迁移规则）
> - W10 `covered_by_pack` → 默认 W11 `extract_l1`（待回标）
> - W10 `unprocessable` → W11 `unprocessable`（不变）
> - W10 `duplicate_or_redundant` → W11 `duplicate`
> - W10 `pending_decision` → W11 进入预分流程（auto + 人工）

---

## 四、4 闸门 × 三层补充

| Gate | 现含义 | 三层补充 |
|---|---|---|
| Gate 1 闭环场景 | 谁在什么场景下用 | 必填 `consumption_purpose` ∈ {judgement, generation, execution} |
| Gate 2 九表反推 | 能否结构化落表 | L1 强投影；L2 强投影 + play_card_register；L3 转 runtime_assets |
| Gate 3 规则泛化 | 跨场景复用 | L1/L2 必须泛化；L3 可场景化（容忍）|
| Gate 4 生产可用 | 能否被系统调用 | L2 强制 `production_tier` + `default_call_pool` 非空 |

---

## 五、语义去重规则（D2 决议）

不上 embedding，使用 **5-gram 重叠率 + 人工审清单**：

| 规则 | 自动状态 |
|---|---|
| `body_hash` 完全相同 | `duplicate` |
| 5-gram overlap ≥ 50% | `merge_candidate`（待人工审） |
| 标题相似 + source_type 相同 + production_tier 相同 | `semantic_merge_review` |
| 人工确认后 | `merge_to_existing` |

---

## 六、L2 入库口径（B-lite）

不动 9 表 schema。流程：

1. L2 候选章节 → 现有 8 类 pack_type 之一承载（最常用 `training_unit / styling_rule`）
2. 该 pack 的 yaml 加 `granularity_layer: L2` + production 5 字段
3. 9 表行（06_rule / 02_field 等）正常派生
4. 同步在 `play_cards/play_card_register.csv` 登记一行：
   - `play_card_id, source_pack_id, granularity_layer=L2, production_tier, default_call_pool, ...`
5. 06_rule 行通过 `source_pack_id` 反查 register 即可拉取玩法元数据

> 等 W12 玩法卡超 500 条且确认是长期核心资产时，再升格为正式表。

---

## 七、新增硬门（W11 落地后 27 道）

| Gate | 检查 | 阻断条件 |
|---|---|---|
| **G19** | source_unit 三层裁决完整性 | 任意 source_unit `adjudication_status` 不在 6 类枚举或缺 `granularity_layer` |
| **G20** | L2 玩法卡字段完整性 | `granularity_layer=L2` 的 pack 缺任一 production 字段 |
| **G21** | L3 资产注册完整性 | `defer_l3_to_runtime_asset` 章节未在 runtime_assets 注册 |

---

## 八、W11 验收口径（最终）

> W11 完成 = 1578 个 source_unit 100% 完成 L1/L2/L3/排除/合并裁决；已入库 194 pack 完成 `granularity_layer` 回标；L1 缺口补入 9 表；L2 先进入 `play_card_register.csv` 并关联 9 表，仅高置信玩法卡增量生成 pack；L3 全部注册 `runtime_assets`；G19-G21 全绿。

不要求"L2 高价值全部抽进 9 表"——避免 W11 膨胀成模型升级工程。

---

## 九、与 CLAUDE.md / SKILL.md 红线兼容性

- ✅ 不改 9 表数量（仍 9 张）
- ✅ 不改 prompt §13 8 类 pack_type 白名单
- ✅ 不改 brand_layer 多租户隔离纪律
- ✅ play_card_register / runtime_assets 是新增旁路目录，登记进 manifest，不污染 candidates
- ✅ 三层是落点维度，与 4 闸合格维度正交，不冲突

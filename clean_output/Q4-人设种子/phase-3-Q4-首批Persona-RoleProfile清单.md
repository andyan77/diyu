# 首批 Persona / RoleProfile（人设 / 岗位画像）清单

> **文档性质：** 结构清单（候选 v0.1）
> **创建日期：** 2026-04-15
> **所属问题：** Q4
> **承接上游：** [phase-3-Q4-品牌首批默认启用几套人设.md](../phase-3-Q4-品牌首批默认启用几套人设.md)（Q4 裁决稿本稿）
>
> **状态：** 候选 — 待最终签字冻结
> **用途：** 作为冷启动阶段的人设对象总表与岗位挂接总表，供知识工程、内容运营、Prompt 配置、种子数据准备共同使用。
>
> **说明：** 本稿严格承接 Q4 第一份裁决稿冻结的口径（1 个品牌唯一层 + 3 个通用 Persona + 7 个 RoleProfile），不额外扩写平台细则与完整字段卡片。

---

## 零、这份清单解决什么问题

Q4 第一份裁决稿 [phase-3-Q4-品牌首批默认启用几套人设.md](../phase-3-Q4-品牌首批默认启用几套人设.md) 已经回答了：

> **品牌首批默认启用结构 = 1 个品牌唯一层 + 3 套通用 Persona（人设）**

但那份文档是"裁决口径稿"。这份第二清单继续回答：

> **这 1 + 3 结构具体由哪些正式对象构成、每套通用 Persona（人设）下面挂哪些首批 RoleProfile（岗位画像）、它们之间是什么关系。**

用白话说：

- **第一份文档回答"Q4 怎么定"**
- **这份清单回答"Q4 定完以后，系统里到底要先建哪些对象"**

---

## 一、当前清单的分层原则

本清单按两层正式对象组织：

### 1.1 品牌唯一层（Brand-Unique Layer，品牌唯一层）

该层当前只包含：

- `FounderProfile`（创始人画像）

**特点：**

- 每品牌有且仅有一份
- 不可复用
- 服务于 `founder_ip`（创始人 IP）这条内容线
- **不进入**通用 `Persona`（人设）编号体系

[phase-3-Q1-内容生产首批做什么.md §七.2](../phase-3-Q1-内容生产首批做什么.md#L401-L427) 已明确 `FounderProfile` 是每品牌唯一对象，并与 `founder_ip` 绑定；[Q4 裁决稿 §2.2](../phase-3-Q4-品牌首批默认启用几套人设.md) 已正式选定 `FounderProfile` 为对象类型名称（Q4 裁决稿记录了历史备选名的废弃过程，本种子不再重复）。

### 1.2 通用可复用层（Reusable Persona Layer，可复用人设层）

该层包含：

- `store_operator`（门店经营者）
- `styling_advisor`（穿搭顾问）
- `product_professional`（商品专业者）

**特点：**

- 可作为首批默认启用的通用 `Persona`（人设）壳
- 下面挂接具体 `RoleProfile`（岗位画像）
- 后续可扩展字段卡片、兼容矩阵、Prompt 注入参数

`Persona`（人设）的正式字段结构已在 [phase-3-内容生产核心思想落盘方案.md:215-263](../phase-3-内容生产核心思想落盘方案.md#L215-L263) 定义。

---

## 二、品牌唯一层清单

### 2.1 `FounderProfile`（创始人画像）

| 字段 | 内容 |
|---|---|
| `object_type`（对象类型）| `FounderProfile` |
| `display_name`（显示名称）| 创始人画像 |
| `scope`（作用范围）| `brand` |
| `multiplicity`（数量约束）| 每品牌 0/1（柔性使用，参考 [Q1 §柔性使用](../phase-3-Q1-内容生产首批做什么.md#L245-L249)）|
| 主要服务的 ContentType | `founder_ip`（创始人 IP）|
| 是否进入通用 `persona_id` 体系 | **否** |
| 命名冻结状态 | **本 Q4 正式选定 `FounderProfile`**（历史备选名废弃记录见 Q4 裁决稿 §2.2）|
| 字段结构初稿 | 见 [ITR-026](../../iteration-backlog.md)：`founder_name` / `value_system` / `worldview` / `brand_philosophy` / `lifestyle_manifesto` / `aesthetic_preferences` / `inspiration_sources` / `origin_story` / `signature_phrases` |
| 当前状态 | **本轮冻结建议：保留为品牌唯一层，不改造成通用 Persona** |

#### 说明

`FounderProfile`（创始人画像）不是"第 4 套通用人设"，而是**品牌唯一层**。对象性质不同、权限边界不同、服务题材不同，不能为了表面对称而把它硬塞进通用 `Persona`（人设）体系。

**命名冻结**：本 Q4 裁决稿 §2.2 已正式选定 `FounderProfile` 作为品牌唯一层对象类型名称（历史备选名的废弃记录归属 Q4 裁决稿原文）。对于"没有明显创始人文化"的品牌（老板不愿出镜 / 加工厂转型品牌 / 多人合伙无单一创始人），按 Q1 §柔性使用的口径，**允许不填 `FounderProfile`、不启用 `founder_ip` 题材**——这是启用与否的问题，不是命名贴不贴的问题，不需要通过更名解决。

---

## 三、通用 Persona（人设）清单

### 3.1 `store_operator`（门店经营者）

| 字段 | 内容 |
|---|---|
| `persona_id`（人设编号）| `store_operator` |
| `display_name`（显示名称）| 门店经营者 |
| 层级 | 通用 Persona |
| 核心作用 | 承接门店经营、带队、复盘、后台协同、秩序与氛围相关内容 |
| 首批挂接 RoleProfile | `store_manager`（门店店长）/ `warehouse_supervisor`（仓库主管）|
| 主承接 ContentType | `store_daily`（门店日常）/ 部分 `training_material`（培训物料）/ 部分 `emotion_expression`（情绪表达）|
| 可承接 ContentType | `behind_the_scenes`（幕后记录）/ `event_documentary`（事件纪录）/ `role_work_vlog`（岗位工作 Vlog，以门店视角切入）|
| 当前状态 | **本轮冻结建议：直接进入首批默认启用包** |

### 3.2 `styling_advisor`（穿搭顾问）

| 字段 | 内容 |
|---|---|
| `persona_id`（人设编号）| `styling_advisor` |
| `display_name`（显示名称）| 穿搭顾问 |
| 层级 | 通用 Persona |
| 核心作用 | 承接前台接客、试穿建议、搭配建议、顾客体感判断 |
| 首批挂接 RoleProfile | `sales_associate`（门店店员 / 导购）|
| 主承接 ContentType | `product_review`（产品测评）/ `outfit_of_the_day`（每日穿搭）/ `product_copy_general`（产品文案通用）|
| 可承接 ContentType | `knowledge_sharing`（穿搭与接客知识）/ `emotion_expression`（接客情绪）|
| 当前状态 | **本轮冻结建议：直接进入首批默认启用包** |

### 3.3 `product_professional`（商品专业者）

| 字段 | 内容 |
|---|---|
| `persona_id`（人设编号）| `product_professional` |
| `display_name`（显示名称）| 商品专业者 |
| 层级 | 通用 Persona |
| 核心作用 | 承接设计、打样、工艺、面料、版型、商品判断与专业知识内容 |
| 首批挂接 RoleProfile | `designer`（设计师）/ `sample_worker`（样衣工）/ `design_director`（设计总监）/ `merchandising_director`（商品总监）|
| 主承接 ContentType | `role_work_vlog`（岗位工作 Vlog）/ `product_journey`（产品历程）/ `process_trace`（工艺溯源）/ `knowledge_sharing`（专业向知识分享）|
| 可承接 ContentType | `product_review`（产品测评）/ `product_copy_general`（产品文案通用）|
| 当前状态 | **本轮冻结建议：直接进入首批默认启用包** |

---

## 四、首批 RoleProfile（岗位画像）清单

> **说明：** `RoleProfile`（岗位画像）是具体岗位知识来源，不是"说话身份壳"。它的职责是为通用 `Persona`（人设）提供岗位动作、术语、困境、真实性锚点和知识素材底座。[phase-3-冷启动知识底座建设规划.md](../phase-3-冷启动知识底座建设规划.md) 已明确：没有岗位知识，人设会空心。

### 4.1 `store_manager`（门店店长）

| 字段 | 内容 |
|---|---|
| `role_profile_id`（岗位画像编号）| `store_manager` |
| `display_name`（显示名称）| 门店店长 |
| 挂接 `persona_id` | `store_operator` |
| 主要支撑方向 | 门店经营、带队、培训、复盘、接客秩序 |

### 4.2 `warehouse_supervisor`（仓库主管）

| 字段 | 内容 |
|---|---|
| `role_profile_id`（岗位画像编号）| `warehouse_supervisor` |
| `display_name`（显示名称）| 仓库主管 |
| 挂接 `persona_id` | `store_operator` |
| 主要支撑方向 | 调货、库存、后场协同、后台视角、执行纪律 |

### 4.3 `sales_associate`（门店店员 / 导购）

| 字段 | 内容 |
|---|---|
| `role_profile_id`（岗位画像编号）| `sales_associate` |
| `display_name`（显示名称）| 门店店员 / 导购 |
| 挂接 `persona_id` | `styling_advisor` |
| 主要支撑方向 | 试穿建议、搭配判断、顾客体感、转化沟通、私域出货承接 |

### 4.4 `designer`（设计师）

| 字段 | 内容 |
|---|---|
| `role_profile_id`（岗位画像编号）| `designer` |
| `display_name`（显示名称）| 设计师 |
| 挂接 `persona_id` | `product_professional` |
| 主要支撑方向 | 灵感来源、设计判断、改版逻辑、产品表达 |

### 4.5 `sample_worker`（样衣工）

| 字段 | 内容 |
|---|---|
| `role_profile_id`（岗位画像编号）| `sample_worker` |
| `display_name`（显示名称）| 样衣工 |
| 挂接 `persona_id` | `product_professional` |
| 主要支撑方向 | 打样、工艺细节、真实劳动感、失败留痕 |

### 4.6 `design_director`（设计总监）

| 字段 | 内容 |
|---|---|
| `role_profile_id`（岗位画像编号）| `design_director` |
| `display_name`（显示名称）| 设计总监 |
| 挂接 `persona_id` | `product_professional` |
| 主要支撑方向 | 更高层的设计判断、审美标准、否决与取舍逻辑 |

### 4.7 `merchandising_director`（商品总监）

| 字段 | 内容 |
|---|---|
| `role_profile_id`（岗位画像编号）| `merchandising_director` |
| `display_name`（显示名称）| 商品总监 |
| 挂接 `persona_id` | `product_professional` |
| 主要支撑方向 | 商品策略、上新逻辑、货品判断、经营视角的商品分析 |

---

## 五、首批挂接总表

| 层级 | `object_id / role_profile_id` | `display_name` | 挂接对象 | 说明 |
|---|---|---|---|---|
| 品牌唯一层 | `FounderProfile` | 创始人画像 | — | 服务 `founder_ip`（创始人 IP），不进入通用 Persona 体系 |
| 通用 Persona | `store_operator` | 门店经营者 | — | 门店经营与后台协同主视角 |
| 通用 Persona | `styling_advisor` | 穿搭顾问 | — | 前台接客与搭配建议主视角 |
| 通用 Persona | `product_professional` | 商品专业者 | — | 设计、工艺、商品判断主视角 |
| RoleProfile | `store_manager` | 门店店长 | `store_operator` | 门店经营主岗位 |
| RoleProfile | `warehouse_supervisor` | 仓库主管 | `store_operator` | 后场协同岗位 |
| RoleProfile | `sales_associate` | 门店店员 / 导购 | `styling_advisor` | 前台接客岗位 + 私域出货承接 |
| RoleProfile | `designer` | 设计师 | `product_professional` | 设计岗位 |
| RoleProfile | `sample_worker` | 样衣工 | `product_professional` | 打样岗位 |
| RoleProfile | `design_director` | 设计总监 | `product_professional` | 高层设计决策岗位 |
| RoleProfile | `merchandising_director` | 商品总监 | `product_professional` | 商品决策岗位 |

**总计：** 1 个 `FounderProfile` + 3 个通用 `Persona` + 7 个 `RoleProfile` = **11 个正式对象**

---

## 六、为什么清单要这样组织

### 6.1 为什么不是"一岗位一人设"

因为首批冷启动阶段，系统更需要的是**少量高频、可持续、可被 Prompt / Skill / 运营反复调用的通用人设壳**，而不是一上来就把所有岗位都升格成独立 `Persona`（人设）。

岗位本身的专业度和真实性，应该由 `RoleProfile`（岗位画像）来补。这样既符合最佳工程实践，也更符合内容生产的稳定性要求。岗位知识是人设真实感底座，这一点冷启动规划已经明确。

### 6.2 为什么 `sales_associate`（门店店员 / 导购）必须补进首批 7 个岗位

如果不补，`styling_advisor`（穿搭顾问）这套人设会缺岗位底座，导致它虽然名字成立，但真实感和专业度来源不清。

更重要的是：**对服装零售业务，门店导购的朋友圈是出货主战场**——导购人设如果没有对应的岗位知识底座，私域内容生成就会空心。这在 Q3 新增 `PrivateOutletChannel`（私域出口位）之后变得尤其致命。

补上它以后，三套通用 Persona（人设）都各自有明确的岗位知识来源：

- `store_operator` ← 店长 / 仓库主管
- `styling_advisor` ← 门店店员 / 导购
- `product_professional` ← 设计 / 打样 / 商品 / 设计管理

### 6.3 为什么 `FounderProfile`（创始人画像）不进清单编号体系

因为它不是"通用说话身份壳"，而是品牌唯一层。它的存在，是为了服务 `founder_ip`（创始人 IP）这条首批正式内容线，而不是为了和三套通用 Persona 做编号对称。[phase-3-Q1-内容生产首批做什么.md §七.2](../phase-3-Q1-内容生产首批做什么.md#L401-L427) 已明确它是单独对象，Q4 裁决稿 §2.2 已正式选定名称。

---

## 七、本清单对后续产物的影响

这份第二清单一旦冻结，后面 4 份产物的范围就会自然收口：

### 7.1 人设卡片 × N（下一轮补）

需要先给：

- `store_operator`
- `styling_advisor`
- `product_professional`

三套通用 Persona（人设）补字段卡片。字段口径已在 [phase-3-内容生产核心思想落盘方案.md:215-263](../phase-3-内容生产核心思想落盘方案.md#L215-L263) 定义，包含：`role_type` / `life_archetype` / `emotional_spectrum` / `authenticity_anchors` / `topic_scope` / `typical_scenarios`。

`FounderProfile`（创始人画像）的字段卡片也在本轮范围外，字段初稿见 [ITR-026](../../iteration-backlog.md)。

### 7.2 《Persona × ContentType × Platform 兼容矩阵》

按 [Q4 裁决稿 §三](../phase-3-Q4-品牌首批默认启用几套人设.md) 冻结的"一层真源 + 一层派生视图"口径构建：

- **真源层：** `Persona × ContentType` 兼容边（`support/risk/reason`）
- **平台维度：** 承接 Q3 `(:System)-[:SUPPORTS_PLATFORM {tier}]->` 关系，不新建边
- **派生视图：** 以本清单的 1 + 3 + 7 结构作为输入对象集合，由 Skill 层运行时组合计算

### 7.3 《首批岗位知识素材清单》（下一轮补）

需要围绕这 7 个 `RoleProfile`（岗位画像）来列素材准备要求：

- 每个岗位的素材采集方式
- 每个岗位的真实性锚点来源
- 素材质量标准

按冷启动规划，素材以领域专家提供为主。

### 7.4 《参数级填充清单：Q4 部分》（下一轮补）

需要以本清单的 **1 + 3 + 7 = 11 个正式对象**作为参数主索引，列出每个对象还缺哪些字段、哪些素材、哪些兼容关系待填。

---

## 八、本稿结论

本轮《首批 Persona / RoleProfile（人设 / 岗位画像）清单》候选稿，正式收口为：

### 品牌唯一层（1 个）

- `FounderProfile`（创始人画像）— **正式选定**（历史备选名废弃记录归 Q4 裁决稿 §2.2）

### 三套通用 Persona（3 个）

- `store_operator`（门店经营者）
- `styling_advisor`（穿搭顾问）
- `product_professional`（商品专业者）

### 首批 7 个 RoleProfile

- `store_manager`（门店店长）→ `store_operator`
- `warehouse_supervisor`（仓库主管）→ `store_operator`
- `sales_associate`（门店店员 / 导购）→ `styling_advisor`
- `designer`（设计师）→ `product_professional`
- `sample_worker`（样衣工）→ `product_professional`
- `design_director`（设计总监）→ `product_professional`
- `merchandising_director`（商品总监）→ `product_professional`

### 总结

**1 个 `FounderProfile` + 3 个通用 `Persona` + 7 个 `RoleProfile` = 11 个正式对象**

本清单与 [phase-3-Q4-品牌首批默认启用几套人设.md](../phase-3-Q4-品牌首批默认启用几套人设.md) 形成 Q4 冷启动阶段的第一轮正式产物组合，支撑 Phase 3 Step 2-3 的 Entity Type 注册与种子数据导入任务开工。

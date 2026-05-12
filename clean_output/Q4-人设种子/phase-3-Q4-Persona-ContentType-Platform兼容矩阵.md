# Persona × ContentType × Platform 兼容矩阵

> **文档性质：** 兼容矩阵（候选 v0.1）
> **创建日期：** 2026-04-15
> **所属问题：** Q4
> **承接上游：**
> - [phase-3-Q4-品牌首批默认启用几套人设.md](../phase-3-Q4-品牌首批默认启用几套人设.md)（Q4 裁决稿 — §3.1 "一层真源 + 一层派生视图" 口径）
> - [phase-3-Q4-首批Persona-RoleProfile清单.md](phase-3-Q4-首批Persona-RoleProfile清单.md)（首批清单稿 §3.1-3.3 主承接 / 可承接口径）
> - [phase-3-Q4-三套通用Persona首批卡片.md](phase-3-Q4-三套通用Persona首批卡片.md)（三套 Persona 字段壳）
> - [phase-3-Q3-首批平台支持与适配边界.md](../phase-3-Q3-首批平台支持与适配边界.md)（Q3 v1 真源 — `PlatformTone / PrivateOutletChannel / tier` 四档 + [ADR-072](../../adr/ADR-072-platform-support-tier-and-private-outlet-channel.md)）
> - [phase-3-内容生产核心思想落盘方案.md](../phase-3-内容生产核心思想落盘方案.md)（`COMPATIBLE_WITH` 关系边 / `support × risk` 四档）
>
> **状态：** 候选 — 待最终签字冻结
> **说明：** 本稿只负责回答"**谁 × 做什么内容 × 发到哪里**"的兼容性问题；严格承接 Q4 裁决稿 §3.1 "**一层真源 + 一层派生视图**" 冻结口径，**不新建 `ContentType × Platform` 关系边**，不重复裁 Q3 平台清单，不改写 Q3 真源。
>
> **范围纪律：** 本稿恪守 Q3 v1 §2.3 "v1 只建系统级关系、不建品牌级、不建关系扩展属性" 的范围纪律，**不引入新的 schema 变更**，不需要 `[CONTRACT]` 标签，不需要新 ADR。

---

## 零、本文件解决什么问题

前 3 份 Q4 产物已经回答了：

- Q4 冷启动阶段要启用哪几层对象
- 首批有哪些 `Persona`（人设）和 `RoleProfile`（岗位画像）
- 三套通用 `Persona`（人设）各自长什么样

但系统还差一个关键问题没有结构化回答：

> **某一套人设，在某一种内容类型下，发到某一个平台或私域出口位，到底是"现在就能用"、还是"要补配置"、还是"只适合特殊场景"、还是"不建议"。**

这份矩阵就是专门回答这个问题。

用白话说：

- **前三份文档回答"系统里先建谁"**
- **这份矩阵回答"建完以后，谁去发什么，发到哪里，是否合适"**

[phase-3-内容生产核心思想落盘方案.md:823-835](../phase-3-内容生产核心思想落盘方案.md#L823-L835) 已明确，多维支持矩阵不能只停留在单维度 `ContentType`（内容类型）上，而要在关系边上标注 `support`（支持度）与 `risk`（风险）属性；同时，组合判定对象本来就是 `ContentType × Persona × Style × Platform`（内容类型 × 人设 × 风格 × 平台）。

---

## 一、本稿的正式对象与真源分层

本稿承接 4 类正式对象：

- `Persona`（人设）
- `ContentType`（内容类型）
- `PlatformTone`（平台语调）— 公域分发位规范（承接 Q3 v1 真源）
- `PrivateOutletChannel`（私域出口位）— 私域出口位规范（承接 Q3 v1 真源）

### 1.1 真源分层原则（正式冻结）

本稿**严格承接 [Q4 裁决稿 §3.1](../phase-3-Q4-品牌首批默认启用几套人设.md) 的 "一层真源 + 一层派生视图" 冻结口径**：

> **一层真源 + 一层派生视图**

#### 真源层：`Persona × ContentType` 兼容关系

表示"**这套人设讲这种内容合不合适**"，是本 Q4 唯一新建立的关系真源层。直接承接 [phase-3-内容生产核心思想落盘方案.md:796-835](../phase-3-内容生产核心思想落盘方案.md#L796-L835) 已定义的 `COMPATIBLE_WITH` 关系边：

```
(:Persona)-[:COMPATIBLE_WITH {support, risk, reason}]->(:ContentType)
```

**本稿 §四 给出三套通用 Persona × 18 个 ContentType 的 54 条兼容边数据，作为真源层的业务内容。**

#### 平台维度：承接 Q3 真源，不新建关系边

**本稿不在 `ContentType × Platform` 或 `Persona × Platform` 维度上新建关系边。** 平台维度的真源承接 [phase-3-Q3-首批平台支持与适配边界.md §2 / §四](../phase-3-Q3-首批平台支持与适配边界.md#L55-L143) 已建立的系统级关系：

```
(:System)-[:SUPPORTS_PLATFORM {tier: P0_native | P1_light_adapt | P2_cross_post_only | deferred}]->(:PlatformTone)
(:System)-[:SUPPORTS_PLATFORM {tier: ...}]->(:PrivateOutletChannel)
```

#### 派生视图层：`Persona × ContentType × Platform/Channel`

表示"**这套人设讲这种内容，发到这个具体平台或私域出口位，运营最终看到的建议档位**"。

派生视图**不是真源、不写入图谱**，由 `Persona × ContentType` 真源边 + Q3 `SUPPORTS_PLATFORM.tier` 临时组合计算得出。具体组合公式见本稿 §六。

### 1.2 为什么这样分层

#### 工程纪律

[phase-3-Q3-首批平台支持与适配边界.md §2.3](../phase-3-Q3-首批平台支持与适配边界.md#L83-L91) 已明确 Q3 v1 "只建系统级关系、不建品牌级、不建关系扩展属性"。本 Q4 恪守 Q3 v1 的范围纪律：

- **不新建** `ContentType × Platform` 关系边（那是后续 Q 的事）
- **不卷入** 品牌级平台覆盖（Q3 明确推迟）
- **不引入** 新 ADR 或 schema 变更

#### 工程效率

把 `ContentType × Platform` 直接做成真源关系边有 4 个问题：维护成本高（18 × 10 = 180 条边）、容易不一致（两份真源改完派生视图会漂移）、难以增量扩展（新增平台或人设会指数级膨胀）、违反渐进纪律。

#### 业务效率

- 冷启动阶段连第一个品牌的种子数据都还没导入，不需要追求"内容 × 平台"最细粒度真源
- Q3 tier + Q4 `Persona × ContentType` 两个真源组合出来的派生视图，对运营和 IP 运营的日常决策已足够
- 未来真出现"某个内容在某个平台有特殊例外"的业务需求，再升级为真源边也来得及——路径是开着的，不会被本 Q4 锁死

### 1.3 "平台"一词的本稿统称说明

本稿在描述派生视图时会用 "**平台**" 作为统称，同时覆盖两类 Q3 真源对象：

| 类别 | 真源实体（Q3） | 首批承载 |
|---|---|---|
| **公域分发位**（有算法分发）| `PlatformTone` | 小红书 / 抖音 / 视频号 / 快手 / 公众号 / B 站 / 微博 |
| **私域出口位**（无算法分发，靠强关系链）| `PrivateOutletChannel` | 微信朋友圈（P0_native）/ 微信群（占位）/ 微信私信（占位）|

**"平台"是描述性统称**，不是新引入的实体类型，不写入图谱。具体对象仍以 Q3 真源中的 `PlatformTone` / `PrivateOutletChannel` 两个并列实体为准。

---

## 二、矩阵字段口径（正式冻结）

### 2.1 工程字段

本稿沿用真源 [phase-3-内容生产核心思想落盘方案.md:796-835](../phase-3-内容生产核心思想落盘方案.md#L796-L835) 已给出的关系属性：

- `support`（支持度）: `now | enhanced | custom | unsupported`
- `risk`（风险）: `low | medium | high`
- `reason`（原因）: string，可选（当 `support != "now"` 时建议说明原因）

### 2.2 四档 support 业务解释

| `support` | 中文解释 | 运营侧展示档 |
|---|---|---|
| `now` | 现在就支持 | **默认可用** |
| `enhanced` | 补充配置后可支持 | **补充配置后可用** |
| `custom` | 需定制开发 / 品牌级特殊场景 | **品牌级 / 特殊场景** |
| `unsupported` | 不建议 / 无法支持 | **不建议** |

真源 [phase-3-内容生产核心思想落盘方案.md:832-835](../phase-3-内容生产核心思想落盘方案.md#L832-L835) 已把这四档定义与判定规则写清楚，并指出组合支持等级取相关路径中**最高的 support 要求**。

### 2.3 三档 risk 风险解释

| `risk` | 中文解释 |
|---|---|
| `low` | 常规风险，可默认放行 |
| `medium` | 存在表达偏差或风格偏移风险，建议提示 |
| `high` | 品牌风险、真实性风险、平台错位风险高，不应默认放行 |

---

## 三、平台维度承接 Q3 真源

### 3.1 本稿不重复裁 Q3 平台清单

[phase-3-Q3-首批平台支持与适配边界.md](../phase-3-Q3-首批平台支持与适配边界.md) 已经回答了：

- 首批支持哪些公域平台
- 各平台在系统中的 `tier` 支持层级
- 私域出口位的对象清单与边界

因此本稿**不重新枚举平台清单，不修改平台对象名，不重裁平台范围**，具体对象 ID 和支持层级以 [Q3 §四 平台分层最终表](../phase-3-Q3-首批平台支持与适配边界.md#L127-L143) 为准。

### 3.2 本稿引用 Q3 真源的方式

派生视图层（§六）组合时，从 Q3 真源中读取 `tier` 值，按 §六.1 的派生公式计算运营展示档。**本稿不在 Q3 真源之外新建任何 `ContentType × Platform` 关系边**。

### 3.3 为什么必须同时覆盖公域分发位与私域出口位

因为在服装零售实际场景里，`sales_associate`（门店店员 / 导购）挂接 `styling_advisor`（穿搭顾问）以后，它最核心的分发战场之一不是只有公域平台，而是：

- 朋友圈
- 微信群
- 私信触达
- 一对一转发 / 老客回访

如果 Q4 兼容矩阵只覆盖公域平台，就会把导购这条最强转化链路从系统视野里漏掉，导致 Step 3 种子数据准备与真实业务错位。本稿承接 Q3 新增的 `PrivateOutletChannel`（私域出口位）实体，让派生视图在公域、私域两侧都能给出合理展示档。

---

## 四、首批通用 Persona × ContentType 真源矩阵

> **说明：** 本章是 Q4 **唯一真源层**（参见 §1.1）。每条兼容边对应一条 `(:Persona)-[:COMPATIBLE_WITH {support, risk, reason}]->(:ContentType)` 关系。三张表总计 54 条兼容边，是本 Q4 向 Phase 3 Step 3 种子数据导入输出的核心数据。
>
> 三张表的"主承接方向判定"与 [phase-3-Q4-首批Persona-RoleProfile清单.md §3.1-3.3](phase-3-Q4-首批Persona-RoleProfile清单.md#L93-L132) 的 "主承接 / 可承接" 口径完全对齐。

### 4.1 `store_operator`（门店经营者）× 18 个 ContentType

| `ContentType`（内容类型）| `support` | `risk` | `reason`（原因）|
|---|---|---|---|
| `store_daily`（门店日常）| `now` | `low` | 门店经营者是该内容的天然主视角 |
| `training_material`（培训物料）| `now` | `low` | 带队、复盘、执行提醒天然成立 |
| `emotion_expression`（情绪表达）| `enhanced` | `medium` | 需要控制情绪真实性与品牌边界 |
| `behind_the_scenes`（幕后记录）| `now` | `low` | 前后台协同、经营劳动感天然成立 |
| `event_documentary`（事件纪实）| `enhanced` | `low` | 适合从门店经营视角讲事件 |
| `role_work_vlog`（岗位工作 Vlog）| `enhanced` | `medium` | 适合店长工作日常，不适合冒充所有岗位 |
| `personal_vlog`（个人 Vlog）| `enhanced` | `medium` | 需要控制"个人感"与"经营视角"的平衡 |
| `knowledge_sharing`（知识分享）| `enhanced` | `medium` | 更适合经营/带店知识，不宜假装专业工艺知识 |
| `product_review`（产品测评）| `enhanced` | `medium` | 可讲门店视角的判断，但不如前台顾问自然 |
| `outfit_of_the_day`（每日穿搭）| `enhanced` | `medium` | 可用，但不是最优视角 |
| `product_copy_general`（通用产品文案）| `enhanced` | `medium` | 能写经营视角卖点，但不如商品/导购视角自然 |
| `daily_fragment`（日常碎片）| `enhanced` | `low` | 可作为门店/经营碎片存在 |
| `humor_content`（幽默内容）| `enhanced` | `medium` | 可用，但需防门店官方口吻错位 |
| `lifestyle_expression`（生活方式表达）| `custom` | `medium` | 可承接部分主理型内容，但不是首批默认强项 |
| `talent_showcase`（才艺展示）| `custom` | `medium` | 不是该人设首批主力线 |
| `product_journey`（产品历程）| `custom` | `high` | 门店视角不天然适合讲研发决策全链路 |
| `process_trace`（工艺溯源）| `unsupported` | `high` | 专业度与证据链不足 |
| `founder_ip`（创始人 IP）| `unsupported` | `high` | 对象层级不匹配 |

---

### 4.2 `styling_advisor`（穿搭顾问）× 18 个 ContentType

| `ContentType`（内容类型）| `support` | `risk` | `reason`（原因）|
|---|---|---|---|
| `product_review`（产品测评）| `now` | `low` | 最自然的前台接客视角之一 |
| `outfit_of_the_day`（每日穿搭）| `now` | `low` | 天然适配搭配建议与身体体感翻译 |
| `product_copy_general`（通用产品文案）| `enhanced` | `medium` | 可写转化向文案，但需避免客服腔 |
| `knowledge_sharing`（知识分享）| `now` | `low` | 适合讲穿搭、场景、体型、试穿知识 |
| `emotion_expression`（情绪表达）| `enhanced` | `medium` | 一线情绪成立，但需控制"导购鸡汤化" |
| `personal_vlog`（个人 Vlog）| `enhanced` | `low` | 可承接个人导购视角生活流内容 |
| `daily_fragment`（日常碎片）| `enhanced` | `low` | 适合接客与试衣间碎片 |
| `humor_content`（幽默内容）| `enhanced` | `medium` | 可用，但要防"销售段子号"化 |
| `role_work_vlog`（岗位工作 Vlog）| `enhanced` | `low` | 前台岗位工作 Vlog 自然成立 |
| `talent_showcase`（才艺展示）| `enhanced` | `medium` | 适合有明显个人风格的一线导购账号 |
| `lifestyle_expression`（生活方式表达）| `enhanced` | `medium` | 可成立，但更偏个人号而非品牌号 |
| `store_daily`（门店日常）| `enhanced` | `low` | 适合前台接客片段，不适合门店经营主视角 |
| `training_material`（培训物料）| `custom` | `medium` | 可做前台接客训练，但首批不是主线 |
| `behind_the_scenes`（幕后记录）| `custom` | `medium` | 能讲前台幕后，但不是首批默认强项 |
| `event_documentary`（事件纪实）| `custom` | `medium` | 可作为参与者视角，不是主叙事位 |
| `product_journey`（产品历程）| `unsupported` | `high` | 角色专业度不足 |
| `process_trace`（工艺溯源）| `unsupported` | `high` | 角色专业度不足 |
| `founder_ip`（创始人 IP）| `unsupported` | `high` | 对象层级不匹配 |

---

### 4.3 `product_professional`（商品专业者）× 18 个 ContentType

| `ContentType`（内容类型）| `support` | `risk` | `reason`（原因）|
|---|---|---|---|
| `role_work_vlog`（岗位工作 Vlog）| `now` | `low` | 设计 / 打样 / 商品岗位天然适配 |
| `product_journey`（产品历程）| `now` | `low` | 研发—改版—上市叙事天然适配 |
| `process_trace`（工艺溯源）| `now` | `low` | 面料 / 工艺 / 打样 / 品控类内容天然适配 |
| `knowledge_sharing`（知识分享）| `now` | `low` | 专业知识输出是强项 |
| `product_review`（产品测评）| `enhanced` | `medium` | 可做专业测评，但前台亲和感稍弱 |
| `product_copy_general`（通用产品文案）| `enhanced` | `low` | 权威度强，但需补转化表达 |
| `behind_the_scenes`（幕后记录）| `enhanced` | `low` | 可讲专业劳动与流程幕后 |
| `training_material`（培训物料）| `enhanced` | `low` | 适合商品 / 工艺 / 上新训练 |
| `event_documentary`（事件纪实）| `enhanced` | `medium` | 适合作为专业参与者视角 |
| `emotion_expression`（情绪表达）| `enhanced` | `medium` | 可成立，但需防"专业人设突然抒情过重" |
| `daily_fragment`（日常碎片）| `enhanced` | `medium` | 可讲专业工作碎片 |
| `store_daily`（门店日常）| `custom` | `medium` | 不是天然主视角 |
| `outfit_of_the_day`（每日穿搭）| `custom` | `medium` | 可从专业搭配逻辑切入，但不是首批主力线 |
| `personal_vlog`（个人 Vlog）| `custom` | `medium` | 容易变成专业流水账 |
| `lifestyle_expression`（生活方式表达）| `custom` | `medium` | 可做"专业审美生活化"，但首批不是默认强项 |
| `talent_showcase`（才艺展示）| `custom` | `medium` | 只有在专业技艺本身可视化时才成立 |
| `humor_content`（幽默内容）| `custom` | `high` | 风格错位风险高 |
| `founder_ip`（创始人 IP）| `unsupported` | `high` | 对象层级不匹配 |

---

## 五、平台维度承接规则（派生视图的组合输入）

> **重要声明：** 本章**不声明任何新的真源关系边**。平台维度的真源完全由 Q3 v1 的 `(:System)-[:SUPPORTS_PLATFORM {tier}]->(:PlatformTone / :PrivateOutletChannel)` 承载。本章只规定**派生视图组合时如何引用 Q3 真源**。

### 5.1 承接对象

派生视图组合时，从以下两类 Q3 真源对象读取 `tier` 值：

#### A. 公域分发位（`PlatformTone`）

承接 [Q3 §四 平台分层最终表](../phase-3-Q3-首批平台支持与适配边界.md#L127-L143) 中所有 `承载实体 = PlatformTone` 的平台对象：

- 小红书（`xiaohongshu` / `tier = P0_native`）
- 抖音（`douyin` / `tier = P0_native`）
- 视频号（`wechat_channels` / `tier = P0_native`）
- 快手（`kuaishou` / `tier = P1_light_adapt`）
- 微信公众号（`wechat_official_account` / `tier = P1_light_adapt`）
- B 站（`bilibili` / `tier = P1_light_adapt`）
- 微博（`weibo` / `tier = P2_cross_post_only`）

#### B. 私域出口位（`PrivateOutletChannel`）

承接 [Q3 §四](../phase-3-Q3-首批平台支持与适配边界.md#L127-L143) 中所有 `承载实体 = PrivateOutletChannel` 的出口位对象：

- 微信朋友圈（`wechat_moments` / `tier = P0_native`）
- 微信群（`wechat_group` / `tier = deferred`，占位）
- 微信私信（`wechat_dm` / `tier = deferred`，占位）

### 5.2 承接原则

- **本稿不重命名、不重分级、不重写 tier**
- **本稿不新建** `ContentType × PlatformTone` / `ContentType × PrivateOutletChannel` / `Persona × Platform` 任何方向的关系边
- 具体对象 ID、启用边界、清单明细以 [Q3 §四](../phase-3-Q3-首批平台支持与适配边界.md#L127-L143) 为准

### 5.3 冷启动阶段的最小承接原则

本稿冻结 1 条最重要的业务规则：

> **凡首批与导购 / 门店经营强相关的内容线，其派生视图必须同时覆盖公域平台与私域出口位，不得只做公域。**

这是为了避免 Q4 矩阵在服装零售场景里出现"导购人设已建好，但导购朋友圈没有矩阵位置"的错位——对应到本稿 §六 的派生公式，意味着 `styling_advisor × outfit_of_the_day × 微信朋友圈` 这种组合必须能在派生视图中被正确计算并展示。

---

## 六、Persona × ContentType × Platform/Channel 派生视图规则

> **说明：** 本章定义的派生视图**不是真源，不写入图谱**，而是运营 / IP 运营 / Prompt 配置 / 能力发现页面实际看到的结果表。

### 6.1 派生公式（冻结建议）

对于任意一个请求组合 `Persona × ContentType × Platform/Channel`，系统派生时：

1. **先查真源层** `(:Persona)-[:COMPATIBLE_WITH {support, risk, reason}]->(:ContentType)` 的 `support / risk / reason` 值
2. **再查 Q3 真源** `(:System)-[:SUPPORTS_PLATFORM {tier}]->(:PlatformTone / :PrivateOutletChannel)` 的 `tier` 值
3. **按组合规则表计算运营展示档**（见 §6.2）
4. **最终展示档的风险位**继承真源层的 `risk`

### 6.2 组合规则（直接对齐 [Q4 裁决稿 §3.1](../phase-3-Q4-品牌首批默认启用几套人设.md) 已冻结表）

| 真源层 `Persona × ContentType` | Q3 平台 `tier` | 派生视图展示档 |
|---|---|---|
| `support = now` | `tier = P0_native` | **默认可用** |
| `support = now` | `tier = P1_light_adapt` | **补充配置后可用** |
| `support = enhanced` | `tier = P0_native` | **补充配置后可用** |
| `support = enhanced` | `tier = P1_light_adapt` | **补充配置后可用** |
| `support = custom` | 任意 `tier` | **品牌级 / 特殊场景** |
| `support = unsupported` | 任意 `tier` | **不建议** |
| 任意 `support` | `tier = P2_cross_post_only` | **补充配置后可用**（转发提示）|
| 任意 `support` | `tier = deferred` | **不建议**（系统未支持）|

### 6.3 派生示例

**示例 1：默认可用组合**

- `styling_advisor × outfit_of_the_day` = `support: now, risk: low`（本稿 §4.2）
- 小红书（`xiaohongshu`）= `tier: P0_native`（Q3 §四）
- **派生结果**：`support=now + tier=P0_native → 默认可用`，风险继承为 `low`

**示例 2：风险来自人设 × 内容组合，平台无法挽救**

- `product_professional × humor_content` = `support: custom, risk: high`（本稿 §4.3）
- 抖音 = `tier: P0_native`
- **派生结果**：即使平台 `tier=P0_native`，因为 `support=custom` → **品牌级 / 特殊场景**；风险继承为 `high`
- **业务解释**：问题不在平台，而在"专业人设 × 幽默表达"的角色错位风险

**示例 3：私域出口位命中服装零售核心转化链**

- `styling_advisor × product_review` = `support: now, risk: low`（本稿 §4.2）
- 微信朋友圈（`wechat_moments`）= `tier: P0_native`（Q3 §四）
- **派生结果**：`default 可用`——导购在朋友圈发产品测评是服装零售最强转化链路之一，矩阵必须命中这个组合

**示例 4：系统未支持平台一律兜底为"不建议"**

- `store_operator × store_daily` = `support: now, risk: low`（本稿 §4.1）
- 微信群（`wechat_group`）= `tier: deferred`（Q3 §四，占位未启用）
- **派生结果**：即使真源层完全就绪，因 `tier=deferred` → **不建议**
- **业务解释**：等 Q3 后续轮次把微信群的 tier 升级后自动解锁，无需改动 Q4

---

## 七、冷启动首批派生视图示例（示范，不替代真源）

> **说明：** 下面只给少量示范，帮助运营理解矩阵会怎么被看见。真正的完整派生表由系统运行时从 §四 的真源层 + Q3 真源临时组合生成，**不写入图谱**。

| `Persona`（人设）| `ContentType`（内容类型）| 平台/出口位 | 展示档 | 说明 |
|---|---|---|---|---|
| `styling_advisor` | `outfit_of_the_day` | 小红书（`P0_native`）| **默认可用** | 前台搭配建议天然适配 |
| `styling_advisor` | `product_review` | 微信朋友圈（`P0_native`）| **默认可用** | 导购测评在朋友圈私域场景高适配——服装零售核心转化链 |
| `store_operator` | `store_daily` | 微信朋友圈（`P0_native`）| **默认可用** | 门店经营视角非常适合老客维系 |
| `product_professional` | `process_trace` | 抖音（`P0_native`）| **默认可用** | 专业工艺内容与强平台支持叠加 |
| `product_professional` | `humor_content` | 任一平台 | **品牌级 / 特殊场景** | 真源层 `support=custom`，风险来自人设与内容组合，非平台问题 |
| `store_operator` | `process_trace` | 任一平台 | **不建议** | 真源层 `support=unsupported`，专业度与证据链不足 |
| `styling_advisor` | `outfit_of_the_day` | 视频号（`P0_native`）| **默认可用** | 与小红书同档 |
| `styling_advisor` | `product_copy_general` | B 站（`P1_light_adapt`）| **补充配置后可用** | 平台要求轻改适配，真源层 `support=enhanced` 叠加 |
| `store_operator` | `store_daily` | 微博（`P2_cross_post_only`）| **补充配置后可用**（转发提示）| 平台仅支持转发，需提示 |
| `styling_advisor` | `product_review` | 微信群（`deferred`）| **不建议**（系统未支持）| Q3 占位未启用，待后续升级 |

---

## 八、能力发现与后续实现如何消费这张矩阵

[phase-3-内容生产核心思想落盘方案.md §8](../phase-3-内容生产核心思想落盘方案.md) 已给出能力发现机制：系统会从 `ContentType`（内容类型）出发，联带取兼容的 `Persona`（人设）和平台对象，最终向用户呈现"当前可用的内容生产能力菜单"。

因此，这份矩阵冻结以后，可以直接服务 4 类下游：

1. **能力发现菜单**
   用户问"我现在能做什么内容"，系统可按当前 org 上下文自动展示可用组合。运行时从 §四 真源 + Q3 真源临时组合生成。

2. **Prompt 组装前的前置判断**
   若组合派生档为 `enhanced / custom / unsupported`，先给提示，不直接盲生成。`risk` 值同步作为生成前风险提示的依据。

3. **运营手动规划**
   运营可按"人设 × 内容 × 平台 / 出口位"查可用位和高风险位，用于首批默认启用包检查和 IP 运营日常决策。

4. **反馈学习闭环**
   后续发布效果回传时，可把真实高表现组合写入反馈学习链路。[phase-3-内容生产核心思想落盘方案.md](../phase-3-内容生产核心思想落盘方案.md) 已考虑"题材 + 角色 + 风格 + 平台组合真的有效"这一反馈结构。

---

## 九、本稿结论（冻结建议）

本轮《Persona × ContentType × Platform 兼容矩阵》候选稿，正式冻结以下 4 条口径：

### 9.1 真源分层

**严格承接 [Q4 裁决稿 §3.1](../phase-3-Q4-品牌首批默认启用几套人设.md) 的冻结口径：**

> **一层真源 + 一层派生视图**

- **真源层**：`(:Persona)-[:COMPATIBLE_WITH {support, risk, reason}]->(:ContentType)`，本稿 §四 给出三张 Persona × 18 个 ContentType 的 54 条兼容边数据
- **平台维度**：承接 Q3 `(:System)-[:SUPPORTS_PLATFORM {tier}]->(:PlatformTone / :PrivateOutletChannel)`，**不新建 `ContentType × Platform` 或 `Persona × Platform` 关系边**
- **派生视图层**：`Persona × ContentType × Platform/Channel`，由真源层 + Q3 真源临时组合计算，**不写入图谱**

### 9.2 字段口径

统一使用：

- `support = now | enhanced | custom | unsupported`（与 [ADR-069](../../adr/ADR-069-knowledge-id-naming-convention.md) 同一套枚举）
- `risk = low | medium | high`
- `reason = string`（当 `support != "now"` 时建议说明原因）

### 9.3 平台维度

- 平台维度统一覆盖两类 Q3 真源对象：`PlatformTone`（公域分发位）+ `PrivateOutletChannel`（私域出口位）
- 承接 [Q3 §四](../phase-3-Q3-首批平台支持与适配边界.md#L127-L143) 的平台分层最终表
- 本稿**不重裁** Q3 平台清单，**不改写** Q3 `tier` 枚举，**不新建** 任何 `ContentType × Platform` 关系边
- "平台"一词在本稿内是描述性统称，不引入任何新实体类型

### 9.4 冷启动矩阵使用原则

本轮冻结冷启动阶段的 54 条 `Persona × ContentType` 真源兼容边（3 Persona × 18 ContentType）+ 派生视图组合公式，不做超重三维真源表，不做重复 ADR，不做与 Q3 重叠的再裁决。

**下游可开工：**

- Phase 3 Step 2 Entity Type 注册（54 条兼容边入图谱）
- Phase 3 Step 3 种子数据导入
- Skill 层能力发现机制接入（从 ContentType 出发联带查兼容 Persona 与 Q3 平台）
- Prompt 组装前置判断（按派生档位给提示）

### 范围约束（本稿明确不做）

- **不新建** `ContentType × Platform` / `Persona × Platform` 任何方向的关系边
- **不引入** `DistributionTarget` 或类似的新实体类型
- **不卷入** Q3 v1 §2.3 明确推迟到后续 Q 的事（品牌级覆盖 / 关系扩展属性 / tier 历史）
- **不引入** 新 ADR / 不挂 `[CONTRACT]` 标签 / 不触发 schema 变更

### 本轮 Q4 产物进度

- ✅ 产物 1：[phase-3-Q4-品牌首批默认启用几套人设.md](../phase-3-Q4-品牌首批默认启用几套人设.md)
- ✅ 产物 2：[phase-3-Q4-首批Persona-RoleProfile清单.md](phase-3-Q4-首批Persona-RoleProfile清单.md)
- ✅ 产物 3：[phase-3-Q4-三套通用Persona首批卡片.md](phase-3-Q4-三套通用Persona首批卡片.md)
- ✅ 产物 4：本稿
- ⏳ 产物 5：[phase-3-Q4-首批岗位知识素材清单.md](phase-3-Q4-首批岗位知识素材清单.md)（同批落盘）
- ⏳ 产物 6：《参数级填充清单：Q4 部分》

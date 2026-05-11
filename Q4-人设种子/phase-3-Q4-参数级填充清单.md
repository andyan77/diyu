# 参数级填充清单：Q4 部分

> **文档性质：** 实施清单（候选 v0.1）
> **创建日期：** 2026-04-15
> **所属问题：** Q4
> **承接上游：**
> - [phase-3-Q4-品牌首批默认启用几套人设.md](../phase-3-Q4-品牌首批默认启用几套人设.md)（Q4 裁决稿，§3.1 已冻结"一层真源 + 一层派生视图"口径）
> - [phase-3-Q4-首批Persona-RoleProfile清单.md](phase-3-Q4-首批Persona-RoleProfile清单.md)（首批 1+3+7 对象清单）
> - [phase-3-Q4-三套通用Persona首批卡片.md](phase-3-Q4-三套通用Persona首批卡片.md)（三套 Persona 字段壳）
> - [phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md](phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md)（54 条兼容边 + 派生视图组合公式）
> - [phase-3-Q4-首批岗位知识素材清单.md](phase-3-Q4-首批岗位知识素材清单.md)（7 个 RoleProfile 素材采集清单）
> - [phase-3-Q3-首批平台支持与适配边界.md](../phase-3-Q3-首批平台支持与适配边界.md)（Q3 v1 真源 — `PlatformTone / PrivateOutletChannel / tier`）
>
> **状态：** 候选 — 待最终签字冻结
> **用途：** 把 Q4 已冻结 / 候选 / 待补的参数，统一整理成技术、知识工程、内容运营可直接接力的执行清单。
> **说明：** 本稿不是新的裁决稿，不重复回答"该怎么定"；本稿只回答"**已经定了什么、还差什么、下一步谁填什么**"。
> **范围纪律：** 本稿与 [Q4 裁决稿 §3.1](../phase-3-Q4-品牌首批默认启用几套人设.md#L184-L269) 的"**一层真源 + 一层派生视图**"口径完全一致——Q4 唯一新建立的关系真源是 `(:Persona)-[:COMPATIBLE_WITH {support, risk, reason}]->(:ContentType)`，平台维度承接 Q3 已建立的 `(:System)-[:SUPPORTS_PLATFORM {tier}]->(:PlatformTone / :PrivateOutletChannel)`，**不在 Q4 新建 `ContentType × Platform` 关系边**。

---

## 零、本文件解决什么问题

前 5 份 Q4 产物已经把方向和对象基本收口了，但如果没有一张参数级填充清单，后续仍然会卡在 3 个地方：

1. **技术团队不知道哪些字段已经可以建 schema，哪些还不能硬编码**
2. **知识工程不知道哪些素材已经足够，哪些岗位还要补证据**
3. **内容运营不知道哪些矩阵档位是已冻结，哪些只是候选展示语义**

因此，这份文档要做的不是再提新想法，而是把 Q4 当前所有参数拆成三类：

- **已冻结（Frozen）** — 本轮 Q4 已正式冻结，下游可直接消费
- **候选待填（Candidate）** — 已给出最小可用值，等品牌素材或下一份产物补
- **待补证 / 待后续 Q 承接（Pending）** — 等 Q19/Q20/Q21/Q22 或 Q3 真源回填

用白话说：

- **前面 5 份产物回答"先建什么、长什么样、怎么挂、怎么发"**
- **这份清单回答"现在到底定到了哪一步，下一步该谁动"**

---

## 一、Q4 参数分层总览

Q4 当前涉及 4 层参数：

| 参数层 | 作用 | 主要对象 |
|---|---|---|
| **对象层** | 系统里先建哪些正式对象 | `FounderProfile`（创始人画像）/ `Persona`（人设）/ `RoleProfile`（岗位画像）|
| **字段层** | 这些对象有哪些字段、字段当前填到什么程度 | `role_type`（岗位类型）/ `life_archetype`（生活原型）/ `emotional_spectrum`（情绪光谱）/ `authenticity_anchors`（真实性锚点）/ `topic_scope`（话题边界）/ `typical_scenarios`（典型场景）|
| **关系层** | 对象之间怎么挂接 | `RoleProfile → Persona`（岗位画像挂接人设）/ `Persona × ContentType`（人设 × 内容类型，本 Q4 唯一新建关系真源）|
| **派生层** | 内容最终发到哪里以及怎么看是否合适 | `Persona × ContentType × Platform/Channel` 派生视图（不写入图谱，由本 Q4 的真源边 + Q3 真源临时组合）|

这 4 层的设计基础，均来自可见真源：

- `Persona`（人设）扩展字段已被 [phase-3-内容生产核心思想落盘方案.md:215-263](../phase-3-内容生产核心思想落盘方案.md#L215-L263) 正式定义
- `FounderProfile`（创始人画像）已被 [Q1 §7.2](../phase-3-Q1-内容生产首批做什么.md#L401-L427) 作为新增依赖对象提出，本 Q4 §2.2 正式选定为命名（[ITR-026](../../iteration-backlog.md) 待注册）
- `COMPATIBLE_WITH` 关系边的 `support / risk / reason` 属性已在 [phase-3-内容生产核心思想落盘方案.md:796-835](../phase-3-内容生产核心思想落盘方案.md#L796-L835) 定义
- 平台维度承接 [Q3 v1 §四 平台分层最终表](../phase-3-Q3-首批平台支持与适配边界.md#L127-L143)，**Q4 不新建任何 `ContentType × Platform` 或 `Persona × Platform` 关系边**

---

## 二、对象层参数清单

### 2.1 品牌唯一层对象

| 参数名 | 当前值 | 状态 | 备注 |
|---|---|---|---|
| `FounderProfile`（创始人画像）是否纳入 Q4 冷启动结构 | 纳入 | **已冻结** | 品牌唯一层，和通用 `Persona` 分层处理（[Q4 裁决稿 §2.1](../phase-3-Q4-品牌首批默认启用几套人设.md)）|
| `FounderProfile` 是否进入通用 `persona_id` 体系 | 否 | **已冻结** | 不新造 `founder_storyteller` 之类的通用 ID |
| `FounderProfile` 是否每品牌强制启用 | 否 | **已冻结** | 每品牌 0/1（柔性使用，[Q1 §柔性使用](../phase-3-Q1-内容生产首批做什么.md#L245-L249)）|
| `FounderProfile` 命名冻结 | `FounderProfile` | **已冻结** | 本 Q4 §2.2 正式选定（历史备选名废弃记录归 Q4 裁决稿原文）|
| `FounderProfile` Entity Type 注册状态 | 待注册 | **待补证** | 见 [ITR-026](../../iteration-backlog.md)，归属 TASK-K3-1 / TASK-K3-6 |

### 2.2 通用 Persona 对象

| 参数名 | 当前值 | 状态 | 备注 |
|---|---|---|---|
| 通用 `Persona`（人设）数量 | 3 套 | **已冻结** | 与品牌唯一层分开计数 |
| `persona_id` #1 | `store_operator`（门店经营者）| **已冻结** | 通用经营与后场协同主视角 |
| `persona_id` #2 | `styling_advisor`（穿搭顾问）| **已冻结** | 前台接客与穿搭建议主视角 |
| `persona_id` #3 | `product_professional`（商品专业者）| **已冻结** | 设计、工艺、商品判断主视角 |
| 通用 Persona 命名规范 | 英文 `snake_case` + 中文 `display_name` | **已冻结** | 与现有 `Persona.role_type` 注释枚举模式一致 |

### 2.3 RoleProfile 对象

| 参数名 | 当前值 | 状态 | 备注 |
|---|---|---|---|
| 首批 `RoleProfile`（岗位画像）数量 | 7 个 | **已冻结** | 首批岗位知识底座 |
| `store_manager`（门店店长）| 已纳入 | **已冻结** | 挂接 `store_operator` |
| `warehouse_supervisor`（仓库主管）| 已纳入 | **已冻结** | 挂接 `store_operator` |
| `sales_associate`（门店店员 / 导购）| 已纳入 | **已冻结** | 挂接 `styling_advisor`，本 Q4 补入第 7 个 |
| `designer`（设计师）| 已纳入 | **已冻结** | 挂接 `product_professional` |
| `sample_worker`（样衣工）| 已纳入 | **已冻结** | 挂接 `product_professional` |
| `design_director`（设计总监）| 已纳入 | **已冻结** | 挂接 `product_professional` |
| `merchandising_director`（商品总监）| 已纳入 | **已冻结** | 挂接 `product_professional` |

---

## 三、字段层参数清单

> **说明：** `Persona`（人设）的正式字段壳已由 [phase-3-内容生产核心思想落盘方案.md:215-263](../phase-3-内容生产核心思想落盘方案.md#L215-L263) 定义：`role_type`（岗位类型）/ `life_archetype`（生活原型）/ `emotional_spectrum`（情绪光谱）/ `authenticity_anchors`（真实性锚点）/ `topic_scope`（话题边界）/ `typical_scenarios`（典型场景）。本 §三 各表的字段值参考 [phase-3-Q4-三套通用Persona首批卡片.md](phase-3-Q4-三套通用Persona首批卡片.md) §2。

### 3.1 `store_operator`（门店经营者）

| 字段名 | 当前状态 | 当前值级别 | 下一步动作 |
|---|---|---|---|
| `role_type`（岗位类型）| 候选待填 | 不硬填单一岗位 | 由挂接 `store_manager` / `warehouse_supervisor` 共同支撑；schema 单值/多挂一语义待裁决 |
| `life_archetype`（生活原型）| 候选待填 | 已给候选池（`家庭负重者` / `职场精英`）| 真源 schema 是 string 单值，品牌启用时从池中选一个 |
| `emotional_spectrum`（情绪光谱）| 候选待填 | 已给最小候选集（3 条）| 后续 Q21 细化强度与频率最终冻结 |
| `authenticity_anchors`（真实性锚点）| 首批可用 | 已给最小集（4 条）| 需用岗位素材清单（产物 5）补实证句到 5+ 条 |
| `topic_scope`（话题边界）| 首批可用 | 已给候选边界（allowed / forbidden / perspective_focus 三子项齐全）| 后续结合品牌边界再收紧 |
| `typical_scenarios`（典型场景）| 首批可用 | 已给最小集（5 条）| 后续结合门店真实场景扩容 |

### 3.2 `styling_advisor`（穿搭顾问）

| 字段名 | 当前状态 | 当前值级别 | 下一步动作 |
|---|---|---|---|
| `role_type`（岗位类型）| 首批可用 | 可直接写 `门店店员 / 导购` | 与 `sales_associate`（首批 7 岗之一）保持一致 |
| `life_archetype`（生活原型）| 候选待填 | 已给候选池（`社交达人` / `初入职场小白`）| 后续看品牌是否要保留更强"社交型"或"新人型"分支 |
| `emotional_spectrum`（情绪光谱）| 候选待填 | 已给最小候选集（3 条）| 后续 Q21 细化 |
| `authenticity_anchors`（真实性锚点）| 首批可用 | 已给最小集（4 条）| 需用导购真实案例（产物 5 §3.3）补强 |
| `topic_scope`（话题边界）| 首批可用 | 已给候选边界 | 后续结合私域出口位（`PrivateOutletChannel`）细化 |
| `typical_scenarios`（典型场景）| 首批可用 | 已给最小集（5 条）| 可与试衣间 / 朋友圈 / 私信场景继续联动补全 |

### 3.3 `product_professional`（商品专业者）

| 字段名 | 当前状态 | 当前值级别 | 下一步动作 |
|---|---|---|---|
| `role_type`（岗位类型）| 候选待填 | 不硬填单一岗位 | 由设计 / 样衣 / 商品 / 设计管理 4 个挂接岗位共同支撑；同样面临单值/多挂一 schema 语义待裁决 |
| `life_archetype`（生活原型）| 候选待填 | 已给候选池（`专业匠人` / `职场精英`）| 后续可细分为匠人型 / 决策型 |
| `emotional_spectrum`（情绪光谱）| 候选待填 | 已给最小候选集（3 条）| 后续 Q21 细化 |
| `authenticity_anchors`（真实性锚点）| 首批可用 | 已给最小集（4 条）| 需用打样 / 改版 / 上新复盘（产物 5 §3.4-3.7）补强 |
| `topic_scope`（话题边界）| 首批可用 | 已给候选边界 | 后续结合品牌敏感边界再收口 |
| `typical_scenarios`（典型场景）| 首批可用 | 已给最小集（6 条）| 后续结合企业事件（`EnterpriseEvent`）继续扩展 |

### 3.4 `FounderProfile`（创始人画像）字段

| 字段名 | 当前状态 | 来源 | 下一步动作 |
|---|---|---|---|
| `founder_name` / `value_system` / `worldview` / `brand_philosophy` / `lifestyle_manifesto` / `aesthetic_preferences` / `inspiration_sources` / `origin_story` / `signature_phrases` | 字段壳已设计 | [ITR-026 字段初稿](../../iteration-backlog.md) | 走 Phase 3 实施时 schema 注册 + 品牌素材回填 |
| 数量约束 | 每品牌 0/1 | [Q1 §7.2 / §柔性使用](../phase-3-Q1-内容生产首批做什么.md#L245-L249) | 已冻结 |
| 写入权限 | `knowledge.manage` + `role=owner` + `org_tier=brand_hq` | [ITR-026](../../iteration-backlog.md) | 已冻结 |

---

## 四、关系层参数清单

### 4.1 `RoleProfile → Persona`（岗位画像挂接人设）

这部分已经在 [phase-3-Q4-首批Persona-RoleProfile清单.md §五](phase-3-Q4-首批Persona-RoleProfile清单.md) 中冻结，本稿只做实施收口。

| 关系参数 | 当前值 | 状态 |
|---|---|---|
| `store_manager → store_operator` | 已确定 | **已冻结** |
| `warehouse_supervisor → store_operator` | 已确定 | **已冻结** |
| `sales_associate → styling_advisor` | 已确定 | **已冻结** |
| `designer → product_professional` | 已确定 | **已冻结** |
| `sample_worker → product_professional` | 已确定 | **已冻结** |
| `design_director → product_professional` | 已确定 | **已冻结** |
| `merchandising_director → product_professional` | 已确定 | **已冻结** |

### 4.2 `Persona × ContentType`（人设 × 内容类型）— Q4 唯一新建关系真源

本部分与 [phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md §四](phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md) 保持完全一致。

| 参数项 | 当前状态 | 说明 |
|---|---|---|
| 关系定义 | `(:Persona)-[:COMPATIBLE_WITH {support, risk, reason}]->(:ContentType)` | **已冻结**；承接 [phase-3-内容生产核心思想落盘方案.md:796-835](../phase-3-内容生产核心思想落盘方案.md#L796-L835) |
| 三套通用 Persona × 18 个 ContentType 的兼容边数据 | 54 条兼容边 | **已冻结**（见兼容矩阵稿 §4.1-4.3）|
| 是否把这张表作为唯一真源 | 是（**Q4 唯一新建关系真源**）| **已冻结** |
| 真源分层口径 | **一层真源 + 一层派生视图** | **已冻结**；严格对齐 [Q4 裁决稿 §3.1](../phase-3-Q4-品牌首批默认启用几套人设.md#L184-L269)，不新建 `ContentType × Platform` 关系边 |
| 是否允许后续升级为更细粒度真源 | 是 | 路径保留，但冷启动不做重表 |

### 4.3 平台维度关系（不在 Q4 新建）

| 参数项 | 当前状态 | 说明 |
|---|---|---|
| `(:System)-[:SUPPORTS_PLATFORM {tier}]->(:PlatformTone)` | 由 Q3 v1 建立 | Q4 **承接**，不重建 |
| `(:System)-[:SUPPORTS_PLATFORM {tier}]->(:PrivateOutletChannel)` | 由 Q3 v1 建立 | Q4 **承接**，不重建 |
| `ContentType × Platform` 关系边 | **不存在** | Q4 **明确不新建**，避免 schema 变更 |
| `Persona × Platform` 关系边 | **不存在** | Q4 **明确不新建**，避免 schema 变更 |

---

## 五、派生层参数清单（不写入图谱）

> **说明：** 本节口径与 [phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md §六](phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md) 完全一致。派生视图**不是真源、不写入图谱**，由真源层 + Q3 真源临时组合计算得出。

### 5.1 派生视图轴

| 参数项 | 当前值 | 状态 | 备注 |
|---|---|---|---|
| 派生视图三个轴 | `Persona × ContentType × Platform/Channel` | **已冻结** | 三维派生，不三维真源 |
| 是否覆盖公域分发位 | 是 | **已冻结** | 承接 Q3 `PlatformTone` 实体（小红书 / 抖音 / 视频号 / 快手 / 公众号 / B 站 / 微博）|
| 是否覆盖私域出口位 | 是 | **已冻结** | 承接 Q3 `PrivateOutletChannel` 实体（朋友圈 / 微信群 / 微信私信）|
| "平台"一词的本稿用法 | 描述性统称 | **已冻结** | **不引入** `DistributionTarget` 之类的新实体类型，"平台"只在叙述层统称 `PlatformTone + PrivateOutletChannel` 两类 Q3 真源对象 |
| 公域平台清单是否在 Q4 重裁 | 否 | **已冻结** | 以 [Q3 §四](../phase-3-Q3-首批平台支持与适配边界.md#L127-L143) 为准 |
| 私域出口位清单是否在 Q4 重裁 | 否 | **已冻结** | 以 Q3 §四 为准 |

### 5.2 派生公式（已冻结）

派生视图组合时，按 [兼容矩阵稿 §6.2](phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md) 的组合规则表执行：

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

### 5.3 运营展示档（已冻结）

| `support` 来源 | 对外展示 |
|---|---|
| 真源层 `now` × 平台 `P0_native` | **默认可用** |
| 真源层 `enhanced` 或平台 `P1_light_adapt` | **补充配置后可用** |
| 真源层 `custom` | **品牌级 / 特殊场景** |
| 真源层 `unsupported` 或平台 `deferred` | **不建议** |

### 5.4 强规则（冷启动唯一硬约束）

| 规则 | 状态 |
|---|---|
| **凡首批与导购 / 门店经营强相关的内容线，其派生视图必须同时覆盖公域分发位与私域出口位，不得只做公域** | **已冻结** |

---

## 六、素材与字段的回填关系清单

> **说明：** 这一节专门把 [phase-3-Q4-首批岗位知识素材清单.md](phase-3-Q4-首批岗位知识素材清单.md) 和本稿打通，避免"素材收了但不知道填到哪"。

### 6.1 岗位素材 → Persona 字段

| 素材类型（产物 5 §2.6）| 优先回填字段 |
|---|---|
| A. 岗位日常动作清单 | `typical_scenarios`（典型场景）/ `topic_scope.perspective_focus`（视角焦点）|
| B. 岗位判断句 / 经验句 | `authenticity_anchors`（真实性锚点）/ `topic_scope.allowed_topics`（可谈话题）|
| C. 高频问题与失败案例 | `authenticity_anchors`（真实性锚点）/ `emotional_spectrum`（情绪光谱）|
| D. 典型场景与时间节点 | `typical_scenarios`（典型场景）|
| E. 特有物件 / 空间 / 证物 | `authenticity_anchors`（真实性锚点）/ `topic_scope.perspective_focus`（视角焦点）|
| F. 对话碎片 / 原话 | `authenticity_anchors`（真实性锚点）/ 后续口吻样例库 |
| G. 不能说什么 / 越界内容 | `topic_scope.forbidden_topics`（禁谈话题）|

### 6.2 岗位素材 → 兼容矩阵真源边

| 素材类型 | 优先影响的兼容矩阵参数 |
|---|---|
| 一线转化案例 | `Persona × ContentType` 的 `support` / `risk` 调档证据 |
| 私域发圈 / 私信案例 | 派生视图层的 `styling_advisor × * × PrivateOutletChannel` 组合校验 |
| 失败案例 | `risk` 上调 / `reason` 增补 |
| 高表现案例 | `support` 从 `enhanced` 升级到 `now` 的证据来源 |

### 6.3 岗位素材 → 后续 Q

| 素材类型 | 后续承接问题 |
|---|---|
| 情绪波动原话 / 真实情绪场景 | Q21 `emotional_spectrum`（情绪光谱）细化 |
| 品牌边界冲突案例 | Q22 `authenticity_policy`（真实性策略）/ Q5-Q6 审核边界 |
| 多角色接力事件 | Q19 `EnterpriseEvent`（企业事件）/ Q20 `NarrativeArc`（叙事弧）|

---

## 七、责任划分与接力清单

### 7.1 内容运营侧

负责：

- 确认三套通用 `Persona`（人设）的业务语义是否稳定
- 审核 [phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md §四](phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md) 的 54 条兼容边是否符合内容运营直觉
- 审核私域出口位（`PrivateOutletChannel`）在导购 / 店长相关内容线中的必要性
- 审核 IP 运营视角下的"默认可用 / 补充配置后可用 / 品牌级 / 不建议" 4 档展示档是否对运营友好

### 7.2 知识工程侧

负责：

- 按 [phase-3-Q4-首批岗位知识素材清单.md §三](phase-3-Q4-首批岗位知识素材清单.md) 给出的 7 个 `RoleProfile` 去拉素材
- 素材结构化记录（按产物 5 §五的统一采集模板）
- 标注每条素材可支撑哪些字段（参见本稿 §6.1）
- 形成最小知识包，作为 Phase 3 Step 3 种子数据导入的输入

### 7.3 技术实现侧

负责：

- Schema 层落 `Persona` 扩展字段（参见 [phase-3-内容生产核心思想落盘方案.md:215-263](../phase-3-内容生产核心思想落盘方案.md#L215-L263)）
- 关系边落 `(:Persona)-[:COMPATIBLE_WITH {support, risk, reason}]->(:ContentType)`，导入 54 条兼容边
- 派生视图运行时计算逻辑（按本稿 §5.2 组合规则表）
- `FounderProfile` Entity Type 注册（[ITR-026](../../iteration-backlog.md)，归属 TASK-K3-1 / TASK-K3-6）
- **不需要做的**：不新建 `ContentType × Platform` 关系边、不挂 `[CONTRACT]` 标签、不新建 ADR

### 7.4 品牌 / 业务专家侧

负责：

- 核实岗位真实感是否符合服装零售实际
- 审核 `authenticity_anchors`（真实性锚点）是否像活人不像 AI
- 审核哪些岗位话题越界、哪些不越界（`topic_scope.forbidden_topics`）
- 审核"人设壳"和"岗位知识"是否没有串味（产物 5 §三的 P0 4 岗位 + P1 3 岗位）

---

## 八、当前"已冻结 / 候选 / 待补"总表

### 8.1 已冻结（Frozen）

| 类别 | 项目 |
|---|---|
| 计数口径 | 1 个品牌唯一层 + 3 套通用 `Persona` |
| 品牌唯一层命名 | `FounderProfile`（创始人画像）—— 历史备选名废弃记录归 Q4 裁决稿 §2.2 |
| 三套通用 Persona 命名 | `store_operator` / `styling_advisor` / `product_professional` |
| 首批 7 个岗位 | `store_manager` / `warehouse_supervisor` / `sales_associate` / `designer` / `sample_worker` / `design_director` / `merchandising_director` |
| 挂接关系 | 7 个岗位到 3 套通用 Persona 的挂接（4-2-1 分布）|
| 兼容矩阵真源关系 | `(:Persona)-[:COMPATIBLE_WITH {support, risk, reason}]->(:ContentType)` 共 54 条边 |
| 矩阵分层 | **一层真源 + 一层派生视图**（严格对齐 [Q4 裁决稿 §3.1](../phase-3-Q4-品牌首批默认启用几套人设.md#L184-L269)）|
| 字段口径 | `support = now \| enhanced \| custom \| unsupported` / `risk = low \| medium \| high` / `reason = string` |
| 派生视图轴 | `Persona × ContentType × Platform/Channel`（不写入图谱）|
| 平台维度承接 | 承接 Q3 `(:System)-[:SUPPORTS_PLATFORM {tier}]->(:PlatformTone / :PrivateOutletChannel)`，**不新建** `ContentType × Platform` 关系边 |
| 运营展示档 | 默认可用 / 补充配置后可用 / 品牌级或特殊场景 / 不建议 |
| 强规则 | 导购 / 门店经营内容线必须同时覆盖公域 + 私域 |

### 8.2 候选待填（Candidate）

| 类别 | 项目 |
|---|---|
| `life_archetype`（生活原型）| 三套通用 Persona 的最终保留值（候选池已给）|
| `emotional_spectrum`（情绪光谱）| 频率与强度区间的最终值（最小候选集已给）|
| `topic_scope`（话题边界）| 允许 / 禁止话题的最终收口（首批边界已给）|
| `typical_scenarios`（典型场景）| 每套 Persona 的完整场景集（最小集已给）|
| `authenticity_anchors`（真实性锚点）| 每套 Persona 的真实细节锚点扩充到 5+ 条（最小 4 条已给）|
| 兼容矩阵 `reason`（原因）| 每一格的精细原因说明（首批已给简要 reason）|

### 8.3 待补证 / 待后续 Q 承接（Pending）

| 类别 | 项目 |
|---|---|
| **Phase 3 实施任务卡** | `FounderProfile` Entity Type 注册（[ITR-026](../../iteration-backlog.md) 待 TASK-K3-1 / TASK-K3-6 承接）|
| **Schema 语义** | `Persona.role_type` 单值 vs 多挂一 RoleProfile 的语义裁决（方案 A 升级数组 / B 保持单值取主岗 / C 用关系边承载）|
| **Q21** | `emotional_spectrum`（情绪光谱）最终细化策略 |
| **Q22** | 品牌真实性策略（`authenticity_policy`）细化 |
| **Q19 / Q20** | `EnterpriseEvent`（企业事件）/ `NarrativeArc`（叙事弧）回填后对兼容矩阵的增强 |
| **品牌素材** | `FounderProfile` 真实品牌素材回填 / 7 个 RoleProfile 的硬证据集采集（参见产物 5 §三）|

---

## 九、本稿结论

《参数级填充清单：Q4 部分》候选 v0.1 正式收口为：

1. **对象层** 已经冻结：

   - `FounderProfile`（创始人画像）— 品牌唯一层，命名已选定，[ITR-026](../../iteration-backlog.md) 待技术注册
   - 3 套通用 `Persona`（人设）— `store_operator` / `styling_advisor` / `product_professional`
   - 7 个 `RoleProfile`（岗位画像）— `store_manager` / `warehouse_supervisor` / `sales_associate` / `designer` / `sample_worker` / `design_director` / `merchandising_director`

2. **字段层** 已经明确：

   - `Persona`（人设）字段壳全部存在（6 字段，结构由真源定义）
   - 当前每个字段区分为"首批可用 / 候选待填 / 待后续 Q 承接"三档

3. **关系层** 已经明确：

   - 7 个岗位的挂接关系冻结（4-2-1 分布到 3 套通用 Persona）
   - `Persona × ContentType` 兼容关系冻结为 54 条真源边（详见兼容矩阵稿 §四）
   - **平台维度承接 Q3 真源，Q4 不新建任何 `ContentType × Platform` 或 `Persona × Platform` 关系边**

4. **派生层** 已经明确：

   - 三维派生视图 `Persona × ContentType × Platform/Channel` 不写入图谱
   - 派生公式由真源层 + Q3 `tier` 临时组合，详见兼容矩阵稿 §6.2 组合规则表
   - "平台"在本稿是描述性统称，覆盖 `PlatformTone`（公域分发位）+ `PrivateOutletChannel`（私域出口位）两类 Q3 真源对象，**不引入新实体类型**

5. **执行层** 已经明确：

   - 内容运营 / 知识工程 / 技术实现 / 业务专家 4 方各自的接力清单
   - 哪些项可以直接进入 Phase 3 Step 2 / Step 3 任务卡
   - 哪些项要等 Q19 / Q20 / Q21 / Q22 递进

### 范围约束（本稿明确不做）

- **不新建** `ContentType × Platform` / `Persona × Platform` 任何方向的关系边
- **不引入** `DistributionTarget` 或类似的新实体类型——"平台"只在叙述层做统称
- **不卷入** Q3 v1 §2.3 明确推迟到后续 Q 的事（品牌级覆盖 / 关系扩展属性 / tier 历史）
- **不引入** 新 ADR / 不挂 `[CONTRACT]` 标签 / 不触发 schema 变更
- **不重复** Q4 裁决稿 / 首批清单 / 三套卡片 / 兼容矩阵 / 岗位素材清单已有的内容，本稿只做参数级收口

### 本轮 Q4 产物进度（最终）

| # | 产物 | 状态 |
|---|---|---|
| 1 | [phase-3-Q4-品牌首批默认启用几套人设.md](../phase-3-Q4-品牌首批默认启用几套人设.md) | ✅ 已落盘 |
| 2 | [phase-3-Q4-首批Persona-RoleProfile清单.md](phase-3-Q4-首批Persona-RoleProfile清单.md) | ✅ 已落盘 |
| 3 | [phase-3-Q4-三套通用Persona首批卡片.md](phase-3-Q4-三套通用Persona首批卡片.md) | ✅ 已落盘 |
| 4 | [phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md](phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md) | ✅ 已落盘 |
| 5 | [phase-3-Q4-首批岗位知识素材清单.md](phase-3-Q4-首批岗位知识素材清单.md) | ✅ 已落盘 |
| 6 | **本稿（参数级填充清单：Q4 部分）** | ✅ **本轮落盘** |

**Q4 冷启动阶段 6 份产物全部落盘完成。下游可直接开工：**

- Phase 3 Step 2 Entity Type 注册（含 `FounderProfile` 注册推进 [ITR-026](../../iteration-backlog.md)）
- Phase 3 Step 3 种子数据导入（54 条 Persona × ContentType 兼容边 + 7 个 RoleProfile 岗位知识包）
- Skill 层能力发现机制接入（从 ContentType 出发联带查兼容 Persona + Q3 平台 tier）
- Prompt 组装前置判断（按派生档位给出风险提示）

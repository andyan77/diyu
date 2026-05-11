# Phase 3 · Q1-Q24 裁决对照表（Decision Reference Matrix）

> **文档性质：** 派生对照稿（Derived Reference）— 不重新裁决任何 Q，仅汇总现有 24 份正式裁决稿
> **创建日期：** 2026-05-07
> **状态：** Active v1.0
> **真源优先级：** Q1-Q24 子稿 > 本对照表（如冲突以子稿为准，本稿同步修正）
> **用途：**
>
> 1. 一张顶层索引表 + 五张分组明细表，提供"一眼对照"视图
> 2. 所有英文标识符附中文释义（十诫 #17 中英对照）
> 3. 枚举类裁决（如 Q1 的 18 个 ContentType）必须列全
> 4. 仅供查阅 / 对照 / 培训新人，不承担工程契约

---

## 〇、阅读指南

- **状态符号：** ✅ Accepted（已正式裁决） / ⏸️ 延后（明确不在 Phase 3 实装）
- **粒度规则：** 顶层表 = 一句话裁决摘要；明细表 = 候选取舍 + 全部枚举项 + 关键产出物
- **术语缩写：** CT = ContentType（内容类型）；BT = BrandTone（品牌调性）；PT = PlatformTone（平台调性）；EE = EnterpriseEvent（企业事件）；NA = NarrativeArc（叙事弧）
- **分组对应路线图：** 内容骨架组（Q1-Q6）/ 陈列搭配组（Q7-Q12）/ Skill 联动组（Q13-Q15）/ 行业边界组（Q16-Q18）/ 内容扩展组（Q19-Q24）

---

## §一 顶层索引表（24 行 · 一眼扫到底）

| Q | 主题 | 分组 | 状态 | 裁决结果（一句话） | 子稿 |
|---|------|------|------|---------------------|------|
| Q1 | 内容生产首批做什么 | 内容骨架 | ✅ v1.1（2026-04-11） | 18 个 ContentType（10 引流 + 4 接客 + 6 企业叙事，去重后 18），三层组织 + 兵团协同 + 禁 AI 味红线 | [Q1](phase-3-Q1-内容生产首批做什么.md) |
| Q2 | 每种内容产出物长什么样 | 内容骨架 | ✅ v0.2（2026-04-14） | 18 份玩法卡片化交付物 = 玩法库 + 元素库 + 红线；253 玩法卡 / 129 突破性 / 13 共享叙事引擎 | [Q2](phase-3-Q2-内容产出物长什么样.md) |
| Q3 | 首批平台支持与适配边界 | 内容骨架 | ✅ v1（2026-04-15） | 12 平台 × 4 档 tier；新增 PrivateOutletChannel 实体；3 P0_native + 1 朋友圈 + 3 P1 + 1 P2 + 4 deferred | [Q3](phase-3-Q3-首批平台支持与适配边界.md) |
| Q4 | 品牌首批默认启用几套人设 | 内容骨架 | ✅ v0.1（2026-04-15） | 1 FounderProfile + 3 通用 Persona + 7 RoleProfile；废弃备选名 BrandSoul | [Q4](phase-3-Q4-品牌首批默认启用几套人设.md) |
| Q5 | 品牌调性管到什么程度 | 内容骨架 | ✅ v0.1（2026-04-16） | "一核两阀"：品牌核 3 字段 + 情绪阀 3 子字段 + 真实性阀 3 档；forbidden_patterns 归 PT | [Q5](phase-3-Q5-品牌调性管到什么程度.md) |
| Q6 | 审核流怎么走 | 内容骨架 | ✅ v0.1（2026-04-16） | 系统机审优先；ContentGuard 6 检查；content_policy 三档（relaxed/standard/strict）；人工兜底归 brand_hq | [Q6](phase-3-Q6-审核流怎么走.md) |
| Q7 | 首批推荐什么维度 | 陈列搭配 | ✅（2026-04-17） | 7 个判断维度（比例/廓形/腰线/主角/颜色/材质/正式度）全量进首批 | [Q7-Q12](phase-3-Q7-Q12-陈列搭配能力边界.md) |
| Q8 | 搭配规则从哪来 | 陈列搭配 | ✅（2026-04-17） | 三级优先序（专家素材/真源抽取/公开知识）；首批 12 条规则 = 8 硬 + 4 软 | [Q7-Q12](phase-3-Q7-Q12-陈列搭配能力边界.md) |
| Q9 | 陈列指南输出什么 | 陈列搭配 | ✅（2026-04-17） | 6 个陈列单元（橱窗/模特/正挂/侧挂/叠装/成套）+ 6 类库存状态适配 + 培训层级 | [Q7-Q12](phase-3-Q7-Q12-陈列搭配能力边界.md) |
| Q10 | 库存感知做到什么程度 | 陈列搭配 | ✅（2026-04-17） | 冷启动直接深感知（色×码）+ 人工录入；6 库存状态 + 5 条硬拦截 | [Q7-Q12](phase-3-Q7-Q12-陈列搭配能力边界.md) |
| Q11 | 培训覆盖哪些真实场景 | 陈列搭配 | ✅（2026-04-17） | 4 大类 × 12 单元；4 培训格式 + 4 层验收；标准动作 vs 判断力分开训 | [Q7-Q12](phase-3-Q7-Q12-陈列搭配能力边界.md) |
| Q12 | 推荐粒度到哪一级 | 陈列搭配 | ✅（2026-04-17） | 款式级推荐 + SKU 级库存校验；SKU 级推荐冷启动不做 | [Q7-Q12](phase-3-Q7-Q12-陈列搭配能力边界.md) |
| Q13 | 联动边界裁决 | Skill 联动 | ✅ v0.1（2026-04-17） | 仅允许 MerchandisingSkill → ContentWriterSkill 单跳串行；非白名单降级为建议提示 | [Q13-Q15](phase-3-Q13-Q15-Skill联动怎么做.md) |
| Q14 | 触发与主从裁决 | Skill 联动 | ✅ v0.1（2026-04-17） | 主 Skill 由用户主诉求决定；下游由 Brain 决定；trigger_mode = auto / confirm | [Q13-Q15](phase-3-Q13-Q15-Skill联动怎么做.md) |
| Q15 | 上下文继承裁决 | Skill 联动 | ✅ v0.1（2026-04-17） | 事实层跟上游（fact_refs）；表达 + 治理层跟终态产物；终态是内容必重过 ContentGuard | [Q13-Q15](phase-3-Q13-Q15-Skill联动怎么做.md) |
| Q16 | 首批行业边界与一级覆盖 | 行业边界 | ✅ v0.1（2026-04-18） | industry_scope = fashion 不外扩；首批男 / 女 / 童 3 子域；亲子装按童装专题承接 | [Q16-Q18](phase-3-Q16-Q18-行业边界与最大公约数能力.md) |
| Q17 | 参数级适配 vs 结构级定制 | 行业边界 | ✅ v0.1（2026-04-18） | 冷启动只做参数级适配（四维：BrandTone / Persona / PlatformAdapter / content_policy）；不结构级定制 | [Q16-Q18](phase-3-Q16-Q18-行业边界与最大公约数能力.md) |
| Q18 | 首批标配 vs 后续扩展切分 | 行业边界 | ✅ v0.1（2026-04-18） | 三判据（全适用 / 冷启动可建 / 品牌无关）；L1-L9 九层标配清单；后续扩展 5 项明确不做 | [Q16-Q18](phase-3-Q16-Q18-行业边界与最大公约数能力.md) |
| Q19 | 首批企业事件类型 | 内容扩展 | ✅ v1.0（2026-04-18） | A 组 10 个 event_type 启用；B 组 6 个降 ITR-038；种子 30-60 条（方案 B） | [Q19](phase-3-Q19-首批企业事件类型.md) |
| Q20 | 首批叙事弧类型 | 内容扩展 | ✅ v1.0（2026-04-18） | 启用 2 个 arc_type（product_journey / process_trace）+ 6 个命名占位；种子 4-6 条 | [Q20](phase-3-Q20-首批叙事弧类型.md) |
| Q21 | Persona 情绪光谱定义 | 内容扩展 | ✅ v1.0（2026-04-18） | 候选 C 服装零售定制 11 词 + 禁用基线；3 Persona §三示例；7 RoleProfile 默认继承 | [Q21](phase-3-Q21-Persona情绪光谱定义.md) |
| Q22 | BrandTone 真实性策略 | 内容扩展 | ✅ v1.0（2026-04-18） | 候选 B：默认 authentic_mixed，onboarding 可改档；不按 ContentType 差异化 | [Q22](phase-3-Q22-BrandTone真实性策略.md) |
| Q23 | 双模式审核差异 | 内容扩展 | ✅ v1.0（2026-04-18） | 候选 A 3×3 矩阵：personal/relaxed · enterprise/standard · both/standard；4 特殊 CT 强制 strict | [Q23](phase-3-Q23-双模式审核差异.md) |
| Q24 | 效果反馈回收与升级 | 内容扩展 | ⏸️ 候选 C 延后（2026-04-18） | Phase 3 不实装，延后 Phase 4/6（ITR-042）；本稿仅作方向性设计参考 | [Q24](phase-3-Q24-效果反馈回收与升级.md) |

---

## §二 内容骨架组（Q1-Q6）明细

### Q1 · 内容生产首批做什么

**裁决依据 / 候选取舍**：源头 A（9 平台命名）+ 源头 B（16 题材）合并 → 保留 B 的题材分类，去掉 A 的平台绑定；新增 `founder_ip`（企业叙事首位）和 `outfit_of_the_day`（服装核心题材）；废弃源头 A 的 `xhs_lifestyle / dy_product_short / dy_vlog_script / wechat_article`（平台适配交给 PlatformAdapter）。

**18 个 ContentType（按三层组织 · 去重后 18）：**

| 层 | English（中文释义） | 说明 |
|---|---|---|
| L1 内容引流引擎 | `personal_vlog`（个人 / 门店 VLOG） | 引流弹药 |
| L1 | `lifestyle_expression`（生活方式 / 态度 / 价值观表达） | 引流弹药 |
| L1 | `knowledge_sharing`（穿搭 / 面料 / 保养 / 流行 / 选购干货） | 引流弹药 |
| L1 | `humor_content`（轻松幽默 / 搞笑表达） | 引流弹药 |
| L1 | `talent_showcase`（才艺展示） | 引流弹药 |
| L1 | `daily_fragment`（日常碎片 / 随拍） | 引流弹药 |
| L1 | `outfit_of_the_day`（穿搭日记 — 本 Q 新增） | 服装行业最核心题材 |
| L1 | `store_daily`（门店日常） | 跨层（兼第二层接客氛围） |
| L1 | `product_review`（商品种草） | 跨层（兼第二层接客辅助） |
| L1 | `emotion_expression`（情绪表达 / 真实吐槽 / 感悟 / 成长） | 引流弹药 |
| L2 库存接客流水线 | `product_copy_general`（通用产品文案） | 详情页 / 私域转化 |
| L2 | `training_material`（培训材料） | 内部赋能 |
| L2 企业叙事（权限高→低） | `founder_ip`（创始人 IP — 本 Q 新增） | 企业叙事首位 + 权限最高 |
| L2 | `role_work_vlog`（岗位工作 VLOG） | 设计师 / 样衣工 / 店长 |
| L2 | `event_documentary`（企业事件纪实） | 订货会 / 拍摄幕后 |
| L2 | `product_journey`（产品旅程） | 一件衣服从设计到上架 |
| L2 | `process_trace`（流程溯源） | 面料 / 品控从源头到终端 |
| L2 | `behind_the_scenes`（幕后记录） | — |

**关键产出物**：18 个 ContentType；新 Entity Type `FounderProfile`（每品牌仅 1 份，9 字段：`founder_name / value_system / worldview / brand_philosophy / lifestyle_manifesto / aesthetic_preferences / inspiration_sources / origin_story / signature_phrases`）；`production_mode` 字段（`personal` / `enterprise`）；架构原则 6（知识向下继承 / 权限向上收敛）+ Promotion Pipeline。

**上游依赖**：架构 §2.4 + 03-Skill 层 §5.1 + 02-Knowledge 层 §3.3 + ADR-066。
**下游解除**：Q2-Q24 全部裁决；Phase 3 K3-1 种子；ITR-026（FounderProfile 注册）。

---

### Q2 · 每种内容的产出物长什么样

**裁决依据 / 候选取舍**：废弃 2026-04-10 工程化空壳路径（六层结构 + 4 类母型 + 13 CT schema），改走玩法卡片化方法论；C1 主流默认禁用 / C2 进阶推荐 / C3 突破性可选。

**18 份交付物（按 production_mode 三分类）：**

| 分类 | ContentType | 玩法卡 | 突破性 |
|---|---|---:|---:|
| personal（7 个） | `personal_vlog` / `lifestyle_expression` / `knowledge_sharing` / `humor_content` / `talent_showcase` / `daily_fragment` / `outfit_of_the_day` | 97 | 52 |
| enterprise（6 个） | `founder_ip` / `role_work_vlog` / `event_documentary` / `product_journey` / `process_trace` / `behind_the_scenes` | 89 | 44（含 14 处共享引擎映射）|
| both（5 个） | `store_daily` / `product_review` / `emotion_expression` / `product_copy_general` / `training_material` | 67 | 33 |
| **合计** | 18 份 | **253** | **129** |

**共享叙事引擎 13 条（v0.2 候选 7 条）：**

- 戛纳广告节范式 4：#1 `反讽对位` / #2 `认知反转` / #3 `空间蒙太奇` / #4 `介质反差`
- 电影影像手法 4：#5 `伪一镜到底` / #6 `手持纪录感` / #7 `循环结构` / #8 `错位剪辑`
- SHOWstudio 1：#9 `时尚影像实验室`
- compass 4：#10 `纯沉默叙事` / #11 `ASMR 感官沉浸` / #12 `定格动画延时摄影` / #13 `MV 电影预告片格式`
- v0.2 候选 7：#14 `倒叙开门` / #15 `微物叙事` / #16 `接力叙事` / #17 `倒叙子引擎` / #18 `双引擎融合卡范式` / #19 `自嘲家族子分类` / #20 `文案叙事引擎分支`

**§H Batch 3 首创机制 5 项**：α 9 种 AI 腔禁用清单 / β 适用场景标签（引流 / 接客 / 通用）/ 5 种声音原型矩阵 / 学习机制术语库（13 个认知科学机制）/ 兵团向口径。

**§J 跨 CT 统一标准**：J.1 玩法分级（`instant` / `long_term` / `brand_tier`）/ J.2 隐私同意（默认同意 / 不保留书面同意例外）/ J.3 字段语义映射（视频型分镜 / 文案型骨架）。

**实拍可行性**：1 人基线（16 CT，单条 ≤ 200 元 / ≤ 4 小时）+ 1-3 人小团队放宽（仅 `event_documentary` / `process_trace` 2 个）；C3 三问自检（手机能拍 / 不依赖专业身份 / ≤ 200 元）。

**玩法卡 10 字段**：档位 / 一句话定义 / 北极星映射 / 表达元素清单 / 30 秒分镜参考 / 服装行业钩子（5 星制） / 实拍可行性（🟢🟡🔴+ 三问） / AI 辅助度 / 来源 / 备注。

**关键产出物**：18 份 v0.2 交付物；253 玩法卡 / 129 突破性；共享层 v0.2.1（13 引擎 + 29 调用）；ITR-049 / ITR-050（CT 注册到 Knowledge 层 + 边界矩阵）。
**上游**：Q1。**下游解除**：Phase 3 K3-1 种子导入；待 Step 3 接 Prompt 工程化 + §J.3 解码器。

---

### Q3 · 首批平台支持与适配边界

**裁决依据 / 候选取舍**：不在 PlatformTone / PlatformAdapter 实体上加 support_level 字段（避免与 ADR-069 的 ContentType.support_level 冲突）；走关系建模 `(:System)-[:SUPPORTS_PLATFORM {tier}]->(:PlatformTone | :PrivateOutletChannel)`；朋友圈不塞进 PlatformTone，独立建 PrivateOutletChannel。

**4 档 tier 受控枚举：**

| Tier | English（中文释义） | 含义 |
|---|---|---|
| 1 | `P0_native`（P0 原生支持） | 首批必须支持，有独立 PT / PrivateOutletChannel 实例 |
| 2 | `P1_light_adapt`（P1 轻改适配） | 不做首批重点，允许从 P0 内容轻改后发布 |
| 3 | `P2_cross_post_only`（P2 仅转发） | 一稿多发，不承诺原生效果 |
| 4 | `deferred`（延后） | 当前阶段暂不纳入 |

**12 个平台分层：**

| Platform | English（中文释义） | Tier | 实体类型 |
|---|---|---|---|
| 1 | `xiaohongshu`（小红书） | `P0_native` | PlatformTone |
| 2 | `douyin`（抖音） | `P0_native` | PlatformTone |
| 3 | `wechat_channels`（视频号） | `P0_native` | PlatformTone |
| 4 | `wechat_moments`（微信朋友圈） | `P0_native` | **PrivateOutletChannel** |
| 5 | `kuaishou`（快手） | `P1_light_adapt` | PlatformTone |
| 6 | `wechat_official_account`（微信公众号） | `P1_light_adapt` | PlatformTone |
| 7 | `bilibili`（B 站） | `P1_light_adapt` | PlatformTone |
| 8 | `weibo`（微博） | `P2_cross_post_only` | PlatformTone（占位） |
| 9 | `wechat_group`（微信群） | `deferred` | PrivateOutletChannel（占位） |
| 10 | `wechat_dm`（微信私信） | `deferred` | PrivateOutletChannel（占位） |
| 11 | `mini_program`（小程序） | `deferred` | — |
| 12 | `taobao_detail_page`（淘宝详情页） | `deferred` | — |

**P0_native PlatformTone 8 字段**：`headline_rules`（标题规则）/ `hook_rules`（钩子规则）/ `body_structure_rules`（正文结构）/ `hashtag_rules`（话题标签）/ `cta_rules`（行动召唤）/ `emoji_policy`（表情策略）/ `length_constraints`（长度约束）/ `basic_compliance_notes`（合规备注）。

**P0_native PrivateOutletChannel 6 字段**：`first_line_fold_point`（首行折叠点）/ `nine_grid_aesthetics`（九宫格美学）/ `narrative_rhythm`（叙事节奏）/ `strong_relation_voice`（强关系链口径）/ `non_disturb_policy`（不打扰节奏）/ `private_chat_handover_phrases`（私聊话术约定）。

**18 × 平台主矩阵特例**：`founder_ip`（抖音 / 视频号 / 公众号主战场，朋友圈不投放，小红书 / B 站辅助场）；`training_material`（不进任何公域，只走视频号企业号 + 公众号 + 内部分发）；`product_copy_general`（朋友圈 + 公众号主战场，小红书 / 抖音 / 视频号 / B 站不投放）。

**首批模板体系 24 份核心对象**：18 ContentBlueprint + 3 P0_native PT + 1 P0_native PrivateOutletChannel + 2 生产模式外壳（`personal_mode` / `enterprise_mode`）— 不做 18×4=72 套笛卡尔积 Prompt。

**关键产出物**：新 Entity Type `PrivateOutletChannel`；新关系类型 `SUPPORTS_PLATFORM`；新受控枚举 `tier` 4 值；ADR-072。
**上游**：Q1 / Q2 / ADR-069。**下游解除**：PlatformTone 参数级填充 + PlatformAdapter 适配 + Phase 3 K3-x；登记 backlog 三条。

---

### Q4 · 品牌首批默认启用几套人设

**裁决依据 / 候选取舍**：选定 `FounderProfile`（废弃 Q1 备选名 `BrandSoul`，工程对称性 + Q1 主候选）；不新建 `ContentType × Platform` 真源边（一层真源 + 一层派生 vs 两层真源，三元真源指数膨胀且与 Q3 v1 范围纪律冲突）。

**1 + 3 + 7 配置：**

| 层 | 数量 | 实例（English（中文释义）） |
|---|---:|---|
| 品牌唯一层 | 1 | `FounderProfile`（创始人画像 / 每品牌 1 份）|
| 通用 Persona | 3 | `store_operator`（门店经营者）/ `styling_advisor`（穿搭顾问）/ `product_professional`（商品专业者）|
| RoleProfile | 7 | `designer`（设计师）→ product_professional · `sample_worker`（样衣工）→ product_professional · `warehouse_supervisor`（仓库主管）→ store_operator · `merchandising_director`（商品总监）→ product_professional · `design_director`（设计总监）→ product_professional · `store_manager`（门店店长）→ store_operator · `sales_associate`（门店店员 / 导购）→ styling_advisor |

**3 通用 Persona 承接范围**：
- `store_operator` → 门店经营、带队、秩序、复盘、接客氛围、培训提醒、幕后视角
- `styling_advisor` → 前台接客、试穿建议、搭配建议、顾客体感、尺码与场景判断
- `product_professional` → 设计、打样、工艺、面料、版型、商品判断、产品历程与工艺溯源

**真源关系边**：`(:Persona)-[:COMPATIBLE_WITH {support, risk, reason}]->(:ContentType)`
- `support` 枚举：`now` / `enhanced` / `custom` / `unsupported`（与 ADR-069 同枚举）
- `risk` 枚举：`low` / `medium` / `high`
- `reason`：可选 string

**派生视图 4 档**：默认可用 / 补充配置后可用 / 品牌级 · 特殊场景 / 不建议（不入 schema）。

**关键产出物**：`FounderProfile` 正式选名；3 通用 Persona + 7 RoleProfile 实例清单；`COMPATIBLE_WITH` 关系边（54 条 = 3×18 待填）。
**上游**：Q1 / Q2 / Q3 / 架构 §核心思想方案。**下游解除**：ITR-026 激活；Phase 3 Step 2 Entity 注册 + Step 3 种子 + ContentWriterSkill Persona 口吻注入。

---

### Q5 · 品牌调性管到什么程度

**裁决依据 / 候选取舍**：方案 A（一核两阀）作为正式对象边界 + 方案 B（主卡 + 外挂卡）协作填写 + 方案 C（双轴罗盘）业务理解视图（不入 schema）。

**"一核两阀"结构：**

| 层 | 字段 / 子字段 | English（中文释义） | 类型 |
|---|---|---|---|
| 品牌核 | `brand_positioning` | 品牌定位 | string |
| 品牌核 | `value_keywords` | 价值观关键词 | string[]（建议 3-7） |
| 品牌核 | `tone_keywords` | 调性关键词 | string[]（建议 3-7） |
| 情绪阀 | `emotional_boundary.allowed_emotions` | 允许情绪 | enum[] |
| 情绪阀 | `emotional_boundary.forbidden_emotions` | 禁用情绪 | enum[] |
| 情绪阀 | `emotional_boundary.tone_guardrails` | 语气护栏（不说教 / 不过度正能量 / 不攻击竞品）| string[] |
| 真实性阀 | `authenticity_policy` | 真实性策略（3 档枚举）| enum |

**真实性阀 3 档枚举：**

| Enum | English（中文释义） | 适用 |
|---|---|---|
| 1 | `strict_positive`（严格正向） | 高度统一口径、强控制品牌 |
| 2 | `authentic_mixed`（真实混合） | 允许真实但不允许失控 — 大多数品牌（系统默认，由 Q22 锁定） |
| 3 | `raw_realistic`（原生写实） | 对真实粗粝表达高容忍 + 治理能力成熟的品牌 |

**`BrandTone.constraints` 4 类承接**：禁用词 / 传播红线（不攻击竞品 / 不外泄内部矛盾 / 不公开撕扯合作方）/ 合规规则（广告法 / 文化禁忌）/ 品牌不接受的表达边界。

**主卡 + 外挂卡 4 张**：
- 主卡 `BrandTone`：品牌核 + constraints + emotional_boundary + authenticity_policy
- 外挂卡 1 `Persona`：emotional_spectrum + authenticity_anchors + topic_scope
- 外挂卡 2 `PlatformTone`：**forbidden_patterns**（唯一归属 PT，不归 BT）+ publishing_rules
- 外挂卡 3 `ContentBlueprint`：style_tags + style_constraints

**双轴罗盘（不入 schema · 仅业务视图）**：横轴 authenticity_policy（左 strict_positive → 中 authentic_mixed → 右 raw_realistic）/ 纵轴 情绪开放度（由 emotional_boundary 推导）。

**关键产出物**：authenticity_policy 三档枚举锁定；`BrandTone.constraints` 口径；`forbidden_patterns` 归属 PT；3 个业务字段是否升 schema 留 Phase 3 Step 2。
**上游**：Q1 / Q2 / Q3 / Q4 / 架构方案。**下游解除**：Q22 选档 + Q21 情绪光谱品牌级上限 + Q6 ContentGuard 输入 + Phase 3 Step 2 种子品牌数据。

---

### Q6 · 审核流怎么走

**裁决依据 / 候选取舍**：服装零售内容高频、门店强时效、低风险量大、高风险出错代价高 → 系统吃低风险高频，人工留给真伤品牌的内容；与 ADR-066 直传总部一致。

**5 项核心裁决**：
1. 默认主链路 = 系统机审优先
2. 冷启动不把组织人工审核设为默认必经链路
3. 冷启动跳过区域审核（region 不作为默认必经节点）
4. 启用人工兜底时优先 `brand_hq`（品牌总部）承担
5. 系统设置保持向后兼容，不关闭人工审核通道

**ContentGuard 6 项检查：**

| # | 检查项 | 输入来源 |
|---|---|---|
| 1 | 品牌红线检查 | `BrandTone.constraints` + `forbidden_words` |
| 2 | 情绪意图分类 | `Persona.emotional_spectrum` + `BrandTone.emotional_boundary`（通过 LLMCallPort）|
| 3 | 情绪强度检查 | `Persona.emotional_spectrum.intensity_range` |
| 4 | 人设一致性检查 | `Persona.topic_scope` + `voice_style` |
| 5 | 平台违规词检查 | `PlatformTone.forbidden_patterns` |
| 6 | 敏感表达检查 | 内部矛盾外泄 / 攻击性表达 / 虚假宣传 |

**`content_policy` 三档语义：**

| Enum | English（中文释义） | 检查项 | WARN 处理 |
|---|---|---|---|
| 1 | `relaxed`（宽松） | 仅 #1 #5（品牌红线 + 平台违规词） | 不进入人工审核 |
| 2 | `standard`（标准） | 全部 6 项 | WARN → 提示用户修改 |
| 3 | `strict`（严格） | 全部 6 项 | WARN → 自动升级 brand_hq 人工 |

**4 类系统输出动作**：`pass`（通过）/ `revise`（修改）/ `escalate`（升级人工）/ `block`（阻断）。

**GuardResult 路由映射**：全 PASS + low/medium → 任意档 pass；含 WARN + low/medium/high → relaxed 不触发 / standard revise / strict escalate；含 BLOCK → 任意档 block。

**人工升级 3 类条件（strict + WARN 触发 escalate）**：高风险 enterprise 内容（`founder_ip` / `process_trace` / 部分 `event_documentary`）/ 强品牌责任内容 / 系统无法自动收口。

**关键产出物**：content_policy 三档语义锁定；GuardResult 路由映射表；amends 03-Skill 层 §5.3。
**上游**：Q1 / Q5 / 架构方案。**下游解除**：Q23（personal/enterprise 默认配置）+ Phase 3 Step 4 ContentWriterSkill / ContentGuard 实装。

---

## §三 陈列搭配组（Q7-Q12）明细

### Q7 · 首批推荐什么维度

**裁决依据 / 候选取舍**：从 12 条首批搭配规则提炼；男装专项维度（`menswear_belt_shoe_rule`）已纳入；近脸提气作为软建议但不升为独立维度；体型细分 / 个人风格标签维度延后。

**7 个判断维度（全量进首批）：**

| # | English（中文释义） | 对应规则 | 举例 |
|---|---|---|---|
| 1 | `proportion`（比例） | `proportion_split_rule` | 上短下长 3:7 |
| 2 | `silhouette`（廓形） | `silhouette_balance_rule` | 上宽下收 / 上收下宽 |
| 3 | `waistline`（腰线） | `waistline_anchor_rule` | 高腰锚点 / 半塞衣角 |
| 4 | `focus`（主角） | `one_focus_rule` | 一身只留一个主角 |
| 5 | `color`（颜色） | `color_echo_rule` + `neutral_plus_accent_rule` | 至少两处呼应 / 中性色打底 |
| 6 | `material`（材质） | `structure_drape_rule` + `premium_item_neutralization_rule` | 挺配垂 / 贵气配基础 |
| 7 | `formality`（正式度） | `formality_consistency_rule` | 场合内单品正式度统一 |

**关键产出物**：`StylingRule.dimensions[]`（7 维度判断标签）；`Attribute` 与 7 维度的映射（color / material / fit / length / occasion / season）。
**上游**：Q1 第二层 / Q2。**下游解除**：MerchandisingSkill 参数填充 + StylingRule 种子。

---

### Q8 · 搭配规则从哪来

**裁决依据 / 候选取舍**：先收口再补缺（现有 61 条 + 12 条交叉去重）；按品类补；不做 AI 自动发现规则、不做 ERP/销售数据挖掘规则、不做 UGC 规则。

**三级优先序：**

| Priority | English（中文释义） | 含义 |
|---|---|---|
| P0 | `expert_input`（领域专家一手素材） | Faye 及团队 — 12 条首批规则核心来源 |
| P1 | `extracted_data`（真源已有抽取数据） | 约 61 条，主偏女装日常 — 补充验证 + 女装基础规则池 |
| P2 | `public_knowledge`（公开行业知识） | 公开零售陈列指南 / 穿搭方法论 / 面料工艺规范 — 辅助验证 |

**首批 12 条规则（8 硬 + 4 软）：**

| 类型 | English（中文释义） |
|---|---|
| 硬规则 8 | 三七比例法 / 松紧对冲法 / 腰线锚点法 / 一身一个主角法 / 颜色呼应法 / 正式度统一法 / 单一问题优先法 / 男装鞋腰带同色法 |
| 软建议 4 | 中性色打底法 / 挺垂对比法 / 贵气单品中和法 / 近脸提气法 |

**规则扩充三条纪律**：先收口再补缺 / 按品类补（男 1 条已有，童 / 正装 / 运动为首批补缺方向）/ 每条新规则必须过 5 层（规则内容 → 为什么成立 → 适用/不适用 → 成立/翻车场景 → 替代边界）。

**关键产出物**：`StylingRule.source_type` 三档枚举；`StylingRule.source_evidence`。
**上游**：Q7 / 冷启动规划。**下游解除**：Step 1 交付物"搭配规则数据来源说明"；男 / 童 / 正装 / 运动品类规则补缺。

---

### Q9 · 陈列指南输出什么

**裁决依据 / 候选取舍**：不纳入线上电商详情页陈列、直播间场景布置、跨门店陈列统一标准（冷启动单店先跑通）。

**6 个陈列单元：**

| # | English（中文释义） | 业务目标 | 培训层级 |
|---|---|---|---|
| 1 | `window_display`（橱窗位） | 拦人、定调、拉进店 | 店长 · 老手 |
| 2 | `mannequin_display`（模特位） | 促试穿、提整套带走率 | 店长 · 老手 |
| 3 | `front_hanging_display`（正挂位） | 抓主款、快速产生拿取 | 新人可学 |
| 4 | `side_hanging_display`（侧挂位） | 承接选择、连续浏览 | 新人可学 |
| 5 | `folded_display`（叠装位） | 促上手、顺手加购 | 新人可学 |
| 6 | `full_look_display`（成套推荐位） | 做连带、整套成交 | 店长 · 老手 |

**6 类库存状态标签**：`new_arrival_complete`（新品齐码）/ `core_push_deep_stock`（主推深库存）/ `full_look_ready`（成套就绪）/ `basic_replenishable`（基础可补货）/ `broken_size_partial`（断码部分）/ `clearance_tail_stock`（尾货清库存）。

**陈列 × 库存联动硬规则**：模特位 / 橱窗位 / 成套位**必须过库存校验**，不得用断码伪成套。

**关键产出物**：`DisplayGuide.unit_type`（6 值枚举）/ `business_goal` / `inventory_requirement` / `training_level`（`beginner` / `advanced`）。
**上游**：Q1 第二层 / Q10。**下游解除**：DisplayGuide 6 单元模板（待案例填充）。

---

### Q10 · 库存感知做到什么程度

**裁决依据 / 候选取舍**：浅感知不能判断断码救场、陈列许可、培训场景；深感知每天 15-25 分钟人工录入冷启动可接受，未来可平滑切 ERP 不返工。

**6 种库存状态：**

| # | English（中文释义） | 描述 | 推荐 / 陈列许可 |
|---|---|---|---|
| 1 | `size_complete`（尺码齐全） | 主销码齐 | 能推荐 / 能做主陈列 |
| 2 | `size_broken`（断码） | 有货但主销码不全 | 看版型敏感度 / 降级 |
| 3 | `color_broken`（断色） | 目标色缺失 | 通常能 / 不暗示全色可选 |
| 4 | `single_size_tail`（单码尾货） | 只剩极少量 | 仅精准推荐 / 仅尾货位 |
| 5 | `single_item_only`（凑不成套） | 单品可售但关键搭配件缺 | 可卖单品价值 / 降级到单品位 |
| 6 | `alternate_not_same_sku`（替代款） | 原款不可售有替代 | 必须明示替代 / 可做主题陈列 |

**5 条硬拦截（不可推荐）**：
1. 顾客核心尺码缺失 + 高版型敏感品类
2. `last_sync` 过旧，无法确认可售
3. 内容/陈列卖"整套"但关键件缺失
4. 颜色本身是成交条件但缺失
5. 替代后核心体感/廓形/场景已变，还假装"差不多"

**一次性配置 2 项**：核心成交码（每品类主力码）/ 版型敏感度（每品类容忍度）。

**`(:Product)-[:AVAILABLE_AT]->(:Store)` 扩展字段**：`sellable_size_list` / `sellable_color_list` / `core_size_missing` / `inventory_state_id`（6 值枚举）。

**关键产出物**：6 库存状态枚举 / 5 条硬拦截 / `AVAILABLE_AT` 关系扩展字段 / `inventory_match` 能力。
**上游**：Q9 / Q12。**下游解除**：断码救场 / 陈列许可 / 培训场景判断。

---

### Q11 · 培训覆盖哪些真实场景

**裁决依据 / 候选取舍**：禁用长视频一次讲完 / 统一话术灌输 / PPT 录屏；标准动作可拍固定步骤、判断力必须放情境里练。

**4 大类 × 12 单元：**

| 大类 | 单元（4 + 4 + 2 + 2 = 12）|
|---|---|
| 接客场景训练（4） | 第一眼判断 / 试穿引导 / 身型顾虑 / 面料体感 |
| 搭配纠错训练（4） | 比例失衡 / 主角不清 / 场景错配 / 颜色犹豫 |
| 陈列纠错训练（2） | 主次失衡 / 密度失控 |
| 库存救场训练（2） | 断码救场 / 替代款解释 |

**4 种培训格式：**

| English（中文释义） | 适用 |
|---|---|
| `branching_scenario`（分支情境） | 判断力训练 |
| `do_dont_contrast`（正误对照） | 标准动作 + 纠错 |
| `pre_shift_micro_coaching`（班前微教练） | 即时提醒 |
| `error_replay`（错误重来） | 复盘纠正 |

**4 层现场验收**：动作复现 / 情境应答（30 秒内说判断顺序）/ 正误辨识（指出错在哪、怎么改）/ 神秘顾客式复盘。

**标准动作 5 项（可拍固定步骤）**：折叠 / 挂装 / 蒸烫 / 模特基础成套 / 试衣前递衣顺序。
**判断力 4 项（必须放情境里练）**：顾客真正顾虑判断 / 身型比例判断 / 库存救场该救还是转 / 替代距离是否过远。

**关键产出物**：`TrainingMaterial` 12 单元 + 4 格式 + 4 层验收；7 岗位 × 12 单元优先级矩阵（待填）。
**上游**：Q4 / Q7 / Q9 / Q10。**下游解除**：12 单元案例填充。

---

### Q12 · 推荐粒度到哪一级

**裁决依据 / 候选取舍**：SKU 级推荐需过 4 道坎（颜色兼容矩阵 30 色 → 900 对 / 跨品类码数映射 / 近实时库存同步 / 规则数据量爆炸）冷启动条件不具备；款式级规则不返工，作为 SKU 级推导上层输入保留。

**三层粒度：**

| 层 | 粒度 | 举例 |
|---|---|---|
| 搭配规则 | 款式级 | "廓形西装外套配直筒西裤" |
| 库存校验 | SKU 级 / 色×码 | "黑色 S/M/L 齐码，藏蓝仅剩 XL" |
| 推荐输出 | 款式级推荐 + SKU 级可售标注 | "推荐搭直筒西裤，黑色齐码可推" |

**升级路径（不返工）**：款式级搭配规则（保留）+ 颜色兼容矩阵（新建）+ 尺码适配规则（新建）+ 近实时库存同步（升级）→ 推导引擎自动生成 SKU 级推荐。

**关键产出物**：`(:Product)-[:COMPATIBLE_WITH]->(:Product)` 关系建在款式级；`StylingRule` 描述款式特征；`inventory_match` 在 SKU 级执行。
**上游**：Q7 / Q8 / Q10。**下游解除**：首批 `COMPATIBLE_WITH` 关系款式对清单基于 12 规则推导。

---

## §四 Skill 联动组（Q13-Q15）明细

### Q13 · 联动边界裁决

**裁决依据 / 候选取舍**：Skill 之间互不感知（架构硬约束）；最强业务闭环是搭配/库存/陈列动作派生内容动作；冷启动不把 Brain 过早做成工作流引擎；非白名单链路降级为"建议提示"。

**联动方向：**

| 类型 | 是否允许 |
|---|---|
| `MerchandisingSkill`（陈列搭配技能） → `ContentWriterSkill`（内容写作技能） | ✅ 允许（首批唯一白名单方向） |
| `ContentWriterSkill` → `MerchandisingSkill` 反向 | ❌ 不开放 |
| 任意多跳链路 | ❌ 不开放 |
| Skill 绕过 Brain 自行串联 | ❌ 不开放 |

**联动深度**：单跳串行（主 Skill 执行 → Brain 读上游 SkillResult → 命中白名单 → 触发一个下游 Skill → 下游输出终态产物）。

**非白名单降级**：以 `text_summary`（文本摘要）或非结构化提示告诉用户系统建议的下一步，不把"建议"伪装成"已执行"。

**关键产出物**：白名单链路集合（编排表承载）；不新增 schema / Entity Type / ADR（架构契约由 ADR-073 承接）。
**上游**：ADR-073 决策一/二/三 / Q1-Q6 / Q7-Q12。**下游解除**：Brain 编排逻辑（实装仍需后续任务卡）。

---

### Q14 · 触发与主从裁决

**裁决依据 / 候选取舍**：上游 Skill 不允许在 SkillResult 中强制指定下游必须执行；高确定性、低表达歧义、低品牌风险 → auto；事实充分但有表达歧义、品牌风险或经营敏感 → confirm。

**主 Skill 判断原则：**

| 用户主诉求 | 主 Skill |
|---|---|
| 搭配 / 陈列 / 库存 / 培训动作 | `MerchandisingSkill` |
| 写内容 / 改内容 / 选平台 / 选人设 / 过审核 | `ContentWriterSkill` |

**Brain 触发下游 4 项综合判断**：用户原始意图 / 上游 SkillResult / 联动编排表白名单 / 当前组织上下文。

**`trigger_mode` 两档枚举：**

| Enum | English（中文释义） | 触发逻辑 |
|---|---|---|
| 1 | `auto`（自动触发） | Brain 命中编排表后无需用户确认，直接触发下游 |
| 2 | `confirm`（确认触发） | Brain 命中编排表后先回主 Skill 结果 + 建议提示，等用户显式确认再触发下游 |

**冷启动首批分档建议（白名单 5 条）：**

| 上游动作 | 下游内容 | 触发模式 |
|---|---|---|
| `outfit_recommend` | `product_review` | `auto` |
| `outfit_recommend` | `product_copy_general` | `auto` |
| `display_guide` | `store_daily` | `confirm` |
| `training_generate` | `training_material` | `auto` |
| `inventory_match` | `product_review` / `product_copy_general` | `confirm` |

**关键产出物**：`trigger_mode` 受控两档枚举（由 ADR-073 决策五冻结）。
**上游**：ADR-073 / Q13。**下游解除**：编排表白名单 + auto/confirm 边界细化；Brain 编排实装。

---

### Q15 · 上下文继承裁决

**裁决依据 / 候选取舍**：内容侧契约已冻结 ContentGuard / content_policy；Q6 明文规定所有内容默认先过 ContentGuard；上游业务上下文不构成绕过审核的理由。

**上下文两层切分：**

| 层 | 跟谁走 | 包含对象 |
|---|---|---|
| 事实层（fact context） | 跟上游业务走 / `coordination_packet.fact_refs` 引用传递 | `Product` / `StylingRule` / `DisplayGuide` / 库存状态 / 门店 · 区域组织上下文 / 搭配理由 / 推荐场景 / 训练目标 |
| 表达 + 治理层（expression + governance context） | 跟终态产物走 / 终态 Skill 重新决定 | `Persona` / `ContentType` / `production_mode` / `BrandTone` / `PlatformAdapter` / `PlatformTone` / `content_policy` |

**纪律**：上游建议 ≠ 下游约束；任何由 MerchandisingSkill 事实派生出的内容，只要终态产物属于内容，**必须重新进入 ContentWriterSkill** 完成 Persona 选择、ContentType 匹配、BrandTone 约束、平台适配与审核判定。

**关键产出物**：`coordination_packet.fact_refs` 字段（架构契约由 ADR-073 决策二冻结）。
**上游**：ADR-073 / Q6 / Q13 / Q14。**下游解除**：Brain 上下文路由实现；不新增 schema。

---

## §五 行业边界组（Q16-Q18）明细

### Q16 · 首批行业边界与一级覆盖口径

**裁决依据 / 候选取舍**：原命名口径漂移修正（自创 1F/2F/5F/6F → 严格沿用真源"三层分工模型"）；`industry_scope` 字段当前是 `str` 而非 `Literal`/`StrEnum`，第 8 轮冻结的是默认值不是枚举集合；亲子装通过现有 `StylingRule` / `scenario` / `topic_library` / `demographic` 承接，无需新增子域。

**3 个一级子域：**

| English（中文释义） | 状态 |
|---|---|
| `menswear`（男装） | `industry_scope=fashion` 已覆盖 / 待补种子数据（估 3 天） |
| `womenswear`（女装） | 已有约 61 条抽取规则在外部抽取目录，尚未结构化入库 |
| `kidswear`（童装） | 待补种子数据（估 2 天，含亲子装 / 成长期调节 / 安全面料） |

**亲子装承接方式**（不单列一级子域，按童装下专题）：`StylingRule`（童装搭配规则补充项）/ `scenario`（家庭亲子场景）/ `topic_library`（家庭亲子话题）/ `demographic`（按年龄段切分）。

**关键产出物**：`industry_scope` 默认 = `fashion`；男 / 女 / 童一级覆盖；亲子装专题承接。
**上游**：第 8 轮裁决 / `base.py:43` 实装 / ADR-068。**下游解除**：Phase 3 Step 3 种子录入节奏；登记 ITR-034 / ITR-035 / ITR-036。

---

### Q17 · 参数级适配 vs 结构级定制

**裁决依据 / 候选取舍**：经验论据（Q5 三档 authenticity_policy 与奢侈/快时尚/运动分野有对应关系）+ 架构论据（Q3 tier 4 档已提供平台级参数分化）+ 工程论据（结构级定制违反 ADR-068 工程收敛精神）。

**四维参数化覆盖品牌分型差异：**

| 维度 | 承接对象 | 来源 Q |
|---|---|---|
| 品牌是谁 | `BrandTone`（一核两阀） | Q5 |
| 谁来讲 | `Persona` + `FounderProfile`（3 通用 Persona + 1 FounderProfile + 7 RoleProfile） | Q4 |
| 在哪讲 | `PlatformAdapter` / `PlatformTone` / `PrivateOutletChannel`（tier 4 档 + 18 × 平台主矩阵） | Q3 |
| 治理边界 | `content_policy`（三档 relaxed / standard / strict） | Q6 |

**触发结构级定制条件（保留为未来裁决）**：某类品牌核心业务对象无法用四维参数表达 / 跨品牌共性新维度 ≥ 3 个且参数化无法承接 / Q19-Q24 暴露参数级适配不足的具体场景。

**关键产出物**：四维参数化承接（不新增 Entity Type）。
**上游**：Q3 / Q4 / Q5 / Q6 / ADR-068。**下游解除**：运动 / 奢侈 / 快时尚 / 设计师品牌的 BrandTone 默认参数预设（承接 Q22）。

---

### Q18 · 首批标配 vs 后续扩展切分线

**裁决依据 / 候选取舍**：首批标配同时满足三条判据；不满足任一条 → 后续扩展。

**3 条判据：**

| # | English（中文释义） | 含义 |
|---|---|---|
| ① | `Universal-Applicable`（全适用） | 所有服装品牌（男 / 女 / 童）都能用 |
| ② | `Cold-Start Buildable`（冷启动可建） | 在冷启动规划既定节奏内可完成种子数据 |
| ③ | `Brand-Independent`（品牌无关） | 不依赖任何品牌私有数据（只靠 global + fashion 知识可跑） |

**L1-L9 首批标配承接对象：**

| Layer | English（中文释义） | 承接对象 |
|---|---|---|
| L1 | `Basic Dictionary`（基础词典） | `Category`（待建类） |
| L2 | `Apparel Professional`（服装专业） | `StylingRule`（待建类，12 条 + 61 条） |
| L3 | `Role Professional`（岗位专业） | `RoleProfile`（已实装） |
| L4 | `Supply Chain`（产业链） | `GlobalKnowledge`（fabric / craft / supply_chain 子类型） |
| L5 | `Scenario / Demographic`（场景人群） | `GlobalKnowledge`（scenario / demographic 子类型，10 类接客场景） |
| L6 | `Content Expression`（内容表达） | `ContentBlueprint` + `GlobalKnowledge`（13 共享叙事引擎） |
| L7 | `Event Narrative`（事件叙事） | `NarrativeArc` + `EnterpriseNarrativeExample` |
| L8 | `Content Output`（内容输出） | `ContentBlueprint` + `PlatformAdapter`（待建类） |
| L9 | `Safety Baseline`（安全底线） | `BrandTone.constraints` + `ComplianceRule`（content_policy 三档） |

**归入「后续扩展」5 项（明确不做）：**

| 项 | 不满足判据 |
|---|---|
| 陈列区位图 | ③（品牌私有空间数据） |
| 动态库存实时拉取 | ②（冷启动 ERP 不接） |
| 跨品牌促销联动 | ③（品牌私有营销逻辑） |
| 地域 · 季节差异化搭配规则 | ②（数据量级超冷启动） |
| 高端定制供应链知识 | ①（仅奢侈 / 高端品牌适用） |

**关键产出物**：3 条判据 + L1-L9 切分清单 + 后续扩展 5 项。
**上游**：Q1 / Q2 / Q4 / Q6 / Q7-Q12 / 冷启动规划九层。**下游解除**：Phase 3 Step 3 种子录入节奏；登记 ITR-034/035/036。

---

## §六 内容扩展组（Q19-Q24）明细

### Q19 · 首批企业事件类型

**裁决依据 / 候选取舍**：甲方案——A 组 10 个对齐方案 §2.2.1 原文示例 / B 组 6 个超出原文示例 → 冷启动锁死 A 组 10 个；品牌级 event_type 扩展点不预留；允许录入 3-5 年前历史事件。

**A 组 10 个 event_type（首批正式启用）：**

| # | English（中文释义） | 喂给 ContentType |
|---|---|---|
| 1 | `ordering_meeting`（订货会） | event_documentary / behind_the_scenes |
| 2 | `product_shooting`（产品拍摄） | behind_the_scenes / product_journey |
| 3 | `fabric_sourcing`（面料选型） | process_trace / product_journey |
| 4 | `sampling_test`（打样测试） | product_journey / process_trace |
| 5 | `quality_inspection`（品控抽检） | process_trace |
| 6 | `warehouse_shipping`（仓储发货） | behind_the_scenes / process_trace |
| 7 | `store_operation`（门店运营） | behind_the_scenes（enterprise 题材侧） |
| 8 | `after_sale_feedback`（售后反馈） | process_trace |
| 9 | `design_review`（设计评审） | product_journey |
| 10 | `production_launch`（量产投产） | product_journey |

**B 组 6 个降级为 ITR-038 待补证（冷启动不启用）：**

| # | English（中文释义） |
|---|---|
| 1 | `founder_speech`（创始人讲话） |
| 2 | `founder_decision`（创始人决策节点） |
| 3 | `role_daily_work`（岗位日常） |
| 4 | `role_achievement`（岗位成就） |
| 5 | `design_inspiration_trip`（采风） |
| 6 | `training_session`（内部培训） |

**种子数据方案 B**：首批种子品牌真实历史 30-60 条；运营协作 + 领域专家整理；登记 ITR-037。

**关键产出物**：`EnterpriseEvent.event_type` 枚举锁定 10 个；ITR-037（种子采集）+ ITR-038（B 组激活）；不新增 Entity Type / schema / ADR。
**上游**：Q1 / Q16-Q18 / 架构 §2.2.1 / ADR-069 命名规范。**下游解除**：Q20（事件是基本单位）+ Phase 3 Step 2 EnterpriseEvent 注册 + Step 4 事件素材消费。

---

### Q20 · 首批叙事弧类型

**裁决依据 / 候选取舍**：甲方案——严格对齐导航索引 §三 Q20 行窄口径（Q1 第二层跨时间故事线 product_journey / process_trace）+ 方案 §2.2.2 原文枚举示例前 2 项；扩展注册机制不在本稿同时设计；未来激活命名占位走独立 ADR + 领域专家评审。

**首批正式注册 2 个 arc_type：**

| # | English（中文释义） | 喂给 |
|---|---|---|
| 1 | `product_journey`（产品旅程） | Q1 第二层 `product_journey` |
| 2 | `process_trace`（流程溯源） | Q1 第二层 `process_trace` |

**非本轮启用命名占位 6 个（冷启动不启用 / 不写入种子数据）：**

| 来源 | English（中文释义） |
|---|---|
| 方案原文预留 | `campaign_record`（活动纪实） |
| 方案原文预留 | `problem_solving`（踩坑解决） |
| Q20 推导 | `role_growth_arc`（岗位成长弧） |
| Q20 推导 | `founder_journey_arc`（创始人历程弧） |
| Q20 推导 | `launch_event_arc`（发布活动弧） |
| Q20 推导 | `making_of_arc`（幕后纪实弧） |

**种子数据方案 B**：每首批 arc_type 2-3 条 / 共 4-6 条 / 登记 ITR-037。

**HAS_STAGE 关系**：阶段数量下限 3 / 上限不设；N:M 关系允许（同一 EnterpriseEvent 可进多个 NarrativeArc）；`HAS_STAGE` 关系边携带 `stage_order`（integer）+ `stage_label`（string）。

**关键产出物**：`NarrativeArc.arc_type` 首批枚举 2 个；HAS_STAGE 关系边属性；阶段下限 3；N:M 关系；不新增 Entity Type / schema / ADR。
**上游**：Q1 第二层 / Q2 / Q18 / Q19 / 架构 §2.2.2。**下游解除**：Phase 3 Step 2 NarrativeArc 接线落库 + Step 4 长叙事生成；依赖 Q19 事件先到位。

---

### Q21 · Persona 情绪光谱定义

**裁决依据 / 候选取舍**：候选 A（Ekman 6 维通用过粗）vs B（Plutchik 24 粒度过细）vs C（服装零售定制覆盖五档：正向 / 专注 / 温情 / 真实 / 禁用）→ 选 C；嵌套规则 Persona/RoleProfile allowed_emotions 必须是 Q5 品牌阀子集 + 不得包含品牌阀 forbidden_emotions。

**情绪词表候选 C（11 词 + 禁用基线 2 词）：**

| 类别 | English（中文释义） |
|---|---|
| 正向基础 | `joy`（喜悦）/ `excitement`（兴奋）/ `anticipation`（期待） |
| 专注向 | `calm`（平静）/ `pride`（自豪）/ `craftsmanship`（匠心） |
| 温情向 | `warmth`（温暖）/ `moved`（感动） |
| 真实向 | `fatigue`（疲惫）/ `resignation`（无奈） |
| 真实向（受限） | `mild_grumble`（克制吐槽，需品牌允许） |
| 禁用基线 | `anger`（愤怒）/ `aggression`（攻击性）（默认禁用，品牌阀值决定） |

**字段结构（沿用方案 line 228-239）：**

| 字段 | English（中文释义） | 类型 |
|---|---|---|
| `emotion` | 情绪 | string（必须是词表中之一） |
| `frequency` | 出现频次 | enum（`daily_base` / `occasional` / `rare`） |
| `intensity_range` | 强度区间 | [float, float]（0.0~1.0） |

**嵌套规则（§2.3）**：Persona/RoleProfile `allowed_emotions` 必须是 Q5 品牌层 `allowed_emotions` 子集 + 不得包含品牌层 `forbidden_emotions`；RoleProfile 必须是所挂接 Persona 子集。

**3 套通用 Persona §三示例光谱：**

| Persona | 日常基调 | 偶尔 | 少见 | 禁用 |
|---|---|---|---|---|
| `store_operator`（门店经营者） | calm | pride / warmth / joy | fatigue / resignation / anticipation | excitement / mild_grumble |
| `styling_advisor`（穿搭顾问） | joy / excitement / warmth | anticipation / moved / calm | fatigue / pride | mild_grumble |
| `product_professional`（商品专业者） | calm / craftsmanship / pride | anticipation / fatigue | joy / moved / warmth | excitement |

**7 RoleProfile 默认继承挂接 Persona**；§四给 2 个示例（`designer` 在 product_professional 基础上 excitement 解禁；`sales_associate` 在 styling_advisor 基础上 fatigue / pride 调为 occasional）；其余 5 个由 ITR-038 按需补齐。

**关键产出物**：服装零售定制情绪词表 11 词 + 禁用基线 2 词；嵌套规则；3 套 Persona 示例光谱；ITR-038（7 RoleProfile 差值）。
**上游**：Q4（字段位预留） / Q5（品牌阀双重约束） / 架构方案 line 228-239。**下游解除**：Phase 3 Step 2 Persona/RoleProfile 种子 + Step 4 ContentGuard 情绪强度检查；不新增 schema / Entity Type / ADR。

---

### Q22 · BrandTone 真实性策略

**裁决依据 / 候选取舍**：候选 B（最简单 / authentic_mixed 命中面最广）vs C（强制自选违反 Q1 开箱即用原则）→ 选 B；候选 A（按品牌类型自动推档）触发 brand_type schema 扩展违反 Q5 §十一"零 schema 变更"纪律 → 移到 §九后续增强。

**6 项裁决：**

| # | 裁决 |
|---|---|
| 1 | 主裁决：候选 B / 系统级默认 = `authentic_mixed` |
| 2 | onboarding 显式提醒："系统已为您默认选择 authentic_mixed，请确认或修改" |
| 3 | 不按 ContentType 差异化：所有 ContentType 共享品牌级档位 |
| 4 | 允许品牌后续改档：是；历史内容兼容性按"改档不回溯、只对后续新内容生效" |
| 5 | §九后续增强方向保留：候选 A 按品牌类型自动推档保留，未来需独立 ADR + `brand_type` schema 扩展 |
| 6 | 三档枚举沿用 Q5 §3.3 定义（不新增枚举值） |

**§九后续增强方向（非当前闭环）按品牌类型映射示例：**

| 品牌类型 | 推荐档位 |
|---|---|
| 高端奢侈 / 强口径控制 | `strict_positive` |
| 主流服装零售 | `authentic_mixed` |
| 独立设计师 / 粗粝风格 / 青年潮牌 | `raw_realistic` |

**关键产出物**：系统级默认 `authentic_mixed`；onboarding 显式提醒规则；ITR-039（onboarding 选档引导 UI）；不新增 schema / Entity Type / ADR。
**上游**：Q5 §3.3（三档枚举）。**下游解除**：Phase 3 Step 2/4 BrandTone 消费 + 品牌 onboarding 选档引导。

---

### Q23 · 双模式审核差异

**裁决依据 / 候选取舍**：候选 A（基础分层）vs B（全面放宽 violates Q6 §二裁决一）vs C（全面收紧 violates Q1 personal 可免审 + 让 brand_hq 被淹没）→ 选 A；b2（按用户实际路径动态切档）依赖 ITR-025 落地，登记 ITR-040 后续激活；品牌级覆盖触发 schema 扩展违反零 schema 纪律。

**3×3 主矩阵：**

| production_mode | content_policy | English（中文释义） |
|---|---|---|
| `personal`（个人创作） | `relaxed` | 宽松 |
| `enterprise`（企业叙事） | `standard` | 标准 |
| `both`（两者均可） | `standard` | 标准（b1 锁定） |

**特殊 ContentType 覆盖（4 项强制 strict）：**

| ContentType | English（中文释义） | 强制档位 |
|---|---|---|
| `founder_ip` | 创始人 IP | strict |
| `process_trace` | 工艺溯源 | strict |
| `event_documentary` | 企业事件纪实 | strict |
| `product_journey` | 产品旅程（高敏感子类） | strict（常规子类保留 standard，粒度由 ContentType 内部元数据承接，登记 ITR-041 配置接入） |

**both 模式**：锁 b1（默认 standard，不做运行时动态切档）；b2 登记 ITR-040 依赖 ITR-025 落地后激活。
**品牌级覆盖**：c1 锁定（系统级矩阵锁死，品牌不可覆盖）；未来另起独立 ADR / 新 Q。

**关键产出物**：3×3 默认矩阵；4 项特殊 ContentType 强制 strict 配置；ITR-040（b2 后续激活）+ ITR-041（特殊 CT strict 覆盖配置）；不新增 schema / Entity Type / ADR。
**上游**：Q1（production_mode 三档） / Q6（content_policy 三档语义）。**下游解除**：Phase 3 Step 4 ContentWriterSkill 运行时分档逻辑 + Step 2 ContentType.default_content_policy 写入。

---

### Q24 · 效果反馈如何回收与升级 ⏸️

**状态**：⏸️ Accepted v1.0 候选 C 延后（Phase 3 不实装，延后 Phase 4/6）

**裁决依据 / 候选取舍**：候选 A（完整半自动）依赖平台 API 对接工程量巨大、归 Phase 4/6；候选 B（最小手动反馈）触及 Gateway API / Memory Core payload contract / 升级阈值属于越层 → 选 C 守三条纪律：Phase 边界纪律 / 契约边界纪律 / 问题定位纪律。

**Phase 3 不做以下任何工程接线**：
- 无效果数据自动回流
- 无手动反馈录入 UI
- 无自动升级 Pipeline
- 不定义任何 Gateway API 端点名 / 不冻结任何 payload contract / 不预先裁决任何 Phase 4 实装细节

**保留为方向性设计参考（未来 Phase 4/6 激活时由独立 ADR + Phase 4 任务卡承接）：**

| 候选 | 性质 | 候选字段 / 形态 |
|---|---|---|
| 候选 B（最小手动反馈 MVP） | 方向性参考 | 反馈数据经 Gateway → Memory Core 写入 `agent_experience`；候选字段 `content_id` / `platform` / `likes/comments/shares/favorites` / `conversion_result`（`no_conversion / inquiry / sale_completed`）/ `self_rating`（1-5）/ `free_text_feedback` |
| 候选 A（完整半自动） | 方向性参考 | 作为 Phase 4/6 成熟阶段目标形态保留 |
| 升级路径架构骨架 | 已定义 | `agent_experience → Promotion Pipeline`（已由 Q1 §四 + ADR-066 定义，实装时机延后） |

**关键产出物**：ITR-042（Q24 反馈闭环 — 延后至 Phase 4/6 实装，本稿为方向性前置文档）；不影响 Q19-Q23 五题独立推进；不影响 Q1 §四 Loop A 闭环方向。
**上游**：Q1-Q6 + Q13-Q15 全体（反馈消费 / 非继承） / ADR-066 / 架构方案 Section 8。**下游解除**：登记 ITR-042 + 状态索引 §4.2 重组为 4.2.A（Q19-Q23）+ 4.2.B（Q24）；不解除任何 Phase 3 工程依赖（Phase 3 不实装）。

---

## §七 上游依赖关系总图

> 摘自 [phase-3-Q19-Q24-导航索引.md §三](phase-3-Q19-Q24-导航索引.md) 防漂移锁 + 各 Q 子稿头部继承段。

| Q | 继承类型 | 上游 Q | 继承的已冻结约束 |
|---|---------|-------|-----------------|
| Q1 | 源头题（无上游 Q） | — | 架构 §2.4 + 03-Skill 层 §5.1 + 02-Knowledge 层 §3.3 + ADR-066 |
| Q2 | 玩法卡片化承接 | Q1 | 18 ContentType + 三层组织 |
| Q3 | 平台维度新增 | Q1 + Q2 + ADR-069 | 18 CT + production_mode；ADR-069 命名规范 |
| Q4 | 人设维度新增 | Q1 + Q2 + Q3 | 18 CT + 跨层；架构 §核心思想方案（Persona 扩展字段） |
| Q5 | 调性维度新增 | Q1 + Q2 + Q3 + Q4 | 一核两阀承接架构方案 §（BrandTone schema 扩展） |
| Q6 | 审核维度新增 | Q1 + Q5 | 18 CT + production_mode + BrandTone constraints；架构方案 §（ContentGuard 6 检查 + 双路径执行流） |
| Q7 | 维度提炼 | Q1 第二层 + Q2 | 库存接客流水线 + 18 份产出物定型 |
| Q8 | 来源优先序 | Q7 + 冷启动规划 | 7 维度 + 现有 61 条规则 |
| Q9 | 陈列单元定义 | Q1 第二层 + Q10 | 6 库存状态对齐 |
| Q10 | 库存深感知 | Q9 + Q12 | 陈列适配 + SKU 校验 |
| Q11 | 培训场景 | Q4 + Q7 + Q9 + Q10 | 7 岗位 + 7 维度 + 6 陈列 + 6 库存 |
| Q12 | 推荐粒度 | Q7 + Q8 + Q10 | 维度 + 规则 + 库存 |
| Q13 | 联动边界 | ADR-073 + Q1-Q6 + Q7-Q12 | 架构契约 |
| Q14 | 触发主从 | ADR-073 + Q13 | trigger_mode 枚举 |
| Q15 | 上下文继承 | ADR-073 + Q6 + Q13 + Q14 | ContentGuard 默认必经 |
| Q16 | 行业边界 | 第 8 轮裁决 + base.py:43 + ADR-068 | industry_scope=fashion 默认值 |
| Q17 | 参数 vs 结构 | Q3 + Q4 + Q5 + Q6 + ADR-068 | 四维参数化 |
| Q18 | 标配切分 | Q1 + Q2 + Q4 + Q6 + Q7-Q12 + 冷启动规划九层 | 三判据 + L1-L9 |
| Q19 | 骨架继承 + 筛选器 | Q1 + Q16-Q18 | 6 enterprise 题材 + industry_scope=fashion + 三判据 |
| Q20 | 骨架继承 + 筛选器 + 基本单位 | Q1 + Q2 + Q18 + Q19 | 第二层跨时间故事线 + 18 玩法卡 + 三判据 + 事件单位 |
| Q21 | 字段预留 + 品牌阀值约束 | Q4 + Q5 | Persona.emotional_spectrum 字段位 + BrandTone.emotional_boundary 上位阀 |
| Q22 | 枚举已预设，选值 | Q5 | authenticity_policy 三档枚举 |
| Q23 | 矩阵两轴 | Q1 + Q6 | production_mode 三档（行）× content_policy 三档（列） |
| Q24 | **反馈消费（非继承）** | Q1-Q6 + Q13-Q15 全体 | 反馈对象（不重写上游骨架） |

---

## §八 真源链接索引

### Q1-Q24 子稿（最高真源）

| Q | 子稿路径 |
|---|---|
| Q1 | [phase-3-Q1-内容生产首批做什么.md](phase-3-Q1-内容生产首批做什么.md) |
| Q2 | [phase-3-Q2-内容产出物长什么样.md](phase-3-Q2-内容产出物长什么样.md) |
| Q3 | [phase-3-Q3-首批平台支持与适配边界.md](phase-3-Q3-首批平台支持与适配边界.md) |
| Q4 | [phase-3-Q4-品牌首批默认启用几套人设.md](phase-3-Q4-品牌首批默认启用几套人设.md) |
| Q5 | [phase-3-Q5-品牌调性管到什么程度.md](phase-3-Q5-品牌调性管到什么程度.md) |
| Q6 | [phase-3-Q6-审核流怎么走.md](phase-3-Q6-审核流怎么走.md) |
| Q7-Q12 | [phase-3-Q7-Q12-陈列搭配能力边界.md](phase-3-Q7-Q12-陈列搭配能力边界.md) |
| Q13-Q15 | [phase-3-Q13-Q15-Skill联动怎么做.md](phase-3-Q13-Q15-Skill联动怎么做.md) |
| Q16-Q18 | [phase-3-Q16-Q18-行业边界与最大公约数能力.md](phase-3-Q16-Q18-行业边界与最大公约数能力.md) |
| Q19 | [phase-3-Q19-首批企业事件类型.md](phase-3-Q19-首批企业事件类型.md) |
| Q20 | [phase-3-Q20-首批叙事弧类型.md](phase-3-Q20-首批叙事弧类型.md) |
| Q21 | [phase-3-Q21-Persona情绪光谱定义.md](phase-3-Q21-Persona情绪光谱定义.md) |
| Q22 | [phase-3-Q22-BrandTone真实性策略.md](phase-3-Q22-BrandTone真实性策略.md) |
| Q23 | [phase-3-Q23-双模式审核差异.md](phase-3-Q23-双模式审核差异.md) |
| Q24 | [phase-3-Q24-效果反馈回收与升级.md](phase-3-Q24-效果反馈回收与升级.md) |

### 治理稿 / 索引稿（更高优先级）

- [phase-3-文档状态索引.md](phase-3-文档状态索引.md) — **全局最高真源**（如本对照表 §一 状态与状态索引冲突，以状态索引为准）
- [phase-3-Q19-Q24-导航索引.md](phase-3-Q19-Q24-导航索引.md) — Q19-Q24 组内统管稿
- [phase-3-真源对齐执行顺序表.md](phase-3-真源对齐执行顺序表.md)

### 关键 ADR

- ADR-066 直传总部
- ADR-068 22 EntityType 收敛至 9 类
- ADR-069 ContentType 命名 + support_level
- ADR-072 Q3 关系建模
- ADR-073 Skill 联动架构契约（Q13-Q15）

---

## §九 接线必闭环登记（十诫 #14）

| 组件 | 消费方 | 状态 |
|------|--------|------|
| 本对照表（Q1-Q24 派生汇总） | 跨题查阅 / 培训新人 / 工程开工前对照 | **待接入** — 落盘后建议在 [phase-3-文档状态索引.md](phase-3-文档状态索引.md) 加入引用条目；本稿不反向修改任何 Q 子稿 |

**冲突处理纪律：**
1. 本对照表与 Q1-Q24 子稿冲突 → 以子稿为准，本稿同步修正
2. 本对照表与 [phase-3-文档状态索引.md](phase-3-文档状态索引.md) 状态字段冲突 → 以状态索引为准
3. 本对照表与 [phase-3-Q19-Q24-导航索引.md](phase-3-Q19-Q24-导航索引.md) §三 承接关系表冲突 → 以导航索引为准

---

## §十 一句话总结

> **Q1-Q24 = 6 题内容骨架 + 6 题陈列搭配 + 3 题 Skill 联动 + 3 题行业边界 + 5 题继承补全 + 1 题反馈消费（延后）；本对照表把 24 题压成 1 张索引 + 5 张分组明细，所有英文标识符附中文释义，所有枚举裁决（如 18 个 ContentType / 12 个平台 / 7 个判断维度 / 12 条搭配规则 / 10 个 event_type）逐项列出，方便查阅和培训。**

---

**对照表维护方：** 落盘后由 Q1-Q24 任一题更新时同步修正本稿；如 Q1-Q18 出现新一轮裁决，§一 顶层表 + 对应分组明细必须同步更新。











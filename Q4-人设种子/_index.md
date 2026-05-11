# Q4 人设交付物模板索引

> **位置：** `docs/planning/人设交付物模板/`
> **创建日期：** 2026-04-15
> **对应路线图问题：** Q4 — 品牌首批默认启用几套人设
> **本工作区性质：** Q4 主裁决稿 + 5 份支撑文档的物理收纳目录，命名参考 [Q2 内容类型交付物模板](../内容类型交付物模板/) 风格。

---

## 1. Q4 主裁决稿是唯一业务口径入口

[phase-3-Q4-品牌首批默认启用几套人设.md](../phase-3-Q4-品牌首批默认启用几套人设.md) — 本工作区唯一的正式裁决文档。所有口径冻结、命名选定、范围声明、冷启动产物清单都在这里。

兼容矩阵粒度的真源口径冻结为 **"一层真源 + 一层派生视图"**（见该稿 §3.1）—— Q4 唯一新建立的关系真源是 `(:Persona)-[:COMPATIBLE_WITH {support, risk, reason}]->(:ContentType)`，平台维度承接 Q3 已建立的 `(:System)-[:SUPPORTS_PLATFORM {tier}]->(:PlatformTone / :PrivateOutletChannel)`，**不在 Q4 新建 `ContentType × Platform` 关系边**。本工作区其他 5 份支撑文档全部以此口径为准。

---

## 2. 三套 Persona 卡片 + RoleProfile 清单是对象真源

- [phase-3-Q4-首批Persona-RoleProfile清单.md](phase-3-Q4-首批Persona-RoleProfile清单.md) — 1 个 `FounderProfile`（创始人画像）+ 3 个通用 `Persona`（`store_operator` / `styling_advisor` / `product_professional`）+ 7 个 `RoleProfile`（首批岗位画像）+ 4-2-1 挂接关系总表
- [phase-3-Q4-三套通用Persona首批卡片.md](phase-3-Q4-三套通用Persona首批卡片.md) — 三套通用 Persona 完整字段卡片（`role_type` / `life_archetype` / `emotional_spectrum` / `authenticity_anchors` / `topic_scope` / `typical_scenarios`）

这两份是 Q4 体系的对象层真源。对象命名 / 数量 / 挂接关系一旦冻结，所有下游消费（Step 2 Entity Type 注册 / Step 3 种子数据导入 / Skill 层能力发现）都以这两份为准。

---

## 3. 矩阵 / 素材 / 参数是功能支撑文档

- [phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md](phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md) — 54 条 `Persona × ContentType` 真源兼容边（3 Persona × 18 ContentType）+ 派生视图组合规则 + 4 档运营展示档
- [phase-3-Q4-首批岗位知识素材清单.md](phase-3-Q4-首批岗位知识素材清单.md) — 7 个 `RoleProfile` 的素材采集执行清单（每岗 5 类素材 / 3 个硬证据 + 4 类证据形态 + P0/P1 优先级）
- [phase-3-Q4-参数级填充清单.md](phase-3-Q4-参数级填充清单.md) — 已冻结 / 候选待填 / 待补证 三档参数总表 + 4 方接力清单（内容运营 / 知识工程 / 技术实现 / 业务专家）

这三份是技术 / 知识工程 / 内容运营 / 业务专家 4 方的接力实施依据，由主裁决稿引用其内容作为参数填充实施依据。

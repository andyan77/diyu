# GAP 裁决建议（专家视角）

> 作者视角：知识工程 + 服装品牌运营 + IP 内容运营三栈交叉判断
> 仅供裁决参考，最终决议由品牌主拍板

---

## GAP-001 · MerchandisingSkill — 推荐 **C（接 RoleProfile）**

### 核心判断

服装零售里的"陈列搭配技能"不是独立资产，所有商业价值都依附于"谁该会"。
这跟 SaaS HR 系统里的 Skill 有根本区别——HR 系统里 Skill 有市场价值（招聘、定价、采购培训），需要独立对象；门店运营里"陈列技能"脱离岗位毫无意义。

### 为什么不选 A（独立 Skill 对象）

- 开"为新概念加对象"的口子，今后 Tone / Aesthetic / SalesTalk 一连串候选会挤进白名单
- 没有真实查询场景需要 `SELECT * FROM skill`——真实查询都是"店长该掌握什么"
- 加一个对象 = 加一类 ETL / 索引 / 生命周期，运营成本远超语义收益

### 为什么不选 B（并入 TrainingMaterial）

- 培训材料是教学侧载体（SOP / 视频 / 手册），技能是达成的能力——1:N 关系
- 同一个"主推动线陈列"技能可能由 3 份培训材料覆盖（新人 / 资深 / 复盘）

### 为什么 C 对

- RoleProfile 加 `required_skills[]` 字段（value_set 是技能枚举）天然解决"谁该会"
- 培训材料→RoleProfile 通过现有白名单关系 `supports_training` 链接
- 14 项关系白名单不破 + 18 项对象白名单不破 = 真正"按现有结构表达"

### 回填动作

1. 02_field 加 `FD-RoleProfile-required_skills`（domain_general）
2. 04_value_set 加 `VS-RoleProfile-required_skills`（具体技能取值，如 `主陈列动线`、`断码救场组合`、`季节叙事陈列`）
3. 已有 TrainingMaterial 包用现成 `supports_training` 关系挂回去


---

## GAP-004 · FounderProfile — 推荐 **B + 多租户分层（不是 A/B/C 三选一）**

### 核心判断

DTC 服装品牌里**创始人 IP 是核心商业资产**——不是可有可无的画像。
茑屋的增田宗昭、内外的刘小璐、观夏的沈黎都是同样的结构。
**"创始人画像"是品类（domain_general），"笛语创始人"是该品类的具体取值（brand_faye）**——这正是多租户分层的教科书案例。

### 为什么 A（Persona 子类）错

- 素材已显式说明"不进 persona_id"——品牌主的明确意志，agent 不能违逆
- Persona 是品牌**对外打造的角色**（店员/达人/虚拟代言），可变；FounderProfile 是**真人锚点**，不可变
- 强行做子类污染 Persona 字段壳

### 为什么 C（仅 brand_faye 私有 schema）不够

- 等于让"创始人画像"这个**品类本身**只在笛语存在——其他品牌要重新发明字段壳
- 违反 CLAUDE.md §1 反偷换警告："Schema 元规则属 domain_general，具体取值属 brand_faye"
- schema 元规则被错降到品牌层 = 典型多租户隔离纪律错误

### 正解：B + 严格双层落档

| 落档对象 | brand_layer | 内容 |
|---|---|---|
| `FounderProfile` 升 19 项白名单 | domain_general | 对象类型 + 9 字段壳定义 |
| 9 字段 schema（founder_name / value_system / origin_story…） | domain_general | 任何品牌都可填 |
| value_set（如 origin_story 的 narrative_subtypes） | domain_general | 跨品牌通用 |
| 笛语创始人具体值 | brand_faye | 笛语专属 |

brand_xyz 应用 SELECT 能直接复用 schema，不必重造字段壳。

### 关键原则

白名单不是不能扩，是"扩之前要论证扩展是不是 schema 元规则层级的通用品类"：
- **FounderProfile 满足**：任意 DTC 品牌都需要 → 可扩
- **MerchandisingSkill 不满足**：技能在零售里不是品类、是岗位属性 → 不可扩

### 回填动作

1. 18 项对象白名单 → 19 项，新增 `FounderProfile`
2. 02_field 加 9 行 founder 字段壳（全 domain_general）
3. 03_semantic / 04_value_set 加通用语义 + 取值集（domain_general）
4. 笛语创始人具体值 yaml → 落 brand_faye，引用上述 schema

---

## GAP-005 · COMPATIBLE_WITH — 强烈推荐 **B（properties_json）**

### 核心判断

schema 已经为这个场景准备好了答案，只是 agent 没看见。
05_relation 表本就有 `properties_json` 列，**存在的唯一目的**就是承接"关系自身带属性"——这是图数据库 day-1 设计模式（reified relation）。

### 为什么 A（升关系为对象）严重错

- 14 项关系白名单和 18 项对象白名单是**有意识对立**的两套语义：关系描述边、对象描述节点
- 把 COMPATIBLE_WITH 升对象 = 把"边"升"节点"，破坏 schema 根本分层
- CLAUDE.md §1.3 反偷换警告明确禁止
- 后续查询"Persona X 兼容哪些 ContentType"要先 JOIN 伪节点表，绕路且慢

### 为什么 C（拆字段到两侧）丢信息

- support / risk / reason 是**关系本身的属性**（"在这一条匹配里支持是什么、风险是什么"），不是 Persona 或 ContentType 各自的属性
- 同一 Persona 跟 ContentType-A 兼容 support="X"，跟 ContentType-B 兼容 support="Y"——拆到 Persona 侧无处安放
- 信息论上等于二维压一维，必然丢

### 为什么 B 是教科书答案

| 维度 | B 得分 |
|---|---|
| schema 内建支持 | ✅ properties_json 就是为此而设 |
| 14 项关系白名单 | ✅ 复用现有 `compatible_with_content_type` |
| 18 项对象白名单 | ✅ 不动 |
| 信息无损 | ✅ JSON 完整保留三字段 |
| 查询便利 | ⚠️ 需 `json_extract()`，标准操作 |

唯一代价是 `json_extract(properties_json, '$.support')`——远小于另两个方案的结构代价。

### 回填动作

1. 14 项关系白名单**不变**，使用现有 `compatible_with_content_type`
2. 05_relation 加 N 行（每条 Persona×ContentType 兼容一行），properties_json 装 `{"support":"...","risk":"...","reason":"..."}`
3. stage4 已删的 6 行只留备份，不再考虑路径 A
4. schema 注释加一句：`relation.properties_json` 为关系级属性载体

---

## GAP-006 · DerivedView — 推荐 **A1（加一项关系白名单）+ SQL VIEW**

### 核心判断

派生视图是**真实的运营查询入口**——内容运营每周问"达人小A 适合在抖音发哪种 ContentType"。
但**绝不能**把它当源表落 9 表（典型反范式：数据冗余、更新难、单一真源被破坏）。

### 真正的卡点

不在派生视图，在 **Persona-Platform / ContentType-Platform 这两条边的关系类型在 14 项白名单里没有合适词**。
GAP-005 的 `compatible_with_content_type` 只覆盖 Persona-ContentType。

### 推荐 A1：14 项 → 15 项，加 `fits_platform_tone`

判定标准跟 FounderProfile 一样——**任何品牌都需要的关系类型**（任何品牌的内容运营都要决定"什么内容上什么平台"），属 schema 元规则层。

### 同时 storage 加 SQL VIEW

```sql
-- 派生视图：内容生成入口
CREATE VIEW v_persona_content_platform_compat AS
SELECT
  p.source_id AS persona_id,
  c.target_id AS content_type_id,
  pt.target_id AS platform_tone_id,
  json_extract(p.properties_json,'$.support') AS pc_support,
  json_extract(c.properties_json,'$.support') AS cp_support
FROM relation p
JOIN relation c ON p.source_id = c.source_id
JOIN relation pt ON c.target_id = pt.source_id
WHERE p.relation_kind = 'compatible_with_content_type'
  AND c.relation_kind = 'fits_platform_tone';
```

### 收益

- 三向关系完整入 9 表，单一真源
- 派生视图作查询时计算落 storage，运营调用一句 SELECT 即可
- reconcile "正交建模 + 视图查询"

### 回填动作

1. 14 项关系白名单 → 15 项，加 `fits_platform_tone`
2. 05_relation 加：Persona→PlatformTone / ContentType→PlatformTone 两批边
3. storage/single_db_logical_isolation.sql 末尾加 v_persona_content_platform_compat VIEW
4. schema/nine_tables.schema.json 同步更新 relation_kind_enum

---

## 总结 · 4 GAP 联动决议地图

| GAP | 推荐 | 是否扩白名单 | 影响 brand_layer | 工程量 |
|---|---|---|---|---|
| GAP-001 Skill | C 接 RoleProfile | ❌ 不扩 | domain_general | 小 |
| GAP-004 FounderProfile | B + 双层 | ✅ 18→19 对象 | domain_general schema + brand_faye 取值 | 中 |
| GAP-005 COMPATIBLE_WITH | B properties_json | ❌ 不扩 | domain_general | 小 |
| GAP-006 DerivedView | A1 + SQL VIEW | ✅ 14→15 关系 | domain_general | 中 |

### 两条共通判定原则（方法论）

**1. 白名单扩展的"品类性测试"**：候选概念是不是任意同类品牌都需要？

- FounderProfile ✅ 是品类（茑屋/内外/观夏都需要）→ 可扩
- fits_platform_tone ✅ 是品类（任何内容运营都要做平台适配）→ 可扩
- Skill ❌ 是岗位属性（依附 RoleProfile 才有意义）→ 不扩
- COMPATIBLE_WITH ❌ 是关系不是对象（schema 已有承载）→ 不扩

**2. Schema 元规则与具体取值的强制分层**：

- 元规则（字段壳、关系类型、对象类型）= **必须 domain_general**
- 具体取值（笛语创始人故事、笛语兼容矩阵权重）= **brand_faye**
- 这正是 prompt §1 多租户隔离硬纪律的精确执行

### 建议执行顺序

1. **第一波（最小扩展）**：GAP-005 properties_json 回填 + GAP-001 RoleProfile.required_skills 加字段——不破白名单
2. **第二波（白名单扩展）**：GAP-004 加 FounderProfile 第 19 项 + GAP-006 加 fits_platform_tone 第 15 项——同步更新 18/14 项白名单 + schema enum + DDL
3. **第三波（VIEW + brand_faye 落档）**：加 SQL VIEW + 落笛语创始人具体值到 brand_faye

### 最重要的非工程提醒

**GAP-004 的处理方式会决定本仓未来对其他 DTC 品牌的可复用性。**

- 选 B + 双层：今后接 brand_xyz 创始人画像直接复用 schema
- 选 C：每个品牌都要重造字段壳，多租户隔离纪律名存实亡

这一条不是技术裁决，是**架构资产决策**——建议优先级最高。

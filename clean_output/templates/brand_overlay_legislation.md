# 品牌专属 Overlay 扩容立法（W12/W13 补丁）

> 状态：立法草案 · 是 CLAUDE.md §3.5 的明示扩展，不破坏既有红线
> 适用：所有 `brand_layer = brand_<name>` 的候选包

---

## 一、为什么补这条立法

CLAUDE.md §3.5 原始定义把 `brand_<name>` 限定为两类：
1. 品牌调性
2. 创始人画像

W13.A 引入笛语 7 份 brand-only 源料后发现：现实中品牌专属内容**还有两类**和 §3.5 同等重要，且仅适用于该品牌：

- **品牌专属团队 Persona**（如笛语样衣师、加盟店主、店长）——他们的人格 anchor 是品牌私有，不可跨品牌复用
- **品牌专属 ContentType overlay**（如笛语创始人 IP 规格、流程溯源规格）——同名 ContentType 在不同品牌的输出结构、钩子、平台目标都不同

这两类强行塞 `domain_general` 会污染通用库（每抽一个品牌的样衣师就要在通用库新增一行）；强行塞既有 §3.5 两类又不符合（既不是调性也不是创始人画像）。

所以扩容立法。

---

## 二、扩容后的 4 类 brand_<name> 内容

`brand_<name>` 严格仅限以下 4 类：

| 类别 | 含义 | 判别要诀 |
|---|---|---|
| **A. 品牌调性** | 语气/情绪/词汇/句式/平台调性 | 内容只能是这一个品牌的语气，换品牌必须重写 |
| **B. 创始人画像** | 创始人个人 Persona、签名短语、价值观锚点 | 创始人换人必须重写 |
| **C. 品牌专属团队 Persona**（W13 新增）| 该品牌内部团队成员（样衣师 / 加盟店主 / 店长 / 导购等）的真人格画像 | 换品牌团队完全不同的真实细节（生活原型 / 情绪谱 / authenticity_anchors / speaking_habits）|
| **D. 品牌专属 ContentType overlay**（W13 新增）| 该品牌对某个 ContentType 的私有 output_structure / required_knowledge / typical_hooks / ab_variants_hint | 同名 ContentType 在不同品牌的"怎么写"完全不同 |

> 注：C/D 不替代 domain_general 的 schema 元规则。
> "什么是 brand_founder Persona schema"是 `domain_general`；
> "笛语品牌的 brand_founder 真人格画像取值"是 `brand_<name>`。
> 同样：
> "什么是 ctype_founder_ip 设计原则"可作为 `domain_general` schema 元规则；
> "笛语对 ctype_founder_ip 的具体 output_structure / hooks / ab_variants 取值"是 `brand_<name>` overlay。

---

## 三、判别流程（4 步法）

每个候选包按下序判别：

1. **是否落在 §一中 7 + Schema 元规则共 8 类 domain_general 通用范畴？** 是 → `domain_general`
2. **是否是 A 品牌调性？** 是 → `brand_<name>`（type=brand_voice）
3. **是否是 B 创始人画像？** 是 → `brand_<name>`（type=founder_persona）
4. **是否是 C 品牌专属团队 Persona？** 是 → `brand_<name>`（type=team_persona_overlay）
5. **是否是 D 品牌专属 ContentType overlay？** 是 → `brand_<name>`（type=content_type_overlay）
6. 否 → `needs_review`

---

## 四、反偷换警告（防止扩容被滥用）

❌ 不许把"行业通用 ContentType 设计原则"标 D 品牌专属（如"output_structure 三段制本身"是 domain_general schema，不是 D；只有"笛语版本的字数 / hooks / examples 取值"才是 D）

❌ 不许把"行业通用岗位画像"标 C 品牌专属（如"什么是样衣师"是 domain_general schema；只有"笛语样衣师 38-48 岁、家里常备老花镜护手霜针线盒、说'这地方不对'"等真人格细节才是 C）

❌ 不许把"内容写作规范 / 4 闸 / 9 表 schema"等元层规则塞进 brand_<name>（这些是 domain_general 永远不变的部分）

---

## 五、9 表存储与查询的影响

不影响 9 表数量、不影响 4 闸判定、不影响 brand_layer GLOB CHECK。

| 字段 | 取值 |
|---|---|
| brand_layer | `domain_general` / `brand_<name>` / `needs_review`（不变）|
| pack_type | 仍 prompt §13 8 类白名单（不动）|
| 新增 yaml 顶部可选字段 | `brand_overlay_kind: brand_voice / founder_persona / team_persona_overlay / content_type_overlay`（仅 brand_<name> 行可填）|

查询模式不变：
- 笛语应用：`WHERE brand_layer IN ('domain_general', 'brand_faye')`
- xyz 应用：`WHERE brand_layer IN ('domain_general', 'brand_xyz')`

---

## 六、与 W13.A 七份候选的对应

按本立法 4 类判别：

| pack | 类别 | 升 brand_faye 资格 |
|---|---|:---:|
| KP-product_attribute-faye-brand-tone-core | A 品牌调性 | ✅ 立即可升 |
| KP-product_attribute-faye-persona-founder | B 创始人画像 | ✅ 立即可升 |
| KP-product_attribute-faye-persona-franchise-owner | C 团队 Persona overlay | ✅ 立法后可升 |
| KP-product_attribute-faye-persona-sample-maker | C 团队 Persona overlay | ✅ 立法后可升 |
| KP-training_unit-faye-ctype-founder-ip | D ContentType overlay | ✅ 立法后可升 |
| KP-training_unit-faye-ctype-process-trace | D ContentType overlay | ✅ 立法后可升 |
| KP-training_unit-faye-ctype-store-daily | D ContentType overlay | ✅ 立法后可升 |

本立法生效后，7 份全部具备 brand_faye 升级资格。

---

## 七、立法生效条件

- 本文档落盘 ✅
- 与 CLAUDE.md §3.5 的关系：本文档是 §3.5 的**明示扩展**，不撤销原 2 类，仅新增 C/D 两类
- 后续如发现 4 类不够覆盖，须在本文档追加，禁止 ad-hoc 越界
- reviewer 在下次正式审查时确认本立法是否合理；如不合理，5 份 C/D 可降回 needs_review

时间戳：2026-05-04

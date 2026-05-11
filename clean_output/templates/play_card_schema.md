# L2 玩法卡 schema · W12 立法

> 状态：W12.0 立法版 · 与 W11 `granularity_layer_framework.md` 字段口径对齐
> 适用：所有 `granularity_layer: L2` 的 pack（B-lite 决议下不进 9 表 schema，登记到 `play_cards/play_card_register.csv`）

---

## 一、必填字段（W11 基线 + W12 业务扩展）

### A. W11 基线字段（继承自 `granularity_layer_framework.md`，G19 已强制）

| 字段 | 取值 | 说明 |
|---|---|---|
| `granularity_layer` | `L2` | 三层粒度标识 |
| `consumption_purpose` | `generation` | 用途——生成选题/脚本骨架 |
| `production_difficulty` | `low` / `medium` / `high` | 实拍难度 |
| `production_tier` | `instant` / `long_term` / `brand_tier` | 资源约束分级 |
| `resource_baseline` | 字符串，例 `1人+手机+200元+4h` | 资源基线，与 tier 对齐：<br>- instant → `1人+手机+200元+4h`<br>- long_term → `2-3人+轻设备+1000元+1-2天`<br>- brand_tier → `专业团队+品牌资源+不限` |
| `default_call_pool` | `true` / `false` | 是否进默认调用池（instant 默认 true） |

### B. W12 玩法卡业务字段

| 字段 | 取值 | 说明 |
|---|---|---|
| `hook` | 字符串 ≥10 字 | 钩子/北极星：观众一句话总结的"为什么会停下来看" |
| `steps` | 列表 ≥2 项 | 玩法步骤（如 ["开场 5 秒抛悬念","中段揭示","结尾留白"]）|
| `anti_pattern` | 字符串 ≥10 字 | 翻车模式：什么样的拍法是错的 |
| `duration` | `short` (<30s) / `medium` (30-90s) / `long` (>90s) | 视频时长档位 |
| `audience` | 字符串 ≥6 字 | 目标观众（"想买衣服的年轻人 / 关注品牌故事的中产..."）|
| `source_pack_id` | string | 反查 9 表的关联键，必须是 candidates/ 下存在的 pack_id |

---

## 二、yaml 写入位置（不破坏现有结构）

W11 已在每个 yaml 顶部注入 `granularity_layer: L2` + `production_tier` + `default_call_pool`。W12 在其后追加 `play_card:` 块：

```yaml
pack_id: KP-...
granularity_layer: L2
production_tier: instant
default_call_pool: true
schema_version: candidate_v1
pack_type: training_unit
brand_layer: domain_general
state: drafted

play_card:
  consumption_purpose: generation
  production_difficulty: low
  resource_baseline: "1人+手机+200元+4h"
  hook: "用幽默做认知翻面，让观众笑完发现自己想错了"
  steps:
    - "开场 5 秒抛荒诞前提"
    - "用动作展示而不是用嘴解释"
    - "结尾翻面，观众自己悟出真意"
  anti_pattern: "套热门音频做表情反应"
  duration: short
  audience: "刷段子但希望刷到有营养内容的年轻人"
  source_pack_id: KP-...

knowledge_assertion: ...
```

> 注：W12 不动任何已有顶部字段（`pack_id / pack_type / brand_layer / state / knowledge_assertion / ...`）。`play_card:` 块是新增旁路，不进 9 表。

---

## 三、play_card_register.csv 列定义

`clean_output/play_cards/play_card_register.csv`：每个 L2 pack 一行。

```
play_card_id, pack_id, granularity_layer, consumption_purpose,
production_difficulty, production_tier, resource_baseline, default_call_pool,
hook, steps_count, anti_pattern, duration, audience,
source_pack_id, source_md, brand_layer
```

`play_card_id` = `PC-` + pack_id 后缀（如 `PC-styling_rule-old-sample-as-error-archive`）。  
`steps` 列表序列化为 JSON 字符串存 yaml；register 仅存 `steps_count`（≥2）便于查询。

---

## 四、resource_baseline 自动派生规则

为减少人工填写量，`resource_baseline` 可从 `production_tier` 派生：

| production_tier | resource_baseline 默认值 |
|---|---|
| instant | `1人+手机+200元+4h` |
| long_term | `2-3人+轻设备+1000元+1-2天` |
| brand_tier | `专业团队+品牌资源+不限` |

人工可覆盖（如某 instant 玩法实测需要 `1人+手机+0元+2h`）。

---

## 五、production_difficulty 与 production_tier 的关系

不重复——前者是"拍这条玩法的实操门槛"，后者是"资源约束分级"。

| 组合 | 含义 |
|---|---|
| difficulty=low + tier=instant | 上手简单且不需投入（推荐入默认调用池）|
| difficulty=high + tier=instant | 资源极简但需要熟练度（如"安静跟拍不解释动机"）|
| difficulty=low + tier=long_term | 操作不难但要投入时间或人力 |
| difficulty=high + tier=brand_tier | 大制作（罕见） |

W12.A 验收时，每个 L2 pack 必须显式填写两个字段，不允许默认。

---

## 六、G20 硬门契约

`scripts/check_play_card.py` 校验：

1. 每个 `granularity_layer: L2` pack 的 yaml 必须含完整 `play_card:` 块
2. `play_card_register.csv` 行数 == L2 pack 总数（当前 29）
3. 必填字段（W11 基线 6 + W12 业务 6 = 12 字段）任一缺失或非法 → 红
4. `source_pack_id` 必须能在 candidates/ 找到（FK 一致性）
5. `play_card_id` 唯一
6. 失败仅写 `audit/_process/g20_violations.csv`，不动业务产物

---

## 七、与 W11 G19 的关系

G19 校验：source_unit + pack 的 `final_layer` / `final_status` 完整性  
G20 校验：L2 pack 的玩法卡业务字段完整性

两者关注点不同，互不覆盖：
- G19 红 ⊥ G20 绿：layer 标对了，但玩法卡业务字段没填
- G19 绿 ⊥ G20 红：业务字段填了，但 layer 没标 L2

W12.A 验收口径：G19 + G20 同时绿。

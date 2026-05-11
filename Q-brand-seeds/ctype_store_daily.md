---
source_workspace: diyu-infra-05/data/mvp/seeds
source_path: diyu-infra-05/data/mvp/seeds/content_type/ctype_store_daily.json
entity_id: ctype_store_daily
entity_type: ContentType
visibility: brand
brand_id: diyu_001
imported_at: 2026-05-04
import_decision: clean_output/audit/_process/cross_workspace_import_decision.md
---

# 门店日常真实内容（store daily authentic content / 门店日常真实内容）

> entity_id: `ctype_store_daily` · entity_type: `ContentType` · visibility: `brand`

## source

- **type**: founder_input
- **ref**: memory §10.11 + 创始人规划 + 门店场景设想 + 2026-04-14 本轮补全
### reviewer

- 安映华
- 林静文

- **reviewed_at**: 2026-04-14

## content_type_id

ctype_store_daily

## display_name

门店日常真实内容（store daily authentic content / 门店日常真实内容）

## layer

traffic_acquisition

## production_mode

llm_assist_human_edit

## support_level

full

## required_knowledge


- **entity_type**: BrandTone
- **min_count**: 1
- **purpose**: 保证门店日常内容虽然口语、轻、快，但仍然符合笛语品牌的真实、温柔、有生活感的表达边界，不滑向促销广播。（ensure store-daily content, though colloquial, light and quick, stays within laidiyu's authentic-gentle-life-flavored expression boundary — never sliding into promotional broadcasting / 保证门店日常内容虽然口语、轻、快，但仍然符合笛语品牌的真实、温柔、有生活感的表达边界，不滑向促销广播。）

- **entity_type**: Persona
- **min_count**: 1
- **purpose**: 运行时优先绑定 store_staff 类型 Persona，读取店长/导购的一线说话口气、情绪起伏和现场判断；若当前 K-DATA-01 仍以 franchise_owner 为主，则由后续门店一线 Persona 补足。（at runtime, preferentially bind a store_staff Persona for first-line voice, emotional shifts and on-site judgment from store managers/sales associates; if K-DATA-01 currently still has franchise_owner as primary, later store-floor Persona will fill the gap / 运行时优先绑定 store_staff 类型 Persona，读取店长/导购的一线说话口气、情绪起伏和现场判断；若当前 K-DATA-01 仍以 franchise_owner 为主，则由后续门店一线 Persona 补足。）

- **entity_type**: RoleProfile
- **min_count**: 1
- **purpose**: 读取店长、导购、陈列、收银等门店岗位的动作、服务话术和现场判断，让门店日常不只是'有客人来了'，而是'有人在认真接住这家店'。（read actions, service phrasing and on-site judgment from store-manager, sales-associate, display and cashier roles so store-daily is not merely 'a customer walked in' but 'someone is truly holding this store together' / 读取店长、导购、陈列、收银等门店岗位的动作、服务话术和现场判断，让门店日常不只是'有客人来了'，而是'有人在认真接住这家店'。）

## output_structure

- **format**: 短图文 / 朋友圈文案 / 短视频配文（short illustrated post / WeChat Moments copy / short video caption / 短图文 / 朋友圈文案 / 短视频配文）
### length_range

- 100
- 400

### sections


- **name**: 门店瞬间（store moment / 门店瞬间）
- **purpose**: 抓一个具体瞬间开场，比如开门、试衣、熟客带娃、补货、收工前最后一次整理，而不是抽象说今天很忙。（open with a specific moment — opening up, fitting, regular bringing a child, restocking, last tidy-up before closing — rather than abstract claims like 'today was busy' / 抓一个具体瞬间开场，比如开门、试衣、熟客带娃、补货、收工前最后一次整理，而不是抽象说今天很忙。）
- **word_budget**: 80

- **name**: 现场判断（on-site judgment / 现场判断）
- **purpose**: 讲清当时门店里的人看见了什么、怎么判断、为什么这样做，突出线下不可见的专业和人情分寸。（show what the people in the store saw, how they judged, why they did what they did — highlighting the offline-invisible professionalism and human-touch sense of proportion / 讲清当时门店里的人看见了什么、怎么判断、为什么这样做，突出线下不可见的专业和人情分寸。）
- **word_budget**: 110

- **name**: 余味落点（lingering note / 余味落点）
- **purpose**: 落回真实经营体温、熟客关系、孩子上身反馈、门店秩序感或今天的小小情绪，不强行上价值。（land back to the warmth of real operations, regular-customer relationships, child fit-feedback, store orderliness or today's small emotion — never forced value-elevation / 落回真实经营体温、熟客关系、孩子上身反馈、门店秩序感或今天的小小情绪，不强行上价值。）
- **word_budget**: 70


## review_level

brand_review

## platform_targets

- wechat_moments
- douyin

## ab_variants_hint

A版偏'空间氛围'，强调声音、光线、秩序和店的体温；B版偏'人物关系'，强调熟客、孩子、店员判断、试衣间瞬间。两版都不要把门店拍成促销货架扫拍。（version A leans toward 'spatial atmosphere', emphasizing sounds, light, order and the store's body temperature; version B leans toward 'human relationships', emphasizing regulars, children, staff judgment and fitting-room moments; both must avoid filming the store like a promotional shelf sweep / A版偏'空间氛围'，强调声音、光线、秩序和店的体温；B版偏'人物关系'，强调熟客、孩子、店员判断、试衣间瞬间。两版都不要把门店拍成促销货架扫拍。）

## example_references

- 开门前10分钟：卷帘门、灯光、蒸汽、第一杯水、第一件被扶正的衣服，让门店像一个活的空间。（the 10 minutes before opening: rolling shutter, lights, steam, first cup of water, first garment straightened — making the store feel like a living space / 开门前10分钟：卷帘门、灯光、蒸汽、第一杯水、第一件被扶正的衣服，让门店像一个活的空间。）
- 今天差点出什么事：比如尺码断了、橱窗不顺眼、试衣间灯太黄、客人临时改主意，记录问题如何被修掉。（what almost went wrong today: a sold-out size, an off-looking window, a too-yellow fitting room light, a customer who changed her mind — record how the problem got fixed / 今天差点出什么事：比如尺码断了、橱窗不顺眼、试衣间灯太黄、客人临时改主意，记录问题如何被修掉。）
- 熟客带孩子来店里：不是拍成交，而是拍店员怎么记住孩子年级、颜色偏好、上身反应。（regulars bring their children to the store: don't film the transaction; film how staff remember the child's grade, color preferences, fit reactions / 熟客带孩子来店里：不是拍成交，而是拍店员怎么记住孩子年级、颜色偏好、上身反应。）
- 雨天的店：门口脚垫、湿掉的伞、试衣间门帘、关灯前最后一排衣架，做成有情绪的门店日记。（the store on a rainy day: door mat, wet umbrella, fitting room curtain, last row of hangers before lights-out — turn it into an emotional store diary / 雨天的店：门口脚垫、湿掉的伞、试衣间门帘、关灯前最后一排衣架，做成有情绪的门店日记。）
- 店的声纹：卷帘门、门铃、衣架、扫码、纸袋摩擦、拉链、关灯，10个声音组成一条内容。（the store's sound print: rolling shutter, doorbell, hangers, barcode beep, paper bag rustle, zipper, lights-off — ten sounds composing a single piece of content / 店的声纹：卷帘门、门铃、衣架、扫码、纸袋摩擦、拉链、关灯，10个声音组成一条内容。）

## season_relevance

很高。春夏上新、秋冬换季、开学季、节庆陈列、周末人流、雨雪天气、放假节点，都能自然触发门店日常；这是最容易做连续更新的 ContentType。（very high relevance: spring/summer launches, fall/winter transitions, back-to-school, holiday displays, weekend traffic, rain/snow weather, vacation moments all naturally trigger store-daily content; this is the easiest ContentType for continuous updates / 很高。春夏上新、秋冬换季、开学季、节庆陈列、周末人流、雨雪天气、放假节点，都能自然触发门店日常；这是最容易做连续更新的 ContentType。）

## typical_ctas

- 你要是路过门口，进来先试一试，不着急决定。（if you pass by the door, come in and try first, no rush to decide / 你要是路过门口，进来先试一试，不着急决定。）
- 带孩子来的话，先让他上身走两步，我们再说。（if you bring your child, let them put it on and walk a few steps first, then we'll talk / 带孩子来的话，先让他上身走两步，我们再说。）
- 你不用被文案说服，来店里摸一下、穿一下，感觉会更准。（you don't need to be persuaded by copy — come to the store, touch it, wear it, the feeling will be more accurate / 你不用被文案说服，来店里摸一下、穿一下，感觉会更准。）

## typical_hooks

- 今天店里最让我记住的，不是卖了多少，是一个很小的瞬间。（what I remember most about the store today isn't how much we sold — it's a very small moment / 今天店里最让我记住的，不是卖了多少，是一个很小的瞬间。）
- 她进门的时候什么都没说，我大概就知道她先不该试那一排。（she didn't say a word when she walked in, but I already knew she shouldn't try that rack first / 她进门的时候什么都没说，我大概就知道她先不该试那一排。）
- 门店日常真正难的，从来不是把货摆出来，而是把人接住。（what's really hard about store daily life is never putting the goods out — it's catching the people / 门店日常真正难的，从来不是把货摆出来，而是把人接住。）


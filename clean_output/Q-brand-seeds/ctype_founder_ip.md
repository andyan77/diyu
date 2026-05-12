---
source_workspace: diyu-infra-05/data/mvp/seeds
source_path: diyu-infra-05/data/mvp/seeds/content_type/ctype_founder_ip.json
entity_id: ctype_founder_ip
entity_type: ContentType
visibility: brand
brand_id: diyu_001
imported_at: 2026-05-04
import_decision: clean_output/audit/_process/cross_workspace_import_decision.md
---

# 创始人IP叙事内容（founder IP narrative content / 创始人IP叙事内容）

> entity_id: `ctype_founder_ip` · entity_type: `ContentType` · visibility: `brand`

## source

- **type**: founder_input
- **ref**: memory §10.11 + 创始人规划 + 2026-04-14 本轮补全
### reviewer

- 安映华
- 林静文

- **reviewed_at**: 2026-04-14

## content_type_id

ctype_founder_ip

## display_name

创始人IP叙事内容（founder IP narrative content / 创始人IP叙事内容）

## layer

enterprise_narrative

## production_mode

human_first_llm_polish

## support_level

full

## required_knowledge


- **entity_type**: BrandTone
- **min_count**: 1
- **purpose**: 锁定笛语品牌语气边界，确保创始人内容始终保持真实、温柔、有生活方式感，而不滑向成功学、鸡汤或直播间叫卖腔。（lock the laidiyu brand voice boundary so founder content stays authentic, gentle and lifestyle-driven — never sliding into self-help, soulful clichés or livestream hard-sell / 锁定笛语品牌语气边界，确保创始人内容始终保持真实、温柔、有生活方式感，而不滑向成功学、鸡汤或直播间叫卖腔。）

- **entity_type**: Persona
- **min_count**: 1
- **purpose**: 绑定 brand_founder 类型 Persona，读取创始人视角下的生活原型、情绪谱和真实性锚点，让内容像安映华本人在说，而不是品牌客服在说。（bind a brand_founder Persona; read the founder's life archetype, emotional spectrum and authenticity anchors so content sounds like Anyinghua herself, not brand customer service / 绑定 brand_founder 类型 Persona，读取创始人视角下的生活原型、情绪谱和真实性锚点，让内容像安映华本人在说，而不是品牌客服在说。）

- **entity_type**: ComplianceRule
- **min_count**: 1
- **purpose**: 提前约束创始人表述中的绝对化、功效化、价值观越界和不当承诺，降低 founder 内容因个人表达过猛带来的合规风险。（pre-constrain absolute claims, efficacy claims, value overreach and improper promises in founder voice; reduce compliance risk from overly intense personal expression / 提前约束创始人表述中的绝对化、功效化、价值观越界和不当承诺，降低 founder 内容因个人表达过猛带来的合规风险。）

## output_structure

- **format**: 短图文 / 视频配文 / 公众号短叙事（short illustrated post / video caption / WeChat OA short narrative / 短图文 / 视频配文 / 公众号短叙事）
### length_range

- 180
- 500

### sections


- **name**: 当下场景（present scene / 当下场景）
- **purpose**: 先给一个真实、具体、可见的当下场景或物件，让创始人不是先讲理念，而是先让观众看见她正在面对什么。（open with a real, specific, visible scene or object so the founder shows what she's facing rather than starting with abstract principles / 先给一个真实、具体、可见的当下场景或物件，让创始人不是先讲理念，而是先让观众看见她正在面对什么。）
- **word_budget**: 110

- **name**: 判断与取舍（judgment and trade-off / 判断与取舍）
- **purpose**: 讲清今天这个判断为什么难、为什么这样选、背后牺牲了什么，核心不是输出观点，而是展示判断过程。（explain why today's judgment is difficult, why this choice, what was sacrificed; the core is showing the decision process, not delivering opinions / 讲清今天这个判断为什么难、为什么这样选、背后牺牲了什么，核心不是输出观点，而是展示判断过程。）
- **word_budget**: 140

- **name**: 落回品牌价值（return to brand value / 落回品牌价值）
- **purpose**: 把眼前这一次小判断，落回笛语关于孩子、舒适、安全、真实表达和长期价值的品牌立场。（land this small decision back to laidiyu's brand stance on children, comfort, safety, authentic expression and long-term value / 把眼前这一次小判断，落回笛语关于孩子、舒适、安全、真实表达和长期价值的品牌立场。）
- **word_budget**: 90


## review_level

compliance_review_required

## platform_targets

- xiaohongshu
- wechat_official_account

## ab_variants_hint

A版偏'决策现场'，突出今天必须做出的一个选择；B版偏'关系戏'，突出孩子、家人、员工、顾客如何反过来影响创始人的判断；同一主题禁止两版都写成创业感悟。（version A leans toward 'decision moment' highlighting a choice that must be made today; version B leans toward 'relational drama' highlighting how a child, family member, employee or customer influences the founder's judgment in return; never write both versions of the same theme as entrepreneurship reflections / A版偏'决策现场'，突出今天必须做出的一个选择；B版偏'关系戏'，突出孩子、家人、员工、顾客如何反过来影响创始人的判断；同一主题禁止两版都写成创业感悟。）

## example_references

- 旧样衣审判庭：拿一件压箱底失败样衣，逐处讲当年为什么错、今天为什么还会犹豫。（old sample trial court: take a stored-away failed sample and discuss piece by piece why it was wrong then and why it still gives pause today / 旧样衣审判庭：拿一件压箱底失败样衣，逐处讲当年为什么错、今天为什么还会犹豫。）
- 老板不看镜头的一天：全程不对镜说教，只拍开门、摸面料、改版、关灯这些动作，让人格从细节里长出来。（the founder's no-camera day: never preaches to the camera; only films opening, touching fabric, revising patterns, turning off lights — letting personality grow from details / 老板不看镜头的一天：全程不对镜说教，只拍开门、摸面料、改版、关灯这些动作，让人格从细节里长出来。）
- 桌面证物剧场：一块面料、一张退货小票、一枚纽扣、一张改版纸条，7个物件讲完创始人一天的判断和压力。（desktop evidence theater: one fabric, one return receipt, one button, one revision note — seven objects telling the founder's whole day of judgment and pressure / 桌面证物剧场：一块面料、一张退货小票、一枚纽扣、一张改版纸条，7个物件讲完创始人一天的判断和压力。）
- 两代人穿同一件判断：创始人和母亲/老员工对同一件衣服给出不同看法，让品牌判断放进关系冲突里。（two generations judging the same piece: founder and mother/veteran employee give different views on the same garment, placing brand judgment inside relational conflict / 两代人穿同一件判断：创始人和母亲/老员工对同一件衣服给出不同看法，让品牌判断放进关系冲突里。）

## season_relevance

中等偏高。可随春夏上新、秋冬换季、开学季、节日节点变化话题物件，但核心不是季节促销，而是季节如何触发创始人的真实判断。（moderate-to-high relevance: topic objects can shift with spring/summer launches, fall/winter transitions, back-to-school season and holiday moments, but the core is not seasonal promotion — it's how the season triggers the founder's real judgments / 中等偏高。可随春夏上新、秋冬换季、开学季、节日节点变化话题物件，但核心不是季节促销，而是季节如何触发创始人的真实判断。）

## typical_ctas

- 你可以先看看我们为什么这样做，再决定要不要信这个品牌。（feel free to first see why we do it this way, then decide whether to trust this brand / 你可以先看看我们为什么这样做，再决定要不要信这个品牌。）
- 如果你愿意看真实过程，我会继续把这些判断拍下来。（if you're willing to see the real process, I'll keep filming these decisions / 如果你愿意看真实过程，我会继续把这些判断拍下来。）
- 不是让你立刻买，是想让你先知道这件衣服为什么会长成这样。（not asking you to buy now; just want you to first understand why this piece came to look the way it does / 不是让你立刻买，是想让你先知道这件衣服为什么会长成这样。）

## typical_hooks

- 这件事如果不自己盯，我其实不放心。（if I don't keep watch over this myself, I don't really feel at ease / 这件事如果不自己盯，我其实不放心。）
- 很多人只看到最后那件衣服，看不到我为什么在这里犹豫了很久。（most people only see the finished piece; they don't see why I hesitated here for a long time / 很多人只看到最后那件衣服，看不到我为什么在这里犹豫了很久。）
- 我今天不想讲大道理，只想讲一个我最后没有妥协的细节。（today I don't want to give a big speech; I only want to talk about one detail I refused to compromise / 我今天不想讲大道理，只想讲一个我最后没有妥协的细节。）


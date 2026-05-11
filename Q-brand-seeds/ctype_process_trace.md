---
source_workspace: diyu-infra-05/data/mvp/seeds
source_path: diyu-infra-05/data/mvp/seeds/content_type/ctype_process_trace.json
entity_id: ctype_process_trace
entity_type: ContentType
visibility: brand
brand_id: diyu_001
imported_at: 2026-05-04
import_decision: clean_output/audit/_process/cross_workspace_import_decision.md
---

# 流程溯源叙事内容（process trace narrative content / 流程溯源叙事内容）

> entity_id: `ctype_process_trace` · entity_type: `ContentType` · visibility: `brand`

## source

- **type**: founder_input
- **ref**: memory §10.11 + 创始人规划 + process_trace 交付物 + 2026-04-14 本轮补全
### reviewer

- 安映华
- 林静文

- **reviewed_at**: 2026-04-14

## content_type_id

ctype_process_trace

## display_name

流程溯源叙事内容（process trace narrative content / 流程溯源叙事内容）

## layer

enterprise_narrative

## production_mode

llm_assist_human_edit

## support_level

full

## required_knowledge


- **entity_type**: BrandTone
- **min_count**: 1
- **purpose**: 确保流程溯源内容虽然在讲工艺、原料和证据，但表达仍然属于笛语的气质，不变成冷硬工业说明书或空洞企业宣传片。（ensure process-trace content, while discussing craft, materials and evidence, still belongs to laidiyu's voice — never becoming a cold industrial manual or empty corporate promo / 确保流程溯源内容虽然在讲工艺、原料和证据，但表达仍然属于笛语的气质，不变成冷硬工业说明书或空洞企业宣传片。）

- **entity_type**: GlobalKnowledge
- **min_count**: 1
- **purpose**: 读取 K-DATA-02 的 L4 产业链知识，给出原料、工序、节点、证据链和可核验的专业背景，这是 process_trace 的灵魂来源。（read K-DATA-02's L4 supply-chain knowledge for raw materials, processes, nodes, evidence chains and verifiable professional context — this is the soul of process_trace / 读取 K-DATA-02 的 L4 产业链知识，给出原料、工序、节点、证据链和可核验的专业背景，这是 process_trace 的灵魂来源。）

- **entity_type**: RoleProfile
- **min_count**: 1
- **purpose**: 读取版师、工艺、质检、面料、供应链相关岗位的一线动作词和判断词，让流程不是抽象步骤，而是有人在做的具体环节。（read first-line action and judgment vocabulary from pattern-makers, craftspeople, QC, fabric and supply-chain roles so the process is not abstract steps but concrete tasks done by real people / 读取版师、工艺、质检、面料、供应链相关岗位的一线动作词和判断词，让流程不是抽象步骤，而是有人在做的具体环节。）

## output_structure

- **format**: 短图文 / 视频解说文案 / 溯源卡片文案（short illustrated post / video voiceover script / traceability card copy / 短图文 / 视频解说文案 / 溯源卡片文案）
### length_range

- 180
- 600

### sections


- **name**: 起点场景（starting scene / 起点场景）
- **purpose**: 从一个具体证据点或具体物件切入，例如面料标签、样布、缝线、拉链、入库单，而不是从'我们的工艺很好'这种抽象话起。（open from a specific evidence point or object — fabric label, swatch, stitch, zipper, intake form — rather than abstract claims like 'our craft is good' / 从一个具体证据点或具体物件切入，例如面料标签、样布、缝线、拉链、入库单，而不是从'我们的工艺很好'这种抽象话起。）
- **word_budget**: 90

- **name**: 过程细节（process detail / 过程细节）
- **purpose**: 说明这个环节到底发生了什么、为什么不能省、观众能看见或验证什么，把复杂流程压缩成少数关键证据点。（explain what actually happens at this stage, why it can't be skipped, what viewers can see or verify; compress a complex process into a few key evidence points / 说明这个环节到底发生了什么、为什么不能省、观众能看见或验证什么，把复杂流程压缩成少数关键证据点。）
- **word_budget**: 170

- **name**: 价值升华（value elevation / 价值升华）
- **purpose**: 把这个工艺或溯源节点与消费者真正关心的体验连接起来，例如亲肤、安全、耐穿、稳定、放心，而不是停在专业词堆叠。（connect this craft or traceability node to what consumers actually care about — skin-friendliness, safety, durability, stability, peace of mind — rather than stacking jargon / 把这个工艺或溯源节点与消费者真正关心的体验连接起来，例如亲肤、安全、耐穿、稳定、放心，而不是停在专业词堆叠。）
- **word_budget**: 110


## review_level

compliance_review_required

## platform_targets

- xiaohongshu
- douyin

## ab_variants_hint

A版偏'证据链'，重点展示可核验点、单据、标签、批次、抽检动作；B版偏'感官化'，重点展示微距纹理、面料声音、机器节奏、手部动作。两版都要避免全流程流水账。（version A leans toward 'evidence chain', focusing on verifiable points, paperwork, labels, batches, sampling actions; version B leans toward 'sensory', focusing on macro textures, fabric sounds, machine rhythm, hand movements; both must avoid full-process running accounts / A版偏'证据链'，重点展示可核验点、单据、标签、批次、抽检动作；B版偏'感官化'，重点展示微距纹理、面料声音、机器节奏、手部动作。两版都要避免全流程流水账。）

## example_references

- 一块面料从原料到上身：不讲空洞工艺词，只讲它为什么更亲肤、更耐穿、为什么这一步不能省。（one fabric from raw material to wear: skip empty craft jargon, only explain why it's softer, more durable, and why this step can't be skipped / 一块面料从原料到上身：不讲空洞工艺词，只讲它为什么更亲肤、更耐穿、为什么这一步不能省。）
- 为什么这条裙子的拉链更贵：把消费者最容易忽略、但最影响体验的一处拆开讲透。（why this dress's zipper costs more: take what consumers most easily ignore but matters most for experience and explain it through / 为什么这条裙子的拉链更贵：把消费者最容易忽略、但最影响体验的一处拆开讲透。）
- 样衣版本树：把 1.0 / 2.0 / 3.0 摆在一起，告诉观众每一次否决到底否决了什么。（sample version tree: line up 1.0 / 2.0 / 3.0 side by side and tell viewers exactly what each rejection rejected / 样衣版本树：把 1.0 / 2.0 / 3.0 摆在一起，告诉观众每一次否决到底否决了什么。）
- 工艺对比实验：同样是基础款，为什么有的洗两次就变形，有的还能继续穿。（craft comparison experiment: same basic style — why some lose shape after two washes while others stay wearable / 工艺对比实验：同样是基础款，为什么有的洗两次就变形，有的还能继续穿。）
- 被拦下的一件成衣：不是只拍通过的流程，而是拍哪一步把问题拦下来，建立'你没有骗我'的信任。（an intercepted garment: not only filming approved processes but filming the step that caught the problem, building 'you're not fooling me' trust / 被拦下的一件成衣：不是只拍通过的流程，而是拍哪一步把问题拦下来，建立'你没有骗我'的信任。）

## season_relevance

高。春夏可重点写透气、轻薄、亲肤、活动量；秋冬可重点写保暖、层次、耐穿、内里和工艺稳定性；节点上可与开学季、换季上新、秋冬首发强关联。（high relevance: spring/summer can focus on breathability, lightness, skin-feel, range of motion; fall/winter can focus on warmth, layering, durability, lining and craft stability; can strongly tie to back-to-school, season-change launches, and fall/winter debut moments / 高。春夏可重点写透气、轻薄、亲肤、活动量；秋冬可重点写保暖、层次、耐穿、内里和工艺稳定性；节点上可与开学季、换季上新、秋冬首发强关联。）

## typical_ctas

- 你可以先不急着下判断，先把这几个证据点看完。（don't rush to judge; finish watching these few evidence points first / 你可以先不急着下判断，先把这几个证据点看完。）
- 如果你愿意，我们下一条继续把后面的环节也拍给你看。（if you're willing, we'll keep filming the next stages in our next post / 如果你愿意，我们下一条继续把后面的环节也拍给你看。）
- 不是为了把工艺讲玄，是想让你知道这份价格到底落在了哪里。（not making craftsmanship sound mystical — just want you to know where this price actually goes / 不是为了把工艺讲玄，是想让你知道这份价格到底落在了哪里。）

## typical_hooks

- 这一步平时看不见，但它决定了你拿到手里会不会放心。（you don't usually see this step, but it decides whether you'll feel at ease holding the finished product / 这一步平时看不见，但它决定了你拿到手里会不会放心。）
- 同样是一条拉链，贵和便宜的差别，不在广告词里，在这里。（same zipper, the difference between expensive and cheap isn't in the ad copy — it's right here / 同样是一条拉链，贵和便宜的差别，不在广告词里，在这里。）
- 我今天不带你看全流程，只带你看5个能核验的点。（today I won't walk you through the full process; I'll just take you through five points you can verify / 我今天不带你看全流程，只带你看5个能核验的点。）


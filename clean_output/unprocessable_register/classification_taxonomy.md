# UnprocessableRegister 分类说明

> Phase A 阶段尚未登记不可处理项；本文件仅声明分类口径，供 Phase B 起使用。

UnprocessableRegister 是**一等产出**，不是失败垃圾桶。
不要为了减少 unprocessable 数量而强行抽 CandidatePack。

## 8 类 classification 口径

| classification | 触发条件 | 后续动作 |
|---|---|---|
| `needs_human_judgment` | 内容明显有业务价值，但 AI 无法决定属于哪个 pack_type 或 brand_layer | 人工裁决 |
| `scenario_not_closed` | Gate 1 fail：只有观点 / 口号 / 标题 / 片段，凑不齐 8 要素 | 回到素材定位完整段落或舍弃 |
| `evidence_insufficient` | Gate 2 fail：9 表派生后无法反推核心语义；或 evidence_quote 不能支撑 knowledge_assertion | 补证据后再抽 |
| `gate_failure_specific` | 明确指出某一闸 fail 的具体原因（如 Gate 3 只是个案） | 视具体闸决定是否落档为 parked |
| `meta_layer_not_business` | 内容是工程流程 / 元层定义 / 治理体系，不是业务知识 | 直接归档，不进 9 表 |
| `process_description_needs_split` | 是流程描述（多步骤），需要拆分成多条独立 CandidatePack | 拆分后重抽 |
| `duplicate_or_redundant` | 与既有 CandidatePack 实质重复 | 引用既有 pack_id，不重复落档 |
| `out_of_scope` | 不在当前工作区三个素材目录范围内 | 直接拒绝处理 |

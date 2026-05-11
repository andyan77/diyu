````text
# 任务：服装零售领域知识 · 4 闸 9 表结构化抽取

## 0. 任务边界

你现在只执行一个任务：

把当前工作区中的服装零售业务素材 markdown（标记文档）抽取为可机器消费的领域知识，并按 4 闸投影到 9 张表。

本任务不是：
- 不是写 ADR（架构决策记录）
- 不是写 KER（知识抽取记录）治理体系
- 不是生成大量审计脚手架
- 不是做内容创作
- 不是泛泛总结素材
- 不是把 markdown（标记文档）原文搬运到 YAML（数据文件）

本任务的核心目标是：

markdown（标记文档）业务血肉
→ CandidatePack（候选知识包）
→ 4 Gates（四闸）
→ 9 Tables（九张表）
→ single_db_logical_isolation（单库逻辑隔离）可入库数据

必须优先保护 domain layer（领域层）。
不要把任务做成 meta-layer（元层）或 meta-meta-layer（元元层）工程。

---

## 1. 输入范围

当前工作区只包含以下素材目录：

1. Q2-内容类型种子（内容类型种子目录）
2. Q4-人设种子（人设种子目录）
3. Q7Q12-搭配陈列业务包（搭配陈列业务包目录）

输入文件类型只处理：

markdown（标记文档）

不读取、不引用、不继承任何旧工作区的历史产物、旧状态、旧阻断项、旧写回目录、旧候选状态。

如果某个信息不在当前工作区素材里，就标记为：

unknown_in_current_workspace（当前工作区未知）

不要凭历史记忆补。

---

## 2. 最终产出目录

请在当前工作区生成以下目录：

clean_output（干净输出目录）/
  candidates（候选知识包目录）/
    domain_general（领域通用层目录）/
    brand_faye（笛语品牌层目录）/
    needs_review（待人工复核目录）/

  nine_tables（九张表目录）/
    01_object_type.csv（对象类型表）
    02_field.csv（字段表）
    03_semantic.csv（语义表）
    04_value_set.csv（取值集表）
    05_relation.csv（关系表）
    06_rule.csv（规则表）
    07_evidence.csv（证据表）
    08_lifecycle.csv（生命周期表）
    09_call_mapping.csv（调用映射表）

  unprocessable_register（不可处理登记目录）/
    register.csv（不可处理登记表）
    classification_taxonomy.md（不可处理分类说明）

  storage（存储方案目录）/
    single_db_logical_isolation.sql（单库逻辑隔离建表 SQL）

  audit（最小审计目录）/
    extraction_log.csv（抽取日志）
    four_gate_results.csv（四闸结果）
    brand_layer_review_queue.csv（品牌层人工复核队列）
    blockers.md（阻断项说明）
    final_report.md（最终报告）

  templates（模板目录）/
    candidate_pack.template.yaml（候选知识包模板）

  README.md（说明文档）

禁止额外生成以下类型文件，除非人工明确要求：

ProgressSync（进度同步）
MilestoneReport（里程碑报告）
QualityGateReport（质量门禁报告）
NoExecutionAudit（无执行审计）
ADR（架构决策记录）
KER（知识抽取记录）
LifecycleLegislation（生命周期立法）

---

## 3. 核心数据对象：CandidatePack（候选知识包）

每个 CandidatePack（候选知识包）必须代表一条独立、可复述、可机器消费的业务知识。

一个 CandidatePack（候选知识包）不是“素材段落”，不是“证据指针”，不是“对象壳”。

它必须回答：

这条知识到底说了什么？
谁在什么场景下用？
正确做法是什么？
为什么成立？
什么时候会翻车？
边界是什么？
证据来自哪里？
能不能投影到 9 张表？

---

## 4. CandidatePack（候选知识包）模板

实际 YAML（数据文件）请使用英文键名；每个字段含义如下。

```yaml
pack_id: ""                         # pack_id（知识包编号）
schema_version: "candidate_v1"       # schema_version（结构版本）
pack_type: ""                       # pack_type（知识包类型）
brand_layer: ""                     # brand_layer（品牌层）
state: "drafted"                    # state（状态）

knowledge_assertion: ""             # knowledge_assertion（知识断言）

scenario:                           # scenario（闭环场景）
  who:                              # who（谁）
    primary_role: ""                # primary_role（主要角色）
    target_audience: ""             # target_audience（目标对象）
  when:                             # when（何时）
    trigger: ""                     # trigger（触发条件）
    context: ""                     # context（上下文）
  what:                             # what（做什么）
    action_type: ""                 # action_type（动作类型）
    decision_or_action: ""          # decision_or_action（判断或动作）
  result:                           # result（结果）
    success_pattern: ""             # success_pattern（成功模式）
    flip_pattern: ""                # flip_pattern（翻车模式）
  underlying_mechanism: ""          # underlying_mechanism（底层机制）
  boundary:                         # boundary（边界）
    applicable_when: ""             # applicable_when（适用条件）
    not_applicable_when: ""         # not_applicable_when（不适用条件）
  alternative_path: []              # alternative_path（替代路径）

evidence:                           # evidence（证据）
  source_md: ""                     # source_md（来源 markdown 文件）
  source_anchor: ""                 # source_anchor（来源锚点）
  source_type: ""                   # source_type（证据类型）
  inference_level: ""               # inference_level（推断等级）
  evidence_quote: ""                # evidence_quote（证据原文摘录）

gate_self_check:                    # gate_self_check（四闸自检）
  gate_1_closed_scenario: ""        # gate_1_closed_scenario（第一闸闭环场景）
  gate_2_reverse_infer: ""          # gate_2_reverse_infer（第二闸九表反推）
  gate_3_rule_generalizable: ""     # gate_3_rule_generalizable（第三闸规则泛化）
  gate_4_production_feasible: ""    # gate_4_production_feasible（第四闸生产可用）
  notes: ""                         # notes（说明）

brand_layer_review:                 # brand_layer_review（品牌层判断）
  decision_suggestion: ""           # decision_suggestion（判断建议）
  rationale: ""                     # rationale（理由）
  faye_review_required: false       # faye_review_required（是否需要笛语人工复核）
  splittable_components: []         # splittable_components（可拆分组件）

nine_table_projection:              # nine_table_projection（九表投影建议）
  object_type: []                   # object_type（对象类型表）
  field: []                         # field（字段表）
  semantic: []                      # semantic（语义表）
  value_set: []                     # value_set（取值集表）
  relation: []                      # relation（关系表）
  rule: []                          # rule（规则表）
  evidence: []                      # evidence（证据表）
  lifecycle: []                     # lifecycle（生命周期表）
  call_mapping: []                  # call_mapping（调用映射表）
````

---

## 5. CandidatePack（候选知识包）硬标准

每条 CandidatePack（候选知识包）必须满足以下要求。

### 5.1 knowledge_assertion（知识断言）要求

knowledge_assertion（知识断言）必须是一句具体业务判断。

合格示例：

* 亚麻适合表达干爽、空气感、松弛感，但不能承诺全天不皱。
* 断码零散货不能站主陈列位，否则画面成立但成交路径断裂。
* 顾客说“再看看”不一定是拒绝，导购应先判断她是在试探、防御，还是等待更贴身解释。
* 缎面直身裙不适合腹部和内衣痕迹敏感的顾客，因为光泽会放大身体线条。

不合格示例：

* 该内容具有业务价值。
* 要根据情况判断。
* 这是一条搭配规则。
* 需要提升门店转化。
* 符合业务逻辑。

写不出 knowledge_assertion（知识断言）的内容，直接进入 unprocessable_register（不可处理登记表）。

---

## 6. pack_type（知识包类型）

pack_type（知识包类型）只能从以下 8 类选择：

1. fabric_property（面料属性）
2. craft_quality（工艺品控）
3. styling_rule（搭配规则）
4. display_rule（陈列规则）
5. service_judgment（接客判断）
6. inventory_rescue（库存救场）
7. training_unit（培训单元）
8. product_attribute（商品属性）

不得新增 pack_type（知识包类型）。

如果无法归类，进入 unprocessable_register（不可处理登记表），分类为 needs_human_judgment（需要人工判断）。

---

## 7. 不同 pack_type（知识包类型）的抽取重点

### 7.1 fabric_property（面料属性）

必须抽出：

* 面料名称
* 关键体感
* 视觉表现
* 风险边界
* 搭配影响
* 陈列影响
* 培训提示
* 证据原文

示例：

亚麻容易产生自然折痕，这不是缺陷，而是它表达松弛感和空气感的一部分；但不能向顾客承诺全天平整。

### 7.2 craft_quality（工艺品控）

必须抽出：

* 工艺特征
* 品质信号
* 失败信号
* 会影响什么推荐或陈列
* 门店如何解释
* 培训如何使用

示例：

线迹不顺不仅是细节问题，会直接影响近看质感，适合作为员工辨别工艺稳定性的训练点。

### 7.3 styling_rule（搭配规则）

必须抽出：

* 规则内容
* 为什么成立
* 适用场景
* 不适用场景
* 成功模式
* 翻车模式
* 替代边界
* 可调用位置

示例：

三七比例法适合显高显利落，高腰下装和短上衣能制造视觉拉长；上衣卡胯或腰线消失时会翻车。

### 7.4 display_rule（陈列规则）

必须抽出：

* 陈列位置
* 业务目标
* 适合商品或库存状态
* 不适合情况
* 常见错误
* 对成交的影响
* 培训层级

示例：

断码零散货不应站主陈列位，因为主陈列位承诺的是可被多数顾客购买的路径。

### 7.5 service_judgment（接客判断）

必须抽出：

* 顾客触发语
* 导购第一判断
* 正确动作
* 错误动作
* 成功模式
* 翻车模式
* 替代路径

示例：

顾客问“会不会扎”时，导购不能只回答“不扎”，应先判断她介意的是触感、温度、透度、弹性、静电还是内搭难度。

### 7.6 inventory_rescue（库存救场）

必须抽出：

* 库存状态
* 是否还能推荐
* 是否还能陈列
* 何时救场
* 何时转向
* 何时放弃
* 替代优先级

示例：

只有单品但凑不成套时，可以卖单品价值，但不能继续把它包装成完整套装。

### 7.7 training_unit（培训单元）

必须抽出：

* 错误动作
* 正确动作
* 为什么错
* 如何纠正
* 掌握检查
* 适合训练的岗位

示例：

新人不能只说“显瘦”，必须指出肩线、腰线、下摆或裤长哪个结构点在起作用。

### 7.8 product_attribute（商品属性）

必须抽出：

* 属性名称
* 标准取值
* 同义词
* 会不会改变搭配结论
* 会不会改变陈列方式
* 证据来源

示例：

fit（版型）和 length（长度）会直接改变搭配结论，不能只作为展示字段。

---

## 8. brand_layer（品牌层）判断规则

brand_layer（品牌层）只能使用：

1. domain_general（领域通用）
2. brand_faye（笛语品牌专属）
3. needs_review（待人工复核）

### 8.1 domain_general（领域通用）

满足以下条件时，标为 domain_general（领域通用）：

* 跨服装零售品牌成立
* 不含笛语专属品牌表达
* 不依赖某个门店、某位老板、某次活动
* 可以被其他女装、服装零售、门店培训复用

示例：

亚麻容易皱但适合表达松弛感。

### 8.2 brand_faye（笛语品牌专属）

满足以下条件时，标为 brand_faye（笛语品牌专属）：

* 明确出现笛语专属口吻、品牌偏好、品牌禁忌
* 明确来自笛语内部动作、组织习惯、门店政策
* 只适合笛语当前品牌表达，不应直接复用给其他品牌

示例：

笛语门店不要把高级感讲成贵妇感，而要讲成松弛、真实、好接近。

### 8.3 needs_review（待人工复核）

以下情况进入 needs_review（待人工复核）：

* 既像通用经验，又带明显笛语表达
* 需要拆分成通用部分和品牌部分
* 证据不足以判断品牌层
* 执行 AI（人工智能）无法确定

needs_review（待人工复核）必须写入：

audit/brand_layer_review_queue.csv（品牌层人工复核队列）

---

## 9. 4 Gates（四闸）

4 Gates（四闸）是过滤器，不是模板。不要为了过闸而编内容。

### Gate 1（第一闸）：closed_scenario_origin（闭环场景来源）

检查：

* 是否有 who（谁）
* 是否有 when（何时）
* 是否有 what（做什么）
* 是否有 success_pattern（成功模式）
* 是否有 flip_pattern（翻车模式）
* 是否有 underlying_mechanism（底层机制）
* 是否有 boundary（边界）
* 是否有 alternative_path（替代路径）

判定：

* pass（通过）：8 要素基本完整
* partial（部分通过）：知识本体成立，但场景略缺
* fail（失败）：只有观点、口号、标题或片段

fail（失败）处理：

进入 unprocessable_register（不可处理登记表），classification（分类）= scenario_not_closed（场景不闭环）

### Gate 2（第二闸）：nine_tables_can_reverse_infer（九表可反推）

检查：

只看 9 表派生结果，能否反推回 CandidatePack（候选知识包）的核心语义。

至少要能反推：

* 知识断言是什么
* 适用条件是什么
* 翻车模式是什么
* 证据来自哪里
* 属于哪一类 pack_type（知识包类型）

判定：

* pass（通过）：可反推核心语义
* partial（部分通过）：能反推规则，但丢失边界或翻车
* fail（失败）：只能看到对象名、字段名、证据引用，无法还原业务判断

fail（失败）处理：

进入 unprocessable_register（不可处理登记表），classification（分类）= evidence_insufficient（证据不足）或 gate_failure_specific（具体闸失败）

### Gate 3（第三闸）：rule_generalizable（规则可泛化）

检查：

这条知识是否能跨场景、跨门店、跨客群、跨平台复用。

判定：

* pass（通过）：可作为 domain_general（领域通用）或稳定 brand_faye（笛语品牌专属）规则
* partial（部分通过）：知识有价值，但泛化范围有限
* fail（失败）：只是一次性个案

fail（失败）处理：

不强行入 9 表，进入 unprocessable_register（不可处理登记表）或标 state（状态）= parked（搁置）

### Gate 4（第四闸）：production_feasible（生产可用）

检查：

这条知识是否能被以下至少一种运行场景调用：

* content_generation（内容生成）
* outfit_recommendation（搭配推荐）
* display_guidance（陈列指南）
* store_training（门店培训）
* inventory_rescue（库存救场）
* platform_adaptation（平台适配）

判定：

* pass（通过）：可生成 call_mapping（调用映射）
* partial（部分通过）：知识本体成立，但运行入口待补
* fail（失败）：暂不可调用

fail（失败）处理：

可保留 CandidatePack（候选知识包），state（状态）= parked（搁置），不进入最终可调用表。

---

## 10. 9 Tables（九张表）最小结构

所有 9 张表都必须包含：

brand_layer（品牌层）
source_pack_id（来源知识包编号）

### 10.1 object_type（对象类型表）

列：

type_id（类型编号）
type_name（类型名称）
supertype（上级类型）
brand_layer（品牌层）
source_pack_id（来源知识包编号）

### 10.2 field（字段表）

列：

field_id（字段编号）
owner_type（所属对象类型）
field_name（字段名称）
data_type（数据类型）
value_set_id（取值集编号）
semantic_id（语义编号）
brand_layer（品牌层）
source_pack_id（来源知识包编号）

### 10.3 semantic（语义表）

列：

semantic_id（语义编号）
owner_field（所属字段）
definition（定义）
examples_json（示例 JSON）
brand_layer（品牌层）
source_pack_id（来源知识包编号）

### 10.4 value_set（取值集表）

列：

value_set_id（取值集编号）
value（取值）
label（标签）
ordinal（排序）
brand_layer（品牌层）
source_pack_id（来源知识包编号）

### 10.5 relation（关系表）

列：

relation_id（关系编号）
source_type（源对象类型）
target_type（目标对象类型）
relation_kind（关系类型）
properties_json（属性 JSON）
brand_layer（品牌层）
source_pack_id（来源知识包编号）

### 10.6 rule（规则表）

列：

rule_id（规则编号）
rule_type（规则类型）
applicable_when（适用条件）
success_scenario（成功场景）
flip_scenario（翻车场景）
alternative_boundary（替代边界）
brand_layer（品牌层）
source_pack_id（来源知识包编号）

### 10.7 evidence（证据表）

列：

evidence_id（证据编号）
source_md（来源 markdown 文件）
source_anchor（来源锚点）
evidence_quote（证据原文摘录）
source_type（证据类型）
inference_level（推断等级）
brand_layer（品牌层）
source_pack_id（来源知识包编号）

### 10.8 lifecycle（生命周期表）

列：

lifecycle_id（生命周期编号）
owner_type（所属对象类型）
state（状态）
transition_to（可迁移状态）
condition（条件）
brand_layer（品牌层）
source_pack_id（来源知识包编号）

说明：

除非素材明确包含状态迁移，否则 lifecycle（生命周期表）可以为空。不要为了凑表而编生命周期。

### 10.9 call_mapping（调用映射表）

列：

mapping_id（映射编号）
runtime_method（运行时方法）
input_types（输入类型）
output_types（输出类型）
governing_rules_json（治理规则 JSON）
brand_layer（品牌层）
source_pack_id（来源知识包编号）

---

## 11. pack_type（知识包类型）到 9 Tables（九张表）的默认投影

### fabric_property（面料属性）

必投：

* semantic（语义表）
* value_set（取值集表）
* rule（规则表）
* evidence（证据表）

可投：

* call_mapping（调用映射表）

默认不投：

* lifecycle（生命周期表）

### craft_quality（工艺品控）

必投：

* semantic（语义表）
* rule（规则表）
* evidence（证据表）

可投：

* value_set（取值集表）
* call_mapping（调用映射表）

默认不投：

* lifecycle（生命周期表）

### styling_rule（搭配规则）

必投：

* rule（规则表）
* evidence（证据表）
* call_mapping（调用映射表）

可投：

* semantic（语义表）
* value_set（取值集表）
* relation（关系表）

### display_rule（陈列规则）

必投：

* rule（规则表）
* relation（关系表）
* evidence（证据表）
* call_mapping（调用映射表）

可投：

* value_set（取值集表）

### service_judgment（接客判断）

必投：

* rule（规则表）
* evidence（证据表）
* call_mapping（调用映射表）

可投：

* semantic（语义表）
* lifecycle（生命周期表）

### inventory_rescue（库存救场）

必投：

* rule（规则表）
* relation（关系表）
* evidence（证据表）
* call_mapping（调用映射表）

可投：

* semantic（语义表）
* value_set（取值集表）

### training_unit（培训单元）

必投：

* rule（规则表）
* evidence（证据表）
* call_mapping（调用映射表）

可投：

* semantic（语义表）
* lifecycle（生命周期表）

### product_attribute（商品属性）

必投：

* field（字段表）
* semantic（语义表）
* value_set（取值集表）
* evidence（证据表）

可投：

* relation（关系表）

默认不投：

* lifecycle（生命周期表）

---

## 12. ID（编号）生成规则

ID（编号）必须稳定、可复跑、不可随机。

禁止使用自增数字作为主 ID（编号）。

建议规则：

pack_id（知识包编号）：

KP-<pack_type>-<normalized_slug>

evidence_id（证据编号）：

EV-<pack_id>

rule_id（规则编号）：

RL-<pack_id>

semantic_id（语义编号）：

SM-<pack_id>-<concept>

value_set_id（取值集编号）：

VS-<pack_id>-<concept>

field_id（字段编号）：

FD-<owner_type>-<field_name>

relation_id（关系编号）：

RE-<source_type>-<relation_kind>-<target_type>-<hash4>

mapping_id（调用映射编号）：

CM-<runtime_method>-<pack_id>

同一输入重复执行时，ID（编号）必须完全一致。

---

## 13. UnprocessableRegister（不可处理登记表）

unprocessable_register/register.csv（不可处理登记表）列：

unprocessable_id（不可处理编号）
source_md（来源 markdown 文件）
source_anchor（来源锚点）
content_excerpt（内容摘录）
classification（分类）
classification_reason（分类理由）
follow_up_action（后续动作）
status（状态）
created_at（创建时间）

classification（分类）只允许：

1. needs_human_judgment（需要人工判断）
2. scenario_not_closed（场景不闭环）
3. evidence_insufficient（证据不足）
4. gate_failure_specific（具体闸失败）
5. meta_layer_not_business（元层内容非业务知识）
6. process_description_needs_split（流程描述需要拆分）
7. duplicate_or_redundant（重复或冗余）
8. out_of_scope（超出范围）

UnprocessableRegister（不可处理登记表）是一等产出，不是失败垃圾桶。

不要为了减少 unprocessable（不可处理项）数量而强行抽 CandidatePack（候选知识包）。

---

## 14. 反空壳门禁

以下情况必须判为不合格：

1. knowledge_assertion（知识断言）是空话。
2. success_pattern（成功模式）和 flip_pattern（翻车模式）没有明确对照。
3. evidence_quote（证据原文摘录）不能支撑 knowledge_assertion（知识断言）。
4. 只生成 source_md（来源 markdown 文件）和 evidence_ref（证据引用），没有业务判断。
5. 只是复述标题，没有重组为业务知识。
6. 只写“根据情况判断”“符合业务逻辑”“有助于提升转化”等泛话。
7. 9 表派生后无法反推原业务语义。
8. 单个 CandidatePack（候选知识包）派生超过 50 行 9 表记录，说明粒度可能过大，必须停下复核。

---

## 15. 工作流程

### Phase 0（阶段 0）：DomainSkeleton（领域骨架）确认

在执行 Phase A（阶段 A）样本抽取之前，必须先建立最小 domain skeleton（领域骨架）。

domain skeleton（领域骨架）的作用不是生成正式模型，不是定义完整 schema（结构），不是新建治理体系。

它只用于约束后续 CandidatePack（候选知识包）抽取时的对象挂靠、字段命名、关系方向和 9 Tables（九张表）投影。

### 15.1 输出文件

请生成：

clean_output/domain_skeleton（领域骨架目录）/
  domain_skeleton.yaml（领域骨架 YAML 数据文件）
  pack_type_mapping.md（知识包类型映射说明）
  skeleton_gap_register.csv（领域骨架缺口登记表）

### 15.2 domain_skeleton.yaml（领域骨架 YAML 数据文件）最小内容

必须包含以下内容：

1. domain_name（领域名称）
2. scope_statement（范围说明）
3. core_object_types（核心对象类型）
4. core_field_groups（核心字段组）
5. allowed_relation_kinds（允许关系类型）
6. allowed_pack_types（允许知识包类型）
7. pack_type_to_object_type（知识包类型到对象类型映射）
8. forbidden_objects（禁止临时新增对象）
9. unresolved_gaps（待确认缺口）

### 15.3 首批允许的 core_object_types（核心对象类型）

只允许使用以下对象类型：

Product（商品）
Category（品类）
Attribute（属性）
Collection（系列）
FabricKnowledge（面料知识）
CraftKnowledge（工艺品控知识）
StylingRule（搭配规则）
DisplayGuide（陈列指南）
TrainingMaterial（培训材料）
RoleProfile（岗位画像）
Persona（人设）
ContentType（内容类型）
PlatformTone（平台语调）
PrivateOutletChannel（私域出口位）
InventoryState（库存状态）
CustomerScenario（顾客场景）
CallMapping（调用映射）
Evidence（证据）

不得随意新增对象类型。

如果素材中出现无法挂靠的对象，写入：

clean_output/domain_skeleton/skeleton_gap_register.csv（领域骨架缺口登记表）

不要临时发明新对象。

### 15.4 首批允许的 allowed_relation_kinds（允许关系类型）

只允许使用以下关系类型：

has_attribute（拥有属性）
belongs_to_category（归属品类）
uses_fabric_knowledge（使用面料知识）
uses_craft_knowledge（使用工艺品控知识）
governed_by_rule（受规则约束）
supports_training（支持培训）
supports_display（支持陈列）
supports_styling（支持搭配）
requires_inventory_state（需要库存状态）
fits_customer_scenario（适配顾客场景）
spoken_by_role（由岗位表达）
compatible_with_content_type（兼容内容类型）
mapped_to_runtime（映射到运行时）
supported_by_evidence（由证据支撑）

不得随意新增 relation_kind（关系类型）。

如果确实需要新增，写入 skeleton_gap_register.csv（领域骨架缺口登记表），不要直接入 9 Tables（九张表）。

### 15.5 pack_type_to_object_type（知识包类型到对象类型映射）

必须按以下默认映射执行：

fabric_property（面料属性）
→ FabricKnowledge（面料知识）
→ 可关联 Product（商品） / Attribute（属性） / TrainingMaterial（培训材料） / StylingRule（搭配规则）

craft_quality（工艺品控）
→ CraftKnowledge（工艺品控知识）
→ 可关联 Product（商品） / TrainingMaterial（培训材料） / DisplayGuide（陈列指南）

styling_rule（搭配规则）
→ StylingRule（搭配规则）
→ 可关联 Product（商品） / Attribute（属性） / CustomerScenario（顾客场景） / InventoryState（库存状态）

display_rule（陈列规则）
→ DisplayGuide（陈列指南）
→ 可关联 Product（商品） / Category（品类） / InventoryState（库存状态） / StylingRule（搭配规则）

service_judgment（接客判断）
→ CustomerScenario（顾客场景） / TrainingMaterial（培训材料）
→ 可关联 RoleProfile（岗位画像） / Product（商品） / StylingRule（搭配规则）

inventory_rescue（库存救场）
→ InventoryState（库存状态） / StylingRule（搭配规则） / DisplayGuide（陈列指南）
→ 可关联 Product（商品） / CustomerScenario（顾客场景）

training_unit（培训单元）
→ TrainingMaterial（培训材料）
→ 可关联 RoleProfile（岗位画像） / StylingRule（搭配规则） / DisplayGuide（陈列指南） / InventoryState（库存状态）

product_attribute（商品属性）
→ Product（商品） / Category（品类） / Attribute（属性）
→ 可关联 StylingRule（搭配规则） / DisplayGuide（陈列指南）

### 15.6 domain skeleton（领域骨架）硬约束

1. domain skeleton（领域骨架）只能约束抽取，不得替代抽取。
2. 不得因为 domain skeleton（领域骨架）存在，就跳过 CandidatePack（候选知识包）。
3. 不得把 domain skeleton（领域骨架）写成完整正式模型。
4. 不得把素材原文直接塞进 domain_skeleton.yaml（领域骨架 YAML 数据文件）。
5. 不得新增复杂状态机。
6. 不得新建立法文档。
7. 不得新增 ADR（架构决策记录）。
8. 不得新增 KER（知识抽取记录）。
9. 所有无法挂靠的内容进入 skeleton_gap_register.csv（领域骨架缺口登记表）。
10. Phase 0（阶段 0）完成后，必须继续执行 Phase A（阶段 A）3 条样本抽取。

### 15.7 Phase 0（阶段 0）验收标准

Phase 0（阶段 0）合格标准：

1. core_object_types（核心对象类型）清晰。
2. allowed_relation_kinds（允许关系类型）清晰。
3. pack_type_to_object_type（知识包类型到对象类型映射）清晰。
4. 没有随意新增对象。
5. 没有生成元层治理体系。
6. 可以指导 Phase A（阶段 A）3 条样本抽取。
7. skeleton_gap_register.csv（领域骨架缺口登记表）存在，即使为空也要有表头。

Phase 0（阶段 0）不要求生成 9 Tables（九张表）。
Phase 0（阶段 0）不要求生成 canonical model（正式标准模型）。
Phase 0（阶段 0）不要求批量抽取。

### Phase A（阶段 A）：小样本试抽，必须先做

只处理 3 条样本，不进入批量。

从以下 3 类素材中各抽 1 条：

1. fabric_property（面料属性）样本
2. service_judgment（接客判断）样本
3. display_rule（陈列规则）样本

每条样本必须完整产出：

* CandidatePack（候选知识包）
* 4 Gates（四闸）自检
* 9 Tables（九张表）派生行
* brand_layer（品牌层）判断
* evidence（证据）记录
* reverse_infer（反推）说明

Phase A（阶段 A）完成后，写：

audit/phase_a_review.md（阶段 A 复核报告）

报告内容：

1. 3 条 CandidatePack（候选知识包）的路径
2. 每条 knowledge_assertion（知识断言）
3. 每条 4 Gates（四闸）结果
4. 每条 9 表派生行数
5. 每条 brand_layer（品牌层）
6. 每条 reverse_infer（反推）是否成立
7. 是否出现空壳风险
8. 是否建议进入 Phase B（阶段 B）

Phase A（阶段 A）完成后必须停，等待人工确认。

不要直接进入 Phase B（阶段 B）。

---

### Phase B（阶段 B）：批量抽取

人工确认 Phase A（阶段 A）后，才进入 Phase B（阶段 B）。

推荐顺序：

1. Q7Q12-搭配陈列业务包（搭配陈列业务包目录）
2. Q4-人设种子（人设种子目录）
3. Q2-内容类型种子（内容类型种子目录）

每份 markdown（标记文档）处理流程：

1. 通读全文。
2. 识别业务知识单元。
3. 对每个单元先写 knowledge_assertion（知识断言）。
4. 写不出来则进 UnprocessableRegister（不可处理登记表）。
5. 选择 pack_type（知识包类型）。
6. 填 CandidatePack（候选知识包）。
7. 做 brand_layer（品牌层）判断。
8. 做 4 Gates（四闸）自检。
9. 生成 nine_table_projection（九表投影建议）。
10. 追加 extraction_log（抽取日志）。

每处理 5 份 markdown（标记文档），必须生成 checkpoint（检查点）摘要：

* 新增 CandidatePack（候选知识包）数量
* 新增 UnprocessableRegister（不可处理登记）数量
* 新增 needs_review（待人工复核）数量
* 主要 pack_type（知识包类型）分布
* 空壳风险
* blocker（阻断项）

---

### Phase C（阶段 C）：四闸验证

对所有 CandidatePack（候选知识包）运行 4 Gates（四闸）。

输出：

audit/four_gate_results.csv（四闸结果）

每行包含：

pack_id（知识包编号）
pack_type（知识包类型）
brand_layer（品牌层）
gate_1_closed_scenario（第一闸闭环场景）
gate_2_reverse_infer（第二闸九表反推）
gate_3_rule_generalizable（第三闸规则泛化）
gate_4_production_feasible（第四闸生产可用）
final_state（最终状态）
failure_reason（失败原因）

---

### Phase D（阶段 D）：9 表派生

只对满足以下条件的 CandidatePack（候选知识包）生成 9 表数据：

1. Gate 1（第一闸）不是 fail（失败）
2. Gate 2（第二闸）不是 fail（失败）
3. knowledge_assertion（知识断言）合格
4. evidence_quote（证据原文摘录）可支撑业务断言

输出 9 张 CSV（逗号分隔值文件）：

nine_tables（九张表目录）/
01_object_type.csv（对象类型表）
02_field.csv（字段表）
03_semantic.csv（语义表）
04_value_set.csv（取值集表）
05_relation.csv（关系表）
06_rule.csv（规则表）
07_evidence.csv（证据表）
08_lifecycle.csv（生命周期表）
09_call_mapping.csv（调用映射表）

---

### Phase E（阶段 E）：单库存储方案

生成：

storage/single_db_logical_isolation.sql（单库逻辑隔离建表 SQL）

只实现：

single_db_logical_isolation（单库逻辑隔离）

要求：

1. 9 张表 CREATE TABLE（建表语句）
2. 每张表含 brand_layer（品牌层）
3. 每张表含 source_pack_id（来源知识包编号）
4. brand_layer（品牌层）建立索引
5. source_pack_id（来源知识包编号）建立索引
6. 提供 domain_general（领域通用）查询示例
7. 提供 brand_faye（笛语品牌层）查询示例
8. 提供未来 brand_xyz（新品牌层）扩展说明

不做物理分库。
不做多方案转换脚本。

---

### Phase F（阶段 F）：收口报告

生成：

audit/final_report.md（最终报告）

必须包含：

1. 输入 markdown（标记文档）数量
2. CandidatePack（候选知识包）数量
3. 过 4 Gates（四闸）的数量和比例
4. 进入 UnprocessableRegister（不可处理登记表）的数量和分类分布
5. brand_layer（品牌层）分布
6. pack_type（知识包类型）分布
7. 9 Tables（九张表）各表行数
8. needs_review（待人工复核）数量
9. 空壳风险检查结论
10. 抽样 reverse_infer（反推）结果
11. 下一步建议

---

## 16. 停止条件

遇到以下情况必须停，写入 audit/blockers.md（阻断项说明）：

1. Phase A（阶段 A）3 条样本中有 1 条无法写出合格 knowledge_assertion（知识断言）。
2. Phase A（阶段 A）3 条样本中有 1 条 Gate 2（第二闸）无法反推。
3. 批量抽取中超过 30% 内容进入 scenario_not_closed（场景不闭环）。
4. 单个 CandidatePack（候选知识包）派生 9 表超过 50 行。
5. brand_layer（品牌层）无法判断的项连续超过 20 条。
6. 同一素材段被反复抽成重复 CandidatePack（候选知识包）。
7. 执行中发现大量素材是工程流程、元层定义，而非业务知识。
8. 出现明显互相冲突的规则。
9. 执行 AI（人工智能）只能生成空泛总结，无法抽出具体业务断言。

---

## 17. 人工验收标准

人工验收时会检查：

1. 抽样 5 条 CandidatePack（候选知识包），knowledge_assertion（知识断言）是否具体。
2. 抽样 5 条 CandidatePack（候选知识包），success_pattern（成功模式）和 flip_pattern（翻车模式）是否成对。
3. 抽样 5 条 CandidatePack（候选知识包），evidence_quote（证据原文摘录）是否能支撑断言。
4. 抽样 5 条 9 表派生记录，是否能反推原 CandidatePack（候选知识包）。
5. UnprocessableRegister（不可处理登记表）是否分类合理。
6. brand_layer（品牌层）是否没有默认乱填。
7. pack_type（知识包类型）分布是否合理。
8. 是否有空壳 CandidatePack（候选知识包）。
9. 是否出现过度工程化输出。
10. 是否真正把 markdown（标记文档）业务血肉结构化进 9 Tables（九张表）。

---

## 18. 现在开始

请只执行 Phase A（阶段 A）。

不要进入 Phase B（阶段 B）。

Phase A（阶段 A）的任务是：

1. 从当前工作区素材中选 3 条样本：

   * 1 条 fabric_property（面料属性）
   * 1 条 service_judgment（接客判断）
   * 1 条 display_rule（陈列规则）

2. 为每条样本生成：

   * CandidatePack（候选知识包）
   * 4 Gates（四闸）自检
   * 9 Tables（九张表）派生行
   * brand_layer（品牌层）判断
   * evidence（证据）记录
   * reverse_infer（反推）说明

3. 写入：

   * candidates（候选知识包目录）
   * nine_tables（九张表目录）
   * unprocessable_register（不可处理登记目录）
   * audit/phase_a_review.md（阶段 A 复核报告）

4. 完成后停下，等待人工确认。

````

---

## 这个版本相比原版的关键优化

| 优化点 | 目的 |
|---|---|
| 先做 `Phase A（阶段 A）` 3 条样本 | 防止一上来批量空壳化 |
| 强化 `knowledge_assertion（知识断言）` | 防止只抽指针和状态 |
| 增加 `pack_type（知识包类型）` 抽取重点 | 防止一个模板硬套所有领域知识 |
| 明确 `Gate 2（第二闸）` 反推验收 | 防止 9 表碎片化 |
| 删除物理分库和转换脚本 | 避免过度工程化 |
| 限制审计文件数量 | 避免重新跑回元层 |
| 加停止条件 | 执行 AI（人工智能）能力不足时及时暴露 |
| 明确不要继承旧工作区 | 避免历史噪音污染 |

最终目标只剩一个：

```text
把 markdown（标记文档）里的真实服装零售业务知识，
变成 CandidatePack（候选知识包）和 9 Tables（九张表）里的可机器消费领域模型。
````
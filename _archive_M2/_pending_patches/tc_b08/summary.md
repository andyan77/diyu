# TC-B08 抽取摘要 · 岗位手感与一线判断包

## 输入
- Q7Q12-搭配陈列业务包/岗位手感与一线判断包.md
- 软依赖：TC-B04（10 类接客）+ TC-B07（培训纠错 13 条）作为去重基线

## pack 数：5（全部 pack_type=training_unit, brand_layer=domain_general）

| pack_id | RoleProfile | 主断言核心 |
|---|---|---|
| KP-training_unit-store-manager-rhythm-first | store_manager | 货场主次→店员站位→顾客停顿→后场接力 四步看节奏 |
| KP-training_unit-warehouse-supervisor-fact-not-promise | warehouse_supervisor | 拒绝 4 类前场乱推（断码当齐码/替代当同款/调货未确认/成套与货况脱节）|
| KP-training_unit-designer-locate-defect-source | designer | 样衣问题先按版型/面料/细节三选一定位根因 |
| KP-training_unit-sample-worker-rework-as-judgment | sample_worker | 返工是工艺判断；区分补表面 vs 补根因 |
| KP-training_unit-merch-director-stylable-not-sellable | merchandising_director | 搭配挂结构+价位+连带+体感+门店承接 5 维同时看 |

## 4 闸通过率：5/5 全 pass

## 9 表新增行数（合计 21 行）
- 01_object_type: 0（OT-RoleProfile/OT-TrainingMaterial/OT-InventoryState 已存在，复用）
- 02_field: 0
- 03_semantic: 0
- 04_value_set: 0
- 05_relation: 6（5 条 spoken_by_role + 1 条 requires_inventory_state）
- 06_rule: 5
- 07_evidence: 5
- 08_lifecycle: 0
- 09_call_mapping: 5

## 与 B04 / B07 去重（4 条进 unprocessable_register）
- UP-tcb08-001 sales_associate 岗位手感 → duplicate_or_redundant（B04 + B07 已覆盖）
- UP-tcb08-002 design_director 岗位手感 → evidence_insufficient（无具体业务断言；具体品牌边界应进 brand_<name>）
- UP-tcb08-003 "只能参考不能写硬规则" 反例清单 → duplicate_or_redundant（B04/B07 flip_pattern 已隐含）
- UP-tcb08-004 §二/三/四/七 元规则 → meta_layer_not_business

去重项合计：3 条与 B04/B07 重复 + 1 条元层 = 4 条。

## 验收抽样反推（3 条全部成立）
- store-manager-rhythm-first：RL.success/flip 可反推"四看顺序诊断节奏"主断言
- warehouse-supervisor-fact-not-promise：RL + RE-requires_inventory_state(size_broken/set_incomplete/substitute_only/transfer_pending) 可反推"4 类乱推"边界
- merch-director-stylable-not-sellable：RL 5 维诊断可反推"搭得成立≠卖得成立"主断言

## 不变量自检
- pack_id 遵循 SKILL.md §10
- RE-* 用 tcb08-NN 后缀避免撞键
- success/flip 成对，evidence_quote 直引原文
- 单条派生 ≤ 5 行（远低于 50 行）
- 全部 domain_general（岗位手感属通用门店运营规则）

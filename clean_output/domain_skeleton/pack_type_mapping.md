# pack_type_mapping（知识包类型到对象类型映射说明）

> Phase 0 产出，仅用于约束 Phase A 起的抽取挂靠。
> 不替代抽取，不替代正式 schema。

## 映射总览

| pack_type | 主对象（落在哪） | 可关联对象 | 默认必投 9 表 |
|---|---|---|---|
| `fabric_property` | `FabricKnowledge` | `Product` / `Attribute` / `TrainingMaterial` / `StylingRule` | semantic / value_set / rule / evidence |
| `craft_quality` | `CraftKnowledge` | `Product` / `TrainingMaterial` / `DisplayGuide` | semantic / rule / evidence |
| `styling_rule` | `StylingRule` | `Product` / `Attribute` / `CustomerScenario` / `InventoryState` | rule / evidence / call_mapping |
| `display_rule` | `DisplayGuide` | `Product` / `Category` / `InventoryState` / `StylingRule` | rule / relation / evidence / call_mapping |
| `service_judgment` | `CustomerScenario` + `TrainingMaterial` | `RoleProfile` / `Product` / `StylingRule` | rule / evidence / call_mapping |
| `inventory_rescue` | `InventoryState` + `StylingRule` + `DisplayGuide` | `Product` / `CustomerScenario` | rule / relation / evidence / call_mapping |
| `training_unit` | `TrainingMaterial` | `RoleProfile` / `StylingRule` / `DisplayGuide` / `InventoryState` | rule / evidence / call_mapping |
| `product_attribute` | `Product` / `Category` / `Attribute` | `StylingRule` / `DisplayGuide` | field / semantic / value_set / evidence |

## 抽取过程中的挂靠纪律

1. 一条 CandidatePack 只能挂一个 `pack_type`，不得复合。
2. `nine_table_projection.relation` 中的 `relation_kind` 必须来自 `domain_skeleton.yaml` 的 `allowed_relation_kinds` 清单。
3. 出现 skeleton 之外的概念时，写入 `skeleton_gap_register.csv`，**不要在 9 表里临时造对象/关系**。
4. 默认不投 `lifecycle`；只有素材明确出现状态迁移（例如库存状态从 `new_arrival_complete` 流向 `clearance_tail_stock`）才投。

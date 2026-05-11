# TC-B06 抽取小结

> 日期：2026-05-03
> 源 MD：`Q7Q12-搭配陈列业务包/库存与替代包.md`
> 模式：agent 截断后主控接管 + 复用 agent 已落 yaml

## 产出
- pack：10 条全 `inventory_rescue` / `domain_general`（agent 被 socket kill 前已落盘）
  - state-catalog-six-states / three-sentence-discipline
  - hard-block-five-conditions / soft-substitute-four-paths
  - customer-priority-six-axes / display-priority-five-axes
  - shallow-vs-deep-sensing / match-result-output-shape
  - can-rescue-scenarios（与 B04 重叠，原行保留）/ no-rescue-scenarios（同上）
- 4 闸：10/10 全 pass
- 9 表新增数据行：8 净新 pack 派生 ~115 行（其中 2 条 can/no-rescue-scenarios 在 B04 阶段已派生）

## value_set 复用
- 与 B03 `VS-KP-display_rule-full-look-no-broken-size-allowed_inventory / forbidden_inventory` 互为补集，不冲突
- B06 新建独立 inventory_state catalog（6 状态），下游 B03/B04 子集仍可继续使用

## 主控接管细节
- agent 任务被 socket 截断
- 主控初次手抽 4 条（six-state-catalog / three-mode-decision / five-hard-block / priority-wearability-first）发现与 agent 已落盘 10 条主题重复，已回滚（删 yaml + 移 9 表行）
- 最终采用 agent 10 条作为正式产出

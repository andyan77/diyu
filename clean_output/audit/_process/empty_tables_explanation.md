---
snapshot_type: live
last_validated: 2026-05-03
rationale: 9 表行数现状说明，随 manifest 演进；G18 检测此文档与 manifest 的数值一致性
---

# 9 表行数现状与暂空说明

> 范围：9 张表当前数据行 + 暂空表（行数=0）的产生条件

---

## 当前 9 表行数（与 manifest.json `nine_tables.data_rows` 对齐）

| 表 | 行数 |
|---|---:|
| 01_object_type | 18 |
| 02_field | 98 |
| 03_semantic | 163 |
| 04_value_set | 604 |
| 05_relation | 173 |
| 06_rule | 201 |
| 07_evidence | 201 |
| 08_lifecycle | 1 |
| 09_call_mapping | 243 |

合计 1702 数据行（W13.A 跨工作区引入新增 7 rule + 7 evidence）。

---

## 08_lifecycle 当前 1 行（W3+ 后已不再为空）

W3 之后已抽出 1 条 lifecycle 行：

- `LC-emotion_expression-prepublish`（owner_type=ContentType，generated → published_or_downgraded，三锚点全 pass → published；任一 fail → downgraded 或剔除）

W1+W2 阶段无 lifecycle 行，因当时 8 份 MD 全部以"规则+触发条件+成功/翻车模式"表达，不以状态机表达。W3 起 ContentType 内容类型族出现明确发布状态机叙述，故新增 1 条。

后续 MD 抽取若再出现状态迁移叙述（Persona 字段成熟度 / RoleProfile 启用 / InventoryState 转移），可继续填充。

---

## 关于"暂空"原则

按 SKILL.md §8 的"无内容的列暂空但表头保留"原则，9 表中如再次出现行数=0 的表，需在此文件追加说明，并标注 W 几抽取后预期可填。

禁止编造空话凑行——0 行是合法状态。

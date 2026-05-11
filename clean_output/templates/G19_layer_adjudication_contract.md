# G19 三层裁决完整性 · 硬门契约（W11 立法）

> 状态：草案，等 W11.1 人工复核完成后启用
> 适用：`audit/source_unit_adjudication_v2.csv` + `audit/pack_layer_register.csv`

---

## 一、6 类合法 final_status 枚举

```
extract_l1
extract_l2
defer_l3_to_runtime_asset
merge_to_existing
unprocessable
duplicate
```

任何 final_status 不在此白名单 → G19 触红。

## 二、final_layer 合法枚举

```
L1   # 概念层
L2   # 玩法层
L3   # 执行层
L_NA # unprocessable / duplicate（无层语义）
```

## 三、必填规则（按 final_status 分流）

| final_status | 必填字段 |
|---|---|
| `extract_l1` | `final_layer=L1`、`reviewer_decision`、`review_notes`（≥10 字） |
| `extract_l2` | `final_layer=L2`、`production_tier ∈ {instant,long_term,brand_tier}`、`default_call_pool ∈ {true,false}` |
| `defer_l3_to_runtime_asset` | `final_layer=L3`、`review_notes`（说明 asset_type） |
| `merge_to_existing` | `merge_target` 必须是 candidates 中存在的 pack_id |
| `unprocessable` / `duplicate` | `final_layer=L_NA` |

## 四、完整性规则

- 1578 行 source_unit 必须 100% 有 `final_status`（无空、无 `_pending_review_`）
- 194 行 pack_layer_register 必须 100% 有 `final_layer`
- `reviewer_decision` 必须 ∈ {accept, override, defer}
- `accept` ⇒ `final_status == suggested_status` 且 `final_layer == suggested_layer`
- `override` ⇒ `review_notes` 非空且 ≥10 字（解释覆写原因）
- `defer` ⇒ 暂时允许，但 G19 会 warning（不阻断）

## 五、与 W10 4 态的迁移规则（apply 脚本依据）

W10 → W11：
- `covered_by_pack` → `extract_l1`（layer 由 pack_layer_register 决定）
- `unprocessable` → `unprocessable`
- `duplicate_or_redundant` → `duplicate`
- `pending_decision` → 必须由 reviewer_decision 转成 6 类之一

## 六、dry-run 输出契约

`apply_layer_adjudication.py --dry-run` 必须输出：

1. **变更摘要**：
   - 多少 source_unit 状态变更（按 from→to 计数）
   - 多少 yaml 文件将被改写（pack 加 `granularity_layer` + 可选 production 字段）
   - 多少 csv 行将更新
2. **冲突清单**：
   - reviewer_decision=override 但 review_notes 不足 10 字
   - extract_l2 但 production 字段缺失
   - merge_to_existing 但 merge_target 不存在
3. **零写入保证**：dry-run 模式不允许触碰任何 yaml/csv 文件
4. **退出码**：有冲突返回 1，无冲突返回 0

实际写回必须 `--apply --confirmed`，且：
- 自动备份 `audit/_process/_backup_w11/`（同 W10 模式）
- 写回后立即跑 24 道硬门 + G19，任一失败立即报错（但不回滚——交由人工 review 后决定）

## 七、G19 实现要求（`scripts/check_layer_adjudication.py`）

输入：`audit/source_unit_adjudication_v2.csv` + `pack_layer_register.csv`

检查项：
1. `final_status` 全行非空且在 6 类白名单
2. 每行按 final_status 必填字段满足
3. `reviewer_decision` 全行非空
4. `merge_target` 引用合法
5. accept 行 final == suggested

任一失败 → 退 1 + 写 `audit/_process/g19_violations.csv`。

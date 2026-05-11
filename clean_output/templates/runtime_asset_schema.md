# L3 执行资产 schema · W12 立法

> 状态：W12.0 立法版 · 与 W11 立法对齐
> 适用：所有 `granularity_layer: L3` 的 pack（按 D2 决议进 `clean_output/runtime_assets/`，不进 9 表核心）

---

## 一、必填字段

| 字段 | 取值 | 说明 |
|---|---|---|
| `runtime_asset_id` | `RA-<pack_id 后缀>` | 唯一标识 |
| `asset_type` | **W11 受控枚举**（D7 拍板）：`shot_template` / `dialogue_template` / `action_template` / `prop_list` / `role_split` | L3 资产五类 |
| `granularity_layer` | `L3` | 三层粒度标识（继承自 W11） |
| `consumption_purpose` | `execution` | 用途——操作/执行 |
| `source_pointer` | `<source_md>:<line_no>` | 反查原 md 位置 |
| `source_pack_id` | string | 关联 candidates/ pack（与 9 表反查） |
| `brand_layer` | `domain_general` / `brand_<name>` / `needs_review` | 多租户隔离 |
| `content_pointer` | `runtime_assets/templates/<asset_id>.md` | 实际资产文件位置（可选，先建索引后慢慢补内容） |

> production 字段在 L3 不强制（与 W11 立法一致：`production 字段可选，除非是视频执行模板`）

---

## 二、目录结构

```
clean_output/
  runtime_assets/
    runtime_asset_index.csv      # 索引表（所有 L3 资产一行）
    templates/
      shot_templates/             # 镜头脚本模板（W12.A 暂空，W12.B 填）
      dialogue_templates/
      action_templates/
      prop_lists/
      role_splits/
```

---

## 三、runtime_asset_index.csv 列定义

```
runtime_asset_id, asset_type, granularity_layer, consumption_purpose,
source_pointer, source_pack_id, brand_layer, content_pointer,
created_at, last_validated
```

W12.A 阶段 `content_pointer` 可空（仅注册不落实际模板内容），W12.B 阶段补具体模板。

---

## 四、yaml 写入位置（如 L3 pack 来自现有 candidates）

24 个 L3 pack 当前都在 candidates/ 里。W12 在其 yaml 顶部添加 `runtime_asset:` 块（与 play_card 块平行）：

```yaml
pack_id: KP-...
granularity_layer: L3
schema_version: candidate_v1
pack_type: ...
brand_layer: domain_general
state: drafted

runtime_asset:
  runtime_asset_id: RA-...
  asset_type: shot_template
  consumption_purpose: execution
  source_pointer: "Q4-人设种子/xxx.md:42"
  content_pointer: ""    # W12.A 暂空
```

---

## 五、asset_type 受控枚举（W11 立法版本，D7 强制）

| asset_type | 含义 | 典型样本 |
|---|---|---|
| `shot_template` | 镜头脚本/分镜模板 | "OOTD 三段式：远景→中景→特写" |
| `dialogue_template` | 台词/口播模板 | "开场不能说'最后机会'，应说..." |
| `action_template` | 拍摄动作/手势模板 | "开柜门 → 凝视 3 秒 → 拿起单品" |
| `prop_list` | 道具清单 | "拍摄日所需道具：5 件商品 + 灯具 + ..." |
| `role_split` | 角色分工 | "店长拍 / 店员收音 / 助理盯灯" |

不在 5 类的进 unprocessable，不允许临时新增。

---

## 六、G21 硬门契约

`scripts/check_runtime_asset.py` 校验：

1. 每个 `granularity_layer: L3` pack 的 yaml 必须含完整 `runtime_asset:` 块
2. `runtime_asset_index.csv` 行数 == L3 pack 总数（当前 24）
3. `asset_type` 必须 ∈ 5 类受控枚举
4. `runtime_asset_id` 唯一且以 `RA-` 开头
5. `source_pointer` 必须解析为 `<md>:<line>` 且 md 存在
6. `source_pack_id` 必须在 candidates/ 找到
7. 失败仅写 `audit/_process/g21_violations.csv`

---

## 七、与 9 表的关系

L3 资产**不进 9 表核心库**（D6 拍板）。但通过 `source_pack_id` 与 9 表 `06_rule.source_pack_id` 等列做反查，下游可以"按 rule_id 找其执行模板"。

> D3 拍板：W12.A 不在 09_call_mapping 加 runtime_asset_id 列。W13 再视下游需求决定是否补"调用入口"行。

---

## 八、L3 与 L2 的边界

| 维度 | L2 玩法卡 | L3 执行资产 |
|---|---|---|
| 用途 | 生成（结构骨架） | 操作（具体动作/模板） |
| 落地 | play_card_register.csv（旁路）+ 9 表 source_pack_id 反查 | runtime_asset_index.csv + templates/ |
| production 字段 | 必填 6 个（W11 强制） | 可选 |
| 受控枚举 | 无（业务字段开放） | asset_type 5 类受控 |
| 重叠场景 | 一张玩法卡可引用多个 L3 资产（未来 W13 加 `linked_assets:` 字段） | 一个 L3 资产可被多张玩法卡复用 |

---

## 九、W12.A 验收口径

- 24 个 L3 pack 的 yaml 全部含 `runtime_asset:` 块
- `runtime_assets/runtime_asset_index.csv` 24 行，asset_type 5 类全在白名单
- G21 硬门绿
- W11 三层裁决证据继续成立（W12 不污染 W11）

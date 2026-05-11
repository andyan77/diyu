---
snapshot_type: live
last_validated: 2026-05-04
rationale: W12.A 三层资产化 + G20/G21 收口验收报告
---

# W12.A 验收报告 · 三层资产化 + G20/G21

> 范围：W12.0 立法 → W12.A.3-6 审表+写回 → W12.A.7-8 G20/G21 接入 → W12.A.9 demo → W12.A.10 验收

---

## 一、验收结论

✅ **PASS** · 27/27 硬门绿 · 15/15 W12 对抗测试通过 · 29 L2 + 24 L3 资产化完成 · W11/W10 兼容层完整保留

> W12.A 是 W12 的最小可交付（资产契约 + 硬门）。W12.B（329 L2 新抽 + 128 L3 新抽）按 D4 决议**推迟**到下一轮，本轮不承诺。

---

## 二、27 道硬门成绩

| 段 | Gate | 检查 | 状态 |
|---|---|---|:---:|
| W2-W7 | G0-G14 / Gv | 抽取闭环 + 多租户 + schema + FK | 14 ✅ |
| W8-W10 | G15-G18 | 顶层纯净 + 章节级 + row 级 + 派生文档 | 10 ✅ |
| W11 | G19 | 三层裁决完整性 | 1 ✅ |
| **W12** | **G20** | **L2 玩法卡完整性（12 必填字段 + FK + 受控枚举）** | **1 ✅** |
| **W12** | **G21** | **L3 runtime_asset 注册完整性（5 类受控 asset_type + 唯一 ID）** | **1 ✅** |

合计 **27 道，0 红 / 0 跳过**。

---

## 三、W12.A 资产化产出

### 3.1 立法（templates/）

- `play_card_schema.md` · L2 玩法卡 yaml schema：W11 基线 6 字段（granularity_layer / consumption_purpose / production_difficulty / production_tier / resource_baseline / default_call_pool）+ W12 业务 6 字段（hook / steps / anti_pattern / duration / audience / source_pack_id）
- `runtime_asset_schema.md` · L3 资产格式：5 类受控 asset_type（shot_template / dialogue_template / action_template / prop_list / role_split）

### 3.2 旁路真源（B-lite 决议下不进 9 表）

- `play_cards/play_card_register.csv` · **29 行** L2 玩法卡
  - production_tier: instant=28 / long_term=1
  - default_call_pool=true: 29/29
  - production_difficulty: 由人工审填，分布见 `final_report.md` §6.6
  - duration: short / medium / long 分布见 §6.6
- `runtime_assets/runtime_asset_index.csv` · **24 行** L3 资产
  - asset_type: action_template=9 / role_split=8 / dialogue_template=5 / shot_template=2 / prop_list=0

### 3.3 yaml 注入（194 个 pack 中 53 个被改）

- 29 个 L2 yaml 加 `play_card:` 块（W11 基线字段已在顶部，W12 在 `default_call_pool` 后追加）
- 24 个 L3 yaml 加 `runtime_asset:` 块（含 runtime_asset_id / asset_type / title / summary / source_pointer）
- 不动现有任何顶部字段（pack_id / pack_type / brand_layer / state / knowledge_assertion / scenario / ...）

### 3.4 demo（W12.A.9）

- `scripts/dify_consume_demo.py` · 5 段 demo：
  - Demo 1: play_card → 9 表 rule → evidence → 原 md 反查链路
  - Demo 2: runtime_asset → yaml 反查
  - Demo 3: 多租户组合查询（domain_general / brand_xyz）
  - Demo 4: L2 按 default_call_pool 过滤
  - Demo 5: L3 按 asset_type 分桶
- 输出: `runtime_assets/dify_demo_log.txt`
- 验证消费方可按"领域通用 + 品牌专属"组合调用，反查链路完整

---

## 四、W12 对抗+边缘测试（15/15 通过）

`scripts/run_w12_adversarial_tests.py` 实测：

| ID | 用例 | 结果 |
|---|---|:---:|
| W12-T1 | G20 缺 hook | ✅ |
| W12-T2 | G20 hook < 10 字 | ✅ |
| W12-T3 | G20 production_difficulty 非法 | ✅ |
| W12-T4 | G20 duration 非法 | ✅ |
| W12-T5 | G20 production_tier 非法 | ✅ |
| W12-T6 | G20 source_pack_id FK 断 | ✅ |
| W12-T7 | G20 steps_count < 2 | ✅ |
| W12-T8 | G21 asset_type 非法 | ✅ |
| W12-T9 | G21 title < 6 字 | ✅ |
| W12-T10 | G21 summary < 10 字 | ✅ |
| W12-T11 | G21 runtime_asset_id 重复 | ✅ |
| W12-T12 | W11 主表分布不变（W12 不污染 W11） | ✅ |
| W12-T13 | 9 表数据不变（W12 仅 yaml + 旁路） | ✅ |
| W12-T14 | 29 L2 yaml 含 play_card: 块 | ✅ |
| W12-T15 | 24 L3 yaml 含 runtime_asset: 块 | ✅ |

还原后 full_audit 27/27 仍绿，零业务数据污染。

---

## 五、不变性证据（W12 不污染 W10/W11）

- 9 表行数: 1688（不变）
- W11 主表 `_w11.csv` 1578 行 + 三层分布（extract_l1=454 / extract_l2=329 / defer_l3=128 / unprocessable=658 / duplicate=9）不变
- W10 兼容主表 `source_unit_adjudication.csv` 4 态（357/430/9/782）不变
- 24 道 W10/W11 兼容硬门完全保留，G19 不动

---

## 六、W12.B 推迟说明（按 D4 决议）

下面这些不在本轮承诺：

- **W12.B.1** L3 注册（128 条 W11 标 `defer_l3_to_runtime_asset` 的 source_unit）→ 仅有 24 已标 L3 pack 资产化，其余 128 章节未抽
- **W12.B.2-4** L2 玩法卡新抽（329 条 W11 标 `extract_l2` 的 source_unit）→ 仅有 29 已标 L2 pack 资产化
- **G22 / G23** source_unit → register/index 反查可达硬门 → 推迟，等 B 启动后启用

W13 启动条件：W12.A 成品稳定 + 下游笛语 AI 真实调用样例确认有价值。

---

## 七、关键产物清单

| 类型 | 路径 |
|---|---|
| 立法 | `templates/play_card_schema.md` · `templates/runtime_asset_schema.md` |
| 旁路真源 | `play_cards/play_card_register.csv` (29) · `runtime_assets/runtime_asset_index.csv` (24) |
| 审表 | `audit/l2_play_card_review.csv` · `audit/l3_runtime_asset_review.csv` |
| 写回脚本 | `scripts/apply_l2_play_card.py` · `scripts/apply_l3_runtime_asset.py`（默认 dry-run） |
| 硬门脚本 | `scripts/check_play_card.py` (G20) · `scripts/check_runtime_asset.py` (G21) |
| demo | `scripts/dify_consume_demo.py` · 输出 `runtime_assets/dify_demo_log.txt` |
| 对抗测试 | `scripts/run_w12_adversarial_tests.py` (15/15) |
| 备份 | `audit/_process/_backup_w12/<utc-ts>/` |
| 报告 | `audit/final_report.md` §6.6/§6.7 + 本文件 |

---

## 八、回滚预案

```bash
# 1. 还原 yaml + register + index
cp audit/_process/_backup_w12/<ts>/yamls/* candidates/<sub>/   # 注：需手工分目录
cp audit/_process/_backup_w12/<ts>/play_card_register.csv play_cards/   # 旧版无此文件则删除
cp audit/_process/_backup_w12/<ts>/runtime_asset_index.csv runtime_assets/

# 2. 删 W12 旁路目录（彻底回滚到 W11）
rm -rf play_cards/ runtime_assets/

# 3. 从 full_audit GATES 移除 G20/G21（手工编辑 full_audit.py）

# 4. 重跑 25 道
python3 scripts/full_audit.py
```

W12.A 与 W11 的依赖：仅依赖 `pack_layer_register.csv` 的 `final_layer` 列。回滚 W12.A 不影响 W11。

---

> 本报告由 W12.A.10 验收阶段生成，2026-05-04。

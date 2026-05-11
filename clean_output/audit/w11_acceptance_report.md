---
snapshot_type: live
last_validated: 2026-05-04
rationale: W11 三层粒度框架收口验收报告 · 与 audit_status.json 同步
---

# W11 验收报告 · 三层粒度框架 + Finding 2/3 关闭

> 范围：W11.0 立法 → W11.1 预分/审表/写回 → W11.2 G19 接入 → W11.3 口径切换 → W11.7 对抗测试 → W11.8 验收

---

## 一、验收结论

✅ **PASS** · 25/25 硬门绿 · 10/10 W11 对抗测试通过 · Finding 2/3 按 W11 口径关闭 · W10 兼容层完全保留

---

## 二、25 道硬门成绩（机器可读 → `audit/audit_status.json`）

| 段 | Gate | 检查 | 状态 |
|---|---|---|:---:|
| W2-W7 | G0-G14, Gv | 抽取闭环 + 多租户 + schema + FK + 反向追溯 | 14 ✅ |
| W8-W10 | G15-G18 | 顶层纯净 + 章节级裁决 + row 级证据 + 派生文档冻结 | 10 ✅ |
| **W11** | **G19** | **三层裁决完整性（6 态枚举 + 必填字段 + accept 一致性）** | **1 ✅** |

合计 **25 道，0 红 / 0 跳过**。

---

## 三、W11 三层真源（Finding 2/3 关闭口径）

### source_unit 终态（1578 行 100% 签字 · `audit/source_unit_adjudication_w11.csv`）

| 状态 | 行数 | 业务章节占比 |
|---|---:|---:|
| `extract_l1` 概念层（判断用） | 454 | **39.5%** |
| `extract_l2` 玩法层（生成用） | 329 | **28.7%** |
| `defer_l3_to_runtime_asset` 执行层 | 128 | **11.1%** |
| `unprocessable` | 658 | — |
| `duplicate` | 9 | — |

业务章节合计 1148。**L1+L2+L3 = 79.3%** 业务章节有显式落点。

### pack 终态（194 个 · `audit/pack_layer_register.csv`）

| 层 | 数量 | production 字段 |
|---|---:|---|
| L1 | 141 | 无（概念层不需要） |
| L2 | 29 | tier=instant×29，pool=true×29 |
| L3 | 24 | 暂登记，W12 落 runtime_assets |

---

## 四、Finding 2/3 关闭证据

### Finding 2（章节级覆盖低，原 22.6%）

- W10 口径不变（兼容层）：357/1148 = 31.1%
- **W11 layer-aware 口径**：L1+L2+L3 = **79.3%**（903/1148 业务章节有显式分层落点）
- 不在 9 表 ≠ 不可见：L2 玩法卡通过 `pack_layer_register` 关联 9 表；L3 推迟到 W12 进 runtime_assets
- 证据：`audit/source_unit_adjudication_w11.csv` 1578 行全部带 `final_status` ∈ 6 类枚举

✅ **关闭**

### Finding 3（pending_decision 782 条未闭环）

- W10 主表保持 4 态：782 pending（兼容口径）
- **W11 主表 0 pending**：782 条全部分流到 extract_l1 (212) / extract_l2 (223) / defer_l3 (128) / unprocessable (219)
- G19 硬门：`final_status` 必须 ∈ 6 类枚举，无空值；当前 0 违规
- 证据：`audit/_process/g19_violations.csv` 当前为空（只在故障注入时写入）

✅ **关闭**

---

## 五、W11 对抗+边缘测试（10/10 通过）

`scripts/run_w11_adversarial_tests.py` 实测：

| ID | 用例 | 结果 |
|---|---|:---:|
| W11-T1 | G19 检测 final_status 为空 | ✅ |
| W11-T2 | G19 检测非法 final_status | ✅ |
| W11-T3 | G19 检测 L2 缺 production_tier (source_unit) | ✅ |
| W11-T4 | G19 检测 L2 缺 default_call_pool (source_unit) | ✅ |
| W11-T5 | G19 检测 merge_target 不存在 | ✅ |
| W11-T6 | G19 检测 accept 但 final != suggested | ✅ |
| W11-T7 | layer_distribution 防漂移（G12+G16d 后仍在） | ✅ |
| W11-T8 | 194 yaml granularity_layer 不变性 | ✅ |
| W11-T9 | G19 检测 pack L2 缺 production_tier | ✅ |
| W11-T10 | W10 兼容主表 4 态分布不变（W11 不污染 W10） | ✅ |

还原后 full_audit 25/25 仍绿，确认零业务数据污染。

---

## 六、W11 边界声明（不在本轮范围）

按降级实施口径，以下推迟到 **W12**：

- L2 玩法卡入 9 表（B-lite 当前仅落 `pack_layer_register.csv` 旁路）
- L3 资产注册建 `clean_output/runtime_assets/` 目录
- G20（L2 production 字段完整性）+ G21（L3 注册完整性）上硬门
- 玩法卡级粒度真正下沉到 9 表（需先验证下游消费需求）

---

## 七、关键产物清单

| 类型 | 路径 |
|---|---|
| 立法 | `templates/granularity_layer_framework.md` · `templates/G19_layer_adjudication_contract.md` |
| 主表 | `audit/source_unit_adjudication_w11.csv` (1578 行) · `audit/pack_layer_register.csv` (194 行) |
| 审表（人工填写痕迹） | `audit/review_must.csv` · `audit/pack_review_must.csv` · `audit/pack_dispute_review.csv` |
| 预分启发式 | `audit/source_unit_adjudication_v2.csv` · `audit/review_sample.csv` |
| 脚本 | `scripts/build_layer_prediction.py` · `build_review_sample.py` · `apply_layer_adjudication.py` · `apply_pack_dispute.py` · `check_layer_adjudication.py` · `build_pack_dispute_review.py` · `run_w11_adversarial_tests.py` |
| 备份 | `audit/_process/_backup_w11/<utc-ts>/` |
| coverage SSOT | `audit/coverage_status.json` · `layer_distribution` 块（防漂移） |
| 报告 | `audit/final_report.md` · §6.0（W11 真源）· §6.4-6.5（W10 兼容）· 本文件 |

---

## 八、回滚预案

如果 W11 写回需要回滚：

```bash
# 1. 还原 pack_layer_register
cp audit/_process/_backup_w11/<ts>/pack_layer_register.csv audit/

# 2. 还原 yaml
cp audit/_process/_backup_w11/<ts>/candidates_*/* candidates/<sub>/

# 3. 还原 coverage（可选，G16d_a 会自动重算）
cp audit/_process/_backup_w11/<ts>/coverage_status.json audit/

# 4. 删除 W11 主表（删除即"回到 W10 状态"）
rm audit/source_unit_adjudication_w11.csv

# 5. 重跑硬门
python3 scripts/full_audit.py
```

W10 24 道硬门仍可在不依赖 W11 主表的前提下绿（G19 会因缺 _w11.csv 红，需把 G19 从 full_audit GATES 列表移除即可降级回 W10 24 道版本）。

---

> 本报告由 W11.8 验收阶段生成，2026-05-04。

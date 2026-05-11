# 基线对齐证据 / Baseline Alignment Evidence · KS-S0-001

> 落盘日期 / date: 2026-05-12
> 任务卡 / task card: `KS-S0-001` · W12 基线漂移修复 / W12 baseline drift fix
> S 门 / S-gate: S0 baseline_alignment

## 1. 漂移现状 / drift snapshot (修复前 / before fix)

| 表 / table | 旧测试期望 / old expected | 实际行数 / actual rows | 漂移 / drift |
|---|---|---|---|
| `01_object_type` | 18 | 18 | ✅ 一致 |
| `02_field` | 98 | 98 | ✅ |
| `03_semantic` | 163 | 163 | ✅ |
| `04_value_set` | 604 | 604 | ✅ |
| `05_relation` | 173 | 173 | ✅ |
| **`06_rule`** | **194** | **201** | ❌ 漂移 +7 |
| **`07_evidence`** | **194** | **954** | ❌ 漂移 +760 |
| `08_lifecycle` | 1 | 1 | ✅ |
| `09_call_mapping` | 243 | 243 | ✅ |

漂移来源 / drift origin：W12 阶段新增 7 条 `brand_faye` rule（笛语品牌专属规则）+ evidence row 级裁决账本扩充。方案 §A1 中"201/201"描述与 evidence 实际值不符，本卡以实测为准 / actual values prevail。

## 2. 修复动作 / fix action

仅改测试常量 / test constants only，**9 表 CSV 0 改动 / 9 tables unchanged**：

| 文件 / file | 行 / line | 旧 | 新 |
|---|---|---|---|
| `clean_output/scripts/run_w12_adversarial_tests.py` | 106-107 | `"06_rule": 194, "07_evidence": 194` | `"06_rule": 201, "07_evidence": 954` |

W10 历史脚本 `adversarial_tests_w10.py:52-53` **不改**——W10 是已凝固历史快照 / frozen historical snapshot，按 CLAUDE.md 执行红线第 7 条"同一输入重复执行所有 ID 完全一致"。

## 3. 修复后结果 / post-fix result

```
$ python3 clean_output/scripts/full_audit.py
汇总: pass=26  deprecated=1  fail=0  skipped=0  total=27
gates pass/total: 26/27（含 G6 deprecated）
```

| 状态 / status | 计数 / count | 说明 |
|---|---|---|
| pass | 26 | 26 道硬门绿 |
| deprecated_pass | 1 | G6 `load_to_sqlite` 因 KS-S0-002 path B 决议废弃 |
| fail | 0 | 无失败 |
| skipped | 0 | 无跳过 |

## 4. manifest hash

待 KS-S0-006 执行后填入 / pending KS-S0-006:
- `source_manifest_hash`: <待生成>
- 当次 `manifest.json`: `clean_output/manifest.json`（已有，待重生成）

## 5. 9 表 CSV 改动核验 / 9-table unchanged verification

```
$ git diff --stat clean_output/nine_tables/
（应为空 / should be empty）
```

实测 / actual: `clean_output/nine_tables/*.csv` 全部 0 改动 ✓

## 6. 与 task_cards 的对应 / linkage

任务卡 KS-S0-001 status: `not_started` → `done`
dag.csv 同步更新。

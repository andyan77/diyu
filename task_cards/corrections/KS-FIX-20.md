---
task_id: KS-FIX-20
corrects: KS-DIFY-ECS-010
severity: RISKY
phase: Dify-ECS
wave: W11
depends_on: [KS-FIX-16, KS-FIX-19]
files_touched:
  - scripts/replay_context_bundle.py
  - knowledge_serving/audit/replay_KS-FIX-20.json
  - knowledge_serving/tests/test_replay_bulk_cli.py
artifacts:
  - knowledge_serving/audit/replay_KS-FIX-20.json
creates:
  - knowledge_serving/tests/test_replay_bulk_cli.py
status: done
---

# KS-FIX-20 · 全量 W11+ request_id replay（不只单条）

## 1. 任务目标
- **business**：原卡只证 1 个 request_id；dirty diff 显示 brand layer / overlay count 可漂；本卡：遍历 W11+ CSV 全部 request_id，每条 byte-identical 对账，落数组 artifact。
- **engineering**：失败 N 条都列出，不掩盖。
- **S-gate**：S11 retrieval determinism。
- **non-goal**：不改 retrieval 逻辑。

## 2. 前置依赖
- KS-FIX-16（API 真接 + 部署）。
- KS-FIX-19（Dify 真 chat 一例存在）。

## 3. 输入契约
- W11+ retrieval_log CSV 全部 request_id。

## 4. 执行步骤
1. 读所有 request_id list。
2. 逐条 replay（call API）；对比当时 bundle sha256。
3. 写 audit：数组形式，每条含 request_id / byte_identical / diff_summary。
4. F2：通过率 = byte_identical=true 数 / 总数；阈值 100% 才 pass。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/replay_KS-FIX-20.json` | json (array) | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | CLI 既不传 `--request-id` 也不传 `--all` | **fail-closed**：argparse 报错，exit 非 0 |
| AT-02 | `--all --strict` 全量 replay，artifact 是 per_row 数组、`count==total==CSV 行数` | 全 byte_identical=True → exit 0；任一 False → exit 非 0 |
| AT-03 | artifact 缺 runtime envelope（env/checked_at/git_commit/evidence_level） | 测试 fail |
| AT-04 | 单条模式 nonexistent request_id | exit 非 0（不要伪 PASS） |
| AT-05 | ci_gate 缺 `byte_identical_rate_eq_1.0` / `count_eq_total` | 测试 fail（防"挑选冒充全量"） |

## 7. 治理语义一致性
- 跨租户 0 串味（R7）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 scripts/replay_context_bundle.py --since W11 --all --strict --out knowledge_serving/audit/replay_KS-FIX-20.json
pass:    byte_identical_rate == 1.0 且 count == total
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25。

## 10. 独立审查员 Prompt
> 验：1) artifact 是数组不是单条；2) count 真等于 CSV 行数；3) 任何 diff 都被记录不被掩盖。

## 11. DoD
- [x] count == total（实测 168/168，复审后刷新到当前 canonical CSV 全量；audit.count=168=total=168；per_row 长度=168）
- [x] byte_identical_rate=1.0（168/168 byte_identical=True；fail=0；risky_flag=0；audit.ci_gate.byte_identical_rate_eq_1.0=True）
- [x] CLI 全量入口可执行（**复审 finding fix**：原 main() 只支持 `--request-id`，§8 ci_command `--since W11 --all --strict --out` 不可执行；本轮 main() 新增 `--all` 走 `_bulk_replay()` 路径 + `--since/--strict/--out` 接通；实测 `python3 scripts/replay_context_bundle.py --since W11 --all --strict --out knowledge_serving/audit/replay_KS-FIX-20.json` → exit 0 / verdict=PASS / 168/168）
- [x] AT-01..AT-05 全 pass（`python3 -m pytest knowledge_serving/tests/test_replay_bulk_cli.py -v` → 5 passed；test_replay.py 16 个 regression 同步通过）
- [x] artifact runtime_verified（`knowledge_serving/audit/replay_KS-FIX-20.json` 数组形式，env=staging / checked_at=2026-05-14T17:30+ / git_commit=e7d3671 baseline / evidence_level=runtime_verified / verdict=PASS / mode=bulk）
- [x] 审查员 pass（§10 三项：artifact 是 per_row 数组 / count 真等于 CSV 行数 168 / 任何 diff 都按行落 per_row.diff_summary；§6 row 3 adversarial 实测 nonexistent request_id → exit 2）
- [x] 原卡 KS-DIFY-ECS-010 回写（§14 追加 KS-FIX-20 全量 W11+ replay 数组补证段）

## 12. AT 映射 / test_id 映射

| AT | pytest function | 测试文件 |
|---|---|---|
| AT-01 | `test_at01_neither_request_id_nor_all_must_fail_closed` | knowledge_serving/tests/test_replay_bulk_cli.py |
| AT-02 | `test_at02_all_strict_array_artifact_against_full_csv` | knowledge_serving/tests/test_replay_bulk_cli.py |
| AT-03 | `test_at03_artifact_runtime_envelope_full` | knowledge_serving/tests/test_replay_bulk_cli.py |
| AT-04 | `test_at04_nonexistent_request_id_single_mode_exits_nonzero` | knowledge_serving/tests/test_replay_bulk_cli.py |
| AT-05 | `test_at05_subset_count_lt_total_strict_fail_closed` | knowledge_serving/tests/test_replay_bulk_cli.py |

## 16. 被纠卡同步 / sync original card

- 被纠卡：**KS-DIFY-ECS-010**（W11 主卡 · context bundle replay）。
- 同步动作：原卡 §14 实施记录已追加 KS-FIX-20 全量 W11+ replay 数组补证段（详见原卡 §14）。
- 双写 runtime artifact：[knowledge_serving/audit/replay_KS-FIX-20.json](../../knowledge_serving/audit/replay_KS-FIX-20.json)（本卡 §5 唯一 artifact，env=staging / evidence_level=runtime_verified / mode=bulk / count=total=168）。
- 同步时间戳：当前 canonical CSV 168 行全量 replay 复跑（复审后 156→168 刷新，eliminate 历史 PASS 冒充当前 PASS 的风险）。

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
artifacts:
  - knowledge_serving/audit/replay_KS-FIX-20.json
status: not_started
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
| 测试 | 期望 |
|---|---|
| 单条挑选冒充全量 | **fail-closed**：count < total → fail |
| brand layer 变化 byte_identical=true | 显式 RISKY 标注 |
| request_id 缺失原 bundle | exit 1 |

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
- [ ] count == total
- [ ] byte_identical_rate=1.0
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-DIFY-ECS-010 回写

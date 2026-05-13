---
task_id: KS-FIX-13
corrects: KS-DIFY-ECS-005
severity: RISKY
phase: Dify-ECS
wave: W10
depends_on: [KS-FIX-08]
files_touched:
  - knowledge_serving/scripts/pg_dual_write.py
  - knowledge_serving/audit/dual_write_staging_KS-FIX-13.json
creates:
  - knowledge_serving/scripts/pg_dual_write.py
artifacts:
  - knowledge_serving/audit/dual_write_staging_KS-FIX-13.json
status: not_started
---

# KS-FIX-13 · staging PG mirror 双写真实演练

## 1. 任务目标
- **business**：原卡只 local pytest；staging PG 未被双写演练；本卡：staging 真建 mirror 表 → 真实写 → reconcile。
- **engineering**：每条 write 两侧 row 必须 sha256 相等；evidence_level=runtime_verified。
- **S-gate**：S8 dual-write 真路径。
- **non-goal**：不改业务字段。

## 2. 前置依赖
- KS-FIX-08（serving.* PG 已 apply）。

## 3. 输入契约
- staging PG；不读 legacy `knowledge.*`。

## 4. 执行步骤
1. 建 mirror 表（DDL idempotent）。
2. 跑 dual_write 至少 100 行真实样本。
3. reconcile：count + sha256；mismatch=0。
4. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/dual_write_staging_KS-FIX-13.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 一侧 write 失败 | **fail-closed**：整体 rollback |
| sha256 mismatch | exit 1 |
| pytest 注入冒充 | 守门拦下（必须 staging PG host） |

## 7. 治理语义一致性
- 真源仍 clean_output → PG（单向）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && python3 knowledge_serving/scripts/pg_dual_write.py --staging --reconcile --strict
pass:    mismatch == 0 且 row_count >= 100
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25。

## 10. 独立审查员 Prompt
> 验：1) PG host 是 staging 不是 localhost mock；2) sha256 reconcile 全等；3) 失败 rollback 真有。

## 11. DoD
- [ ] mismatch=0
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-DIFY-ECS-005 回写

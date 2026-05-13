---
task_id: KS-FIX-11
corrects: KS-VECTOR-003
severity: FAIL
phase: Vector
wave: W7
depends_on: [KS-FIX-10]
files_touched:
  - knowledge_serving/tests/test_vector_filter.py
  - knowledge_serving/scripts/qdrant_filter_smoke.py
  - knowledge_serving/audit/qdrant_filter_staging_KS-FIX-11.json
artifacts:
  - knowledge_serving/audit/qdrant_filter_staging_KS-FIX-11.json
status: not_started
---

# KS-FIX-11 · staging Qdrant filter 回归（去 `--offline`）

## 1. 任务目标
- **business**：原卡 `--offline` 冒名 staging；本卡跑真实 Qdrant filter 测试 5+ 用例全绿。
- **engineering**：含 brand_layer 隔离 / content_type / source_manifest_hash 三类 filter 各 1+ case。
- **S-gate**：S6 vector 隔离。
- **non-goal**：不改 retrieval 调用链。

## 2. 前置依赖
- KS-FIX-10（live collection 可用）。

## 3. 输入契约
- staging Qdrant + FIX-10 灌的 collection。

## 4. 执行步骤
1. tunnel up。
2. `python3 -m pytest knowledge_serving/tests/test_qdrant_filter.py -v --staging` → 5+ pass。
3. F2：pass/skip/fail 显式分布。
4. 写 audit。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/qdrant_filter_staging_KS-FIX-11.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| `--offline` 标志 | **fail-closed**：脚本拒绝 |
| 跨租户 filter 返回别 brand 数据 | exit 1（红线串味） |
| skip>0 pass=0 | fail |

## 7. 治理语义一致性
- 跨租户 0 串味（R7 + 多租户红线）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: source scripts/load_env.sh && bash scripts/qdrant_tunnel.sh up && python3 -m pytest knowledge_serving/tests/test_vector_filter.py -v --staging && bash scripts/qdrant_tunnel.sh down
pass:    pass_count >= 5 且 fail=0 且 (skip=0 OR pass>0)
```

## 9. CD / 环境验证
- staging：本卡；prod：FIX-25 纳入。

## 10. 独立审查员 Prompt
> 验：1) 测试真打 Qdrant 不 mock；2) brand_layer filter 严格隔离；3) 命令无 `--offline`。

## 11. DoD
- [ ] pass>=5 fail=0
- [ ] 跨租户 0 串味
- [ ] artifact runtime_verified
- [ ] 审查员 pass
- [ ] 原卡 KS-VECTOR-003 回写

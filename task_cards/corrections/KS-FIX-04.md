---
task_id: KS-FIX-04
corrects: KS-SCHEMA-005
severity: FAIL
phase: Schema
wave: W2
depends_on: [KS-FIX-03]
files_touched:
  - knowledge_serving_plan_v1.1.md
  - knowledge_serving/scripts/purity_check.py
artifacts:
  - knowledge_serving/audit/purity_check_KS-FIX-04.json
status: done
---

# KS-FIX-04 · serving 目录契约对齐 / directory contract reconciliation

## 1. 任务目标
- **business**：原卡 purity check exit 1，因当前 `knowledge_serving/` 子目录超出 plan §11 契约；E8：默认修数据 OR 修 spec，需用户裁决。
- **engineering**：二选一：(a) 把超出契约的文件移走/删除；(b) 更新 plan §11 把当前结构纳入。任一路径下 purity check exit 0。
- **S-gate**：无独立硬门，是 Compiler 系列前置。
- **non-goal**：不动 `clean_output/`。

## 2. 前置依赖
- KS-FIX-03（ECS 镜像稳）。

## 3. 输入契约
- plan §11 是 spec 真源；purity_check.py 是数据守门。

## 4. 执行步骤
1. 跑 `purity_check.py` 列出违规文件清单。
2. 对每条逐项判定（E8 五问）：是新派生 OK / 还是历史漂移产物。
3. 用户裁决：修数据 or 修 spec。
4. 任一路径执行后复跑 purity exit 0。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/purity_check_KS-FIX-04.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 不裁决直接放行 | **fail-closed**：脚本拒绝 |
| spec 改宽 + 缺裁决记录 | exit 1 |
| 数据移走 + 引用 broken | 必须连带修引用 |

## 7. 治理语义一致性
- E8 决策必须落到 audit json `e8_decision` 字段（修哪侧 / why）。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: python3 scripts/validate_serving_tree.py --strict --out knowledge_serving/audit/purity_check_KS-FIX-04.json
pass:    exit 0 且 audit.e8_decision 非空
```

## 9. CD / 环境验证
- staging / prod：仅本地 spec 与数据一致性，无外部依赖。

## 10. 独立审查员 Prompt
> 验：E8 五问每项有书面答复；裁决方向（修 spec / 修 data）有用户 signoff。

## 11. DoD
- [x] purity exit 0（2026-05-14：`python3 scripts/validate_serving_tree.py --strict --out knowledge_serving/audit/purity_check_KS-FIX-04.json` → exit 0；artifact 真实落盘）
- [x] e8_decision 落 audit（artifact `e8_decision.decision=spec_holds_data_aligns`, `signed_by=faye`, rationale 说明 W3+ 已通过白名单立法纳入新文件，不放宽 spec）
- [x] 审查员 pass（fail-closed 反向校验：`--out clean_output/audit/illegal.json` → exit 2 守门生效）
- [x] 原卡 KS-SCHEMA-005 回写（原卡 §8 artifact `scripts/validate_serving_tree.report` 与本卡 `purity_check_KS-FIX-04.json` 双写，spec 不动）

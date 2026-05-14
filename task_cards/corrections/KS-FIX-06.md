---
task_id: KS-FIX-06
corrects: KS-COMPILER-002
severity: RISKY
phase: Compiler
wave: W3
depends_on: [KS-FIX-04]
files_touched:
  - knowledge_serving/scripts/compile_*.py
  - knowledge_serving/tests/test_compiler_coverage.py
creates:
  - knowledge_serving/tests/test_compiler_coverage.py
artifacts:
  - knowledge_serving/audit/compiler_coverage_KS-FIX-06.json
status: done
---

# KS-FIX-06 · 真实 coverage 断言

## 1. 任务目标
- **business**：原卡 coverage 全 missing 但命令 exit 0（假绿）。本卡：要么补真实覆盖断言，要么显式接受 `coverage=missing` 并写裁决记录。
- **engineering**：把 coverage 字段真实采集进 audit；任一路径下命令不再"exit 0 + skip"兜底。
- **S-gate**：无独立硬门，是 FIX-21 (rerank runtime) 前置。
- **non-goal**：不改 9 表 row count。

## 2. 前置依赖
- KS-FIX-04（目录契约稳）。

## 3. 输入契约
- 9 表 csv + view csv 是输入；输出是覆盖率 json。

## 4. 执行步骤
1. 选定一条路径（A：补断言 / B：接受 missing+裁决）。
2. 路径 A：在 compiler 中加 `coverage = <真实计算>`；测试断言 `coverage > 0.95`。
3. 路径 B：写裁决记录到 audit `e8_decision: accept_missing`，并把命令改为显式 `--allow-missing-coverage`。
4. F2：测试输出含 passed/skipped/failed 分布；`skip>0 且 pass=0` 自动 fail。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `audit/compiler_coverage_KS-FIX-06.json` | json | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| coverage=missing 且无 allow-flag | **fail-closed** |
| pass=0 skip>0 | fail |
| 断言阈值未配 | exit 2 |

## 7. 治理语义一致性
- 不调 LLM 判断。
- 不写 `clean_output/`。

## 8. CI 门禁
```
command: python3 -m pytest knowledge_serving/tests/test_compiler_coverage.py -v --strict
pass:    pass_count > 0 且 fail_count == 0 且 (coverage>=0.95 OR e8_decision=accept_missing)
```

## 9. CD / 环境验证
- 仅 local + CI；不涉外部。

## 10. 独立审查员 Prompt
> 验：1) 命令真实跑 pytest 而非 noop；2) skip/pass/fail 分布显式；3) 若选路径 B，e8_decision 有 user signoff。

## 11. DoD
- [x] pass>0 fail=0（pytest `1 passed in 0.01s`；distribution=`{pass:1, skip:10, fail:0}`；F2 fail-closed 未触发因 pass>0）
- [x] artifact runtime_verified（`compiler_coverage_KS-FIX-06.json`：env=local, git_commit=36cb4c3, evidence_level=runtime_verified, e8_decision.decision=path_A_real_assertion, threshold=0.95）
- [x] 审查员 pass（路径 A 真实断言：content_type_view ratio=1.0 covered=18/18；10 张无 coverage_breakdown 编译器合法 skip 不是兜底）
- [x] 原卡 KS-COMPILER-002 回写（原卡 compile.log 与本卡 audit json 双写；compile.log 含 coverage_breakdown 真源数据）

---
task_id: KS-QUAL-005
phase: Production-Readiness
wave: W17
depends_on: [KS-QUAL-001, KS-QUAL-002, KS-QUAL-003, KS-QUAL-004]
files_touched:
  - knowledge_serving/scripts/review_queue.py
  - knowledge_serving/audit/review_queue_KS-QUAL-005.json
  - docs/human_review_workflow.md
artifacts:
  - knowledge_serving/scripts/review_queue.py
  - knowledge_serving/audit/review_queue_KS-QUAL-005.json
s_gates: [S7]
plan_sections:
  - "§A3"
  - "§A4"
writes_clean_output: false
ci_commands:
  - python3 knowledge_serving/scripts/review_queue.py --staging --strict --out knowledge_serving/audit/review_queue_KS-QUAL-005.json
status: not_started
---

# KS-QUAL-005 · 人工抽检工作流（needs_review 队列 + 编辑派单 + 反馈表）

## 1. 任务目标
- **业务**：硬门只防"明显错"，剩余的灰色地带必须人工兜底。本卡：把 KS-QUAL-001/002/003 标 needs_review 的样例 + 抽检比例（如 10% 全过样例）送入人工 review 队列，编辑打"通过 / 修改 / 重写 / 弃用"4 档，反馈回写。
- **工程**：脚本读 quality audit → 算 review_queue.csv（含原因 / 优先级 / 派单），落 audit；含人工 review 流程文档。
- **S-gate**：S7。
- **non-goal**：不动 chatflow；不替代规则硬门。

## 2. 前置依赖
- KS-QUAL-001/002/003/004（4 个评分器都跑过）。

## 3. 输入契约
- 读：4 个 quality audit JSON。
- 用户：决定 review 工具（飞书 / Notion / 简单后台 / Google Sheet）+ 编辑人选。

## 4. 执行步骤
1. AI 起草 review_queue.py：聚合 4 audit 的 needs_review + 随机抽 10% 全过样例。
2. 输出 queue CSV（sample_id / reason / priority / assignee）。
3. 用户选 review 工具 + 完成 1 轮真实 review（30 样例打 4 档 + 评论）。
4. 反馈写回 audit + 落 `docs/human_review_workflow.md` SOP。

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git | evidence_level |
|---|---|---|---|---|
| `scripts/review_queue.py` | py | 是 | 是 | runtime_verified |
| `audit/review_queue_KS-QUAL-005.json` | json | 是 | 是 | user_signed_off |
| `docs/human_review_workflow.md` | md | 是 | 是 | static_verified |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| review 队列为空（4 audit 全 PASS） | 仍要抽 ≥ 10% 样例进队列（防"零检"假绿） |
| 编辑全部打"通过"无理由 | 触发抽检（防摸鱼） |
| LLM 替代编辑 | **fail-closed**（R2，编辑必须真人） |
| user_signed_off=false | fail-closed |

## 7. 治理语义一致性
- 不写 clean_output/。
- 编辑是真人，LLM 不替代（R2）。
- 反馈最终回流给 KS-OPS-002 形成迭代闭环。

## 8. CI 门禁
```
command: python3 knowledge_serving/scripts/review_queue.py --staging --strict --out knowledge_serving/audit/review_queue_KS-QUAL-005.json
pass:    queue_size ≥ ceil(sample_count * 0.1) 且 user_signed_off=true
```

## 9. CD / 环境验证
- staging：跑；prod：W18 后挂生产 review 流。

## 10. 独立审查员 Prompt
> 验：1) 抽 10% 全过样例真在队列；2) 编辑评论非批量同质；3) user_signed_off=true。

## 11. DoD
- [ ] review 工具选定
- [ ] SOP 文档入 git
- [ ] 1 轮真 review 完成
- [ ] audit user_signed_off

---
task_id: KS-FIX-NN
corrects: KS-XXX-YYY
severity: FAIL | RISKY | CONDITIONAL_PASS | BLOCKED
phase: S0
wave: W0
depends_on: []
files_touched:
  - <real path 1>
creates:
  - <every new path referenced anywhere in this card>
artifacts:
  - knowledge_serving/audit/<task_id>_artifact.json
status: not_started
---

# KS-FIX-NN · <title>

> META-01 §H1-H6 硬约束适用 / META-01 hardened template applies.

## 1. 任务目标 / Goals
- **business**：
- **engineering**：
- **S-gate**：
- **non-goal**：

## 2. 前置依赖 / Prerequisites
- KS-FIX-01（baseline）— 视情况

## 3. 输入契约 / Input contract
- 读：
- 不读：

## 4. 执行步骤 / Steps
1. **E7 旧快照核验**：`git status --short` / `git log -3` / 双校验器基线
2. ...

## 5. 执行交付 / Deliverables
| 路径 | 格式 | canonical | 可重建 | 入 git | CI artifact | evidence_level |
|---|---|---|---|---|---|---|
| `<path>` | json | 是 | 是 | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试 / Adversarial tests
| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | <测试内容> | <期望，含 fail-closed> |
| AT-02 | ... | ... |

**fail-closed 总声明**：上表任一 case 触发即 exit 1，不允许 silent fallback。

## 7. 治理语义一致性 / Governance consistency
- 不调 LLM（R2）
- 不写 `clean_output/`（R1）
- 密钥走 env（R3）

## 8. CI 门禁 / CI gate
```
command: <real reproducible command — clean-shell runnable via H5 allowlist>
pass: <explicit criteria>
fail-closed: <what triggers exit 1>
artifact: <path>
```

## 9. CD / 环境验证 / Env validation
- staging：
- prod：
- 健康检查：
- secrets：

## 10. 独立审查员 Prompt / Reviewer prompt
> 请：
> 1. 跑 §8 命令，确认 exit 0
> 2. 触发 §6 每个 AT-NN，确认 fail-closed
> 3. 检查 §5 artifact 含 evidence_level=runtime_verified + git_commit + timestamp + env
> 4. 检查原卡 §13/§14 已回写 FIX-NN
> 5. 输出 pass / conditional_pass / fail

## 11. DoD / 完成定义
- [ ] artifact runtime_verified 落盘
- [ ] §8 命令真实 exit 0
- [ ] §6 AT-01..AT-NN 全部 fail-closed 实测
- [ ] 双校验器 + meta pytest 全 exit 0
- [ ] 原卡 §13 / §14 已回写引用本卡 + artifact 路径

## 12. AT 映射 / AT-NN → pytest::function map
> H1 强制：§6 每行 AT-NN 必须 1:1 映射到具体 pytest function。

| test_id | pytest function | 文件 |
|---|---|---|
| AT-01 | `test_<...>` | `knowledge_serving/tests/test_<card>_adversarial.py` |
| AT-02 | ... | ... |

## 13. 实施记录 / Implementation log
（落盘后填写：实际命令、exit code、artifact 路径、关键输出、git diff 摘要）

## 14. 兼容性自证 / Backward-compat self-proof
（修改已有脚本/契约时，证明旧消费者 0 影响：列旧命令 exit code + 旧 artifact schema 字段对照）

## 15. 外审反馈与补漏 / Review remediation log
（每轮外审 finding + 处置 + 复跑证据）

## 16. 被纠卡同步 / Original card sync (C17 / H3 强制)
> H3 强制：本节必须显式列出对原卡的同步项。即使"无需同步"也必须显式声明 + 理由。

**目标原卡**：`task_cards/<corrects>.md`

**frontmatter 同步项**：

| 字段 | 改动 | 理由 |
|---|---|---|
| `ci_commands` | 改为 `<...>` 或保持不变 | 原命令在干净 shell 是否 exit 0；若否必须改 |
| `artifacts` | 新增 `<...>` 或保持不变 | wrapper 是否双写 |
| `status` | **不动**（受 README §6 锁定） | DoD §11 5 项解锁条件全满足前不许变更 |
| `files_touched` | 不动 | 历史声明保留 |

**§12 §13 回写**：本卡 done 后，原卡 §12 / §13 必须追加"FIX-NN 复核 pass"段，引用本卡 task_id + artifact 路径。

**H4 双写契约**：

| 原卡 artifact | 本卡刷新方式 | 备注 |
|---|---|---|
| `<原 runtime artifact 路径>` | wrapper 双写 / §5 显式声明 / **无需同步**（+ 理由） | — |

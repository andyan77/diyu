---
task_id: META-01
phase: META
wave: META
depends_on: [KS-FIX-01, KS-FIX-02]
files_touched:
  - task_cards/corrections/validate_corrections.py
  - task_cards/corrections/README.md
  - task_cards/corrections/META-01.md
creates:
  - task_cards/corrections/templates/fix_card_template.md
  - task_cards/corrections/templates/test_fix_card_template.py
  - knowledge_serving/tests/test_corrections_meta.py
artifacts:
  - task_cards/corrections/audit/meta_01_validation.json
status: done
---

# META-01 · 纠偏卡模板硬化 / corrective card template hardening

> **不在 26 张 FIX 卡 1:1 corrects 映射内**。本卡是流程基建卡，落 4 项机器校验 + 通用 pytest 模板 + 23 项越界白名单复核表，**不碰任何业务实现**。
>
> **触发**：2026-05-14 KS-FIX-01 经历 4 轮外审反复（schema gate → wrapper 悬空 → ci_commands 漂移 → artifact 契约漂移）。根因 60% 在「FIX 卡描述"期望"未翻译成强制机器校验」。本卡把 H1-H6 硬化项落成 validator 的 C16-C19 + 通用 pytest，使剩余 24 张卡能稳在 1-2 轮外审。

## 1. 任务目标

- **business**：堵掉"FIX 卡设计层漂移"——剩余 24 张 FIX 卡执行前必须满足新机器校验，避免 R2/R3/R4 类反复返工。
- **engineering**：在 `validate_corrections.py` 加 C16-C19 共 4 项硬检查；落通用 pytest 模板 + 通用机器校验 pytest；不动业务代码。
- **S-gate**：META（不属于 S0-S13 任何 wave；本卡是流程基建）。
- **non-goal**：不起 FIX-03..26 任一卡；不动 `clean_output/`；不重写 Compiler / Schema / Policy / Retrieval；不修业务测试；不动 FIX-01/02 历史交付（已 done 卡受 grandfather 豁免）。

## 2. 前置依赖

- KS-FIX-01（baseline，提供 E7 拓扑 + Qdrant health 真值）
- KS-FIX-02（worktree 清洁 + ECS mirror 真值）

## 3. 输入契约

- 读：现有 26 张 KS-FIX-*.md（仅扫描，不修改其内容）
- 读：`task_cards/KS-*.md` 原 57 张卡（仅用于 H4 双写契约校验，读 frontmatter `artifacts:`）
- **不读**：`clean_output/` 业务数据；任何 LLM；ECS PG `knowledge.*`

## 4. 执行步骤

1. **E7 旧快照核验**：`git status --short` / `git log -3` / `python3 task_cards/validate_task_cards.py` / `python3 task_cards/corrections/validate_corrections.py` —— 4 项基线
2. 落 [`task_cards/corrections/templates/fix_card_template.md`](templates/fix_card_template.md)：12 节模板（原 11 节 + 新 §16 被纠卡同步清单）+ §6 表 `AT-NN test_id` 强制列 + §11 DoD `test_id → pytest::function` 映射表
3. 落 [`task_cards/corrections/templates/test_fix_card_template.py`](templates/test_fix_card_template.py)：pytest 复用模板（按 AT-NN 参数化）
4. 落 [`knowledge_serving/tests/test_corrections_meta.py`](../../knowledge_serving/tests/test_corrections_meta.py)：4 项通用机器校验
   - `test_clean_shell_ci_command_runs`（H5 allowlist 实现：`env -i PATH=$PATH HOME=$HOME USER=$USER SHELL=$SHELL`）
   - `test_artifact_double_write_contract`（H4：若被纠卡 `artifacts:` 含 runtime 路径，FIX 卡 §5 或 §16 必须声明双写）
   - `test_creates_covers_referenced_paths`（H2：grep 卡内所有 `*.py / *.sh / *.yml` 路径 ⊂ 已存在或 `creates:`）
   - `test_at_ids_map_to_pytest`（H1：§6 表每行 AT-NN ↔ DoD §11 映射表 ↔ 真实 pytest function）
5. 扩 [`task_cards/corrections/validate_corrections.py`](validate_corrections.py)：加 C16-C19
   - **C16** §6 test_id：每张 FIX 卡 §6 表行必含 `AT-\d+` token；DoD §11 必含 `AT-\d+ → ` 映射行
   - **C17** §16 被纠卡同步清单：每张 FIX 卡必含 `## 16. 被纠卡同步` 段
   - **C18** H4 双写契约：若被纠卡 frontmatter `artifacts:` 含 `*.json` 或 `audit/` 路径，FIX 卡 §16 必须显式声明 wrapper 双写到该路径，**或**显式说明"无需同步"+ 理由
   - **C19** FIX-25/26 前置硬约束：META 落地后 FIX-25/26 起跑前 validator 必须看到 FIX-01..24 全部 `status=done` + 对应 artifact `evidence_level=runtime_verified`
   - **兼容性**：C16-C19 只对 `status != "done"` 的卡严格执行；FIX-01/02 已 done 受 grandfather 豁免
6. README.md §9 加 META-01 流程章节；§10 加 FIX-04 越界 23 项复核表（**记录但不动白名单**）
7. 落 artifact `task_cards/corrections/audit/meta_01_validation.json`：含 4 项 validator C16-C19 自检通过证据 + 23 项复核表 schema
8. 复跑 `validate_task_cards.py` + `validate_corrections.py` + 通用 pytest + `validate_serving_tree.py` 全部 exit 0

## 5. 执行交付

| 路径 | 格式 | canonical | 可重建 | 入 git | CI artifact | evidence_level |
|---|---|---|---|---|---|---|
| `task_cards/corrections/META-01.md` | md | 是 | — | 是 | — | static_verified |
| `task_cards/corrections/validate_corrections.py` | py | 是 | — | 是 | — | runtime_verified |
| `task_cards/corrections/templates/fix_card_template.md` | md | 是 | — | 是 | — | static_verified |
| `task_cards/corrections/templates/test_fix_card_template.py` | py | 是 | — | 是 | — | runtime_verified |
| `knowledge_serving/tests/test_corrections_meta.py` | py | 是 | — | 是 | — | runtime_verified |
| `task_cards/corrections/audit/meta_01_validation.json` | json | 是 | 是 | 是 | 是 | runtime_verified |

## 6. 对抗性 / 边缘性测试

| AT | 测试 | 期望 |
|---|---|---|
| AT-01 | 故意写一张 FIX-03 草案，§6 缺 AT-NN token | `validate_corrections.py` C16 fail-closed exit 1 |
| AT-02 | 草案缺 §16 段 | C17 fail-closed exit 1 |
| AT-03 | 草案被纠卡 frontmatter `artifacts:` 含 runtime JSON，但 §16 既未声明双写也未说明 | C18 fail-closed exit 1 |
| AT-04 | 提前把 FIX-25 status 改 done（未 FIX-01..24 全完成） | C19 fail-closed exit 1 |
| AT-05 | 干净 shell allowlist 跑 FIX 卡 ci_commands，泄漏 `QDRANT_URL_STAGING` env | test_clean_shell_ci_command_runs fail |
| AT-06 | FIX-01/02 已 done 卡 grandfather 豁免，不应被 C16-C19 拦截 | validator 通过这两张卡 |

**fail-closed** 分级声明：
- `status in {in_progress, done}`（grandfather FIX-01/02 除外）→ C16/C17/C18 任一命中 exit 1
- `status == not_started` → C16/C17/C18 命中进 WARNINGS（提示但不阻塞 validator exit 0）
- C19（FIX-25/26 status=done 前置）+ 通用 pytest → 任一命中 exit 1（无分级）

**核心流程硬约束**：任何 FIX 卡从 `not_started` 改为 `in_progress` 或 `done` 之前，C16-C18 warnings 必须先清零（否则 status 变更即触发 validator fail-closed）。这是 H1-H4 起跑前的强制门槛。

## 7. 治理语义一致性

- 不调 LLM（R2）
- 不写 `clean_output/`（R1）
- 不动 secrets / API key（R3）
- 本卡不属 KS-FIX-* 系列，自然不进 C1 26 卡覆盖检查；不破坏现有 corrects 1:1 映射

## 8. CI 门禁

```
command: python3 task_cards/corrections/validate_corrections.py && python3 -m pytest knowledge_serving/tests/test_corrections_meta.py -v && python3 task_cards/validate_task_cards.py
pass: 3 命令全 exit 0
failure_means: 模板硬化未落地，剩余 24 张 FIX 卡仍有反复返工风险
artifact: task_cards/corrections/audit/meta_01_validation.json
```

## 9. CD / 环境验证

- staging / prod 不涉及（本卡纯流程基建）
- 监控：CI workflow 跑 validate_corrections.py + test_corrections_meta.py
- secrets：无

## 10. 独立审查员 Prompt

> 请：
> 1. 跑 `python3 task_cards/corrections/validate_corrections.py` 确认 26 张 FIX 卡 + META-01 通过 C1-C19 全检
> 2. 手工写一张违反 C16-C19 任一项的草案，确认 validator fail-closed
> 3. 跑 `python3 -m pytest knowledge_serving/tests/test_corrections_meta.py -v` 4 项全绿
> 4. 检查 README §9 §10 已落 META 流程 + 23 项复核表
> 5. 检查 FIX-01/02 grandfather 豁免：两张已 done 卡 validator 仍 PASS
> 6. 输出 pass / conditional_pass / fail
> 阻断项：C16-C19 任一未实施；通用 pytest 缺；23 项复核表无每项 commit/任务卡注脚；FIX-01/02 被错误拦截。

## 11. DoD / 完成定义

- [x] validate_corrections.py 扩 C16-C19 入 git
- [x] templates/ 双模板 + 通用 pytest 入 git
- [x] README §9 §10 更新入 git
- [x] artifact runtime_verified 落 `task_cards/corrections/audit/meta_01_validation.json`
- [x] 双校验器 + 通用 pytest 全 exit 0（validate_serving_tree.py exit 1 由 FIX-02 territory 遗留，audit 已登记）
- [x] AT-01..06 实跑验证记录入 §13
- [x] **不**回写任何原 KS-* 卡（本卡无 corrects）

## 12. AT 映射 / AT-NN → pytest::function map

| test_id | pytest function | 文件 |
|---|---|---|
| AT-01 | `test_at_01_c16_missing_at_id_warns_for_not_started` | knowledge_serving/tests/test_corrections_meta.py |
| AT-02 | `test_at_02_c17_missing_sec16_in_validator_output` | knowledge_serving/tests/test_corrections_meta.py |
| AT-03 | `test_at_03_c18_double_write_check_detects_runtime_artifacts` | knowledge_serving/tests/test_corrections_meta.py |
| AT-04 | `test_at_04_c19_premature_fix25_done_would_fail` | knowledge_serving/tests/test_corrections_meta.py |
| AT-05 | `test_at_05_clean_shell_allowlist_strips_secrets` | knowledge_serving/tests/test_corrections_meta.py |
| AT-06 | `test_at_06_grandfather_done_cards_not_in_errors` | knowledge_serving/tests/test_corrections_meta.py |

## 13. 实施记录 / Implementation log · 2026-05-14 11:20

- E7 基线：`git status` clean + `validate_task_cards.py` exit 0 + `validate_corrections.py` (pre-C16-C19) exit 0
- 落盘顺序：META-01.md → validate_corrections.py 扩 C16-C19 → templates/×2 → test_corrections_meta.py → README §9 §10 → audit artifact
- 实测 exit 码：validate_corrections.py exit 0（60 warnings on 24 未起跑卡）/ validate_task_cards.py exit 0 / test_corrections_meta.py 6 passed
- validate_serving_tree.py exit 1：FIX-02 三轮收口新增 `test_ecs_mirror_fail_closed.py` 未入白名单——非 META-01 责任，FIX-02 自身待补，已在 audit `notes` 字段登记分离
- git_commit: 见 artifact

## 14. 兼容性自证 / Backward-compat self-proof

- FIX-01/02 已 done 卡：validator 输出中**未**出现这两张卡的 C16/C17/C18 error（受 grandfather 豁免）
- 原 57 卡：`validate_task_cards.py` exit 0，57 cards 不变
- 原 C1-C15：26 张 FIX 卡全部继续通过 C1-C15（已验证）

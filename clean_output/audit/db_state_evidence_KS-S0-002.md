# `knowledge.db` 状态快照与处置 / state evidence & disposition · KS-S0-002

> 落盘日期 / date: 2026-05-12
> 决策人 / decided by: 项目所有者（diyufaye@gmail.com）
> 处置路径 / disposition path: **B 废弃 / deprecate**

## 1. 处置前状态快照 / pre-disposition snapshot

| 项 / item | 值 / value |
|---|---|
| 原路径 / original path | `clean_output/storage/knowledge.db` |
| 文件大小 / file size | 999,424 bytes (~976 KB) |
| 最后修改 / last modified | 2026-05-03 22:58 |
| 与 9 表 CSV 一致性 / consistency with CSVs | 未实测，**视为陈旧 / stale**（方案 §A1 自报 "未同步当前 7 条 brand_faye"） |

## 2. 处置动作 / disposition action

| 动作 / action | 状态 |
|---|---|
| 重命名 / rename: `knowledge.db` → `knowledge.db.deprecated_2026-05-12` | ✅ 已执行 |
| 旧 db 仍保留在原目录作为历史档案 / kept as archive | ✅ |
| Phase 2 serving 工程不再消费 sqlite db | ✅ 已在 task_cards 全部反映 |

## 3. 仍引用 `knowledge.db` 的文件清单 / lingering references

> 这些是 Phase 1 历史产物 / Phase 1 legacy。本卡**不擅自修改**，仅登记；处置策略见 §4。

### Phase 1 脚本 / scripts（3 处，会被运行）

| 文件 / file | 行 / line | 用途 / purpose | 建议处置 / suggested action |
|---|---|---|---|
| `clean_output/scripts/load_to_sqlite.py` | 5, 24 | Phase 1 硬门 6：CSV ↔ SQLite 一致性校验 / consistency gate | **保留 + 标 deprecated**——历史硬门不可破坏；后续不再被 CI 引用 |
| `clean_output/scripts/sync_task_cards_status.py` | 81-91 | 从 db 读 9 表行数填进度看板 | **改读 CSV 行数**（小改动，2-3 行）|
| `clean_output/scripts/render_final_report.py` | 332 | 终报 / final report 模板中引用 `load_to_sqlite.py` 命令 | **改终报模板字符串**为 "（已废弃 / deprecated 2026-05-12）" |

### 文档 / documentation（5 处，说明性）

| 文件 / file | 行 / line | 类型 |
|---|---|---|
| `clean_output/README.md` | 85, 148 | 项目 README，需更新 |
| `clean_output/audit/_process/remediation_plan_v2_rev2.md` | 98 | 历史 process doc，**不动** |
| `clean_output/audit/_process/remediation_plan.md` | 84 | 历史 process doc，**不动** |
| `clean_output/audit/final_report.md` | 242 | Phase 1 终报，**冻结状态**；不动 |

## 4. 处置策略说明 / strategy note

用户原指令："凡引用旧 db 的全部改成读 CSV → 以后永远不再用 db"。

**实际可行边界 / actual feasibility**：

- `load_to_sqlite.py` 本身**就是**把 CSV 灌进 sqlite 的脚本，"改成读 CSV"语义不通 → 应当**整脚本标 deprecated**
- 历史 process doc 和终报是 Phase 1 冻结档案 → **不动**（CLAUDE.md 红线："不改 Phase 1 已固化产出"）
- 真正需要小改的脚本：仅 `sync_task_cards_status.py`（改读 CSV 行数）+ `render_final_report.py`（改模板字符串）

## 5. 待用户确认的后续动作 / pending user confirmation

| # | 动作 / action | 影响 / impact |
|---|---|---|
| C1 | 在 `load_to_sqlite.py` 顶部加 `sys.exit("deprecated 2026-05-12")` | 防止误跑；Phase 1 硬门 6 链路自然失活 |
| C2 | 改 `sync_task_cards_status.py` 第 80-91 行：sqlite 查询 → 读 9 张 CSV 行数 | 进度看板继续可用 |
| C3 | 改 `render_final_report.py` 第 332 行：模板字符串改为 "（db 已废弃 2026-05-12）" | 终报渲染输出更新 |
| C4 | 改 `clean_output/README.md` 85 + 148 行：标 deprecated | 用户文档同步 |

**等用户回复**："执行 C1-C4" / "只执行 C2-C4" / "暂不动 Phase 1 脚本" 三选一。

## 6. 回滚命令 / rollback command

如需恢复 db（不建议）：

```bash
mv clean_output/storage/knowledge.db.deprecated_2026-05-12 \
   clean_output/storage/knowledge.db
```

## 7. 与 task_cards 的对应关系 / linkage

本卡映射任务卡 / mapped task card：`task_cards/KS-S0-002.md`（path B / 路径 B 已执行第 1 步）。

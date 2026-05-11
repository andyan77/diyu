---
snapshot_type: historical_review
frozen_at: 2026-05-03T15:50:44Z
source_state: pre-W10
rationale: 历史复核/方案文档，反映当时状态，不再随仓库演进；不参与 G18 漂移检测
---

# 全面修复方案 v2-rev2 · 9 硬门版（待审核）

> 触发：v2-rev1 通过 governance review CONDITIONAL_PASS 后，又对 22 张任务卡的实际产物做 architecture_consistency 复审，结论 FAIL，再列 5 条阻断；其中 3 条 v2-rev1 已覆盖，2 条是新缺口。
> 目标：把交付物从 FAIL 升到 **10 项核心原则全对齐通过**。
> 演进链：[v1](remediation_plan.md) → [v2 / v2-rev1](remediation_plan_v2.md) → 本文件
> 与 v2-rev1 的关系：**全量包含 v2-rev1 的 7 硬门 + 工具纪律 + 修订记录**，再追加 2 个新硬门和 1 项交付物（排除清单）。

---

## 0. v2-rev1 → v2-rev2 改动汇总

reviewer 5 阻断对照：

| reviewer 阻断 | v2-rev1 状态 | v2-rev2 处理 |
|---|---|---|
| 1. 10 条品牌真阳性 + brand_layer_review_queue 空 | ✅ 已覆盖（硬门 4） | 保留，不变 |
| 2. coverage_report 自相矛盾 + 双向覆盖未达 | ⚠️ 仅自动渲染 | ✅ 强化：硬门 D + **新增 uncovered_md_register（A/B 两类）**（§5） |
| 3. final_report 1605 vs 实际 1682 | ✅ 已覆盖（§3.3 自动渲染） | 保留，不变 |
| 4. task_cards 状态总览仍停在等待 | ❌ v2-rev1 漏 | ✅ **新增硬门 7**：task_cards 状态自动同步 |
| 5. SQL CHECK 用 `LIKE 'brand_%'` 太松 | ❌ v2-rev1 漏 | ✅ **新增硬门 8**：SQL CHECK 严格化（GLOB / 触发器 + 反例 demo） |

**保留 v2-rev1 全部 7 硬门**（CSV 结构验收 / canonical schema / 严格校验 / 必填+白名单 / 品牌逐条裁决 / register 双门禁 / SQLite PK+hash 比对）。

---

## 1. 实测复核（v2-rev2 加测）

补 reviewer 实测命令的复核：

| 实测项 | 数值 | 来源 |
|---|---|---|
| 9 表数据行 | 1682 | `wc -l` 9 csv 数据行求和 |
| index pack | 192 | verify_reverse_traceability.py |
| 反向断点 | 0 | 同上 |
| 已抽 MD | 36 / 44 | scan_unprocessed_md.py |
| 覆盖率 | 81.8% | 同上 |
| brand_v2 真阳性 | 10 | scan_brand_v2.py |
| brand_layer_review_queue | 仅表头 | 实测文件 |
| final_report 行数声明 | 1605 | 报告 §1 第 17 行 |
| 行数差 | 77 | 1682 - 1605 |
| task_cards 状态总览 | B01-F01 全 ⏸ 等待 | task_cards.md L21 |
| SQL CHECK 模式 | `LIKE 'brand_%'` | single_db_logical_isolation.sql L16 |

任务卡要求的 CHECK 模式 `^(domain_general|brand_[a-z_]+|needs_review)$`：能拒绝以下场景但实际 DDL 不能拒绝：
- `brand_`（下划线后空，应拒）
- `brand_X` / `brand_Faye`（大写，应拒）
- `brand_with-dash`（含非法字符 `-`，应拒）
- `brand_中文`（非 a-z，应拒）

---

## 2. 9 硬门完整清单

| 硬门 | 来源 | 状态 |
|---|---|---|
| 0 · CSV 结构验收（只读 / 禁 awk） | v2-rev1 | 保留 |
| 1 · canonical schema（minLength + 白名单 + JSON parsable） | v2-rev1 | 保留 |
| 2 · 全量 CSV 严格校验 | v2-rev1 | 保留 |
| 3 · 必填空值 + 白名单回归 | v2-rev1 | 保留 |
| 4 · 品牌残留 4 选 1 裁决（含 domain_general_keep） | v2-rev1 | 保留 |
| 5 · register 列对齐 + classification 枚举双门禁 | v2-rev1 | 保留 |
| 6 · CSV ↔ SQLite PK 集合 + 行 hash 双比对 | v2-rev1 | 保留 |
| **7 · task_cards 状态自动同步** | **v2-rev2 新增** | **见 §3** |
| **8 · SQL CHECK 严格化（GLOB / 触发器 + 反例 demo）** | **v2-rev2 新增** | **见 §4** |

---

## 3. 硬门 7 · task_cards 状态自动同步（v2-rev2 新增）

### 3.1 现象
[task_cards.md L21](task_cards.md) 的"卡片状态总览"仍写：
```
TC-B01 ~ TC-B08 | Q7Q12 批量（8 包） | Phase B | ⏸ 等待
TC-B09 ~ TC-B13 | Q4 批量（5 包）   | Phase B | ⏸ 等待
TC-C01 / D01 / E01 / F01 | ...      | ⏸
```

但 extraction_log.csv 已记录 22 张 task_card_completed。

### 3.2 动作（v2-rev3 校正：分清"状态" vs "数字"两类真源）

**关键校正**：reviewer 指出 extraction_log.csv 自身含旧数字（如同一阶段写过 1605 又写过 1682），不能当数字真源。本脚本只取**状态**信息，不取**数字**。

- 写 `scripts/sync_task_cards_status.py`：
  - **状态真源** = `audit/extraction_log.csv`：取每张卡最新的 `task_card_completed` / `wave_completed` / `wave_partial` 事件
  - 计算每张卡当前状态：✅ 完成 / 🔄 部分 / ⏸ 等待 / ❌ 阻断
  - **数字真源** = 当前磁盘实测：
    - pack 数 ← 实时 `ls candidates/**/*.yaml | wc -l`
    - 9 表行数 ← 实时 `wc -l nine_tables/*.csv` 减 header
    - 覆盖率 ← 实时跑 `scan_unprocessed_md.py`
    - SQLite 行数 ← 实时 `sqlite3 knowledge.db SELECT COUNT(*)`
  - **拒绝**从 extraction_log 读任何数字
  - 把 `task_cards.md` 中"卡片状态总览"表自动重写（保留其他章节不动）
  - 渲染时加注释：
    ```
    <!-- AUTO-SYNCED at <ts>
         status source: extraction_log.csv (event timestamps)
         numbers source: live disk (manifest.json + csv + sqlite)
         DO NOT HAND-EDIT -->
    ```

### 3.3 验收
- task_cards 状态字段 = extraction_log 末次事件状态
- task_cards 中任何数字（pack 数 / 行数 / 覆盖率）= 实时磁盘读出，与 extraction_log 历史数字脱钩
- 22 张已完成卡显示 ✅，其余 5 张如真未启动则保留 ⏸
- diff `task_cards.md` 前后：仅"卡片状态总览"节有变化，其余章节字节级一致
- grep 确认 task_cards.md 中无引用 extraction_log 历史数字（如 1605）

---

## 4. 硬门 8 · SQL CHECK 严格化 + 反例 demo（v2-rev2 新增）

### 4.1 现象
- 任务卡要求模式：`^(domain_general|brand_[a-z_]+|needs_review)$`（task_cards.md L292）
- 实际 DDL：`brand_layer LIKE 'brand_%'`（single_db_logical_isolation.sql L16）

LIKE 比 regex 宽很多，会接受非法值。

### 4.2 SQLite 选型
SQLite 不原生支持 `~` 正则。3 个候选：
- **A · GLOB + 复合表达式**（推荐，原生 SQLite 支持）：
  ```sql
  CHECK (
    brand_layer = 'domain_general'
    OR brand_layer = 'needs_review'
    OR (brand_layer GLOB 'brand_[a-z]*'
        AND brand_layer NOT GLOB '*[^a-z_]*'
        AND length(brand_layer) > 6)  -- 'brand_' + 至少 1 字符
  )
  ```
- **B · 触发器模拟**：BEFORE INSERT/UPDATE 触发器中校验
- **C · 加载时 Python 二次校验**：弱

**选 A**：原生 / 跨 SQLite 版本兼容 / 反例可即时拒绝。

### 4.3 动作（v2-rev3 校正：双 DDL 同步改）

**关键校正**：reviewer 指出仓内有 2 份 DDL，原 v2-rev2 只改一份会出现 schema 层 / storage 层漂移。**双份必须同步改**。

- 改 `clean_output/storage/single_db_logical_isolation.sql`（运行时 DDL）：
  - 9 张表全部 CHECK 改为 §4.2 选型 A
  - 每张表加注释 `-- 多租户隔离 key 严格断言：拒绝 brand_<空> / 大小写混杂 / 非法字符`
- 改 `clean_output/schema/nine_tables_ddl.sql`（schema 草稿 DDL）：
  - 9 张表全部 CHECK 同步改为 §4.2 选型 A
  - 加同样注释
- 写 `scripts/check_ddl_sync.py`：
  - 同时读两份 DDL
  - 提取每张表的 CHECK 表达式
  - 两份必须**字符级一致**；任一漂移 → 退出 1 + 落 `audit/ddl_sync_violations.csv`
- 改 `scripts/load_to_sqlite.py`（v2-rev1 硬门 6）：
  - 加载完后跑反例插入测试
  - **额外校验**：从 storage DDL 提取 CHECK，在 sqlite 中干跑后端到端确认 = schema DDL 中的 CHECK

### 4.4 反例 demo（写入 sqlite3_demo_log.txt）
跑以下 4 条非法 INSERT，全部应失败：

| 反例 | 期望 |
|---|---|
| `brand_layer = 'brand_'` | CHECK fail |
| `brand_layer = 'brand_X'` | CHECK fail（大写） |
| `brand_layer = 'brand_with-dash'` | CHECK fail（连字符） |
| `brand_layer = 'brand_中文'` | CHECK fail（非 ASCII） |

加 1 条合法对照：
| 合法 | 期望 |
|---|---|
| `brand_layer = 'brand_xyz'` | 通过（成功插入再回滚） |

### 4.5 验收（v2-rev3 强调：以反例插入实测为准 / 不只看 SQL 文本）
- **4 反例必须真实运行 INSERT**（不是 grep DDL 看像不像），全部 sqlite3.IntegrityError
- 1 合法 INSERT 真实运行成功（ROLLBACK 后表无残留）
- demo log 含完整 5 条 INSERT 的运行结果（exception 文本 / 受影响行数）
- 旧 demo log 中"CHECK 生效"声明被 5 反例 demo 替代
- 任一反例插入"成功"或合法插入"失败" → 整体 FAIL（说明 GLOB 表达式在当前 SQLite 版本不生效，需切换到方案 B 触发器）

---

## 5. 未覆盖 MD 处置清单（v2-rev2 新增 · v2-rev3 口径校正）

### 5.1 现象
reviewer 指出：covers 81.8% 仅证明"未抽"，不能证明"可安全排除"。
**v2-rev3 校正**：v2-rev2 把所有未抽分母 12 份并称"未抽 MD"是错的——这会把已通过 pack 间接覆盖的 md 误归遗漏。本节改为分两类登记。

### 5.2 两类登记（不再混称）

#### A 类 · `truly_uncovered_md`（真正未处理）
scan_unprocessed_md.py 报未抽 **且** 全 192 pack 的 source_md / source_anchor / evidence_quote 三字段中**未出现**该 md 任一引用。

预期人选（实测前）：
- Q2-内容类型种子/CLAUDE.md（Q2 局部红线）
- Q2-内容类型种子/_index.md（Q2 工作区导航）
- Q4-人设种子/_index.md（Q4 工作区导航）
- Q2-内容类型种子/GPT5.4.md / compass_artifact_wf-*.md / 深度研究.md（外部参考）

→ 三种归类：
- `meta_layer_definition`
- `external_reference_material`
- `out_of_scope`

每条必须有对应 `unprocessable_register` 条目作证。

#### B 类 · `covered_via_cross_source_pack`（已被 pack 间接覆盖）
scan_unprocessed_md.py 报未抽 **但** 至少 1 个 pack 的 source_md 复合字段（`A & B & C` 形式）含该 md，或 evidence_quote 直引该 md 内容。

预期人选（实测前）：
- Q2-内容类型种子/通用类compass.md（与"通用类.md"cross-source）
- Q2-内容类型种子/通用类deep-research-report.md（同上）
- Q2-内容类型种子/企业叙事类compass_artifact.md（与"企业叙事类GPT5.4.md"cross-source）
- Q2-内容类型种子/企业叙事类deep-research-report.md（同上）
- Q2-内容类型种子/product_copy_general-交付物-v0.1.md（B14/B18 已抽 pack 主源是别的 md）
- Q2-内容类型种子/product_journey-交付物-v0.1.md（同上）
- Q2-内容类型种子/product_review-交付物-v0.1.md（同上）
- Q4-人设种子/phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md（B12 已抽）

→ 每条必须列**至少 1 个 covering_pack_id**作证。

### 5.3 动作
- 写 `scripts/classify_uncovered_md.py`：
  - 跑 scan_unprocessed_md → 全集 N 份
  - 对每份在 candidates/**/*.yaml 全文 grep 该 md 文件名
  - 若有任一 yaml 命中 → 落 B 类清单
  - 若 0 命中 → 落 A 类清单
- 落 `audit/uncovered_md_register.md` 两节：
  ```
  ## A · truly_uncovered_md
  | source_md | classification | unprocessable_id | rationale | confirmed_by |

  ## B · covered_via_cross_source_pack
  | source_md | covering_pack_ids | how_covered | confirmed_by |
  ```

### 5.4 验收
- 两类总数 = scan_unprocessed_md 报告的 N
- A 类每行有 unprocessable_id（实存于 register）
- B 类每行有 ≥1 个 covering_pack_id（实存于 candidates）
- **任一行 confirmed_by 留空 → FAIL**
- 任何 md 同时落 A 和 B → 数据不一致 → FAIL

---

## 6. master full_audit 升级（v2-rev1 + 新增项）

### 6.1 `scripts/full_audit.py` 增加检查项

在 v2-rev1 已规划的 9 项基础上，加 5 项：

| # | 检查 | 失败条件 |
|---|---|---|
| 10 | task_cards 状态总览 = extraction_log 末次状态 | diff != 0 |
| 11 | SQL CHECK 严格断言 4 反例全部拒绝 | 任一反例插入成功 |
| 12 | uncovered_md_register A/B 两类全有决策依据（A 类有 unprocessable_id / B 类有 covering_pack_ids，confirmed_by 非空）| 任一空 |
| 13a | **brand_residue_review.csv 行数 = scan_brand_v2 命中全集**（裁决前 / 全量审计盘）| 不等 |
| 13b | **brand_layer_review_queue.csv 行数 = brand_residue_review.csv 中 decision ∈ {split_two_packs, migrated_to_brand, needs_review} 的子集**（仅待裁决 / 迁移 / 拆分项）| 不等 |
| 14 | final_report 数字与 manifest 一致（grep 硬编码失败） | 任一硬编码与 manifest 不一致 |

任一 fail → 退出 1。

### 6.2 audit_status.json 新增字段
```json
{
  "task_cards_synced": true,
  "sql_check_strict_passed": true,
  "uncovered_md_register_complete": true,
  "review_queue_aligned": true,
  "report_numbers_consistent": true
}
```

### 6.3 验收
- `full_audit.py` 退出 0
- `audit_status.json` `verdict = ALL_PASS` 含全部 14 字段为 true

---

## 7. 执行顺序（v2-rev2 调整）

| 阶段 | 硬门 / 动作 | 依赖 | 备注 |
|---|---|---|---|
| 1 | 硬门 0 + 硬门 5 + 硬门 7 + uncovered_md_register | 无 | 数据 / 文档清理（廉价 + 并行） |
| 2 | 硬门 1（canonical schema）| 1 完成 | 基于清洗后真值锁 |
| 3 | 硬门 2（严格校验脚本）| 2 完成 | 暴露 02/03/05 违反 |
| 4 | 硬门 3（必填 + 白名单）| 3 完成 | 按违反清单处理 |
| 5 | 硬门 4（品牌逐条裁决）| 4 完成 | 用户在场 / 对齐 review_queue |
| 6 | 硬门 8（SQL CHECK 严格化 + 反例 demo）| 1 完成 | 与硬门 6 可并行 |
| 7 | 硬门 6（CSV ↔ SQLite PK + hash 比对）| 1+8 完成 | 严格 CHECK 后再装载 |
| 8 | full_audit + 自动渲染 final_report + audit_status | 1-8 完成 | 写 master 脚本 |

**估时**：第 1 阶段 + 第 6 阶段单会话；第 5 阶段需用户裁决 10 条；其余基本自动。

---

## 8. 风险与回滚（v2-rev2 增项）

| 风险 | 缓解 | 回滚 |
|---|---|---|
| sync_task_cards_status 误覆盖手工编辑内容 | 仅重写"卡片状态总览"节，不动其他；diff 前后只允许该节变化 | 保留 task_cards.md.bak |
| SQL CHECK 严格化破坏现有 192 行装载 | 装载前在 sqlite 中干跑 SELECT 确认所有 brand_layer 取值合法 | 旧 DDL 备份 |
| GLOB `[^a-z_]` 模式在不同 SQLite 版本行为差异 | 文档化要求 SQLite ≥ 3.6 + 跑反例 demo 验证 | 退化到触发器方案 B |
| uncovered_md_register 漏证某 md 真有业务知识 | reviewer 抽查 + 复跑 scan_unprocessed_md 确认 8 份对得上 | 重新抽该 md |
| 14 项检查里某项假阳性 | 每项独立日志输出，可单独豁免后再跑 | 改阈值或排查 |

---

## 9. 验收 checklist（提交人工 review 前）

v2-rev1 8 项 + v2-rev2 新增 6 项：

**v2-rev1 已有**：
- [ ] 硬门 0：9 csv + register csv 列数对齐 / source_type ⊆ 6 值
- [ ] 硬门 1：schema enum 与真值 100% 一致 / minLength=1 / JSON 标识
- [ ] 硬门 2：validate_csv_strict 退出 0
- [ ] 硬门 3：02/03 必填空 = 0 / 05_relation 非白名单 = 0
- [ ] 硬门 4：brand_residue_review 行数 = scan 命中数 / 每行 decision + rationale 非空
- [ ] 硬门 5：register 0 列错位 / classification 100% ⊆ 8 类枚举
- [ ] 硬门 6：csv vs SQLite PK diff = ∅ / 行 hash 100% 等
- [ ] master：full_audit 退出 0 / audit_status verdict = ALL_PASS

**v2-rev2 新增**：
- [ ] 硬门 7：task_cards 状态总览与 extraction_log 末次状态一致
- [ ] 硬门 7：task_cards 节内含 AUTO-SYNCED 注释
- [ ] 硬门 8：4 反例（brand_ / brand_X / brand_with-dash / brand_中文）全部 IntegrityError
- [ ] 硬门 8：1 合法（brand_xyz）成功插入
- [ ] uncovered_md_register A 类：每行有 unprocessable_id + classification + confirmed_by
- [ ] uncovered_md_register B 类：每行有 ≥1 covering_pack_id + how_covered + confirmed_by
- [ ] A+B 两类总数 = scan_unprocessed_md 报告全集 N；任一 md 同时落 A/B 即 FAIL
- [ ] full_audit 14 字段全 true

---

## 10. 提交审核请求（v2-rev2）

请审核 v2-rev2 + 选定执行模式（沿用 v2-rev1 4 模式）：

| 模式 | 描述 |
|---|---|
| **M1** · 全量串行 | 硬门 0→5→7→1→2→3→4→8→6→master |
| **M2** · 数据先清结构后锁 | 1 阶段（0+5+7+excluded_md）→ 2-4 阶段（schema 锁）→ 5 阶段（品牌裁决）→ 6-7 阶段（SQL+SQLite）→ master |
| **M3** · M2 完成后 reviewer 三审 | 推荐生产级交付 |
| **M4** · 局部修复 | 仅做 0+5+7+uncovered_md_register（最小成本但仍 CONDITIONAL_PASS） |

**默认推荐 M2**：分 5 阶段，每阶段完成可单独提交 reviewer 检查。

---

## 11. 与 v2-rev1 对照

| v2-rev1 章节 | v2-rev2 状态 |
|---|---|
| §0-§9（除 §10 修订记录） | 全部保留 |
| §10 v2-rev1 修订记录 | 保留 + 在本文 §0 引用 |
| 硬门 0-6 | 保留 |
| §3 master + 自动渲染 | 升级（§6） |

v2-rev2 不替代 v2-rev1，而是**增量扩充**。如 reviewer 通过 v2-rev2，执行时按本文件 §7 顺序为准。


---

## v2-rev3 修订记录（reviewer 二审反馈对应）

按 reviewer 二审 CONDITIONAL_PASS 反馈（指出 4 处口径不严）修订：

| # | reviewer 关切 | 原 v2-rev2 状态 | v2-rev3 改为 | 章节 |
|---|---|---|---|---|
| 1 | "8/12 份未抽 MD" 标题与清单不一致；混淆"未抽"与"已 cross-source 覆盖" | 单类 12 份混称 | 改为 A 类 `truly_uncovered_md` + B 类 `covered_via_cross_source_pack` 两类登记，每类独立验收 | §5 |
| 2 | brand_layer_review_queue 行数 = scan 命中数错 | full_audit 检查 13 单条 | 拆为 13a（review_csv = 命中全集）+ 13b（review_queue = 待裁决子集），按 decision 字段精确过滤 | §6.1 |
| 3 | task_cards 数字不能信 extraction_log（自身有旧数字）| sync 脚本从 extraction_log 取所有 | 状态真源 = extraction_log；数字真源 = 实时磁盘（manifest / csv / sqlite）；脚本拒读 extraction_log 的数字 | §3.2 / §3.3 |
| 4 | SQL CHECK 严格化只改一份 DDL | 仅 storage/single_db_logical_isolation.sql | 双份同步改 + `check_ddl_sync.py` 字符级比对 + 反例 demo 双验证 | §4.3 |

修订后保留全部 9 硬门 + 14 检查项，新增 1 项工具（check_ddl_sync.py）。
v2-rev3 不替代 v2-rev2，是同文件原地修订；演进链 v1 → v2 → v2-rev1 → v2-rev2 → **v2-rev3** 全部留在本文件内。


---

## v2-rev3-r1 修订记录（reviewer 三审小修正）

| # | reviewer 关切 | 改动 | 位置 |
|---|---|---|---|
| 1 | 旧文字 "excluded_md_register" / "12 份" 未同步改名 | replace_all → uncovered_md_register；"12 份"改为 A/B 两类描述 | §0 / §6.1 / §7 / §9 等多处 |
| 2 | 执行顺序"硬门 0+5+7+5"第二个 5 误读 | 改为"硬门 0 + 硬门 5 + 硬门 7 + uncovered_md_register" | §7 阶段 1 |
| 3 | SQL CHECK 验收应以反例实测为准 | §4.5 加"必须真实运行 INSERT 不是 grep 文本"+ 失败即降级方案 B | §4.5 |

至此 v2-rev3-r1 = reviewer 三审通过 + 3 项小修完成 → **可执行**。


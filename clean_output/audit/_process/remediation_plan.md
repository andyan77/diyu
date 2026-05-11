---
snapshot_type: historical_review
frozen_at: 2026-05-03T15:50:44Z
source_state: pre-W10
rationale: 历史复核/方案文档，反映当时状态，不再随仓库演进；不参与 G18 漂移检测
---

# 全面修复方案 · 待审核

> 触发：用户对 22 张已落盘任务卡交付做 10 项核心原则对齐审查后，给出整体 FAIL verdict。
> 目标：**让交付物从"主链路可用"升级到"10 项核心原则全对齐通过"**。
> 本方案分 5 个修复轴，每轴含动作 / 实现细节 / 验收 / 影响面。

---

## 0. 当前 verdict 复盘

| 层 | 现状 |
|---|---|
| 知识抽取质量 | CONDITIONAL_PASS（10 条品牌残留待复核）|
| 多租户模型结构 | CONDITIONAL_PASS（结构对，但实际无 brand_faye 行未演练）|
| 机器可读交付 | **FAIL**（schema 枚举与数据不一致）|
| 过程可验证交付 | **FAIL**（数字漂移、文档漂移、SQLite 不全量入库）|
| 整体对齐目标 | **FAIL** |

4 项硬阻断（用户实测）：
1. `nine_tables.schema.json` `source_type` 枚举与 CSV 不一致（schema 仅含 3 值，数据有 6 值）
2. CSV 1682 vs final_report 1605 vs SQLite 部分表更少 —— 三方数字漂移
3. 品牌残留 ~10 条 pack 仍含"笛语"具体字眼但标 domain_general
4. README 停在 W2 / empty_tables_explanation 说 lifecycle=0 但实际=1 / coverage_report checksum 失败

---

## 1. 修复轴 A · schema 与数据强一致（最高优先级 · 解 P8/P9）

### A.1 扩展 schema 枚举以匹配实际数据

**动作**：
- 收集 `07_evidence.source_type` 实际取值清单（grep 全 evidence 行 col5）
- 收集 `07_evidence.inference_level` 实际取值清单
- 重写 `clean_output/schema/nine_tables.schema.json` `07_evidence` 节的 source_type / inference_level 枚举
- 同步 `clean_output/schema/enum_dict.yaml` 的 source_type / inference_level 节
- 同步 `.claude/skills/extract-9tables/SKILL.md` §8 列定义（如有）

**枚举扩展（实际预期）**：
- source_type：`direct_quote` / `paraphrase` / `inference` / `explicit_business_decision` / `explicit_play_card` / `cross_source_consensus` / `explicit_business_principle`
- inference_level：`L0` / `L1` / `L2` / `direct_quote` / `paraphrased`（先实测再定）

### A.2 写 schema 校验脚本 `validate_csv_against_schema.py`

**功能**：
- 读 9 张 csv + nine_tables.schema.json
- 对每行做 JSONSchema 校验
- 输出违反项（行号 + 字段 + 实际值 + 应为 enum）
- 任一违反 → 退出码 1，阻断后续

### A.3 验收
- 全量校验脚本退出 0
- 192 evidence 行 source_type 100% 在 enum 内
- 所有 9 表枚举字段 100% 在 enum_dict 内

---

## 2. 修复轴 B · 数字一致性（解 P4/P9）

### B.1 找出 CSV vs SQLite 不一致的根因

**动作**：
- 用 `csv` 模块严格读取 9 张 csv（非按行 wc）→ 得到真实数据行数
- 写 `scripts/load_to_sqlite.py` 用 csv 模块 + executemany，避免 `.import` 对多行/嵌入引号的解析问题
- 对比"严格 csv 行数 vs SQLite 加载后 SELECT COUNT(*) "，输出每张表差值

### B.2 用 manifest 作为单一事实源（SSOT）

**动作**：
- `build_manifest.py` 已记录每张 csv 的 lines / data_rows
- 改 final_report.md 数字段：所有"行数"段从 manifest.json 自动读取
- 删除 final_report.md 中硬编码的 1605
- 加一节"数字 SSOT 规则：所有交付物中的行数引用 manifest.json，禁止硬编码"

### B.3 重跑 SQLite demo + 写盘新的 demo log

**动作**：
- 用新的 `load_to_sqlite.py` 重建 knowledge.db
- 跑 3 个查询模板 + CHECK 反漂移测试
- 行数 100% 等于 csv 真实行数
- demo log 加一节"加载完整性核对：每张表 csv 行数 vs SQLite 行数 = 0 差异"

### B.4 验收
- manifest / final_report / SQLite demo log / coverage_report 四份文件的行数完全一致
- SQLite COUNT 与 csv 行数差 = 0

---

## 3. 修复轴 C · 品牌残留闭环（解 P1/P2/P7）

### C.1 实测 10 条品牌残留

**动作**：
- 跑 `scripts/scan_brand_v2.py` 输出全量真阳性清单（pack_id / 触发条件 / 命中文本片段 / 所在 yaml 行号）
- 落盘到 `audit/brand_residue_review.csv`：列 `pack_id, trigger, hit_text, hit_line, current_brand_layer, suggested_action, status, decided_by, decided_at`

### C.2 逐条裁决（3 选 1）

每条按 SKILL.md §6.2 三步走：

| 决策 | 动作 |
|---|---|
| **A · 去笛语化保留** | 改 yaml 把"笛语 X"换成抽象表达（如"在某品牌接客场景"），重派 9 表行替换原行；status=`degraded_ok` |
| **B · 拆为两条** | 拆出 domain_general 抽象规则 + brand_faye 具体取值两条 pack；前者覆盖原 yaml，后者新建到 `candidates/brand_faye/`；9 表对应行同步拆；status=`split_done` |
| **C · 整条迁 brand_faye** | yaml 整体迁 `candidates/brand_faye/`；9 表 brand_layer 列改为 `brand_faye`；status=`migrated` |

**默认策略**：能 A 优先 A（成本最低）；含具体笛语口径必须 B；整条只讲笛语具体内容才 C。

### C.3 重跑闸门
- 任一决策完成后重跑 `scan_brand_v2.py` → 真阳性应为 0
- 重跑 `verify_reverse_traceability.py` → 0 断点
- 重跑 `validate_csv_against_schema.py` → 全过

### C.4 brand_layer_review_queue 同步
- B / C 决策的 pack 落 `audit/brand_layer_review_queue.csv`，记录拆分理由 / 迁移理由

### C.5 验收
- `scan_brand_v2.py` 真阳性 = 0
- `brand_layer_review_queue.csv` 行数 = 实际 B+C 决策数
- `brand_residue_review.csv` 全 192 条 status 非空（含 A 类的 degraded_ok）

---

## 4. 修复轴 D · 审计产物去漂移（解 P9）

### D.1 README.md 重写

**动作**：
- 把 `clean_output/README.md` 当前停留状态从 W2 推到 **W7 闭环**
- 加"如何重跑全量校验链"节：列出 5 个 scripts 的执行顺序

### D.2 empty_tables_explanation.md 校正

**动作**：
- 当前说 lifecycle = 0 数据行；实际已 = 1 行
- 改写为"lifecycle 1 行（来自某 pack 的状态迁移）+ 仍未触发的状态机说明"
- 同步触发率指标到当前真实

### D.3 coverage_report.md checksum 校正

**动作**：
- 排查 checksum 失败原因（是 manifest 重生成后未同步，还是行尾 CRLF）
- 重跑 `build_manifest.py` 确保 sha256 与文件实际一致
- coverage_report 末尾加一段"checksum 验证规则：每次更新本文件后必须重跑 build_manifest"

### D.4 final_report.md 加 limitations / pending 节

**动作**：
- 在 §10 之前插入新 §9.1 "已知 limitations"：
  - schema 与数据 strict 校验首次落地（A 轴）
  - 品牌残留闭环（C 轴）
  - 数字 SSOT 规则（B 轴）
- 把 §1 / §4 数字段改为引用 manifest.json
- 在结论末尾加"verdict：knowledge_extraction CONDITIONAL_PASS / multi_tenant_structure CONDITIONAL_PASS / machine_readable PASS（修复后）/ process_verifiable PASS（修复后）"

### D.5 验收
- README 末行 = W7 状态
- empty_tables_explanation 的 lifecycle 描述与实际数据一致
- coverage_report 的 checksum 重算后通过
- final_report 的 verdict 节明确

---

## 5. 修复轴 E · 强化校验闭环（防回归 · 解 P9）

### E.1 加一条 master 校验脚本 `scripts/full_audit.py`

**功能**：依次跑：
1. `build_manifest.py` → 重算 manifest + checksums
2. `verify_reverse_traceability.py` → 反向 0 断点
3. `validate_csv_against_schema.py` → schema 100% 过
4. `scan_unprocessed_md.py` → 覆盖率 + 未抽清单
5. `scan_brand_v2.py` → 品牌残留 0 真阳性
6. `load_to_sqlite.py` → SQLite 行数 = csv 行数
7. 输出综合状态 ALL_PASS / FAIL（任一失败即 FAIL，列出失败项）

### E.2 加一份 `audit/audit_status.json`

每次 full_audit.py 跑完写一份：
```json
{
  "ts": "2026-05-03T...",
  "manifest_sha": "...",
  "verify_reverse": "pass | <breakcount>",
  "schema_validation": "pass | <violations>",
  "coverage_pct": 81.8,
  "brand_residue_count": 0,
  "sqlite_row_diff": 0,
  "verdict": "ALL_PASS | FAIL"
}
```

### E.3 验收
- `full_audit.py` 退出 0
- `audit_status.json` `verdict = ALL_PASS`

---

## 6. 执行顺序与时间预估

| 阶段 | 轴 | 顺序 | 依赖 |
|---|---|---|---|
| 1 | D（部分）| README + empty_tables + coverage checksum | 无依赖（廉价修复） |
| 2 | A | schema 扩展 + validate 脚本 | 无依赖 |
| 3 | B | 数字 SSOT + SQLite 重载 + demo log | 依赖 A 完成 |
| 4 | C | 品牌残留 10 条裁决 + 重派 | 依赖 A/B 完成 |
| 5 | E | full_audit master 脚本 + audit_status.json | 依赖 A-D 完成 |
| 6 | D（剩余）| final_report 加 verdict + limitations 节 | 依赖 A-E 完成 |

**预估**：纯执行 ~ 单会话内可完成轴 1+2+5；轴 3（C 品牌残留 10 条裁决）需要用户在场逐条 OK；轴 4（B SQLite）有概率因 csv 多行嵌入引号需调试。

---

## 7. 风险点与回滚预案

| 风险 | 缓解 | 回滚 |
|---|---|---|
| schema 扩展把不该是 enum 的字段误锁 | 先用 `validate` 跑 dry-run 看违反报告，再决定是 enum 还是 free-text | git diff 还原 schema |
| 9 表行删/改后 PK 冲突 | 任何重派前先对 9 表做 `cp *.csv *.csv.bak` 备份 | 用备份恢复 |
| 品牌残留拆分误拆 | 每条拆分前在 review_csv 先记 status=`split_pending`，用户 OK 才动 yaml | yaml 备份后再改 |
| SQLite 加载 .import 失败仍出现 | 改用 csv 模块 + executemany；若仍失败回退到 INSERT 单行循环 | 保留旧 demo log |

---

## 8. 验收 checklist（提交人工 review 前）

- [ ] A.1 schema enum 与实际数据 100% 一致
- [ ] A.2 `validate_csv_against_schema.py` 退出 0 / 0 违反
- [ ] B.1 csv 严格行数 vs SQLite COUNT 差 = 0
- [ ] B.2 final_report.md 数字段全部引用 manifest（无硬编码）
- [ ] B.3 SQLite demo log 加载完整性核对节
- [ ] C.1 `audit/brand_residue_review.csv` 落盘
- [ ] C.2 10 条全部裁决（status 非空）
- [ ] C.3 `scan_brand_v2.py` 真阳性 = 0
- [ ] D.1 README 状态 = W7
- [ ] D.2 empty_tables_explanation 反映 lifecycle = 1
- [ ] D.3 coverage_report checksum 通过
- [ ] D.4 final_report 含 limitations + verdict 节
- [ ] E.1 `full_audit.py` 退出 0
- [ ] E.2 `audit_status.json` verdict = ALL_PASS

---

## 9. 提交审核请求

请你 **审核本方案** 并选定执行模式：

1. **直接全量执行 A→B→C→D→E**（C 段 10 条品牌残留我会先列出再问你逐条决定）
2. **先执行 1+2 轴（D 廉价 + A schema），跑出真实违反报告再回来商定 B/C/E**
3. **先执行 C（品牌残留）**，因为这是质量项最敏感的，再谈结构性的 A/B/D/E

或对方案本身做修改后再批。

审核通过后我将逐轴推进，每轴完成提交一次小报告再进下一轴，避免在长链路中累积不可见误差。

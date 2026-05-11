---
snapshot_type: historical_review
frozen_at: 2026-05-03T15:50:44Z
source_state: pre-W10
rationale: 历史复核/方案文档，反映当时状态，不再随仓库演进；不参与 G18 漂移检测
---

# 全面修复方案 v2 · 7 硬门版（待审核）

> 触发：v1 方案被 governance review 判为 RISKY；本版按 reviewer 6 项缺口 + 1 项实测新发现重写。
> 目标：把交付物从 CONDITIONAL_PASS 升到 **10 项核心原则全对齐通过**。
> v1 留作演进证据：[remediation_plan.md](remediation_plan.md)

---

## 0. v1 → v2 改动汇总

| reviewer 缺口 | v1 状态 | v2 处理 |
|---|---|---|
| 1. A 轴枚举不完整 / 写错 | 含 `explicit_business_principle`（不存在）| ❌ 删；按实测真值清单（见 §2.1）|
| 2. 只扩 schema 是合法化脏数据 | 缺非空 / 白名单 / JSON 校验 | ✅ 硬门 1 加入：required-non-null + 对象白名单 + JSON 字段可解析 |
| 3. C 轴 `真阳性=0` 验收目标错 | 机械要求归零 → 误迁通用 founder 规则 | ✅ 改为"逐条裁决闭环 + 裁决理由必填"，不要求归零 |
| 4. 192 条全 status 非空不合理 | 浪费审计成本 | ✅ 改为"扫描器命中项落 review_csv，未命中不入审计" |
| 5. unprocessable_register 列漂移未处理 | 完全漏 | ✅ 硬门 5 加入：5 条列错位行结构性修复 |
| 6. B 轴 SQLite 仅比 count | 漏行内容 / 主键集 | ✅ 改为"主键集合 + 行 hash 双比对" |
| **新发现（v1 未列）**：CSV 结构损坏 | 完全漏 | ✅ **新增硬门 0**：CSV 多行嵌套引号修复（最严重） |

---

## 1. 实测发现的真实问题清单

按今日实测（命令见 §10）：

### 1.1 CSV 真值（v2-rev1 校正：撤销"结构损坏"误报）

**校正记录**：v2 初版基于 `awk -F','` 推断 `07_evidence.csv` "多行 evidence_quote 污染下游列"。
reviewer 复核后实测 `csv.DictReader`（Python 标准库，正确处理 quoted multiline）：
- 192 行全部列数对齐（`bad_rows = []`）
- `source_type` 6 干净值，`inference_level` 3 干净值
- 所谓 ` reason}]->(:ContentType)` 等是 awk 不识别 csv 引号导致的工具错误，**不是数据损坏**

→ **v2 工具纪律**：
- 校验 / 诊断 CSV 结构 **以 Python `csv` 模块为唯一事实源**
- **禁用 `awk -F','` 判定 CSV 列数 / 取值**
- 合法的多行字段（如 evidence_quote 跨行原文引用）**保持原样，不强制单行化 `<br>` / `\n`**

实测 source_type 真值清单（csv 模块读取，无污染）：
- `cross_source_consensus`
- `explicit_business_decision`
- `explicit_business_rule`
- `explicit_play_card`
- `explicit_role_skill_lock`
- `structural_pattern`

实测 inference_level 真值清单：
- `direct_quote`
- `low`
- `structural_induction`

### 1.2 必填字段空值

| 表 | 空值情况 |
|---|---|
| 02_field | owner_type / field_name / data_type 均有 6 行全空 |
| 03_semantic | owner_field / definition 各 3 行空 |
| 04_value_set | value 列存在空值（v1 已疑 · 待实测） |

### 1.3 非白名单对象类型

`05_relation.csv` 出现 2 个非 18 项白名单的类型：
- `PersonaContentTypePlatformDerivedView`
- `Persona+ContentType+PlatformTone|PrivateOutletChannel`

这违反 skeleton.yaml 硬约束（白名单关闭）—— 应进 skeleton_gap_register 而非直接落 9 表。

### 1.4 unprocessable_register 列漂移

5 行（line 38/39/41/45/46）列数 ≠ header（9 列），实际值因含逗号未引号包裹串到下一列。

### 1.5 笛语字样残留

scan_brand_v2.py 报 ~10 条真阳性（reviewer 抽样 KP-service_judgment-product-review-concerns-clearance-on-spot 含"笛语在接客场景下最强的转化工具"）。

---

## 2. 7 硬门设计

### 硬门 0 · CSV 结构验收（v2-rev1 缩窄：诊断不修复）

**校正背景**：v2 初版基于 `awk -F','` 判定 `07_evidence.csv` 需"强制单行化"，被 reviewer 复核否定（csv 模块读取 192 行全部对齐 / 6+3 干净 enum）。本硬门改为**只诊断不修复**结构。"修复"职责仅留给真正损坏的文件（实测仅 unprocessable_register，见硬门 5）。

**动作**：
- 写 `scripts/csv_structure_check.py`（**只读 / 不写**）：
  - 用 csv 模块（DictReader）严格读 9 张 nine_tables csv + register csv
  - 输出每张表：`rows_total / bad_len_rows / distinct enum cols`
  - 任一 `bad_len_rows != []` → 退出码 1 + 在 `audit/csv_struct_violations.csv` 列出
- **禁用** `awk -F','` 判定 CSV 列数 / 取值（不识别 csv 引号 → 假阳性）
- **禁止**对合法多行字段（evidence_quote 等）做单行化改写

**验收**：
- 9 张 nine_tables csv 全部 `bad_len_rows == []`（实测已通过）
- `07_evidence.source_type` 取值清单 = §1.1 的 6 值集合
- `07_evidence.inference_level` 取值清单 = §1.1 的 3 值集合
- register csv 列数对齐由硬门 5 单独负责

### 硬门 1 · canonical schema（非合法化脏数据）

**动作**：
- 重写 `clean_output/schema/nine_tables.schema.json`，硬化以下：
  - 所有 required 字段加 `"minLength": 1`
  - `01_object_type.type_name` enum = skeleton 18 项白名单（不可扩）
  - `05_relation.{source_type,target_type}` enum = 同上
  - `05_relation.relation_kind` enum = skeleton 14 项白名单
  - `07_evidence.source_type` enum = §1.1 实测 6 值（**清洗后真值**，不含污染值）
  - `07_evidence.inference_level` enum = §1.1 清洗后 3 值
  - `*.brand_layer` pattern = `^(domain_general|brand_[a-z_]+|needs_review)$`
  - JSON 字段（`properties_json` / `governing_rules_json` / `examples_json`）加 `"format": "json"` 标识，校验脚本里跑 `json.loads()`

**验收**：
- schema 与实测 enum 100% 对齐
- schema 中 enum 值集合 ⊆ skeleton 白名单（不允许 schema 扩 skeleton）

### 硬门 2 · 全量 CSV 严格校验（不只 schema）

**动作**：
- 写 `scripts/validate_csv_strict.py`：
  - 对每张 csv 跑 schema 校验
  - 额外硬检查：required 非空 / 白名单字段精确匹配 / JSON 字段可 `json.loads()`
  - 违反项落 `audit/csv_violations.csv`（pack_id / table / line / field / value / reason）

**验收**：
- 退出码 0 → 全过；退出 1 → `csv_violations.csv` 列出所有违反
- 02/03/04 表的"必填空值"全部修复或删除（详见 §3）
- 05_relation 非白名单类型清理（详见 §4）

### 硬门 3 · 必填空值与白名单回归（解 §1.2 §1.3）

**动作**：

#### 3.1 02_field / 03_semantic 空值行
- 6 + 3 = 9 行实测空必填：先 grep 出对应 source_pack_id，回看 yaml；
- 三选一：
  - 漏写 → 补 yaml 后重派 9 表行
  - 不该入 9 表（meta 信息）→ 删 9 表行 + yaml 标记原因
  - 数据本身无业务字段（占位行）→ 进 unprocessable

#### 3.2 05_relation 非白名单类型归位
- `PersonaContentTypePlatformDerivedView` / `Persona+ContentType+PlatformTone|PrivateOutletChannel`
- 路径选择：
  - **A · 进 skeleton_gap_register**：登记为 GAP-005/006，对应 5 表行先标 `pending_gap_decision` 或暂从 9 表删除
  - **B · 拆为多条 relation**：把 `Persona+ContentType+...` 拆成 Persona→ContentType + Persona→PlatformTone + Persona→PrivateOutletChannel 三条 relation_kind=`compatible_with_*`
- **建议 B**：拆分能保留语义且不破坏白名单纪律
- 修复后重派对应 pack 的 05_relation 行

**验收**：
- 02/03 表必填字段空值 = 0
- 05_relation 表非白名单类型出现次数 = 0
- 涉及的 pack 在 yaml 中明确记录修改

### 硬门 4 · 品牌残留逐条裁决（不要求归零）

**动作**：

#### 4.1 扫描 + 落审计盘
- 跑 `scan_brand_v2.py` 输出全部命中项（约 10 条）
- 落 `audit/brand_residue_review.csv` 列：
  ```
  pack_id, trigger, hit_text, hit_line, current_brand_layer,
  decision, decision_rationale, decided_by, decided_at, status
  ```
- **未命中项不进表**（解决 v1 误要求 192 条全填的问题）

#### 4.2 决策枚举（4 选 1，扩展 v1 的 3 选）
| decision | 含义 | 状态最终 |
|---|---|---|
| `degraded_to_general` | 改 yaml 去笛语化 → 重派 | brand_layer=domain_general |
| `split_two_packs` | 拆 domain_general 抽象 + brand_faye 具体 | 两条 pack |
| `migrated_to_brand` | 整条迁 brand_faye | brand_layer=brand_faye |
| **`domain_general_keep`** | scan 误报：术语 / 通用建模规则非品牌专属 | brand_layer=domain_general（保留）+ rationale 必填 |

#### 4.3 验收（非"=0"）
- `brand_residue_review.csv` 行数 = scan 命中数（约 10）
- 每行 decision + decision_rationale 非空
- 重跑 `scan_brand_v2.py` 后剩余的真阳性必须 100% 在 review_csv 中且 decision=`domain_general_keep`
- 任一 `decided_by` / `decided_at` 留空 → FAIL

### 硬门 5 · unprocessable_register 列漂移 + classification 枚举（v2-rev1 强化）

**校正背景**：reviewer 指出"只修列数不修语义错位也算假通过"。本硬门同时校验**结构**与**枚举**。

**动作**：
- 写 `scripts/fix_register_csv.py`：
  - csv 模块按 `quotechar='"'` 严格读
  - 检测 5 行（实测 line 38/39/41/45/46）列错位
  - 对每行：grep 原 yaml/MD 确认 classification 真值 → 重写 csv 行使列对齐 + classification 落到正确列
- 写 `scripts/validate_register_enum.py`：
  - 读 register csv（修复后），逐行检查 `classification ∈ 受控枚举`
  - 受控枚举（按 SKILL.md 反空壳门禁 8 类 + extract 实战补充）：
    - `meta_layer_definition` / `meta_layer_not_business`
    - `external_reference_material` / `out_of_scope`
    - `duplicate_or_redundant`
    - `evidence_insufficient`
    - `scenario_not_closed`
    - `process_description_needs_split`
  - 任一非枚举 → 退出 1 + 落 `audit/register_enum_violations.csv`

**验收（双门禁）**：
- 结构：`csv.DictReader` 全表 0 列错位 / 每行 9 列严格对齐
- 枚举：`classification` 列 100% ⊆ 上述 8 类受控枚举
- 任一不过 → FAIL（不允许"列对齐但 classification 漂移"假通过）

### 硬门 6 · CSV ↔ SQLite 主键集 + hash 双比对（替代 v1 仅比 count）

**动作**：
- 写 `scripts/load_to_sqlite.py`：
  - 用 csv 模块（不用 `.import`）读全量
  - executemany INSERT
  - SELECT 全量回读
- 写 `scripts/diff_csv_vs_sqlite.py`：
  - 对每张表：csv PK 集合 vs SQLite PK 集合 → 取 symmetric diff，应 = ∅
  - 对每行：md5(行内容) csv vs md5(行内容) SQLite → 应 = 等
  - 输出 `audit/csv_vs_sqlite_diff.csv`，0 行才过

**验收**：
- PK 集合 symmetric diff = ∅
- 全表行 hash 100% 等
- 这 2 项任一 fail → 整体 FAIL

---

## 3. master 校验脚本 + 报告生成（替代 v1 轴 E）

### 3.1 `scripts/full_audit.py`（防假通过）

**与 v1 不同**：不只串现有脚本，而是**每步内嵌新校验**：
1. CSV 结构（DictReader 列数 100% 对齐）
2. schema 严格校验（含 minLength / 白名单 / JSON parsable）
3. 必填非空 + 白名单回归
4. unprocessable_register 列对齐
5. brand_residue_review 全行 decision 非空
6. CSV ↔ SQLite PK + hash 双比对
7. 反向追溯 0 断点
8. coverage 与 manifest 数字一致
9. final_report 数字与 manifest 一致（grep 对比硬编码数字）

**任一 fail → 退出 1**

### 3.2 `audit/audit_status.json`

```json
{
  "ts": "2026-05-03T23:59:59",
  "manifest_sha": "...",
  "csv_struct_ok": true,
  "schema_strict_ok": true,
  "required_non_null_ok": true,
  "whitelist_ok": true,
  "register_aligned_ok": true,
  "brand_residue_decided_ok": true,
  "csv_sqlite_pk_diff": 0,
  "csv_sqlite_hash_diff": 0,
  "reverse_breaks": 0,
  "coverage_pct": 81.8,
  "verdict": "ALL_PASS"
}
```

### 3.3 报告自动生成（解决 v1 "Markdown 无法动态引用"风险）

- 写 `scripts/render_final_report.py`：
  - 读 manifest.json + audit_status.json
  - 模板 fill 渲染 `audit/final_report.md`
  - 加 `<!-- AUTO-GENERATED FROM manifest.json + audit_status.json · DO NOT HARDCODE NUMBERS -->`
  - 每次跑 full_audit 自动重渲染

### 3.4 验收
- `full_audit.py` 退出 0
- `audit_status.json verdict = ALL_PASS`
- final_report.md 末次修改时间晚于 manifest.json（证明被自动渲染）

---

## 4. 执行顺序与依赖

| 阶段 | 硬门 | 依赖 | 备注 |
|---|---|---|---|
| 1 | 0 · CSV 结构修复 | 无 | 必先做，否则后续校验全是假通过 |
| 2 | 5 · unprocessable_register 修复 | 无 | 与硬门 0 可并行 |
| 3 | 1 · canonical schema | 0 完成 | 基于清洗后真值定枚举 |
| 4 | 2 · 严格校验脚本 | 1 完成 | 暴露 02/03/05 表违反清单 |
| 5 | 3 · 必填空值 + 白名单 | 2 完成 | 按违反清单处理 |
| 6 | 4 · 品牌残留逐条裁决 | 3 完成 | 数据干净后再做品牌问题 |
| 7 | 6 · SQLite PK+hash 双比对 | 0+3 完成 | csv 干净后才能比 |
| 8 | full_audit + 自动报告 | 1-6 完成 | 写 master 脚本 |

**估时**：硬门 0+1+2+5 单会话；硬门 3+4 需用户在场逐项裁决；硬门 6+master 单会话。

---

## 5. 风险与回滚（更细粒度）

| 风险 | 概率 | 缓解 | 回滚 |
|---|---|---|---|
| CSV 结构修复改动太大破坏 PK | 中 | 先 cp *.csv.bak.<ts>，diff 改动行数；改动 > 50 行需先报告 | bak 还原 |
| 拆分非白名单 relation 改变语义 | 低 | 拆分前在 yaml 加 `# split-from-PersonaContentTypePlatformDerivedView` 注释 | 按注释合并回去 |
| 必填空值修复时把 placeholder 当真删 | 中 | 删除前导出待删行清单给用户 confirm | 删行清单可重派 |
| 品牌裁决误判（误把品牌专属判 keep）| 中 | 4 选 1 决策必须配 rationale 且 reviewer 二审 | 改 decision 重跑 |
| `domain_general_keep` 滥用 | 中 | full_audit 加扫"keep 占比 > 30% 警告" | 强制重审 |
| schema 改完旧的脏数据被锁出 | 高 | 顺序 0→1→2→3 保证脏数据先清再锁 schema | 改 schema 前打快照 |

---

## 6. 验收 checklist（提交人工 review 前）

- [ ] 硬门 0：9 csv + register csv 列数 100% 对齐 / source_type 取值 ⊆ 6 值
- [ ] 硬门 1：schema enum 与清洗后真值 100% 一致 / minLength=1 / JSON 字段格式标识
- [ ] 硬门 2：`scripts/validate_csv_strict.py` 退出 0
- [ ] 硬门 3：02/03 表必填空 = 0 / 05_relation 非白名单 = 0
- [ ] 硬门 4：`brand_residue_review.csv` 行数 = scan 命中数 / 每行 decision + rationale 非空
- [ ] 硬门 5：unprocessable_register 0 列错位 / classification 全部入受控枚举
- [ ] 硬门 6：csv vs SQLite PK symmetric diff = ∅ / 行 hash 100% 等
- [ ] master：`full_audit.py` 退出 0
- [ ] master：`audit_status.json verdict = ALL_PASS`
- [ ] master：final_report.md 由脚本渲染（含 AUTO-GENERATED 注释）
- [ ] reviewer 抽样：原 KP-service_judgment-product-review-concerns-clearance-on-spot 已正确处理
- [ ] reviewer 抽样：原 PersonaContentTypePlatformDerivedView 已不在 9 表

---

## 7. 与 v1 的对照交付

| v1 模块 | v2 状态 |
|---|---|
| v1 §1 轴 A schema 扩枚举 | 由硬门 0+1 替代（先清数据再锁 canonical schema） |
| v1 §2 轴 B 数字一致性 | 由硬门 6（PK+hash）+ §3.3 自动渲染替代（解决 Markdown 硬编码漂移） |
| v1 §3 轴 C 品牌残留 | 由硬门 4（4 选 1 + rationale 必填）替代，去除"=0"机械要求 |
| v1 §4 轴 D 审计漂移 | 由 §3.3 自动渲染替代 |
| v1 §5 轴 E full_audit | 由 §3.1 内嵌校验版本替代，防假通过 |

---

## 8. 提交审核请求

请审核本 v2 方案 + 选择执行模式：

| 模式 | 描述 | 推荐场景 |
|---|---|---|
| **M1** · 全量串行 | 硬门 0→5→1→2→3→4→6→master | 单次会话内全闭环（C 段需用户在场） |
| **M2** · 数据先清结构后锁 | 先做硬门 0+5+3+6 数据清理，再做 1+2+4 schema/品牌锁定 | 推荐：风险最小化 |
| **M3** · reviewer 二轮 | M2 完成后请 reviewer 再做一次 governance review，再做硬门 4 品牌残留 | 推荐生产级交付时使用 |
| **M4** · 局部修复 | 只做硬门 0+5+1+2（机器可读 / 过程可验证） | 最小成本但仍 CONDITIONAL_PASS |

**默认推荐 M2**：先把数据清干净（避免 schema 锁出），再上 schema 校验，再做品牌裁决与 SQLite 闭环。

---

## 9. 实测命令记录（可重跑）

```bash
# 1.1 检测 source_type / inference_level 实际值
awk -F',' 'NR>1{print $5}' clean_output/nine_tables/07_evidence.csv | sort -u
awk -F',' 'NR>1{print $6}' clean_output/nine_tables/07_evidence.csv | sort -u

# 1.2 必填空值
python3 -c "import csv; rows=list(csv.DictReader(open('clean_output/nine_tables/02_field.csv'))); print('owner_type 空:', sum(1 for r in rows if not r['owner_type'].strip()))"

# 1.3 非白名单
python3 -c "
import csv
WL={'Product','Category','Attribute','Collection','FabricKnowledge','CraftKnowledge','StylingRule','DisplayGuide','TrainingMaterial','RoleProfile','Persona','ContentType','PlatformTone','PrivateOutletChannel','InventoryState','CustomerScenario','CallMapping','Evidence'}
rows=list(csv.DictReader(open('clean_output/nine_tables/05_relation.csv')))
print({r['source_type'] for r in rows if r['source_type'] not in WL} | {r['target_type'] for r in rows if r['target_type'] not in WL})
"

# 1.4 register 列错位
python3 -c "
import csv
rows=list(csv.reader(open('clean_output/unprocessable_register/register.csv')))
hdr=rows[0]
print([i for i,r in enumerate(rows[1:],2) if len(r)!=len(hdr)])
"
```

---

## v2-rev1 修订记录

按 reviewer 复审 CONDITIONAL_PASS 反馈（2026-05-03 第二轮）：

| 修订点 | 原 v2 | rev1 改为 | 验证 |
|---|---|---|---|
| 硬门 0 范围 | "结构修复" / 强制单行化 evidence_quote | "结构验收"（只读不写）/ 禁用 awk / 保留合法多行 | csv 模块实测 192 行 0 bad_rows |
| 硬门 0 工具纪律 | （未明示）| 明文写"以 csv 模块为唯一事实源" | 在 §1.1 / 硬门 0 双处声明 |
| 硬门 5 验收 | 仅"列对齐 + classification 入受控枚举" | **双门禁**：结构 + 枚举各为独立失败条件 | 加 `validate_register_enum.py` + 受控 8 枚举显式列出 |
| §1.1 误报 | "结构损坏" 论断 | 明确撤销 + 标记 awk 工具错误 | 留作纠错证据 |


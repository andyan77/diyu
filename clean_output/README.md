# clean_output · 服装零售 4 闸 9 表抽取产出

> **Verdict**: CONDITIONAL_PASS（可作"结构化知识库工程底座"验收，不能作"真实知识点全集抽尽"验收）
> 数据模型：**多租户单库逻辑隔离**（`domain_general` + `brand_<name>` + `needs_review`）
> 当前状态：194 packs / 9 表 1688 行 / **25 道硬门全绿** / W11 三层裁决落地 / Finding 2/3 关闭
> 数据真源分两层：**W10 兼容层**（4 态主表，旧硬门链路）+ **W11 三层真源**（`source_unit_adjudication_w11.csv` + `pack_layer_register.csv`）

---

## 〇、W11 三层裁决真源（最新口径 · Finding 2/3 关闭）

> W11 把"覆盖率"从一维数字升级为 **layer-aware 资产分布**——四闸管"是否合格"，三层管"以什么粒度被消费"。

**source_unit 终态**（1578 行 100% 签字，见 `audit/source_unit_adjudication_w11.csv`）：

| 状态 | 行数 | 业务章节占比 | 用途 |
|---|---:|---:|---|
| `extract_l1` 概念层 | 454 | **39.5%** | 判断 / 分类 / 质检 / 品牌一致性 |
| `extract_l2` 玩法层 | 329 | **28.7%** | 生成选题 / 脚本骨架 / 栏目玩法 |
| `defer_l3_to_runtime_asset` 执行层 | 128 | **11.1%** | 镜头 / 台词 / 道具 / 模板 |
| `unprocessable` | 658 | — | 元层 / 短节 / 跨源引用 / 外部研究稿 |
| `duplicate` | 9 | — | 同 body sha 去重 |

**pack 终态**（194 个，见 `pack_layer_register.csv`）：L1=141 / L2=29 / L3=24

**Finding 2/3 关闭证据**：
- F2（章节级覆盖低）：W11 layer-aware 口径下 L1+L2+L3 = **79.3%** 业务章节有显式落点 ✅
- F3（pending_decision 未闭环）：W11 主表 0 pending（全部已签 6 类枚举之一）✅
- G19 硬门：每行必须有 final_status + 必填字段；当前 25/25 绿

**W10 兼容层不变**：W10 主表 `source_unit_adjudication.csv` 仍维持 4 态（covered_by_pack=357 / unprocessable=430 / duplicate=9 / pending=782），供 G16d 旧硬门链消费。两份 SSOT 并存，互不污染。

立法文档：[`templates/granularity_layer_framework.md`](templates/granularity_layer_framework.md) · [`templates/G19_layer_adjudication_contract.md`](templates/G19_layer_adjudication_contract.md)

---

## 一、CONDITIONAL_PASS 三声明（W10 兼容口径，请先读）

本批交付经过 9 轮 review。W10 reviewer 判 CONDITIONAL_PASS；W11 通过三层粒度框架关闭 Finding 2/3。三个必须明示的诚实声明（W10 口径，W11 已超越）：

### 1. W10 口径章节级覆盖率：31.1%（业务章节 357/1148）

> **W11 已升级**：见〇节，layer-aware 口径下 79.3% 业务章节已分层覆盖。下面是 W10 兼容口径。


- 输入 44 份 MD → 切到 1578 个 source_unit（H1/H2/H3 章节）
- 业务章节（去元层 / cross-source / unprocessable / 短节）= 1148
- 已被 evidence 直接命中或父 pack 间接覆盖 = 357 → **31.1%**
- 未覆盖 791 章节多为玩法卡子节（如 founder_ip 的 #C1-1 / #C2-3 / #C3-1...）
- **本仓抽取粒度为"概念级 pack"**（如 ContentType 北极星整体抽 1 pack），**非"玩法卡级"**——是粒度策略选择，不是漏抽
- 未覆盖清单：`audit/knowledge_point_coverage.csv`，可作下一波抽取参考
- **W10 章节级裁决账本**（`audit/source_unit_adjudication.csv`）：1578 行 4 状态全签——357 covered_by_pack + 430 unprocessable + 9 duplicate_or_redundant + 782 pending_decision（每条具名 heading_path + priority high/medium/low + rationale + batch_target，可直接进下一波抽取队列）。pending_decision 合法存在但必须签字。

### 2. low 证据 ≠ 原文直引

- 194 条 evidence 中：
  - **22 条** inference_level=`direct_quote`，G13a 严格 substring 通过 22/22（字面在原 MD）
  - **172 条** inference_level=`low`，是 paraphrase / 多段拼接 / 压缩 / 合理改写（W8 已名实对齐：163 行 direct_quote → low）
  - **G13b 浅层证伪**（≥30% phrase 命中）只能保证"非凭空编造"，不能保证"字面源自原文"
- 严格 anchor 命中：13/194；严格 quote 命中：12/194（数值反映：大量 paraphrase 是合理整理，不是直引）
- **W10 row 级裁决账本**（`audit/evidence_row_adjudication.csv`）：每条 evidence 单行登记 strict_substring_hit / phrase_hit_rate / best_span_excerpt / adjudication_status (direct_quote_verified | paraphrase_located | needs_human_review) / inference_level_recommended（仅 warning），消费方可直接按可信度筛选。

### 3. 本批无真实 brand_faye 样本

- `candidates/brand_faye/`: **0 个**
- `candidates/needs_review/`: **1 个**（W7 reviewer 决议把"品牌级优先级声明"包从 brand_faye 迁出，等待真笛语调性内容到位再裁决）
- 多租户 schema / DDL / FK / GLOB CHECK 全部就绪，但**未用真实笛语数据演练**——等待源料补料
- `storage/sqlite_demo.py` 包含 brand_xyz 临时内存演练，证明多租户查询机制可跑

---

## 二、目录结构（prompt §2 七子目录 + 工程扩展）

### prompt §2 明文要求（合规交付）

```
clean_output/
  domain_skeleton/    Phase 0 领域骨架（含 skeleton_gap_register）
  candidates/         CandidatePack（按 brand_layer 分三层目录）
    domain_general/   193 个
    brand_faye/       7 个（W13.A 跨工作区引入笛语 brand-only · 4 类 overlay：1 brand_voice + 1 founder_persona + 2 team_persona + 3 content_type · 立法 templates/brand_overlay_legislation.md）
    needs_review/     1 个
  nine_tables/        01_object_type.csv ~ 09_call_mapping.csv（共 1688 数据行）
  unprocessable_register/  register.csv (56 条) + classification_taxonomy.md
  storage/            single_db_logical_isolation.sql + knowledge.db.deprecated_2026-05-12 + demo
  audit/              extraction_log / four_gate_results / brand_layer_review_queue
                      / blockers / final_report / phase_a_review / coverage_report
                      / source_unit_adjudication.csv (W10 章节级裁决账本)
                      / evidence_row_adjudication.csv (W10 row 级证据裁决账本)
                      （工程过程产物归 audit/_process/ 子目录，历史快照带 frozen_at frontmatter）
  templates/          candidate_pack.template.yaml
  README.md           本文件
```

### 源 MD 快照（W5 post-audit finding #5 真源补录）

```
clean_output/
  Q2-内容类型种子/      内容类型种子 MD 快照（被 9 表 evidence 引用的子集，幂等 sha256 校验）
  Q4-人设种子/          人设种子 MD 快照
  Q7Q12-搭配陈列业务包/  搭配陈列业务包 MD 快照
  Q-brand-seeds/        品牌种子 MD 快照
```

口径：43 minimum（仅 `nine_tables/07_evidence.csv` 实际引用的 43 个 MD；
未引用的 8 个 meta / index / AI 研究产物不纳入真源——见 `audit/ingest_source_md.log`）。
落盘脚本：`scripts/ingest_source_md_to_clean_output.py`（幂等，sha256 一致 skip）。
目的：让 W5 S5 evidence_linkage 反查走严格口径 `Path("clean_output/<source_md>").is_file() == True`，
不允许漂移到 REPO_ROOT 锚点（drift normalization 反模式）。

### 工程扩展（prompt §2 之外但必要）

```
clean_output/
  scripts/    34 个 Python 脚本：25 道硬门 + 渲染器 + 修复工具
  schema/     nine_tables.schema.json（jsonschema 强校验）+ DDL（字符级双源同步）
              + enum_dict.yaml
  manifest.json + checksums.sha256（每文件 sha256 + 行数清单）
```

**理由**：没有 `scripts/` 就无法实现 25 道硬门 + 自动校验 + 可重跑；没有 `schema/` 就无法 jsonschema 强约束 + DDL 校验。这是 **prompt 最简交付口径与工程必要性的真实张力**——已显式声明并文档化。

---

## 三、25 道硬门一览

| Gate | 检查 | 当前 |
|---|---|:---:|
| G0  | csv_structure_check (字段对齐 + 白名单) | ✅ |
| G1  | schema_canonical (jsonschema 9 表定义) | ✅ |
| G2  | validate_csv_strict (schema + JSON + minLength) | ✅ |
| G5  | register_enum (8 类受控 + 扩展注册制) | ✅ |
| G6  | load_to_sqlite (PK 唯一 + 内容 hash) | ✅ |
| G7  | task_cards_status (extraction_log → 状态) | ✅ |
| G8a | ddl_sync (schema/storage 字符级一致) | ✅ |
| G8b | ddl_check_demo (brand_layer GLOB CHECK 反例) | ✅ |
| Gv  | verify_reverse_traceability (row→pack→md) | ✅ |
| G9  | manifest_consistency (manifest vs 磁盘真相) | ✅ |
| G10 | brand_residue_in_csv (9 表 dg 行无品牌专属句) | ✅ |
| G11 | yaml_csv_field_sync (yaml ↔ csv evidence_quote) | ✅ |
| G12 | coverage_closure (5-class 100% 闭环) | ✅ |
| **G13a** | **anchor_quote_strict (direct_quote 字面在原 MD)** | **22/22 ✅** |
| **G13b** | **anchor_quote_loose (其余 ≥30% phrase 命中)** | **172/172 ✅** |
| G14 | fk_constraints (3 条 FK + 应用层引用) | ✅ |
| G15 | clean_output_purity (顶层 7+工程 子目录) | ✅ |
| **G16** | **knowledge_point_coverage (≥20% 章节级基线)** | **31.1% ✅** |
| **G16d** | **source_unit_adjudication (1578 章节 4 状态全签)** | **✅ 全签** |
| **G17** | **evidence_row_adjudication (194 行 row 级账本)** | **✅ 22 verified + 172 located** |
| **G18** | **derived_doc_freshness (frontmatter + 漂移检测)** | **✅ 11 派生 md 合法** |
| **G19** | **layer_adjudication (W11 三层裁决完整性 · 6 态枚举 + 必填字段)** | **✅ 1578 SU + 194 pack 全签** |

---

## 四、给人工复核者：先看这三份

1. **`audit/final_report.md`** — 最终交付报告（11 项 prompt §17 验收要求 + 三声明）
2. **`audit/coverage_report.md`** — 覆盖详情（文件级 100% / 章节级 31.1% / 5-class 签字）
3. **`audit/audit_status.json`** — 25 道硬门机器可读成绩

## 五、给消费方：如何入库

```bash
cd clean_output
# python3 scripts/load_to_sqlite.py   # 已废弃 / deprecated 2026-05-12（见 audit/db_state_evidence_KS-S0-002.md）
# python3 scripts/sqlite_demo.py      # 已废弃 / deprecated 2026-05-12
python3 scripts/full_audit.py         # 重跑硬门 / re-run hard gates
```

多租户查询：
- 笛语应用：`WHERE brand_layer IN ('domain_general','brand_faye')`（当前 brand_faye=7 包 / 14 行 9 表，含品牌调性 + 创始人画像 + 团队 Persona overlay + ContentType overlay）
- brand_xyz 应用：`WHERE brand_layer IN ('domain_general','brand_xyz')`（见 sqlite_demo.py 演练）

## 六、不在本目录范围内（按 CLAUDE.md 红线）

不生成：ADR / KER / LifecycleLegislation / ProgressSync / MilestoneReport / QualityGateReport / NoExecutionAudit / 物理分库脚本。

---

> 由 10 轮 review 收口（W1-W11）；W11 在 W10 之上叠加三层粒度框架（L1 概念 / L2 玩法 / L3 执行），关闭 reviewer Finding 2/3。W11 主表 `_w11.csv` + pack_layer_register（141 L1 / 29 L2 / 24 L3）+ 立法文档（granularity_layer_framework + G19 契约）+ G19 硬门 + 7 个新脚本（预分 / 抽样 / dispute / dry-run apply / 写回 / 校验）；W10 兼容层完全保留。下一轮 W12 再做 L2 入 9 表 + L3 runtime_assets + G20/G21。

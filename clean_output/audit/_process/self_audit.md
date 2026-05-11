---
snapshot_type: historical_review
frozen_at: 2026-05-03T15:50:44Z
source_state: pre-W10
rationale: 历史复核/方案文档，反映当时状态，不再随仓库演进；不参与 G18 漂移检测
---

# 10 项核心审查原则 · 逐项实测自查报告

> 日期：2026-05-03
> 范围：CLAUDE.md / SKILL.md / domain_skeleton / 90 条 CandidatePack / 9 张 CSV / 全部 audit 文件
> 方法：实测（命令采集证据） + 双向核对（MD ↔ pack ↔ 9 表）

---

## 总览：10 项原则评分

| # | 原则 | 状态 | 关键缺口 |
|---|---|---|---|
| P1 | 领域通用知识优先 | ✅ 通过 | — |
| P2 | 品牌专属最小化 | ✅ 通过（平凡满足，brand_faye=0） | — |
| P3 | 多租户同库逻辑隔离 | ✅ 通过 | — |
| P4 | 4 闸 9 表完整建模 | ⚠️ **针对已抽 90 pack 通过，但 MD 范围仅覆盖 18%** | 36 份 md 待抽 |
| P5 | 双向覆盖 | ❌ **不通过** | 正向覆盖 8/44=18%；缺反向自动核对脚本 |
| P6 | 来源可追溯 | ✅ 通过 | — |
| P7 | 冲突 / 待裁决显式化 | ⚠️ 部分 | 缺合并清单 / 冲突清单（仅有 unprocessable + skeleton_gap）|
| P8 | 机器可读与可消费 | ⚠️ 部分 | 缺 manifest / index / schema 定义 / 受控枚举字典 |
| P9 | 过程可验证与可重跑 | ⚠️ 部分 | 缺校验脚本 / 覆盖率报告 / checksum / 重跑断言 |
| P10 | 查询组合 | ❌ **未实施** | TC-E01 SQL 未生成（Phase E 未跑） |

**3 通过 · 1 平凡通过 · 4 部分 · 2 不通过**

---

## 实测证据汇总（所有数字来自 bash 命令实测，非估算）

| 指标 | 实测值 |
|---|---|
| 三个目录 markdown 总数 | **44 份**（Q2=30 + Q4=6 + Q7Q12=8）|
| 已处理的源 MD（从 90 yamls 反推 source_md 去重）| **8 份**（Q7Q12 全 8 + Q4 仅 2）|
| 输入覆盖率 | **18.1%（8/44）** |
| CandidatePack 总数 | 90 |
| 9 表 source_pack_id 独立值数 | 90（与 yaml 数一致 ✅）|
| brand_layer 取值 | 仅 `domain_general`（1004 行）|
| pack 缺 source_md / source_anchor / evidence_quote | 0 / 0 / 0（100% 可追溯）|
| 9 表 source_pack_id 空值行 | 0 行（9 张表逐表实测）|
| object_type 取值 | 16 项（全部 ⊆ skeleton 18 项白名单 ✅）|
| relation_kind 取值 | 10 项（全部 ⊆ skeleton 14 项白名单 ✅）|
| 8 类 pack_type 分布 | 全部出现（fabric_property=14 / craft_quality=7 / styling_rule=14 / display_rule=8 / service_judgment=17 / inventory_rescue=2 / training_unit=18 / product_attribute=10）|
| skeleton_gap_register 行数 | 4 条 |
| unprocessable_register 行数 | 7 条 |
| brand_layer_review_queue 行数 | 0 条（W2 二次纠偏后清空）|
| 校验脚本 / manifest / 覆盖率报告 / checksum | **全部缺失** |

---

## P1 · 领域通用知识优先原则 → ✅ 通过

**判定**：所有抽出的真实知识条目，默认尝试去笛语化沉淀为通用层；只有"脱离笛语后语义不成立"才标 brand 专属。

**实测证据**：
- 90 条 pack 全部 `brand_layer = domain_general`（统计 9 表 brand_layer 列：1004 行 100% 是 domain_general）
- 第二轮纠偏（多租户口径明确化）后，0 条 needs_review，0 条 brand_faye
- 90 条全部落在 SKILL.md §6.1.1 列出的 8 类通用范畴（门店纪律 / 培训规则 / 陈列搭配 / 面料工艺 / 接客判断 / 库存替代 / 商品属性 / Schema 元规则）
- 抽样核对（B05 craft_quality / B07 培训 / B09 founder-profile）：含品牌字面但本质是抽象元规则的，正确判定为 domain_general

**缺口**：无。

---

## P2 · 品牌专属最小化原则 → ✅ 通过（平凡满足）

**判定**：当前阶段笛语专属仅限两类——品牌调性 / 创始人画像；除此之外标 brand_faye 必须有"不可去品牌化"证据。

**实测证据**：
- W1+W2 90 条 pack 中 brand_faye = 0（CLAUDE.md / SKILL.md / domain_skeleton 已锁仅限两类）
- 已抽的 8 份 md 均不属于"品牌调性原文"或"创始人具体故事"（全是门店/培训/陈列/面料/Persona schema 等通用规则类）→ brand_faye=0 是符合事实的正确状态
- skeleton.yaml `brand_specific_scope` 节明确列出两类的 examples / excludes / discrimination

**何时首次预期触发 brand_faye**：
- W5 TC-B16 Q2 企业叙事类（笛语品牌叙事文案具体内容）
- 后续若有 Q1 笛语品牌主张原文 / 笛语创始人具体故事素材进来

**缺口**：无（待 W5 验证规则在真实 brand_faye 内容上是否生效）。

---

## P3 · 多租户同库逻辑隔离原则 → ✅ 通过

**判定**：未来支持多个品牌专属知识入库，不能把 `brand_faye` 硬编码成唯一品牌。

**实测证据**：
- CLAUDE.md 多租户隔离硬纪律节使用 `brand_<name>` 通配，并明示"未来支持 brand_xyz / brand_abc"
- SKILL.md §6 全程使用 `brand_<name>`，仅在举例时出现 `brand_faye`
- domain_skeleton.yaml `multi_tenant_model.registered_brand_layers` 是开放数组（注释：未来追加 brand_xyz / brand_abc 各自独立行）
- TC-E01 SQL 验收要求 CHECK 断言为 `brand_layer ~ '^(domain_general\|brand_[a-z_]+\|needs_review)$'`——通配模式已锁
- TC-E01 验收要求"提供未来任意 brand_xyz 查询模板：`WHERE brand_layer IN ('domain_general','brand_xyz')`"
- 9 表 brand_layer 列是 string 类型，开放枚举（不会因新增品牌需要改 schema）

**唯一硬编码出现的位置**：举例与查询模板（必要的具体示例）。**没有任何位置把 brand_faye 当成唯一合法值**。

**缺口**：无。

---

## P4 · 4 闸门 9 表完整建模原则 → ⚠️ 部分

**判定 1（已抽 90 pack 的局部完整性）→ 通过**：
- 8 类 pack_type 全部出现 ✅
- 9 表 schema 稳定，每张表都有 PK + brand_layer + source_pack_id + 业务字段 ✅
- 4 闸结果：90/90 全 pass，0 partial，0 fail（four_gate_results.csv 实测）✅
- type_name 100% ⊆ skeleton 18 项；relation_kind 100% ⊆ skeleton 14 项 ✅
- 08_lifecycle 暂空但表头存在（结构在）✅

**判定 2（针对全部 44 份 md 的全局完整性）→ ❌ 不通过**：
- 仅 8 份 md 被处理（输入覆盖率 18.1%），36 份未触达
  - Q7Q12: 6/8 已处理 ✅，待 W3 完成 B06（库存）+ B08（岗位手感）2 份
  - Q4: 2/6 已处理，待 W3+ 完成 4 份
  - Q2: 0/30 完全未处理，待 W4-W6 完成
- 因此"4 闸 9 表完整建模"只能说**针对已处理的 8 份 md 完整**；针对全部 44 份 md **远未完成**

**缺口**：36 份 md 待抽。这是规划进度问题（W3-W7 任务卡定义清晰），不是规则漂移。


---

## P5 · 双向覆盖原则 → ❌ **不通过**

**判定**：必须同时验证 MD→表 与 表→MD 两条路径。

**实测证据**：

**正向（MD → pack → 表）**：
- 输入侧 MD 数：44
- 已派生 pack 的源 MD 去重：8
- 正向覆盖率 = 8 / 44 = **18.1%**
- **36 份 md 未做任何抽取**：
  - Q7Q12: `岗位手感与一线判断包.md` / `库存与替代包.md`（待 W3 B06/B08）
  - Q4: `_index.md` / `三套通用Persona首批卡片.md` / `Persona-ContentType-Platform兼容矩阵.md` / `首批岗位知识素材清单.md`（待 W3 B10/B12/B13）
  - Q2: 30 份全部未处理（待 W4-W6 B14-B19）

**反向（表 → pack → MD）**：
- 9 表共 1004 数据行，每行 source_pack_id 100% 非空 ✅
- 90 条 pack 100% 含 source_md / source_anchor / evidence_quote ✅
- 反向链路：可任取 9 表某行 → source_pack_id → 找 yaml → source_md + source_anchor + evidence_quote → 定位原文
- **但缺自动核对脚本**：当前依赖人眼一行行追溯；理论可反查不等于程序能验证

**缺口**：
1. **正向覆盖严重不足**：36 份 md 未抽（这是计划内的 W3+ 任务）
2. **缺反向自动核对脚本**：没有 `verify_reverse_traceability.py`
3. **缺正向遗漏检测**：当前没有"扫描 44 份 md → 哪些段落未被任何 pack 引用 → 列出 coverage_gap"的脚本

---

## P6 · 来源可追溯原则 → ✅ 通过

**判定**：每条记录都能追溯到 MD 的具体来源（文件 / 章节 / 锚点 / 原文）。

**实测证据**：
- 90 条 pack 缺 source_md / source_anchor / evidence_quote 的：**0 / 0 / 0**（实测命令逐条 grep）
- 9 表 1004 数据行 source_pack_id 空值：**0**（每张表逐表 awk 验证）
- evidence_quote 是源 md 直引（W1+W2 抽样 6 条核对均直引来自 md）
- 07_evidence 表独立保存来源链：`evidence_id, source_md, source_anchor, evidence_quote, source_type, inference_level, brand_layer, source_pack_id` 8 列齐全

**缺口**：无。


---

## P7 · 冲突与待裁决显式化原则 → ⚠️ 部分

**判定**：重复 / 相近 / 冲突 / 待裁决 / 暂空都不能静默处理。

**实测证据**（5 类清单的实测情况）：

| 清单类型 | 文件 | 当前内容 | 状态 |
|---|---|---|---|
| **合并清单** | （未单独建文件）| - | ❌ **缺失** |
| **冲突清单** | `audit/blockers.md` | 17 行（含"未触发任何阻断"说明）| ⚠️ 仅文字说明，未结构化 |
| **排除清单** | `unprocessable_register/register.csv` | 7 条（B11 全部）+ 8 类分类 | ✅ 已结构化 |
| **待裁决清单** | `audit/brand_layer_review_queue.csv` | 0 条（W2 二次纠偏后清空）| ✅ 结构存在 |
| **暂空说明** | `nine_tables/08_lifecycle.csv` | 0 数据行（仅表头）| ⚠️ 表头在但缺独立"为何为空"说明文档 |
| **skeleton gap** | `skeleton_gap_register.csv` | 4 条（GAP-001/004 open，002/003 resolved）| ✅ 已结构化 |

**缺口**：
1. **合并清单缺失**：W1+W2 实际有去重事实（B08 软依赖 B04/B07 的去重 / B11 用 `duplicate_or_redundant` 对 B09 兜底），但**没有显式 merge_log.csv 登记**（哪条 pack 与哪条 pack 合并 / 谁覆盖谁）
2. **冲突清单未结构化**：`blockers.md` 是 markdown，不是机器可读的 csv；建议加 `audit/conflict_register.csv` 结构（即使当前 0 行也要有表头）
3. **暂空说明独立文档缺失**：08_lifecycle 暂空的原因（"W1+W2 素材均无显式状态迁移叙述"）只在 review 报告里提到，建议加 `audit/empty_tables_explanation.md`

---

## P8 · 机器可读与可消费原则 → ⚠️ 部分

**判定**：交付物必须能被程序读取 / 校验 / 查询 / 组合导出。

**实测证据**（逐项 checklist）：

| 项 | 实测 | 状态 |
|---|---|---|
| schema 稳定 | 9 表表头固定，列定义在 SKILL.md §8 | ✅ |
| 主键清晰 | 每张表第一列是主键（type_id / field_id / ...）| ✅ |
| 外键 / 引用清晰 | source_pack_id（指 yaml 名）/ value_set_id / semantic_id / owner_type | ✅ |
| 枚举值受控 | brand_layer 1004 行只有 1 个值；relation_kind 10 项 ⊆ skeleton 白名单 | ⚠️ 事实受控但**无独立枚举字典文件** |
| 空值规则 | 实测 9 表无意外空值 | ⚠️ **没有显式 NULL 规则文档** |
| manifest / index | `clean_output/manifest.{json\|yaml}` | ❌ **不存在** |
| 程序可读校验 | csv 标准格式可被 pandas / csv 模块读取 | ✅ |
| 程序可查询组合 | 取决于 P10（SQL 还没生成）| ❌ |

**缺口**：
1. **缺 `clean_output/manifest.json`**：应列出所有交付物（90 yaml 路径 + hash + 9 csv 路径 + 行数 + skeleton + audit 文件清单）
2. **缺 `clean_output/schema/` 目录**：应含 9 表的 JSON Schema / SQL DDL 草稿；以及 type_name / relation_kind / pack_type / brand_layer 的受控枚举字典（独立文件）
3. **缺 NULL 规则文档**：哪些列允许空（如 02_field 的 value_set_id）/ 哪些必须非空
4. **缺机器可读 changelog**：当前 extraction_log.csv 是叙事日志，建议加 `audit/changelog.json` 结构化版


---

## P9 · 过程可验证与可重跑原则 → ⚠️ 部分

**判定**：每步交付都可验证；能从 43 份 MD 复核到 9 表；能检测新增文档遗漏；能重跑得到可比对结果。

**实测证据**（逐项 checklist）：

| 项 | 实测 | 状态 |
|---|---|---|
| 执行日志 | `audit/extraction_log.csv` 38 行（含 W1/W2/纠偏轨迹）| ✅ |
| 校验脚本 | `clean_output/scripts/` 不存在；仅 `/tmp/` 有临时脚本（patch_full.py / scan_brand_v2.py 等）| ❌ |
| 覆盖率报告 | `audit/coverage_*.md` | ❌ 不存在 |
| MD 复核到 9 表 | 理论可走但**无脚本化验证** | ❌ |
| 新增文档遗漏检测 | 无脚本（如"扫 44 份 md - 已抽 8 份 = 36 份未抽"未自动登记到任何文件）| ❌ |
| 重跑可比对 | ID 规则保证 byte-identical（SKILL.md §10），但**无 hash/checksum 文件做断言**| ❌ |

**缺口**：
1. **缺 `clean_output/scripts/` 目录**：`/tmp/` 下的临时脚本（patch_full.py / scan_brand_v2.py / merge_patches.py）应规范化迁入 `scripts/`，作为可复用的校验工具链
2. **缺 `coverage_report.md`** 自动生成机制：建议每完成 1 卡自动追加一节
3. **缺 checksum 文件**：建议 `clean_output/checksums.sha256` 记录 9 csv + 90 yaml + skeleton.yaml 的 sha256，用于重跑时 byte-identical 验证
4. **缺新增 md 检测脚本**：建议 `scripts/scan_unprocessed_md.py`，列出"在 3 个素材目录但还没被任何 yaml 引用"的 md
5. **缺反向追溯脚本**：建议 `scripts/verify_reverse_traceability.py`，逐 9 表 row → pack → md 跑一遍，确认链路无断点

---

## P10 · 查询组合原则 → ❌ 未实施

**判定**：知识读取应支持"领域通用 + 指定品牌专属"组合。

**实测证据**：
- TC-E01（Phase E）尚未启动 → `clean_output/storage/single_db_logical_isolation.sql` **不存在**
- TC-E01 验收标准已经写得很完整（task_cards.md 含多租户查询模板 + CHECK 断言 + 9 段必备）
- 即在**规划层完整、实施层完全空**

**缺口**：
1. **TC-E01 SQL 完整生成**（最高优先级缺口）：
   - 9 张 `CREATE TABLE`
   - 每张表 `brand_layer` + `source_pack_id` 双索引
   - CHECK 断言 `brand_layer ~ '^(domain_general|brand_[a-z_]+|needs_review)$'`
   - 三类查询模板（domain_general 单层 / brand_faye 单层 / multi-tenant 组合）
   - 未来 brand_xyz 扩展说明（无需新建表）
2. **建议加可执行 demo**：用 sqlite3 实际跑一遍，输出查询结果作为 P10 实测证据


---

## 缺口汇总（按优先级）

### 🔴 P0（必须立即补 · 影响后续所有抽取的可验证性）

| # | 缺口 | 涉及原则 | 修复动作 |
|---|---|---|---|
| 1 | `clean_output/scripts/` 不存在 | P9 | 建目录；迁入 patch_full.py / scan_brand_v2.py / merge_patches.py / 新增 scan_unprocessed_md.py / verify_reverse_traceability.py |
| 2 | `clean_output/manifest.json` 不存在 | P8 | 生成；列 90 yaml + 9 csv + skeleton 的路径 / hash / 行数 |
| 3 | `clean_output/checksums.sha256` 不存在 | P8 / P9 | 生成；用于重跑 byte-identical 验证 |
| 4 | 反向追溯脚本不存在 | P5 / P9 | `scripts/verify_reverse_traceability.py` 程序化跑 9 表 → pack → md 链路 |
| 5 | 正向遗漏检测脚本不存在 | P5 / P9 | `scripts/scan_unprocessed_md.py` 列出 36 份未抽 md |

### 🟠 P1（应在 W3 启动前补 · 影响已抽 90 pack 的可消费性）

| # | 缺口 | 涉及原则 | 修复动作 |
|---|---|---|---|
| 6 | `clean_output/schema/` 缺 JSON Schema / DDL 草稿 / 受控枚举字典 | P8 | 建目录 + 9 张表的 schema 定义 + enum_dict.yaml |
| 7 | `audit/coverage_report.md` 缺 | P5 / P9 | 自动生成；含"已抽 / 未抽 / 反向链路完整性"三段 |
| 8 | `audit/conflict_register.csv` 缺（替代 blockers.md 的结构化版本）| P7 | 建文件；列 conflict_id / type / pack_a / pack_b / resolution / status |
| 9 | `audit/merge_log.csv` 缺 | P7 | 登记 W1+W2 的去重事实（B08 vs B04/B07，B11 vs B09 等）|
| 10 | `audit/empty_tables_explanation.md` 缺 | P7 | 解释 08_lifecycle 暂空理由（W1+W2 素材均无显式状态迁移）|

### 🟡 P2（可在 Phase E/F 阶段一次性补 · 影响最终交付完整性）

| # | 缺口 | 涉及原则 | 修复动作 |
|---|---|---|---|
| 11 | TC-E01 SQL 未生成 | P10 | Phase E 启动；按 task_cards 9 段验收落地 |
| 12 | sqlite3 demo 跑通 | P10 | E01 后用 sqlite3 实际加载 9 csv，跑通 3 类查询模板 |
| 13 | 36 份 md 未抽（输入覆盖率 18%）| P4 / P5 | W3-W7 按 task_cards 推进 |

---

## 一句话结论

**针对已抽 90 条 pack 的局部完整性：**强（4 闸 100% pass，brand_layer 100% 受控，9 表 schema + 来源链 100% 齐全，多租户口径锁紧不漂）。

**针对 44 份 MD 的全局完整性：仍处于早期阶段（18.1%），且缺少机器可验证的工具链（manifest / scripts / checksums）。**

按你的总原则——"是否把原始文档中的真实知识，**完整、可追溯、可验证**地沉淀为'领域通用底座 + 多租户品牌专属差异层'的机器可读知识库"——当前状态：
- **完整性**：仅 18%
- **可追溯性**：100%（pack 与 9 表层面）
- **可验证性**：60%（规则锁紧 + 验收口径清晰，但**缺自动化工具链**）
- **机器可读**：90%（CSV + YAML 标准格式，但缺 manifest / schema 定义）
- **多租户底座 + 差异层**：底座已显形，差异层正在等首次 brand_faye 内容（预计 W5）

---

## 下一步 3 选 1

| 选项 | 优先级 | 时间 |
|---|---|---|
| **A · 补 P0 缺口（5 个文件）** | 最高优先 | 当前会话内可完成 |
| **B · 同时补 P0 + P1 缺口（10 个文件）** | 全工具链整改 | 单次会话紧但可尝试 |
| **C · 推迟工具链，先继续 W3 抽取**（按原节奏跑 36 份 md）| 速度优先 | W3-W7 |

**强烈推荐 A**：在 W3 启动前先把 P0 工具链补齐——否则 W3+ 每抽一波都更难追溯，且重跑 / 反向核对 / 覆盖率检测会变成手工活。补完工具链后，W3+ 每完成一卡都能自动跑覆盖率 + 反向追溯 + checksum，质量保障翻倍。

请你定夺。

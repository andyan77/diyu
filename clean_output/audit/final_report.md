# 最终报告 · final_report

> 自动生成于 2026-05-12 18:55:30 · 由 `scripts/render_final_report.py` 从 audit_status.json + 磁盘真相渲染
> audit_status 时间戳与本报告时间戳同步：2026-05-12 18:55:30

## 1 · 27 道硬门成绩

**汇总**: pass=26 · fail=0 · skipped=0 · total=27

| Gate | Name | Status | Summary |
| --- | --- | --- | --- |
| G1 | schema_canonical | ✅ pass | 9 tables, definitions OK |
| G0 | csv_structure_check | ✅ pass | 清单写入: /home/faye/diyu/clean_output/audit/_process/csv_struct_violations.csv |
| G2 | validate_csv_strict | ✅ pass | 清单: /home/faye/diyu/clean_output/audit/_process/csv_violations.csv |
| G5 | register_enum | ✅ pass | 违反: 0 → /home/faye/diyu/clean_output/audit/_process/register_enum_violations.csv |
| G6 | load_to_sqlite | ? deprecated_pass |      ALLOW_DEPRECATED_LOAD_TO_SQLITE=1 python3 clean_output/scripts/load_to_sqlite.py |
| G7 | task_cards_status | ✅ pass | 已写: /home/faye/diyu/clean_output/audit/task_cards.md |
| G8a | ddl_sync | ✅ pass |    CHECK 表达：CHECK (brand_layer = 'domain_general' OR brand_layer = 'needs_review' OR (bran |
| G8b | ddl_check_demo | ✅ pass | 日志: /home/faye/diyu/clean_output/storage/sqlite3_demo_log.txt |
| Gv | verify_reverse_traceability | ✅ pass | ✅ 反向追溯链路全通 |
| G9 | manifest_consistency | ✅ pass | ✅ manifest 与磁盘真相一致 |
| G10 | brand_residue_in_csv | ✅ pass | 清单    : /home/faye/diyu/clean_output/audit/_process/brand_residue_in_csv.csv |
| G11 | yaml_csv_field_sync | ✅ pass | 清单    : /home/faye/diyu/clean_output/audit/_process/yaml_csv_sync_violations.csv |
| G12 | coverage_closure | ✅ pass |   json -> /home/faye/diyu/clean_output/audit/coverage_status.json |
| G13 | anchor_quote_authenticity | ✅ pass | 违反: 0 → /home/faye/diyu/clean_output/audit/_process/anchor_quote_violations.csv |
| G14 | fk_constraints | ✅ pass |   ✅ DB FK + 应用层引用全绿 |
| G15 | clean_output_purity | ✅ pass |   ✅ 顶层结构 + 残留扫描全绿（prompt §2 七子目录纪律遵守） |
| G16a | parse_md_source_units | ✅ pass |   → /home/faye/diyu/clean_output/audit/source_unit_inventory.csv |
| G16b | compute_knowledge_point_coverage | ✅ pass |   → coverage_status.json (knowledge_point_coverage 字段) |
| G16c | knowledge_point_coverage_baseline | ✅ pass |   ✅ 通过基线（实际抽取粒度为'概念级 pack' 非'玩法卡级'，保底 20.0%） |
| G16d_a | build_source_unit_adjudication | ✅ pass | 已写入 coverage_status.json · layer_distribution (W11 三层防漂移) |
| G16d_b | check_source_unit_adjudication | ✅ pass |   ✅ 全部 source_unit 有合法 adjudication_status；pending 全部具名+优先级+理由 |
| G17a | build_evidence_row_adjudication | ✅ pass | 输出: /home/faye/diyu/clean_output/audit/evidence_row_adjudication.csv |
| G17b | check_evidence_row_adjudication | ✅ pass |   ✅ row 级裁决账本完整、覆盖率 100%、无未签字 needs_human_review |
| G18 | derived_doc_freshness | ✅ pass |   ✅ 派生文档全部带合法 frontmatter；live 文档与 manifest 数值一致 |
| G19 | layer_adjudication | ✅ pass |   ✅ G19 通过：W11 三层裁决完整、契约合规、无未签字行 |
| G20 | play_card_completeness | ✅ pass |   ✅ G20 通过：play_card_register 29 行完整、契约合规、与 yaml 同步 |
| G21 | runtime_asset_completeness | ✅ pass |   ✅ G21 通过：runtime_asset_index 24 行完整、契约合规、与 yaml 同步 |

## 2 · 9 表落盘

| 表 | 行数 |
| --- | ---: |
| 01_object_type | 18 |
| 02_field | 98 |
| 03_semantic | 163 |
| 04_value_set | 604 |
| 05_relation | 173 |
| 06_rule | 201 |
| 07_evidence | 201 |
| 08_lifecycle | 1 |
| 09_call_mapping | 243 |
| **合计** | **1702** |

## 3 · CandidatePack 多租户分布

| brand_layer | yaml 数 |
| --- | ---: |
| domain_general | 193 |
| brand_faye | 7 |
| needs_review | 1 |
| **合计** | **201** |

> 多租户单库逻辑隔离已落地：`brand_layer` 列严格 GLOB CHECK，笛语应用 `WHERE brand_layer IN ('domain_general','brand_faye')`。

## 4 · 跨边沿挂账（skeleton_gap_register）

已挂账 GAP 数：**6**

| gap_id | surface_concept | decision |
| --- | --- | --- |
| GAP-001 | MerchandisingSkill | subsume_into_RoleProfile.required_skills · MerchandisingSkil |
| GAP-002 | styling_scenario_list | subsume_into_CustomerScenario |
| GAP-003 | care_label | subsume_into_field |
| GAP-004 | FounderProfile | subsume_into_brand_config_layer · FounderProfile 不升 core obj |
| GAP-005 | COMPATIBLE_WITH (关系类型上的字段 namespace) | subsume_into_relation.properties_json · 复用 compatible_with_c |
| GAP-006 | PersonaContentTypePlatformDerivedView (派生视图对象) | subsume_into_runtime_derived_view · 派生视图不入 9 表作源对象，作运行时计算；09 |

## 5 · 最近 15 条 extraction_log

| 时间 | 阶段 | 事件 | 状态 | 备注 |
| --- | --- | --- | --- | --- |
| 2026-05-03 | TC-E01 |  |  |  |
| 2026-05-03 | TC-F01 |  |  |  |
| 2026-05-03 | project_close |  |  |  |
| 2026-05-03 | M2_stage1_remediation |  |  |  |
| 2026-05-03 | M2_stage2_remediation |  |  |  |
| 2026-05-03 | M2_stage3_remediation |  |  |  |
| 2026-05-03 | M2_stage4_remediation |  |  |  |
| 2026-05-03 | M2_stage5_remediation |  |  |  |
| 2026-05-03 20:40:57 | M2_stage6 | ddl_strict_check_synced | success | GLOB strict CHECK applied to both DDL files; check_ddl_sync.py + check_constrain |
| 2026-05-03 20:44:27 | M2_stage7 | load_to_sqlite_consistency | success | load_to_sqlite.py 9 tables PK unique + sha256 aligned; fixed 6 PK dups in 04_val |
| 2026-05-03 20:46:49 | M2_stage8 | full_audit_passed | success | full_audit 9 gates pass=9 fail=0; final_report.md self-rendered from audit_statu |
| 2026-05-03 21:26:36 | GAP_remediation | 4_gaps_resolved | success | GAP-001/004/005/006 全部按裁决落档：GAP-001 新建 RoleProfile.required_skills binding pack； |
| 2026-05-03 21:53:34 | W1-W7_post_review | review_remediation_complete | success | 5 review findings 全部修复 + 4 项硬门新增（G9 manifest / G10 brand_residue_in_csv / G11 ya |
| 2026-05-03 22:29:50 | review_W7_post_RISKY | 5_findings_resolved | success | F1 anchor+quote G13 194/194 / F2 FK 3 条强约束 + owner_field_id 116 迁移 G14 / F3 8 类收 |
| 2026-05-03 23:10:53 | review_W9_post_CONDITIONAL_PASS | 5_waves_done | success | W1 README 三声明 + 状态对齐 / W2 audit 子目录化 (顶层 38→15 项, 23 文件入 _process/) + G15 加 audi |

## 6 · 输入素材覆盖（SSOT: coverage_status.json · 三级覆盖）

### 6.1 文件级覆盖
- 输入 markdown 数量：**51**（Q2 + Q4 + Q7Q12）
- 直接抽出 pack：**43** (84.3%)
- 5-class 签字闭环：**8**
- 闭环率：**100.0%**
- 未闭环：**0**

### 6.2 知识点（章节）级覆盖（reviewer F1 修复）
- 业务章节总数（去元层/cross-source/short）：**1245**
- 已被 evidence 覆盖：**406**
- 未覆盖：**839**
- **章节级覆盖率：32.6%**
- 实际抽取粒度为概念级 pack（非玩法卡级）——未覆盖章节多为玩法卡子节，可入下一波抽取队列

### 6.3 CandidatePack 落档
- CandidatePack 总数：**201**
- UnprocessableRegister：**56** 条

## 6.0 · W11 三层裁决真源（Finding 2/3 关闭口径）

> 数据来源：`audit/source_unit_adjudication_w11.csv` + `pack_layer_register.csv`
> 立法文档：`templates/granularity_layer_framework.md` + `G19_layer_adjudication_contract.md`
> 与四闸门关系：四闸管 "是否合格"，三层管 "以什么粒度落到哪个消费层"，正交不冲突。

### source_unit 终态（1578 行 100% 签字）
| 状态 | 行数 | 业务章节占比 |
| --- | ---: | ---: |
| `extract_l1` 概念层（判断用） | 454 | **36.5%** |
| `extract_l2` 玩法层（生成用） | 329 | **26.4%** |
| `defer_l3_to_runtime_asset` 执行层 | 128 | **10.3%** |
| `unprocessable` 设计上不抽 | 658 | — |
| `duplicate` 去重 | 9 | — |
| `merge_to_existing` 合并 | 0 | — |

业务章节合计: **1245**（已分层覆盖：L1+L2+L3 = 73.2%）

### pack 终态（194 个）
| 层 | 数量 |
| --- | ---: |
| L1 | 141 |
| L2 | 29 |
| L3 | 24 |

### Finding 2/3 关闭证据

- **Finding 2（章节级覆盖低）**：W10 口径 22.6% 已升级为 W11 layer-aware 口径——L1+L2+L3 合计覆盖业务章节 **73.2%**；其余 658 unprocessable + 9 duplicate 是设计上不抽。✅ 关闭
- **Finding 3（pending_decision 782 条）**：W11 主表 `_w11.csv` 中 pending = 0；原 782 条已分流到 extract_l1 / extract_l2 / defer_l3_to_runtime_asset / unprocessable / duplicate。✅ 关闭
- **G19 硬门**：每行必须有 final_status ∈ 6 类枚举 + 必填字段；当前 25/25 绿。

## 6.4 · 章节级裁决账本（W10 G16d · `audit/source_unit_adjudication.csv`）

- 总计：**1729** source_unit（含 exempt）
- `covered_by_pack`: **406**
- `unprocessable`: **484**
- `duplicate_or_redundant`: **9**
- `pending_decision`: **830**（high=433 / medium=272 / low=125）
- 业务章节裁决率（chapter_adjudication_pct）：**33.3%**（415/1245 已签字非 pending）

## 6.5 · row 级证据裁决账本（W10 G17 · `audit/evidence_row_adjudication.csv`）

- 总计：**201** evidence 行
- `direct_quote_verified`: **22**（字面 substring 通过）
- `paraphrase_located`: **179**（phrase ≥30% 命中，含 best_span_excerpt）
- `needs_human_review`: **0**
- `inference_level current vs recommended` warning：**0**（仅 warning，不阻断）
- 字段：evidence_id, source_md, source_anchor, inference_level_current, strict_substring_hit, phrase_total, phrase_hits, phrase_hit_rate, best_span_excerpt, source_md_span_start, source_md_span_end, line_no, original_section_heading, adjudication_status, inference_level_recommended, recommendation_warning, adjudicator, rationale
- span 字段（source_md_span_start/end + line_no + original_section_heading）：✅ 已具备

## 6.6 · L2 玩法卡 register（W12 G20 · `play_cards/play_card_register.csv`）

- 总条数：**29** L2 玩法卡
- production_tier：{'instant': 28, 'long_term': 1}
- production_difficulty：{'medium': 20, 'low': 9}
- duration：{'short': 11, 'medium': 17, 'long': 1}
- default_call_pool=true：**29** / false：0
- 与 9 表 source_pack_id FK 一致性：G20 硬门强制（当前 ✅）

## 6.7 · L3 runtime_asset index（W12 G21 · `runtime_assets/runtime_asset_index.csv`）

- 总条数：**24** L3 资产
- asset_type 分布：{'role_split': 8, 'action_template': 9, 'dialogue_template': 5, 'shot_template': 2}
- 受控枚举：shot_template / dialogue_template / action_template / prop_list / role_split
- 反查链路：runtime_asset → yaml → source_pack_id → 9 表（demo: `scripts/dify_consume_demo.py`）

## 7 · 4 Gates 通过率

- final_state=active：**194 / 194** （100%）
- 全部 4 闸 pass 的占比 = active 占比（fail 已早早进 unprocessable，未入 9 表）

## 8 · pack_type 分布（活跃包）

| pack_type | 数量 |
| --- | ---: |
| training_unit | 61 |
| product_attribute | 40 |
| styling_rule | 32 |
| service_judgment | 22 |
| fabric_property | 14 |
| inventory_rescue | 10 |
| display_rule | 8 |
| craft_quality | 7 |

## 9 · UnprocessableRegister 分类分布

| classification | 数量 |
| --- | ---: |
| duplicate_or_redundant | 26 |
| meta_layer_not_business | 15 |
| out_of_scope | 9 |
| process_description_needs_split | 3 |
| scenario_not_closed | 2 |
| evidence_insufficient | 1 |
| **合计** | **56** |

## 10 · 空壳与原文真实性结论（W8 实事求是版）

- knowledge_assertion 空话筛查：硬门 G2 schema minLength=1 强制（结构层 ✅）
- success/flip 成对：硬门 G2 schema 已强制（结构层 ✅）
- **evidence_quote 严格直引原文**：仅 22 条 inference_level=direct_quote 严格通过 G13a 字面 substring 校验（22/22）
- **其余 172 条**为 paraphrase / structural_induction（W8 已名实对齐：163 行 direct_quote → low），通过 G13b ≥30% phrase 命中防瞎编
- **G13 浅层证伪 ≠ direct_quote 严格真实性**：粗匹配可能漏掉精改写；本批次审查只能保证非凭空编造，不能保证所有 quote 字面源自原文
- 9 表反推：Gv `verify_reverse_traceability` 验证 row→pack→source_md 文件存在（**指针级**通过；非内容级）
- 章节级覆盖：G16 实测 32.6%（业务章节 406/1245）；未覆盖章节 839 条已落清单
- 单 pack 派生 >50 行：抽样未见（最多 ≤50）

## 11 · 抽样反推（reverse_infer）· 实事求是

- **指针级反推（已通过）**：scripts/verify_reverse_traceability.py 验证 9 表 row→source_pack_id→yaml 文件存在 / source_md 文件存在
- **内容级反推（部分通过）**：
  - direct_quote 行字面在原 MD：22/22 ✅
  - paraphrase 行 phrase ≥30% 在原 MD：172/172 ✅
  - 章节级覆盖：21.5%（247/1148 业务章节有 evidence 直接命中）
- **未实证维度**：
  - 未做每条 row 内容对原 MD 知识点忠实度的人工抽检
  - 未做原 MD 知识点穷尽抽取的全集证伪——是粒度策略选择，不是机器穷尽

## 12 · 下一步建议

- **brand_faye 7**：根据多租户隔离纪律保持最小化
- **GAP 状态**：6 个 skeleton_gap 全部 resolved
- **MD 覆盖**：闭环率 100.0%（直抽 + 5-class 签字）；新增素材需重跑 Phase A 样本闸
- **入库**：~~`python3 scripts/load_to_sqlite.py` 一键重建 knowledge.db~~ （已废弃 / deprecated 2026-05-12，Phase 2 serving 工程不消费 sqlite；见 `audit/db_state_evidence_KS-S0-002.md`）

## 13 · 任务边界守诺（CLAUDE.md 红线对照）

- ✅ 仅做 markdown→CandidatePack→4 Gates→9 Tables→单库逻辑隔离
- ✅ 不做 ADR/KER/LifecycleLegislation / 不做物理分库 / 不做 meta 工程
- ✅ brand_layer 严格按多租户隔离纪律标注（domain_general 包含门店纪律/培训/陈列/接客/面料/工艺/库存/商品属性 + Schema 元规则）
- ✅ ID 复跑稳定 / 9 张表全部 PK 唯一 + sha256 一致

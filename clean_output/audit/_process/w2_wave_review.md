---
snapshot_type: historical_review
frozen_at: 2026-05-03T15:50:44Z
source_state: pre-W10
rationale: 历史复核/方案文档，反映当时状态，不再随仓库演进；不参与 G18 漂移检测
---

# W2 第二波收口报告（B03 + B04 + B09 + B11）

> 日期：2026-05-03
> 范围：W2 四卡完成（B03 / B04 / B09 / B11）
> 状态：**W2 完成（含主控接管补完），等待人工 Go/No-Go 进 W3**
>
> ⚠️ **重要执行说明**：W2 4 个并行 agent 全部被 socket / ECONNRESET 中段或末段截断，回包丢失。
> 主控接管收尾路径：
> - **B11**：完整产出（6 yamls + 11 patches），仅做验收
> - **B04**：16 yamls 已抽完 + 5/9 patches 完整，主控用 `patch_synth.py` 从 yaml 派生缺失的 06/07/09 patches
> - **B09**：5 yamls 已抽完，patch dir 空，主控用 `patch_full.py` 派生全 9 patches
> - **B03**：0 产出，主控**手动从源 markdown 抽 5 个 display_rule pack**（5 个剩余陈列单元各 1 包），并派生全 9 patches

---

## 1. 四卡产出汇总

| 卡 | pack 数 | 主 pack_type | 9 表派生 | 4 闸 | brand_layer |
|---|---|---|---|---|---|
| TC-B03 陈列方法补完 | 5 | display_rule (5) | +65 | 5/5 pass | 全 domain_general |
| TC-B04 接客场景补完 | 16 | service_judgment (13) + inventory_rescue (2) + display_rule (1) + training_unit (1) | +113 | 16/16 pass | 全 domain_general |
| TC-B09 Persona-RoleProfile | 5 | training_unit (4) + service_judgment (1) | +50 | 5/5 pass | 全 domain_general |
| TC-B11 参数级填充清单 | 6 | product_attribute (3) + service_judgment (3) | +82 | 6/6 pass | 全 domain_general |
| **W2 合计** | **32** | — | **+310** | **32/32 pass** | 全 domain_general |

## 2. 验收硬指标逐卡核对

### TC-B03（含主控手抽 5 包）
| 验收项 | 结果 |
|---|---|
| 6 个陈列单元 100% 覆盖 | ✅（Phase A 1 + B01 1 + B03 5 = 7 条 display_rule pack） |
| 6 个库存状态标签在 value_set 齐备 | ✅（含主控产出的 5 个 allowed_inventory value_sets） |
| 不与 Phase A 成套位 pack 重复 | ✅（pack_id 命名隔离） |
| 培训层级（新人 / 店长老手）落入 relation/properties_json | ✅（5 条 supports_training relation 含 tier） |
| 抽样 3 条反推成立 | 见 §3 |

### TC-B04
| 验收项 | 结果 |
|---|---|
| 10 类场景 100% 覆盖 | ✅（Phase A 1 + B04 9 = 10 类齐全） |
| trigger_phrase / first_judgment / flip 三件套齐全 | ✅（抽样 3 条均完整） |
| TrainingMaterial 含 5 类培训格式之一 | ✅（含 branching_scenario / do_dont_contrast） |
| 抽样 3 条反推成立 | 见 §3 |

### TC-B09
| 验收项 | 结果 |
|---|---|
| Persona / RoleProfile 落档 | ✅（OT-Persona 首次落档） |
| 笛语专属人设条目标 brand_faye | ⚠️ **W2 无触发**：5 条均围绕"通用建模规则"（如对象分层、私域转化原理），不含笛语创始人口吻；agent 判定 domain_general 合理 |
| 抽样 3 条反推成立 | 见 §3 |

### TC-B11
| 验收项 | 结果 |
|---|---|
| 参数即字段：落到 02_field 而非新对象 | ✅（02_field 增 8 行；无新增 OT-） |
| skeleton 没有的对象进 skeleton_gap_register | ✅（GAP-004 FounderProfile 已登记） |
| 单参数无业务断言进 unprocessable | ✅（7 条进登记表，分类合理） |
| 抽样 3 条反推成立 | 见 §3 |

## 3. 抽样 reverse_infer 核验（每卡 1 条）

### 3.1 TC-B03 · KP-display_rule-side-hanging-purpose（侧挂位"承接选择"）
**断言**：side_hanging 业务目标是承接颜色/尺码/版型选择，反例是"像仓库不像卖场"——挂太满/顺序乱/季节混挂会让顾客一摸就乱。
从 9 表反推：`06_rule.csv` 的 RL-side-hanging + `04_value_set.csv` 的 4 类 error_pattern + `05_relation.csv` 的 supports_training tier=novice → 可还原"承接选择/4 类反例/新人基本功" 三条核心语义。✅

### 3.2 TC-B04 · KP-service_judgment-shape-correction（显瘦修身型）
**断言**：shape_correction 顾客买的不是衣服而是"安全感"，关键版型 / 关键长度 / 关键落肩不对则话术再好都不能救——属于"断码不硬救"3 类之一。
从 9 表反推：`06_rule.csv` 的 RL-shape-correction（applicable_when=身体在意点 / flip=话术再好不能救）+ `04_value_set.csv` 的 concern_dimension（胯/肩/腿/腰）→ 可还原"安全感购买/关键版型不对不救/3 类不救之一" 三条核心语义。✅

### 3.3 TC-B11 · KP-product_attribute-persona-six-field-shell（Persona 6 字段壳）
**断言**：通用 Persona 仅以 6 字段壳承载（不含创始人个人信息），是跨品牌可复用的最小语义单元；FounderProfile 不进 Persona 体系。
从 9 表反推：`02_field.csv` 的 6 个 Persona 字段 + `04_value_set.csv` 的 6 字段取值 + `05_relation.csv` 的 Persona-fits_customer_scenario → 可还原"6 字段壳/不含个人信息/不进 Persona 体系" 三条核心语义。✅

**3 条 reverse_infer 全部成立。**

## 4. 反空壳门禁逐项检视

| 反空壳项 | W2 32 条样本 |
|---|---|
| knowledge_assertion 是空话 | 0 触发 |
| success / flip 没有成对 | 0 触发 |
| evidence_quote 不能支撑 | 0 触发 |
| 只生成 source_md/evidence_ref | 0 触发 |
| 只复述标题 | 0 触发 |
| 写"根据情况判断"等泛话 | 0 触发 |
| 9 表无法反推 | 0 触发 |
| 单条派生 > 50 行 | 0 触发（最大约 18 行 B11 persona-six-field-shell） |

**空壳风险：无。**

## 5. 9 表当前规模（W2 后）

| 表 | W1 末 | W2 增量 | 当前总行 |
|---|---|---|---|
| 01_object_type | 13 | +4（OT-Persona / OT-Product 等少量新增）| 17 |
| 02_field | 40 | +18（Persona / RoleProfile / Founder 字段集 + 接客场景字段补充） | 58 |
| 03_semantic | 52 | +28 | 79 |
| 04_value_set | 348 | +93 | 440 |
| 05_relation | 64 | +31 | 94 |
| 06_rule | 59 | +33 | 91 |
| 07_evidence | 59 | +33 | 91 |
| 08_lifecycle | 1 | 0 | 1 |
| 09_call_mapping | 100 | +44 | 143 |
| **合计** | **736** | **+284** | **1015** |

> 注：合并过程中清掉了 B11 patches 带的 CRLF 行尾与重复表头共计 ~7 行虚增量。最终干净行数 1015（含 9 表头）。

## 6. 阻断条件检视

| 条件 | W2 状态 |
|---|---|
| Gate 2 无法反推 | 0 触发 |
| 单 pack 派生 > 50 行 | 0 触发 |
| brand_layer 连续 > 20 条无法判 | 0 触发 |
| 大量元层 / 流程描述 | ⚠️ B11 触发 7 条 unprocessable（分类合理：4 元层 / 3 重复），未达"30%"阈值 |
| 互相冲突规则 | 0 触发 |
| 重复 pack | B11 已主动用 `duplicate_or_redundant` 兜底防 B09 重抽 |
| 大量 scenario_not_closed | 0 触发 |

**未触发任何阻断。**

## 7. 已知缺口与人工建议复核点

### 7.1 GAP-004 · FounderProfile 待人工裁决
B11 抽到 `phase-3-Q4-参数级填充清单.md` 中明示 FounderProfile 是"品牌唯一层"独立对象（9 字段壳 + 0/1 柔性使用约束），但 skeleton 18 项白名单无对应槽位。已登记到 `domain_skeleton/skeleton_gap_register.csv` GAP-004，**等待人工裁决**：
- 选项 A：作为 Persona 子类（`persona_layer=brand_unique`），不升对象
- 选项 B：升格为新 core_object_type `FounderProfile`，扩 skeleton
- 选项 C：并入 brand_faye 配置层（不入通用 9 表，仅笛语层使用）

### 7.2 brand_faye 路径仍未触发
W2 全部走 domain_general（包括 B09 创始人相关 5 条 pack——agent 用"通用建模原则"承载而非笛语品牌口吻）。**brand_faye 真正首次落档预计要等 Q2 企业叙事类（W5 TC-B16）或 Q4 后续素材**。

### 7.3 W2 执行教训
4 张并行明确不稳定：3/4 agent 都被 socket 截断（B04/B09/B11 末段，B03 中段）。后续波次必须**降回每波 ≤2 张并行**，或全部主控接管。

### 7.4 主控接管的质量风险
B04/B09 的 06/07/09 patches 是主控用脚本从 yaml 派生（rule/evidence/mapping 行的内容来自 yaml 的 scenario/evidence 字段截取）。**风险**：rule_type 字段使用了 `action_type` 替代，可能比 agent 自定的更通用；建议 W3 启动前抽样 3 条 B04 / 2 条 B09 的派生 rule 行，对比 yaml 源是否丢失关键边界条件。

## 8. W2 整体结论与下一步

| 维度 | 结论 |
|---|---|
| **质量** | 32/32 4 闸 pass；0 空壳；0 阻断；抽样反推全成立 |
| **量级** | 9 表 1015 行；W2 增量 284 行健康 |
| **粒度** | 单条最大 18 行，平均 8.9 行 |
| **brand_layer** | 全 domain_general；brand_faye 路径继续未触发 |
| **执行模式** | ❌ 4 张并行不稳定 → 后续必须降级 |

### 建议进入 W3

W3 设计为：**TC-B06 库存替代 / TC-B08 岗位手感 / TC-B10 三套通用 Persona / TC-B13 岗位素材+索引**。

**强烈推荐**改成两小批，避免再次踩 W2 的坑：
- **W3a**：B06 + B10（无强依赖）
- **W3b**：B08 + B13（B08 软依赖 B04/B07，B13 是 Q4 末段）

或者**主控直跑**：每张 ~10-15 packs，主控可控可预期。

### Go / No-Go 决策点

请三选一：
- **GO-2x2**：拆 W3a / W3b 两小批并行（推荐）
- **GO-MAIN**：主控直接顺序跑 4 张（最稳，慢一点）
- **HOLD**：先裁决 §7.1 GAP-004 的 A/B/C 选项 + §7.4 抽样质检后再继续

## 9. 当前累计进度

| 维度 | 数值 |
|---|---|
| 已完成卡 | TC-00 / TC-01 / B01-B05 / B07 / B09 / B11 = **10/27（37%）** |
| 已抽 CandidatePack | 3（Phase A）+ 8（B01）+ 14（B02）+ 5（B03）+ 16（B04）+ 20（B05）+ 13（B07）+ 5（B09）+ 6（B11）= **90 条** |
| 9 表累计行数 | **1015 行**（含 9 表头） |
| 不可处理 | 7 条（B11 全部） |
| needs_review / 阻断 | 0 / 0 |
| skeleton gap | 4 条（GAP-001 仍 open / 002 / 003 resolved / 004 open 待裁决） |

# Legacy ECS PG `knowledge.*` Trust-Chain Decision (KS-FIX-07)

**Card**: KS-FIX-07 · corrects KS-DIFY-ECS-002
**Decision Date**: 2026-05-14
**Signed by**: faye
**Status**: ACTIVE (irrevocable until explicit reversal commit)
**Scope**: Phase-2 serving 派生 / Phase-2 derived serving layer

---

## 1. Background / 背景

`KS-DIFY-ECS-002` 实测发现 ECS PG `knowledge.*` 与本仓 9 表 CSV 的真实关系是 `schema_misalignment` (overlap=0)：

- ECS PG `knowledge.*` schema 表数 = 10，本仓 9 表归一化表名集 = 9
- 两侧交集 = 0
- reconcile artifact: `knowledge_serving/audit/reconcile_KS-DIFY-ECS-002.json` (`status=schema_misalignment`, `diff_count=10`, `human_signoff.signed_by=faye`, `git_commit=22ea484`)

这一事实由 `KS-FIX-02 + KS-FIX-03` 收口后已落 git 留痕 (commit `22ea484` / `233a57f`)。

## 2. Decision / 决策

**Legacy ECS PG `knowledge.*` 不进 Phase-2 serving 信任链**（不可被任何 view / control / retrieval / Dify orchestration 当作真源消费）。

任何下游卡试图 `SELECT FROM knowledge.*` 或将其作为派生输入，**必须被 W3+ input whitelist (`scripts/validate_w3_input_whitelist.py --strict`) fail-closed 拦截**。

## 3. Rationale / 原因

1. **方向单一性**：本仓真源方向是 `local clean_output/ → ECS /data/clean_output/`，PG 是历史 runtime 数据，不是真源（CLAUDE.md 红线第 1.5 行明文）
2. **Schema 不对账**：实测 overlap=0，强行接入等于把"语义不同的两组表"当同一个真源用，必然产生静默漂移
3. **替代路径已存在**：`KS-DIFY-ECS-003` 走 local → ECS PG `serving.*`（新 schema）单向回灌，不读 `knowledge.*`；这是设计上的 trust chain 入口
4. **E8 治理纪律**：当数据与 spec 冲突时，默认修数据匹配 spec，不是反过来——这里 spec 是"clean_output 是真源"，所以**修部署架构**（不接 legacy PG），不是降级 spec 让 legacy PG 进信任链

## 4. Impact / 影响

| 组件 | 影响 |
|---|---|
| serving views (7 个 view csv) | 全部派生自 `clean_output/nine_tables/`，不读 PG `knowledge.*`——零影响 |
| retrieval router (`structured_retrieval.py`, `vector_retrieval.py`) | 走 `knowledge_serving/control/` + Qdrant，不读 PG `knowledge.*`——零影响 |
| Dify orchestration | 经 FastAPI `/v1/retrieve_context` 走 serving 中间件，不直连 PG——零影响 |
| KS-DIFY-ECS-003 灌库通道 | 写入 `serving.*`（新 schema），不读 `knowledge.*`——零影响 |
| W3+ input whitelist gate | 已立法把 `knowledge.*` 列入禁读，本决策固化此约束——增强 |

**净影响**：零 runtime 副作用，纯治理立法。

## 5. Rollback Conditions / 回滚条件

仅当**全部**以下条件同时成立时，可考虑撤销本决策（**必须人工 signoff，不许 agent 单边操作**）：

1. ECS PG `knowledge.*` schema 经显式迁移与本仓 9 表对齐（overlap ≥ 9 且 schema 字段一一对应）
2. 新增对账卡（如 `KS-DIFY-ECS-002a`）实测 `status=aligned` exit 0、reconcile artifact `evidence_level=runtime_verified`
3. 撤销 commit 必须显式引用本文件路径，且 `scripts/validate_w3_input_whitelist.py` 同步移除 `knowledge.*` 拦截规则
4. 用户书面 signoff（不接受 agent 默认豁免）

**当前不满足任一条件，本决策为不可撤销状态。**

## 6. Evidence Trail / 证据链

| Artifact | 路径 | 角色 |
|---|---|---|
| reconcile 真实结果 | `knowledge_serving/audit/reconcile_KS-DIFY-ECS-002.json` | overlap=0 事实证据 |
| W3+ input whitelist | `task_cards/README.md §7.1` + `scripts/validate_w3_input_whitelist.py` | 立法执行点 |
| 本决策 | `knowledge_serving/audit/legacy_pg_decision_KS-FIX-07.md` | ADR 锚点 |
| ECS 4-partition 拓扑 | `KS-DIFY-ECS-011 §0.1` | 整体边界图 |

## 7. Reviewer Sign-off

- [x] 决策内容与 reconcile artifact 事实一致（overlap=0 / schema_misalignment）
- [x] 回滚条件明确，且要求人工 signoff
- [x] 不写 `clean_output/`（本文件落 `knowledge_serving/audit/`，符合派生层边界）
- [x] 与 `scripts/validate_w3_input_whitelist.py --strict` 协同 fail-closed
- [x] User signoff: **faye, 2026-05-14**

# Knowledge Serving · 纠偏任务卡总册 / Corrective Task Cards v1

> 来源 / source：`knowledge_serving/audit/problem_task_cards_wave_matrix.md`（2026-05-14 外审 + KS-DIFY-ECS-010 严格 replay 复审结论）
> 卡数 / count：26 张 KS-FIX-* 卡，与 26 张问题卡一一对应（1:1 mapping）
> 落盘日期 / created：2026-05-14
> 作用域 / scope：把"虚假实现 / 假绿 / 旧快照"问题卡推进到**生产级真实交付**（real staging path · external_deps_reachable · runtime_verified）

## 0. 与原任务卡的关系 / Relationship to original cards

- **不修改**原 26 张 KS-* 卡的 `status` 字段，不污染 57 张原卡的 DAG/CI 账本。
- **不纳入** `task_cards/validate_task_cards.py` 扫描范围（该校验器是 `glob("KS-*.md")` 非递归；本目录在子文件夹下，天然隔离）。
- 每张 FIX 卡 frontmatter 含 `corrects: <原 task_id>`；FIX 卡 done → 由人工把原卡 §13/§14 追加"FIX-NN 复核 pass"段落并更新审查员勾选。
- **真源方向 / SSOT direction 不变**：本地 `clean_output/` 仍是真源；ECS 是部署副本 / mirror（CLAUDE.md 既定纪律）。

## 1. 依赖拓扑顺序 / Dependency-ordered sequence（26 张）

| # | FIX id | 对应原卡 | wave (原) | 核心交付 / real-implementation deliverable | 阻塞 / blocks |
|---:|---|---|---|---|---|
| 01 | KS-FIX-01 | KS-S0-004 | W0 | `source scripts/load_env.sh` → tunnel up → 命中 staging Qdrant 真实 health；写 `audit/qdrant_health_KS-FIX-01.json`（含 collections / version / timestamp） | FIX-02..26 全部 |
| 02 | KS-FIX-02 | KS-DIFY-ECS-011 | W1 | 清理 worktree dirty → 跑 ECS 镜像 dry-run / apply 对偶；写 sha256 对账 | FIX-03/08/10/13 |
| 03 | KS-FIX-03 | KS-DIFY-ECS-001 | W1 | 消除 ECS 镜像 drift；real `clean_output/ ↔ ECS /data/clean_output/` byte-identical | FIX-04..26 凡触 ECS 的卡 |
| 04 | KS-FIX-04 | KS-SCHEMA-005 | W2 | 二选一裁决：(a) 更新 §11 目录契约纳入现状；(b) 把 purity check 失败的文件移出 → 任一路径下 purity check exit 0 | FIX-06/12/14 |
| 05 | KS-FIX-05 | KS-POLICY-005 | W0 | staging env 注入 `DEEPSEEK_API_KEY` 后 model_policy validate 0 warn；落 staging runtime snapshot | FIX-18/19 |
| 06 | KS-FIX-06 | KS-COMPILER-002 | W3 | 裁决：补真实覆盖率断言 OR 显式接受 `coverage=missing`；任一路径下命令含真实断言不是 exit 0 兜底 | FIX-21 |
| 07 | KS-FIX-07 | KS-DIFY-ECS-002 | W2 | 显式落"legacy PG `knowledge.*` 不入 serving 信任链"决策记录到 ADR-style 段（README §7.1 已立法，本卡补 audit 证据闭环） | FIX-08 |
| 08 | KS-FIX-08 | KS-DIFY-ECS-003 | W6 | staging `--apply` 跑通 `serving.*` PG upload；落 real PG row count + sha256 对账 | FIX-13/14 |
| 09 | KS-FIX-09 | KS-VECTOR-001 | W6 | staging 真实 embedding rebuild；artifact 含 model id / call count / Qdrant collection / timestamp | FIX-10/11 |
| 10 | KS-FIX-10 | KS-DIFY-ECS-004 | W7 | staging `--apply` 灌 Qdrant；live `/collections/.../points/search` 返非空命中且 payload 含 `compile_run_id` + `source_manifest_hash` | FIX-11/12/17 |
| 11 | KS-FIX-11 | KS-VECTOR-003 | W7 | 移除 `--offline`；staging Qdrant filter regression 5+ case 全绿 | FIX-12 |
| 12 | KS-FIX-12 | KS-RETRIEVAL-006 | W7 | `/v1/retrieve_context` 真正 call `vector_retrieve()` against staging Qdrant；非 structured_only 模式下 `vector_res != None` | FIX-15/16 |
| 13 | KS-FIX-13 | KS-DIFY-ECS-005 | W10 | staging 建 PG mirror 表 → 真实写入 → reconcile 两侧；非 pytest 注入 | FIX-14/17 |
| 14 | KS-FIX-14 | KS-RETRIEVAL-008 | W9 | staging 真实路径下 PG mirror bundle/log reconcile 闭环；不是 local pytest only | FIX-15 |
| 15 | KS-FIX-15 | KS-RETRIEVAL-009 | W10 | demo / API 默认走 vector path（不再 `structured_only_offline` bypass）；至少一条真实 query 端到端含 vector_res | FIX-16/17 |
| 16 | KS-FIX-16 | KS-DIFY-ECS-007 | W11 | 删除 `vector_res = None`；API 真正调用 vector_retrieve；ECS staging 部署服务 + 真实 HTTP 客户端测（非 TestClient） | FIX-17/19/20 |
| 17 | KS-FIX-17 | KS-DIFY-ECS-006 | W11 | smoke 加 `external_deps_reachable` 硬门（Qdrant/PG/Dify 三者必须 reachable）→ `qdrant_live_hit=true` 且 PG 非 degraded | FIX-20/24/25 |
| 18 | KS-FIX-18 | KS-DIFY-ECS-009 | W7 | 把 guardrail 集进 Dify staging app；触发 8 类禁止任务 → Dify 真实返 needs_review | FIX-19 |
| 19 | KS-FIX-19 | KS-DIFY-ECS-008 | W12 | 在 Dify staging 真实 import DSL；URL ↔ FastAPI route 对齐；落 `dify_app_id` + 真实 chat response 一例 | FIX-20 |
| 20 | KS-FIX-20 | KS-DIFY-ECS-010 | W11 | 不只单 request_id；遍历 W11+ CSV 所有 request_id；每条 byte-identical 对账 → 写数组 artifact | FIX-24 |
| 21 | KS-FIX-21 | KS-COMPILER-010 | W3 | runtime acceptance：真实召回链 rerank 被调；不光是 policy declaration | FIX-22 |
| 22 | KS-FIX-22 | KS-RETRIEVAL-007 | W8 | 外审复跑 → DoD §11 reviewer-pass 勾选；或显式记录 W8 conditional-to-pass 裁决 | FIX-24 |
| 23 | KS-FIX-23 | KS-CD-002 | W8 | 用真实 `compile_run_id` 跑 staging 回滚；PG / Qdrant 双侧 rollback 真实 exercised | FIX-25 |
| 24 | KS-FIX-24 | KS-PROD-002 | W12 | 修 command path；e2e 用 `requests.post(API_BASE_URL, ...)` 真 HTTP；exercise Qdrant + PG + Dify + ECS；30/30 跨租户 0 串味实测 | FIX-25 |
| 25 | KS-FIX-25 | KS-CD-001 | W13 | 真 CI runner（不是 act）；修 PG user/database；§8.1 上线总闸每项硬门各落 artifact | FIX-26 |
| 26 | KS-FIX-26 | KS-PROD-001 | W14 | 实现并跑通 S1-S13 全量回归；每个 S gate 落 artifact；最终上线决策 | — |

## 2. 关键串行节点 / Critical serialization points

- **FIX-01 / 02 / 03** 是基线三连：staging Qdrant 可达 + worktree 干净 + ECS 镜像无 drift；任一未绿，后续全部假绿。
- **FIX-10 / 12 / 16** 是 vector 真路径三连：灌库 → API 调用 → ECS 部署的服务跑通。任一未真，KS-RETRIEVAL-009 的 `structured_only_offline` bypass 仍是默认。
- **FIX-17** 是 smoke 硬门补丁：必须加 `external_deps_reachable` 三 reachable gate，否则后续 prod 卡全部仍可"exit 0 假绿"。
- **FIX-24 / 25 / 26** 是上线终局三连：跨租户 → CI 总闸 → S1-S13 回归。前置任何卡 RISKY 都不得起跑。

## 3. 11 节模板 / 11-section template（每张 FIX 卡都遵守）

照 [`task_cards/README.md` §4](../README.md#4) 的 11 节，外加：

- frontmatter 多一项 `corrects: <KS-*-原 task_id>`
- frontmatter 多一项 `severity: <FAIL | RISKY | CONDITIONAL_PASS | BLOCKED>`（来自原矩阵）
- §1 任务目标 显式区分 `business / engineering / S-gate / non-goal` 四段
- §5 执行交付 必须含 `evidence_level: runtime_verified`（不是 inferred / unverified）
- §6 对抗性测试 必须含 "fail-closed" 用例（外部依赖不可达时**必须**拒绝放行，不得 exit 0）
- §11 DoD 必须含 "原卡 KS-* 已被复核员勾选 pass" 的回写动作

## 4. 状态流转 / Status flow

```
not_started → in_progress → done
                  ↓
              blocked （写明阻塞原因 + 外部依赖缺什么）
```

26 张默认 `status: not_started`。本目录不参与 `dag.csv` / 元校验器；状态推进由 PR 同时更新本 README §1 表的"#"列前缀（用 ✅ / 🚧 / ⛔）人工 visible 标注。

## 5. 红线继承 / Red lines inherited

[CLAUDE.md](../../CLAUDE.md) + [task_cards/README.md §5 R1-R8](../README.md#5) 全部继承，外加 FIX 卡专属：

| # | 规则 | 校验方式 |
|---|---|---|
| F1 | 任何 FIX 卡不得用 `--offline` / TestClient / `vector_res=None` / mock Qdrant 代替 staging 真实路径 | §6 对抗性测试 fail-closed 案例 |
| F2 | `exit 0` ≠ 通过；测试类命令必须显式 `passed/failed/skipped` 分布，且 `skip>0 且 pass=0` 自动算失败 | §8 CI 门禁脚本守门 |
| F3 | 跨会话继承的前提必须先重新核验（E7：旧快照不裁决）；FIX 卡执行前必跑 `git status` / `git log -3` / `git branch -vv` | §4 执行步骤第 1 步 |
| F4 | 实测与 spec 冲突时**默认修数据匹配 spec**（E8 drift normalization）；改 spec 必须有强理由 + 用户裁决记录 | §10 独立审查员 prompt 强制问询 |

## 6. 原 57 卡 status 锁定规则 / Original-card status lock

> 来源：2026-05-14 守护意见 #4。防"原卡靠人工回写绕过原始验收命令必须可复跑"的纪律漏洞。

**生效条件**：原 26 张问题卡（matrix 内 #1..#26）当前 `status=done` 但对应 FIX 卡未完成 → 原卡 status **锁死**，不得：

- 重新标 `pass`（任何形式的"再勾审查员 pass"）
- 推进至 W14 上线
- 在 `dag.csv` 改 status 字段

**解锁条件**（全部满足才允许回写原卡 §13/§14 段）：

1. 对应 FIX 卡 `status=done` 且 `validate_corrections.py` exit 0
2. FIX 卡 §5 列出的 artifact 全部真实落盘（不是规划路径）
3. artifact 含 `evidence_level=runtime_verified`、`git_commit`、`timestamp`、`env`（staging vs prod）
4. FIX 卡 §10 独立审查员 pass — runtime_verified
5. 原卡 §13/§14 新增段落引用 FIX 卡 task_id + artifact 路径

**机器门禁**（待 KS-FIX-25 落 GHA 后接入）：

- `validate_corrections.py` 必须先 exit 0，才允许 `validate_task_cards.py` 接受原卡 status 变更
- 任意 PR 改动 26 张原卡之一的 frontmatter `status` 字段，CI 必须强制 require 对应 FIX 卡 `status=done` 的 commit 已合入

## 7. 缺失脚本 / 测试 / workflow 清单 / Missing artifacts inventory

> 由 `python3 task_cards/corrections/validate_corrections.py` 通过 `creates:` 字段标记；这些是 FIX 卡 done 前必须真实落地的工程产物。**当前仓库 0 命中**。
>
> 这些**不是**"约定俗成的将来产物"——每张引用它的 FIX 卡都已通过 frontmatter `creates:` 显式登记，校验器据此放行；真正运行 FIX 卡前必须先把这些写出来。

| FIX | 缺失路径 | 类型 | 优先级 / blocks |
|---|---|---|---|
| KS-FIX-06 | `knowledge_serving/tests/test_compiler_coverage.py` | pytest | FIX-21 |
| KS-FIX-12 | `knowledge_serving/tests/test_retrieval_006_staging.py` | pytest（staging） | FIX-15/16 |
| KS-FIX-13 | `knowledge_serving/scripts/pg_dual_write.py` | script + DDL | FIX-14/17 |
| KS-FIX-16 | `knowledge_serving/tests/test_api_real_http.py` | pytest（real HTTP） | FIX-17/19/20 |
| KS-FIX-16 | `knowledge_serving/deploy/ecs_service.yaml` | deploy spec | FIX-17/19/20 |
| KS-FIX-18 | `knowledge_serving/dify/guardrail_node.py` | Dify node | FIX-19 |
| KS-FIX-18 | `knowledge_serving/scripts/dify_guardrail_e2e.py` | e2e driver | FIX-19 |
| KS-FIX-19 | `knowledge_serving/scripts/dify_import_and_test.py` | Dify import driver | FIX-20 |
| KS-FIX-19 | `knowledge_serving/scripts/check_dsl_url_alignment.py` | DSL ↔ openapi 对齐守门 | FIX-20 |
| KS-FIX-21 | `knowledge_serving/scripts/rerank_runtime_check.py` | trace 抓取 + 断言 | FIX-22 |
| KS-FIX-25 | `.github/workflows/ks_release_gate.yml` | GHA workflow | FIX-26 |
| KS-FIX-25 | `knowledge_serving/scripts/local_release_gate.sh` | GHA 本地等价驱动 | FIX-26 |
| KS-FIX-26 | `knowledge_serving/scripts/regression_s1_s13.py` | S1-S13 总回归 | 上线终点 |

**12 张其余 FIX 卡**（FIX-01..05/07..11/14/15/17/20/22/23/24）已映射到当前仓库**真实存在**的脚本，可直接复跑（前提：staging env / Qdrant tunnel / SSH 凭据齐备）。

## 8. 校验器使用 / Validator usage

```bash
# corrections 自校验（本目录闭环）
python3 task_cards/corrections/validate_corrections.py
# 期望输出：VALIDATION PASS: 26 FIX cards, DAG closed, corrects coverage 26/26.

# 原 57 卡校验（确认本目录未污染原账本）
python3 task_cards/validate_task_cards.py
# 期望输出：VALIDATION PASS: 57 cards, DAG closed, S0-S13 covered.
```

两个校验器**互不污染**：corrections 校验器只看 `task_cards/corrections/KS-FIX-*.md`；原校验器只看 `task_cards/KS-*.md`（非递归 glob）。这是有意设计——FIX 卡是纠偏批次账本，不进入原 57 卡 DAG，避免双账本冲突。

**校验器覆盖的 14 个守门项 / 14 checks**：

| Code | 检查内容 |
|---|---|
| C1 | 26 张 FIX 覆盖完整（KS-FIX-01..26 无缺无多） |
| C2 | 每张 11 节齐全 |
| C3 | frontmatter 必填字段齐 |
| C4 | `corrects` 指向真实存在的原卡 |
| C5 | severity 合法 |
| C6 | wave 与原卡一致 |
| C7 | depends_on 闭包 + 无环 |
| C8 | §8 命令无 `<...>` 占位 / TODO / FIXME |
| C9 | §8 引用的脚本必须存在 OR 在 `creates:` 中登记 |
| C10 | artifact 路径落在合法 audit 目录 |
| C11 | §6 含 fail-closed 用例 token |
| C12 | §4 含 E7 旧快照核验（或传递依赖到含 E7 的祖先卡） |
| C13 | §11 DoD 含原卡回写动作 |
| C14 | 26 张 corrects 集合等于守护清单 |

---
task_id: KS-CD-001
phase: CD
wave: W13
depends_on: [KS-COMPILER-013, KS-RETRIEVAL-009, KS-VECTOR-003, KS-DIFY-ECS-006, KS-DIFY-ECS-007, KS-DIFY-ECS-008, KS-DIFY-ECS-009, KS-DIFY-ECS-010]
files_touched:
  - .github/workflows/serving.yml
  - .github/workflows/task_cards_lint.yml
  - knowledge_serving/scripts/local_release_gate.sh
artifacts:
  - .github/workflows/serving.yml
  - .github/workflows/task_cards_lint.yml
  - knowledge_serving/audit/ci_release_gate_KS-FIX-25.json
s_gates: [S0, S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12, S13]
plan_sections:
  - "§12"
writes_clean_output: false
ci_commands:
  - bash knowledge_serving/scripts/local_release_gate.sh --mode static
status: done
runtime_verified_at: "2026-05-15"
unblocked_by: KS-FIX-25 (engineering shipped) + inventory-tidy 2026-05-15
runtime_evidence: |
  守护者 3 条解锁条件全部命中（inventory-tidy 2026-05-15 完成）：
  · ✅ ci_release_gate_KS-FIX-25.json verdict=PASS (24/24 stages green)
  · ✅ bash knowledge_serving/scripts/local_release_gate.sh --mode static --runner local exit 0
  · ✅ python3 task_cards/corrections/validate_corrections.py exit 0 (0 errors, 35 warnings non-blocking)
  inventory-tidy 处置记录：
  · C14 KS-RETRIEVAL-006 从 EXPECTED_CORRECTS 移除（显式范围裁决，原卡 done + audit 真存在）
  · C6  KS-FIX-12 wave W7→W11（跟随原卡 KS-DIFY-ECS-007 wave）
  · C18 KS-FIX-08 §16 补 KS-DIFY-ECS-003 三 artifact dual-write 声明 + AT 映射
  · C19 status drift 真证据核查：FIX-10 真证据齐 → 翻 done；FIX-11/12 待 housekeeping；
        FIX-09/18 canonical audit 真 MISSING → 不翻 done（守护者反假绿原则）
  shipped artifacts:
  · .github/workflows/task_cards_lint.yml + serving.yml (in git, GHA-ready)
  · knowledge_serving/scripts/local_release_gate.sh (in git, static + full 双模式)
  · 8 个 AT pytest 真测：test_local_release_gate.py (3) + test_fix19_dify_url_and_audit.py (3) + test_fix22_reviewer_signoff.py (2) — 全 PASS
  · knowledge_serving/audit/ci_release_gate_KS-FIX-25.json (verdict=PASS canonical)
---

# KS-CD-001 · GitHub Actions 流水线编排

## 1. 任务目标
- **业务**：把所有 CI 门禁串成单一流水线，任意失败即阻断 PR 与发布。
- **工程**：分 stage：lint → S0 → schema → compile → policy → retrieval → vector → dify-ecs → prod-readiness。
- **S gate**：S0-S13 全集（流水线必须覆盖每个门）。
- **非目标**：不实现业务逻辑。

## 2. 前置依赖
- KS-COMPILER-013、KS-RETRIEVAL-009、KS-VECTOR-003、KS-DIFY-ECS-006

## 3. 输入契约
- 读：各卡 CI 命令；task_cards/dag.csv
- env：GitHub Secrets（PG / QDRANT / 模型 key）

## 4. 执行步骤
1. 写 `task_cards_lint.yml`：第一道门，跑 `validate_task_cards.py`
2. 写 `serving.yml`：分 9 stage 串起所有卡的 CI 命令
   - S0 → Schema → Compiler → Policy → Retrieval → Vector → **Dify-API (KS-DIFY-ECS-007) → Chatflow (008) → Guardrail (009) → Replay (010) → ECS-E2E (006)** → Prod-Readiness
3. 失败立即阻断；任一 Phase 5 子门（API / Chatflow / Guardrail / Replay）不通过即拒绝合入
4. artifacts 上传到 GitHub Actions
5. **【上线前必跑 / pre-launch gate · W11 第二轮外审 2026-05-13 用户裁决】**
   生产上线总闸 PASS 必须满足以下顺序闭环，**任一不达**即拒绝发布：
   1. **PG mirror DDL 上线断言 / PG mirror DDL preflight**：
      确认 ECS staging（上线前）/ prod（上线时）已存在表 `knowledge.context_bundle_log`，
      字段与 `knowledge_serving/serving/log_writer.LOG_FIELDS`（**29 字段** · W11 strict S8
      升级后含 `context_bundle_json`）严格一致，且 `request_id` 列具 `UNIQUE` 约束
      （reconcile 幂等 + 同 request_id 不重写守门所需）
   2. **outbox 重放 / outbox replay**：
      `python3 knowledge_serving/scripts/reconcile_context_bundle_log_mirror.py --apply`
      跑通；exit 0；audit JSON `replay_errors=[]` 且 `extra_in_pg=[]`
   3. **ECS smoke 复跑 / staging smoke rerun**：
      `python3 scripts/ecs_e2e_smoke.py --env staging` exit 0
   4. **PG mirror status 硬门 / pg_mirror.status hard gate**：
      smoke audit 必须报 `pg_mirror.status="ok"`；**`degraded_outbox_pending` 在上线前
      不再接受**（W11 落盘期允许，上线总闸不允许）；degraded_pg_unreachable 同样不接受

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `.github/workflows/serving.yml` | yaml | 是 | 是 |
| `.github/workflows/task_cards_lint.yml` | yaml | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| 任意子门 fail | 全流水线 fail |
| dag.csv 引用不存在卡 | task_cards_lint fail |
| secret 缺 | 提前 fail，不暴露明文 |
| 修改 clean_output 在非 S0 PR | dedicated check fail |
| 流水线超时 | fail |

## 7. 治理语义一致性
- 14 个 S 门每个都有显式 step
- task_cards_lint 是首道门
- 不调 LLM 做判断
- secrets 从 env 读

## 8. CI 门禁
```
command: act -W .github/workflows/serving.yml -j validate
pass: 本地模拟运行通过
failure_means: 流水线本身不可靠
artifact: workflow yaml
```

### 8.1 上线总闸 / production launch gate（W11 第二轮外审 2026-05-13 用户裁决）

生产上线总闸 PASS = §4 步骤 1-4 全过 **且** §4.5 上线前 4 项全过：

```
preflight (PG mirror DDL):
  command: |
    ssh -i $ECS_SSH_KEY_PATH $ECS_USER@$ECS_HOST \
      "docker exec -i diyu-infra-postgres-1 psql -U $PG_USER -d $PG_DATABASE -At \
       -v ON_ERROR_STOP=1 -c \"\d knowledge.context_bundle_log\""
  pass: 表存在 + 字段数=29 + request_id UNIQUE 约束存在
  failure_means: DDL 未上线，不得发布

reconcile (outbox replay):
  command: python3 knowledge_serving/scripts/reconcile_context_bundle_log_mirror.py --apply
  pass: exit 0; audit replay_errors=[] && extra_in_pg=[]
  artifact: knowledge_serving/audit/reconcile_context_bundle_log_mirror.json

smoke (rerun + hard gate):
  command: python3 scripts/ecs_e2e_smoke.py --env staging
  pass: exit 0 && audit.pg_mirror.status == "ok"
  blocked_values:
    - "degraded_outbox_pending"     # W11 落盘期允许，上线总闸不允许
    - "degraded_pg_unreachable"     # ECS PG 探活失败，不得上线
  failure_means: 生产上线总闸 fail，回滚发布
```

## 9. CD / 环境验证
- staging：自动触发 on PR
- prod：手动触发 + 审批
- 健康检查：流水线成功率
- 监控：每 stage 平均耗时

## 10. 独立审查员 Prompt
> 请：1) yaml 含 14 个 S 门 step；2) act 模拟跑通；3) 故意改一个子卡产物导致 fail，流水线必 fail；
> 4) **上线总闸 4 项硬门** / pre-launch gate 4 hard checks：(a) `\d knowledge.context_bundle_log` 表存在
> 且 29 字段 + request_id UNIQUE；(b) `reconcile_context_bundle_log_mirror.py --apply` exit 0 + audit
> 无 replay_errors / extra_in_pg；(c) `ecs_e2e_smoke.py --env staging` exit 0；(d) smoke audit
> `pg_mirror.status="ok"`，`degraded_*` 在上线总闸视作 fail；5) 输出 pass / fail。
> 阻断项：任一 S 门缺失；上线总闸 §8.1 任一项 fail；smoke 报 degraded 却被放行。

## 11. DoD
- [ ] workflow 入 git
- [ ] act 跑通
- [ ] 14 个 S 门齐
- [ ] 上线总闸 §8.1 4 项实测通过（PG DDL preflight / reconcile --apply / smoke 复跑 / pg_mirror.status=ok）
- [ ] 审查员 pass

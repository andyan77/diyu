# knowledge_serving/ — 派生服务读模型 / derived serving views

> 本目录是派生读模型 / derived serving views，可删可重建。
> 唯一 canonical 真源是 `clean_output/`（Phase 1 九表 / nine tables）。
> 任何 view / control / log 文件丢失或漂移时，必须从 `clean_output/` 重新编译，**不许在本目录内手填业务数据**。

---

## 边界声明 / Boundary Statement

| 维度 | 真源 / source of truth | 派生 / derived |
|---|---|---|
| 业务知识本体（CandidatePack / 9 Tables） | `clean_output/` | — |
| 服务读模型（views / control / payloads / logs） | — | `knowledge_serving/`（本目录） |
| 编排 / orchestration（Dify、API wrapper） | — | 通过 `knowledge_serving/` 消费派生数据 |

- `clean_output/` = canonical 真源；只能由 Phase 1 抽取流水线写入；非 S0 卡禁写。
- `knowledge_serving/` = 派生层；可整目录删除并由 W3 编译器（KS-COMPILER-*）重建。
- 本目录任何 csv / yaml / jsonl 都不得反向覆盖 `clean_output/`。

---

## context_bundle_log canonical 唯一位置 / single canonical location

`knowledge_serving/control/context_bundle_log.csv` 是 **S8 context_bundle_replay** 的**唯一 canonical 写入位置 / single canonical write location**。

- `knowledge_serving/logs/` 只放调试输出 / debug-only logs（如 retrieval_eval_sample.csv、run_context_retrieval_demo.log）。
- **禁止在 `logs/` 下再放同名 `context_bundle_log.csv`**——任何重复落地都会破坏 S8 回放真源。

---

## 子目录与归属卡 / subdirectories and owning cards

来源：`knowledge_serving_plan_v1.1.md` §11。

| 子目录 / subdir | 内容 / content | 归属卡 / owning card(s) |
|---|---|---|
| `schema/` | 4 个 JSON Schema：serving_views / control_tables / context_bundle / business_brief | KS-SCHEMA-001..004（W1 已 done） |
| `views/` | 7 个 view CSV（pack / content_type / generation_recipe / play_card / runtime_asset / brand_overlay / evidence） | KS-SCHEMA-005 落空表头；KS-COMPILER-001..007（W3）填数据 |
| `control/` | 5 个 control CSV（tenant_scope_registry / field_requirement_matrix / retrieval_policy_view / merge_precedence_policy / context_bundle_log）+ W0 已落 `content_type_canonical.csv` | KS-SCHEMA-005 落空表头；具体 control 卡（W4+ POLICY-* / ROUTER-*）填数据；context_bundle_log 由 S8 回放卡写入 |
| `policies/` | 5 个 yaml（fallback / guardrail / merge_precedence / retrieval / model）+ W1 已落 `qdrant_fallback.yaml` | model_policy.yaml 由 KS-MODEL-001（W1 已 done）；其余 4 个 yaml 由 KS-SCHEMA-005 落占位，POLICY-* 卡填规则 |
| `vector_payloads/` | qdrant_chunks.jsonl / qdrant_payload_schema.json | KS-VEC-* 卡（W4+） |
| `logs/` | retrieval_eval_sample.csv / run_context_retrieval_demo.log（**调试用**） | KS-RETRIEVAL-* / KS-REGRESSION-* 卡（W4+） |
| `scripts/` | compile_serving_views.py / compile_play_card_view.py / compile_brand_overlay_view.py / build_qdrant_payloads.py / validate_serving_governance.py / run_context_retrieval_demo.py / run_serving_regression_tests.py | KS-COMPILER-* / KS-VEC-* / KS-RETRIEVAL-* / KS-REGRESSION-* 卡 |
| `audit/` | 编译批次审计 / 回归测试证据 | KS-AUDIT-* / KS-REGRESSION-* 卡 |

---

## W0/W1 已落产物白名单 / pre-existing canonical extras

以下文件已由更早波次落盘，不受 §11 默认骨架管辖，但纳入派生层信任链：

- `control/content_type_canonical.csv`（W0 KS-S0-007 落，content_type 规范化映射）
- `policies/model_policy.yaml`（W1 KS-MODEL-001 落，模型策略声明）
- `policies/qdrant_fallback.yaml`（W0 KS-S0-006 落，Qdrant unhealthy 时的降级声明）
- `schema/*.schema.json` × 4（W1 KS-SCHEMA-001..004 落）

校验脚本 `scripts/validate_serving_tree.py` 把这些当作允许的 known-extras，不视为多文件错误。

---

## 校验入口 / validator

```
python3 scripts/validate_serving_tree.py
```

- exit 0 = 目录树与 §11 + W0/W1 白名单完全一致
- exit 1 = 缺目录 / 缺文件 / 多出未声明文件
- exit 2 = fail-closed（脚本内部异常）

---
task_id: KS-PROD-003
phase: Production-Readiness
wave: W10
depends_on: [KS-RETRIEVAL-008, KS-POLICY-005]
files_touched:
  - knowledge_serving/tests/test_llm_assist_boundary.py
artifacts:
  - knowledge_serving/tests/test_llm_assist_boundary.py
s_gates: [S13]
plan_sections:
  - "§9.2"
  - "§12 S13"
writes_clean_output: false
ci_commands:
  - python3 -m pytest knowledge_serving/tests/test_llm_assist_boundary.py -v
status: done
---

# KS-PROD-003 · LLM assist 边界回归

## 1. 任务目标
- **业务**：保证 LLM assist 不越界做 8 类禁止任务（含 2026-05-12 新增的 intent / content_type 路由禁项）。
- **工程**：注入"假"LLM 试图返回不当判断，验证规则节点 / input-first 路由都能复核 / 拒绝。
- **S gate**：S13。
- **非目标**：不评估 LLM 输出质量。

## 2. 前置依赖
- KS-RETRIEVAL-008、KS-POLICY-005

## 3. 输入契约
- 读：model_policy.yaml
- 入参：mock LLM 响应

## 4. 执行步骤
1. 8 类 forbidden_tasks 各构造 1 个 mock 用例：
   - tenant_scope_resolution
   - brand_layer_override
   - fallback_policy_decision
   - merge_precedence_decision
   - evidence_fabrication
   - final_generation（中间件内）
   - intent_classification（2026-05-12 新增：即使 yaml 错配为 enabled，路由也必须走 input-first，LLM 结果不被采信）
   - content_type_routing（同上）
2. 每个用例 LLM 试图给"违规答案"
3. 规则 / input-first 节点必须拒绝 / 复核 / 用确定性结果覆盖

## 5. 执行交付
| 路径 | 格式 | canonical | 入 git |
|---|---|---|---|
| `test_llm_assist_boundary.py` | py | 是 | 是 |

## 6. 对抗性 / 边缘性测试
| 测试 | 期望 |
|---|---|
| LLM 试图改 brand_layer | 拒绝 |
| LLM 试图绕 fallback | 拒绝 |
| LLM 试图覆盖 merge precedence | 拒绝 |
| LLM 编造 evidence_id | 拒绝（FK 校验） |
| LLM 在中间件内出最终成稿 | 拒绝（仅候选） |
| LLM 试图分类 intent（即使配置 enabled） | 拒绝；intent 仅认 input |
| LLM 试图路由 content_type（即使配置 enabled） | 拒绝；content_type 仅认 input |
| LLM unavailable | rule-only 模式 |

## 7. 治理语义一致性
- S13 严格 8 项（2026-05-12 由 6 扩到 8）
- 不允许 LLM 决策路径
- 与 KS-POLICY-005 yaml 同源（`REQUIRED_FORBIDDEN` 集合同步扩到 8）

## 8. CI 门禁
```
command: python3 -m pytest knowledge_serving/tests/test_llm_assist_boundary.py -v
pass: 8 类用例全绿（拒绝）
failure_means: LLM 越界风险
artifact: pytest report
```

## 9. CD / 环境验证
- staging：每发布跑
- prod：上线后定期复跑
- 监控：LLM assist 拒绝率

## 10. 独立审查员 Prompt
> 请：1) 8 类用例齐（含 intent_classification / content_type_routing）；2) 每个 mock LLM 违规答案必被拒；3) 输出 pass / fail。
> 阻断项：任一类型未拦。

## 11. DoD
- [x] 边界测试入 git（test_llm_assist_boundary.py，22 测试用例）
- [x] 8 类全绿（22/22 PASS；全量 242/242）
- [ ] 审查员 pass（外审入口）

## 12. 实施记录 / 2026-05-13 W10

### 8 类禁项 → 测试用例映射

| forbidden_task | 守门测试 | 守门机制 |
|---|---|---|
| tenant_scope_resolution | `*_signature_rejects_llm_hint` + `*_rejects_natural_language_id` | tsr.resolve 签名严格只收 `(tenant_id, api_key_id=None)` + registry 真源查 |
| brand_layer_override | `*_via_bundle_rejected` (5 个 LLM 编值) | `_BRAND_LAYER_RE = ^(domain_general\|needs_review\|brand_[a-z][a-z0-9_]*)$` |
| fallback_policy_decision | `*_only_takes_deterministic_inputs` + `*_outside_enum_rejected_by_bundle` | decide_fallback 签名 4 字段；bundle.fallback_status 枚举 5 项 |
| merge_precedence_decision | `*_yaml_only` | merge_context 签名反扫 + precedence_rule 来自 YAML 硬编码 |
| evidence_fabrication | `*_invalid_inference_level_rejected` + `*_missing_evidence_id_rejected` | $defs/evidence_item: inference_level / trace_quality 枚举 + evidence_id 非空 |
| final_generation | `*_schema_has_no_generated_text_field` + `*_bundle_rejects_smuggled_completion` | schema 无成稿字段 + bundle 反向硬拦 user_query 明文 |
| intent_classification | `*_llm_string_rejected` (4 LLM 输入) + `*_unsupported_business_intent_not_promoted_to_generate` | classify 只接受 canonical 枚举；非枚举 → needs_review；4 类业务 intent 不静默兜底 |
| content_type_routing | `*_llm_string_rejected` (4 LLM 输入) | route 只接受 canonical id 或 alias；自然语言 / 多选 / 加修饰全 needs_review |

### 设计要点

- **REQUIRED_FORBIDDEN 同源校验**：`test_model_policy_forbidden_tasks_contains_all_8`
  实测 model_policy.yaml `llm_assist.forbidden_tasks` 与本测试 8 项严格一致，
  任意一侧增删都立刻断；防止 yaml 漂移导致测试假绿
- **LLM unavailable rule-only**：4 个核心确定性模块（classify / route / decide_fallback /
  merge_context）在 0 LLM 输入下产出确定性结果；本测试本身跑通即 rule-only 证据
- **测试本身 LLM-free**：反向 grep 本测试源码不允许 `import dashscope/openai/anthropic`，
  避免假绿（曾经的反模式："测 LLM 边界结果反而调了真 LLM"）
- **brand_layer 5 类 LLM 漂移**：自然语言中文、大小写错、连字符、截断、看似合法但不在枚举——
  覆盖 LLM 输出最容易出错的 5 种格式漂移
- **business intent 静默兜底防回归**：4 类 unsupported 业务 intent 必须返回
  `policy_key=None` + `bridge_status=unsupported_intent_no_policy`，不准悄悄映射到 generate

### 回归证据

- `python3 -m pytest knowledge_serving/tests/test_llm_assist_boundary.py -v` → 22 passed
- `python3 -m pytest knowledge_serving/tests/` → 242 passed（220 + 22 新）
- `python3 knowledge_serving/scripts/run_context_retrieval_demo.py --all` → 4/4 PASS（向后兼容）
- `python3 task_cards/validate_task_cards.py` → 57 cards, DAG closed, S0-S13 covered
- `bash knowledge_serving/scripts/lint_no_duplicate_log.sh` → 单 canonical OK

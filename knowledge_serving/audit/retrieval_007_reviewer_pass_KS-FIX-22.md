---
audit_for: KS-RETRIEVAL-007
issued_by: KS-FIX-22
env: local
checked_at: 2026-05-14T20:53:50+08:00
git_commit: 92da0e1e5a650c74cb40613eeaf941ce4e0a3240
evidence_level: runtime_verified
ci_command: python3 -m pytest knowledge_serving/tests/test_merge_fallback.py -v
ci_exit_code: 0
pytest_summary: 25 passed / 0 failed / 0 skipped in 0.12s
artifact_sha256:
  knowledge_serving/serving/brand_overlay_retrieval.py: b0320502fb3962d0c5e5975692f1d66b4896260e7992e15697a785da42357346
  knowledge_serving/serving/merge_context.py: d6fd09dfc01f189b15c02851ceea9c5b6da9cbd7520246ef1b1815cba0e93eab
  knowledge_serving/serving/fallback_decider.py: da77747abb9391dbbef3069e59609acf38871023fe3c83a3edd600f6efa06c1b
  knowledge_serving/tests/test_merge_fallback.py: f3f7aa4d92e874a7456ab5a15dc60e10f28a73a642d913db6952482d2fadba3c
verdict: PASS
---

# KS-RETRIEVAL-007 · 审查员复跑结论（W8 conditional → pass 裁决）

## 1. 审查员 Prompt（来自 KS-RETRIEVAL-007 §10 verbatim）

> 请：1) 5 状态用例齐；2) overlay 不受 user_query 影响；3) precedence brand > domain；4) 输出 pass / fail。
> 阻断项：domain override brand；overlay 被 query 切换。

## 2. 逐项映射（reviewer_prompt_coverage）

| § | 审查要点 | 验证 pytest case | 实测结果 |
|---|---|---|---|
| §10-1 | 5 fallback states 用例齐 | `test_brand_full_applied` / `test_brand_partial_fallback` / `test_domain_only` / `test_blocked_missing_required_brand_fields` / `test_blocked_missing_business_brief` + `test_fallback_states_enum_locked` | 5/5 PASSED；枚举锁定测试同时锁死状态集合 |
| §10-2 | overlay 不受 user_query 影响 | `TestBrandOverlayRetrieval::test_api_does_not_accept_user_query` + `test_rejects_illegal_brand_layer_naming` | PASSED；模块 API 签名不接受自然语言入参 |
| §10-3 | precedence brand > domain | `test_brand_overrides_domain_on_tone` + `test_domain_cannot_override_brand_on_allow_override_false_field` | PASSED |
| §10-阻断-A | domain override brand 必须拒绝 | `test_domain_cannot_override_brand_on_allow_override_false_field` | PASSED |
| §10-阻断-B | overlay 被 query 切换必须拒绝 | `test_api_does_not_accept_user_query` | PASSED |
| 附 · §10-4 | 输出 pass / fail | 本审查员意见 | **PASS** |

## 3. 5 状态枚举源头（fallback_decider.py）

`fallback_decider.py` 已硬编码 5 枚举（`FALLBACK_STATES`）与判定优先级：
1. `blocked_missing_business_brief` （最高优先）
2. `blocked_missing_required_brand_fields`
3. `domain_only`
4. `brand_partial_fallback`
5. `brand_full_applied`

判定路径与 KS-POLICY-001 一致；pytest 显式覆盖每条路径并锁定枚举。

## 4. CI 实测

```
$ python3 -m pytest knowledge_serving/tests/test_merge_fallback.py -v
…
25 passed in 0.11s
```

exit code 0；无 skip，无 fail；满足 §6 对抗测试 "skip>0 pass=0 → fail" 的 fail-closed 反约束。

## 5. 上下游链路最小验证（runtime）

| 维度 | 命令 | 结果 |
|---|---|---|
| 直接上游 KS-RETRIEVAL-005 | `test -f knowledge_serving/audit/validate_serving_governance.report`; `python3 -c "from knowledge_serving.serving.structured_retrieval import _assert_governance_report_green; _assert_governance_report_green()"`; `python3 -m pytest knowledge_serving/tests/test_struct_retrieval.py -v` | **exit 0 / exit 0 / 21 passed** |
| 直接上游 KS-RETRIEVAL-006 | `python3 -m pytest knowledge_serving/tests/test_vector_filter.py -v` | **23 passed / 0 failed / 0 skipped**（exit 0） |
| 直接上游 KS-POLICY-001 | `yamllint -c .yamllint knowledge_serving/policies/fallback_policy.yaml`; `python3 scripts/validate_policy_yaml.py fallback_policy`; `python3 -m pytest knowledge_serving/scripts/tests/test_validate_policy_yaml.py -q` | **exit 0 / exit 0 / 22 passed** |
| 直接上游 KS-POLICY-003 | `python3 scripts/diff_yaml_vs_csv.py merge_precedence_policy` | **diff-ok**（exit 0） |
| 直接下游 KS-RETRIEVAL-008 | `python3 -m pytest knowledge_serving/tests/test_bundle_log.py -v` | **22 passed / 0 failed / 0 skipped**（exit 0） |
| 仓库 serving 树白名单一致性 | `python3 scripts/validate_serving_tree.py` | **OK**（22 §11 / 8 W0-1 / 79 W3-12 / 2 .gitkeep；exit 0） |

直接上游 / 下游的最小关键路径全绿，未破坏链路。

## 7. 裁决

- **verdict**: PASS
- KS-RETRIEVAL-007 §11 DoD 三项满足：3 模块已入 git（commit `4eaa37e`）/ pytest 全绿 / 审查员 pass（本文件）。
- KS-FIX-22 §11 DoD 满足：reviewer md 落盘 / 原卡 §11 勾选 / 审查员 pass / 原卡回写。

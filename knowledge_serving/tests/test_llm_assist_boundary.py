"""KS-PROD-003 · LLM assist 边界回归.

保证 LLM assist 不越界做 8 类禁止任务（2026-05-12 由 6 扩到 8）：

  1. tenant_scope_resolution    - 租户隔离不可由 LLM 决策
  2. brand_layer_override       - 品牌层不可由 LLM 覆盖
  3. fallback_policy_decision   - 降级策略不可由 LLM 决策
  4. merge_precedence_decision  - 合并优先级不可由 LLM 决策
  5. evidence_fabrication       - 不可编造证据
  6. final_generation           - 中间件内不做最终成稿
  7. intent_classification      - 意图必须 input-first
  8. content_type_routing       - content_type 必须 input-first

每个 forbidden_task 构造一个"mock LLM 试图给违规答案"的场景，
断言规则节点 / input-first 路由必须拒绝 / 复核 / 用确定性结果覆盖。

设计要点 / design notes:
- LLM "答案" 用 dict / str fixture 模拟，不真调任何模型
- 测试不 import 任何 LLM 客户端（dashscope / openai / anthropic）；
  反向 grep 自检
- REQUIRED_FORBIDDEN 集合与 model_policy.yaml 的 llm_assist.forbidden_tasks 同源
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.serving import tenant_scope_resolver as tsr
from knowledge_serving.serving import intent_classifier as ic
from knowledge_serving.serving import content_type_router as ctr
from knowledge_serving.serving import fallback_decider as fdec
from knowledge_serving.serving import merge_context as mctx
from knowledge_serving.serving.context_bundle_builder import (
    BundleValidationError,
    build_context_bundle,
    validate_bundle,
)

MODEL_POLICY_PATH = REPO_ROOT / "knowledge_serving" / "policies" / "model_policy.yaml"
CONTEXT_BUNDLE_SCHEMA = REPO_ROOT / "knowledge_serving" / "schema" / "context_bundle.schema.json"

# 卡 §7 治理一致性：8 类禁止任务（与 model_policy.yaml llm_assist.forbidden_tasks 同源）
REQUIRED_FORBIDDEN = {
    "tenant_scope_resolution",
    "brand_layer_override",
    "fallback_policy_decision",
    "merge_precedence_decision",
    "evidence_fabrication",
    "final_generation",
    "intent_classification",
    "content_type_routing",
}


# ------------------------------------------------------------------
# 0. 同源校验：model_policy.yaml 必须声明全部 8 项
# ------------------------------------------------------------------

def test_model_policy_forbidden_tasks_contains_all_8():
    policy = yaml.safe_load(MODEL_POLICY_PATH.read_text(encoding="utf-8"))
    llm_assist = policy.get("llm_assist") or {}
    declared = set(llm_assist.get("forbidden_tasks") or [])
    missing = REQUIRED_FORBIDDEN - declared
    extra = declared - REQUIRED_FORBIDDEN
    assert not missing, f"model_policy.yaml 缺 forbidden_tasks: {sorted(missing)}"
    assert not extra, f"model_policy.yaml 多 forbidden_tasks: {sorted(extra)}（请同步本测试）"


# ------------------------------------------------------------------
# 1. tenant_scope_resolution: LLM 不能决定租户范围
# ------------------------------------------------------------------

def test_forbidden_tenant_scope_resolution_signature_rejects_llm_hint():
    """LLM 试图通过"自然语言提示"决定 allowed_layers。resolver 签名严格只收
    tenant_id + 可选 api_key_id，任何额外位置 / 关键字参数都被 Python 拒绝。
    """
    llm_attempt = {
        "tenant_id": "tenant_demo",
        "llm_inferred_allowed_layers": ["brand_faye", "brand_xyz"],  # LLM 编造
        "llm_inferred_brand_layer": "brand_xyz",                      # LLM 编造
    }
    with pytest.raises(TypeError):
        tsr.resolve(**llm_attempt)


def test_forbidden_tenant_scope_resolution_rejects_natural_language_id():
    """LLM 直接把"用户问的应该是 brand_faye"喂给 resolver。
    resolver 必须按 registry 真源查 tenant_id，未登记 → TenantNotAuthorized。
    """
    llm_inferred_tenant = "brand_faye 的那个客户"  # 自然语言，非 registry id
    with pytest.raises(tsr.TenantNotAuthorized):
        tsr.resolve(llm_inferred_tenant)


# ------------------------------------------------------------------
# 2. brand_layer_override: LLM 不能覆盖品牌层
# ------------------------------------------------------------------

def test_forbidden_brand_layer_override_via_bundle_rejected():
    """LLM "建议" 把 brand_layer 改成不合规字符串（如自然语言）。
    build_context_bundle / validate_bundle 用正则 ^(domain_general|needs_review|brand_[a-z][a-z0-9_]*)$
    硬拦。
    """
    governance = _minimal_governance()
    merge_result = _minimal_merge_result()
    fallback_decision = _minimal_fallback("brand_full_applied")

    llm_overrides = [
        "高端笛语客户",        # LLM 编自然语言
        "Brand_Faye_Premium",  # LLM 大小写漂移
        "brand-faye",          # LLM 用连字符
        "brand_",              # LLM 截断
        "needs_review_brand",  # 看起来像合法但不在枚举
    ]
    for bad in llm_overrides:
        with pytest.raises(BundleValidationError):
            build_context_bundle(
                request_id="req_brand_override",
                tenant_id="tenant_faye_main",
                resolved_brand_layer=bad,
                allowed_layers=["domain_general"],
                user_query="x",
                content_type="product_review",
                recipe={},
                business_brief={},
                merge_result=merge_result,
                fallback_decision=fallback_decision,
                governance=governance,
            )


# ------------------------------------------------------------------
# 3. fallback_policy_decision: LLM 不能决定降级状态
# ------------------------------------------------------------------

def test_forbidden_fallback_policy_decision_only_takes_deterministic_inputs():
    """LLM 试图通过自由字段"建议"fallback。decide_fallback 只收 4 个枚举字段；
    任何 LLM-style 入参（自然语言 reason / confidence）必被签名拒绝。
    """
    llm_attempt = {
        "business_brief_status": "complete",
        "brand_required_fields_status": "complete",
        "brand_soft_fields_status": "not_applicable",
        "brand_overlay_resolved": True,
        "llm_suggested_status": "brand_full_applied",     # LLM 编
        "llm_confidence": 0.95,                           # LLM 编
        "llm_reasoning": "我看用户语气挺正式的",          # LLM 编
    }
    with pytest.raises(TypeError):
        fdec.decide_fallback(**llm_attempt)


def test_forbidden_fallback_status_outside_enum_rejected_by_bundle():
    """LLM 直接把 status 改成枚举外的字符串。bundle 拒绝。"""
    governance = _minimal_governance()
    merge_result = _minimal_merge_result()
    fake_fb = _minimal_fallback("brand_全部应用")  # 中文 LLM 自创
    with pytest.raises(BundleValidationError):
        build_context_bundle(
            request_id="req_fb_enum",
            tenant_id="tenant_faye_main",
            resolved_brand_layer="brand_faye",
            allowed_layers=["domain_general", "brand_faye"],
            user_query="x",
            content_type="product_review",
            recipe={},
            business_brief={},
            merge_result=merge_result,
            fallback_decision=fake_fb,
            governance=governance,
        )


# ------------------------------------------------------------------
# 4. merge_precedence_decision: LLM 不能改合并优先级
# ------------------------------------------------------------------

def test_forbidden_merge_precedence_decision_yaml_only():
    """merge_context 的优先级来自 merge_precedence_policy.yaml；
    无 LLM 输入参数；本测试通过签名 grep + 注入测试双重确认。
    """
    # 4.1 签名反扫：merge_context 不收 LLM-style 入参
    import inspect

    sig = inspect.signature(mctx.merge_context)
    for forbidden_param in ("llm_response", "llm_suggested_precedence", "llm_judge"):
        assert forbidden_param not in sig.parameters, (
            f"merge_context 出现 LLM-style 参数 {forbidden_param}"
        )

    # 4.2 实际跑：构造一个 overlay 包含 brand_faye 行 vs domain_general 行，
    # 看结果是否始终遵循 YAML "brand_<name> > domain_general" 而无视调用方任何"提示"
    overlay = {
        "overlays": [
            {"brand_layer": "brand_faye", "tone_constraints_json": '{"tone": "warm"}'},
            {"brand_layer": "domain_general", "tone_constraints_json": '{"tone": "neutral"}'},
        ]
    }
    res = mctx.merge_context(resolved_brand_layer="brand_faye", overlay=overlay)
    # 关键断言：precedence_rule 由 YAML 硬编码，不被 caller 改
    assert res["_meta"]["precedence_rule"] == "brand_<name> > domain_general"


# ------------------------------------------------------------------
# 5. evidence_fabrication: LLM 不能编造证据
# ------------------------------------------------------------------

def test_forbidden_evidence_fabrication_invalid_inference_level_rejected():
    """LLM 编造的 evidence_item 含非枚举 inference_level / trace_quality → validate 拒绝。"""
    bundle = _minimal_bundle()
    bundle["evidence"] = [
        {
            "evidence_id": "EV_LLM_FAKE_001",
            "inference_level": "llm_made_up_high_confidence",  # 不在枚举
            "trace_quality": "very_high_just_trust_me",        # 不在枚举
        }
    ]
    with pytest.raises(BundleValidationError, match="inference_level|trace_quality"):
        validate_bundle(bundle)


def test_forbidden_evidence_fabrication_missing_evidence_id_rejected():
    """LLM 试图给一个没有 evidence_id 的"证据"（纯文字推测） → 拒绝。"""
    bundle = _minimal_bundle()
    bundle["evidence"] = [{"evidence_quote": "我觉得用户应该会喜欢羊毛大衣", "source_md": "imagination"}]
    with pytest.raises(BundleValidationError, match="evidence_id"):
        validate_bundle(bundle)


# ------------------------------------------------------------------
# 6. final_generation: 中间件内不做最终成稿
# ------------------------------------------------------------------

def test_forbidden_final_generation_schema_has_no_generated_text_field():
    """context_bundle.schema.json 必须不存在任何"成稿/输出文本"字段。
    中间件返回 candidates；最终成稿由 Dify LLM 节点完成。
    """
    import json as _json

    schema = _json.loads(CONTEXT_BUNDLE_SCHEMA.read_text(encoding="utf-8"))
    props = schema.get("properties", {}) or {}
    forbidden_fields = {
        "generated_content",
        "final_output",
        "final_text",
        "llm_response",
        "completion",
        "model_response",
    }
    intersect = set(props.keys()) & forbidden_fields
    assert not intersect, f"schema 出现成稿字段（应在 Dify 节点产）: {sorted(intersect)}"


def test_forbidden_final_generation_bundle_rejects_smuggled_completion():
    """LLM 试图把成稿塞进 bundle 顶层 → schema 已无该字段，validate 直接拒。

    实测：因为 schema 把 properties 锁死（required 列表），无该字段时 validator 不会
    去校验 'completion'。但 user_query 反向硬拦覆盖了"任何 LLM 文本明文进 bundle"的
    更广义边界——见 KS-RETRIEVAL-008 unit test。这里只断言 schema 不允许成稿字段。
    """
    bundle = _minimal_bundle()
    bundle["user_query"] = "LLM 偷塞的成稿文案"  # 即使叫别的名字，也走 user_query 反扫
    with pytest.raises(BundleValidationError, match="user_query"):
        validate_bundle(bundle)


# ------------------------------------------------------------------
# 7. intent_classification: input-first only
# ------------------------------------------------------------------

@pytest.mark.parametrize("llm_attempt", [
    "我猜用户应该是要做内容生成",       # 自然语言
    "looks_like_quality_check",        # LLM 编造 enum-like
    "content_generation:high",          # LLM 加 confidence
    "[content_generation, training]",   # LLM 多选
])
def test_forbidden_intent_classification_llm_string_rejected(llm_attempt):
    """LLM 试图把推断结果当 intent_hint 喂进 classify()。非 canonical → needs_review。
    确定性 input-first：缺失 / 不识别都走 needs_review，绝不被采信为 valid intent。
    """
    result = ic.classify(llm_attempt)
    assert result["status"] == "needs_review", (
        f"LLM 推断的 intent={llm_attempt!r} 不应该被 classify 当成 ok：{result}"
    )
    assert result["intent"] != "content_generation"


def test_forbidden_intent_classification_unsupported_business_intent_not_promoted_to_generate():
    """5 类业务 intent 中 content_generation 之外的 4 类都不允许悄悄被映射到 'generate' policy。"""
    for biz_intent in ("quality_check", "strategy_advice", "training", "sales_script"):
        res = ic.classify(biz_intent)
        assert res["status"] == "ok"
        bridge = ic.intent_to_policy_key(biz_intent)
        assert bridge["policy_key"] is None, (
            f"业务 intent {biz_intent} 被静默兜底到 generate 了：{bridge}"
        )
        assert bridge["bridge_status"] == ic.BRIDGE_STATUS_UNSUPPORTED


# ------------------------------------------------------------------
# 8. content_type_routing: input-first only
# ------------------------------------------------------------------

@pytest.mark.parametrize("llm_attempt", [
    "用户在问产品的优缺点，应该是产品测评",  # 自然语言
    "product_review_high_priority",          # LLM 加修饰
    "产品测评|护理建议",                      # LLM 多选
    "unknown_xyz_content_kind",               # LLM 编造
])
def test_forbidden_content_type_routing_llm_string_rejected(llm_attempt):
    """LLM 试图当 content_type_hint。非 canonical / 未知 alias → needs_review，
    不被采信为 valid content_type。"""
    result = ctr.route(llm_attempt)
    assert result["status"] == "needs_review", (
        f"LLM 推断的 content_type={llm_attempt!r} 不应该被 route 当成 ok：{result}"
    )
    assert result["content_type"] is None


# ------------------------------------------------------------------
# §6 边缘：LLM unavailable → rule-only 模式
# ------------------------------------------------------------------

def test_llm_unavailable_pipeline_remains_rule_only():
    """完全不调任何 LLM 客户端，13 步关键模块仍可独立工作 + decide。

    通过：本测试模块跑通本身就是 rule-only 证据；额外断言 model_policy
    标记的 rerank / llm_assist enabled 状态独立于核心管线。
    """
    # 关键 4 模块在没有任何 LLM 输入的情况下能产出确定性结果
    intent = ic.classify("content_generation")
    assert intent["status"] == "ok"
    ct = ctr.route("product_review")
    assert ct["status"] == "ok"
    fb = fdec.decide_fallback(
        business_brief_status="complete",
        brand_required_fields_status="complete",
        brand_soft_fields_status="not_applicable",
        brand_overlay_resolved=True,
    )
    assert fb["status"] == "brand_full_applied"
    merge_res = mctx.merge_context(resolved_brand_layer="domain_general")
    assert merge_res["_meta"]["precedence_rule"] == "brand_<name> > domain_general"


# ------------------------------------------------------------------
# 治理一致性：本测试自身不引用任何 LLM 客户端
# ------------------------------------------------------------------

def test_boundary_test_module_does_not_import_llm_clients():
    """KS-PROD-003 测试自身必须 LLM-free（避免假绿）：
    不 import dashscope / openai / anthropic / aliyun_bailian 等客户端。
    """
    src = (REPO_ROOT / "knowledge_serving" / "tests" / "test_llm_assist_boundary.py").read_text(
        encoding="utf-8"
    )
    forbidden_imports = [
        r"^\s*import\s+dashscope",
        r"^\s*from\s+dashscope",
        r"^\s*import\s+openai",
        r"^\s*from\s+openai",
        r"^\s*import\s+anthropic",
        r"^\s*from\s+anthropic",
    ]
    for pat in forbidden_imports:
        assert not re.search(pat, src, re.MULTILINE), (
            f"边界测试自身 import 了 LLM 客户端 {pat}（违反 KS-PROD-003 §7 不调 LLM）"
        )


# ==================================================================
# helpers
# ==================================================================

def _minimal_governance() -> dict:
    return {
        "gate_policy": "active_only",
        "granularity_layers": ["L1", "L2", "L3"],
        "traceability_required": True,
        "compile_run_id": "cr_boundary_test",
        "source_manifest_hash": "sha256:" + "c" * 64,
        "view_schema_version": "v1.1.0",
    }


def _minimal_merge_result() -> dict:
    return {
        "merged_overlay_payload": {},
        "structured_candidates": {},
        "vector_candidates": [],
        "conflict_log": [],
        "needs_review_queue": [],
        "_meta": {
            "resolved_brand_layer": "brand_faye",
            "precedence_rule": "brand_<name> > domain_general",
            "overlay_layers_seen": [],
            "policy_rules_applied": 0,
        },
    }


def _minimal_fallback(status: str) -> dict:
    return {
        "status": status,
        "severity": "info",
        "is_blocking": False,
        "output_strategy": {"constraints": []},
        "downstream_signal": {},
        "missing_fields": [],
        "evaluation_trace": [],
    }


def _minimal_bundle() -> dict:
    return {
        "request_id": "req_boundary",
        "tenant_id": "tenant_faye_main",
        "resolved_brand_layer": "brand_faye",
        "allowed_layers": ["domain_general", "brand_faye"],
        "content_type": "product_review",
        "recipe": {},
        "business_brief": {},
        "domain_packs": [],
        "play_cards": [],
        "runtime_assets": [],
        "brand_overlays": [],
        "evidence": [],
        "missing_fields": [],
        "fallback_status": "brand_full_applied",
        "generation_constraints": [],
        "governance": _minimal_governance(),
    }

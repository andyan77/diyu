"""KS-RETRIEVAL-007 · brand_overlay_retrieval + merge_context + fallback_decider 测试.

覆盖卡 §6 对抗测试 + §10 审查员阻断项：
- brand_overlay_retrieval：禁止 user_query 自然语言切换 overlay（API 不接受 query 入参）
- merge_context：domain_general 不许 override brand（precedence 严格）
- merge_context：conflict_action=block 命中真冲突走 conflict_log（caller 可选 raise）
- fallback_decider：五状态枚举各 ≥1 用例 + business_brief 优先级最高
- 不调 LLM；不写 clean_output
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.serving import brand_overlay_retrieval as bor  # noqa: E402
from knowledge_serving.serving import fallback_decider as fbd  # noqa: E402
from knowledge_serving.serving import merge_context as mc  # noqa: E402


# ========================================================================
# Section 1 · brand_overlay_retrieval
# ========================================================================

class TestBrandOverlayRetrieval:
    def test_brand_faye_resolves_overlays(self):
        r = bor.brand_overlay_retrieve(resolved_brand_layer="brand_faye")
        assert r["overlay_resolved"] is True
        assert len(r["overlays"]) >= 1
        assert all(row["brand_layer"] == "brand_faye" for row in r["overlays"])
        assert all(row["gate_status"] == "active" for row in r["overlays"])
        assert all(row["granularity_layer"] in {"L1", "L2", "L3"} for row in r["overlays"])

    def test_domain_general_short_circuits_no_overlay(self):
        r = bor.brand_overlay_retrieve(resolved_brand_layer="domain_general")
        assert r["overlay_resolved"] is False
        assert r["overlays"] == []
        assert r["_meta"].get("short_circuit_reason") == "domain_general_has_no_overlay"

    def test_unknown_brand_zero_hits_but_not_short_circuit(self):
        r = bor.brand_overlay_retrieve(resolved_brand_layer="brand_doesnotexist")
        assert r["overlay_resolved"] is False
        assert r["overlays"] == []
        # 不应该是 short_circuit；是正常 filter 后 0 命中
        assert r["_meta"].get("short_circuit_reason") is None

    def test_rejects_illegal_brand_layer_naming(self):
        for bad in ("FAYE", "Faye", "brand-faye", "brand_FAYE", ""):
            with pytest.raises(ValueError):
                bor.brand_overlay_retrieve(resolved_brand_layer=bad)

    def test_api_does_not_accept_user_query(self):
        """硬纪律：禁止从自然语言切换 overlay。API 签名层就不接受 query 入参。"""
        import inspect
        sig = inspect.signature(bor.brand_overlay_retrieve)
        forbidden = {"query", "user_query", "natural_language", "text"}
        assert forbidden.isdisjoint(sig.parameters.keys()), (
            "brand_overlay_retrieve 不得接受任何自然语言入参（防自然语言切换 overlay）"
        )

    def test_content_type_filter(self, tmp_path):
        # 构造一个 mini overlay view 验证 content_type 过滤
        view = tmp_path / "ov.csv"
        view.write_text(
            "source_pack_id,brand_layer,granularity_layer,gate_status,target_content_type,target_pack_id,overlay_id,brand_overlay_kind,tone_constraints_json,output_structure_json,required_knowledge_json,forbidden_words,signature_phrases,precedence,fallback_behavior\n"
            "p1,brand_faye,L1,active,coat_brief,P1,O1,brand_voice,{},{},{},[],[],1,use_domain_general\n"
            "p2,brand_faye,L1,active,,P2,O2,brand_voice,{},{},{},[],[],1,use_domain_general\n"
            "p3,brand_faye,L1,active,shirt_brief,P3,O3,brand_voice,{},{},{},[],[],1,use_domain_general\n",
            encoding="utf-8",
        )
        r = bor.brand_overlay_retrieve(resolved_brand_layer="brand_faye",
                                       content_type="coat_brief",
                                       overlay_view_path=view)
        # 命中：p1 (匹配) + p2 (target_content_type 空 = 通用)；不命中：p3
        ids = sorted(row["overlay_id"] for row in r["overlays"])
        assert ids == ["O1", "O2"]


# ========================================================================
# Section 2 · merge_context（precedence + conflict）
# ========================================================================

def _make_overlay_row(*, brand_layer, tone=None, brand_values=None, forbidden_words=None,
                     signature_phrases=None, founder_profile=None):
    tone_obj = {}
    if tone is not None:
        tone_obj["tone"] = tone
    if brand_values is not None:
        tone_obj["brand_values"] = brand_values
    struct_obj = {}
    if founder_profile is not None:
        struct_obj["founder_profile"] = founder_profile
    return {
        "brand_layer": brand_layer,
        "gate_status": "active",
        "granularity_layer": "L1",
        "tone_constraints_json": json.dumps(tone_obj),
        "output_structure_json": json.dumps(struct_obj),
        "forbidden_words": json.dumps(forbidden_words or []),
        "signature_phrases": json.dumps(signature_phrases or []),
    }


class TestMergeContext:
    def test_brand_only_no_conflict(self):
        ov = {"overlays": [_make_overlay_row(brand_layer="brand_faye", tone="elegant")]}
        r = mc.merge_context(resolved_brand_layer="brand_faye", overlay=ov)
        assert r["merged_overlay_payload"].get("tone") == "elegant"
        assert r["conflict_log"] == []
        assert r["needs_review_queue"] == []
        assert r["_meta"]["precedence_rule"] == "brand_<name> > domain_general"

    def test_brand_overrides_domain_on_tone(self):
        """allow_override=true 字段（tone）：brand 胜，domain 被记录。"""
        ov = {"overlays": [
            _make_overlay_row(brand_layer="brand_faye", tone="elegant"),
            _make_overlay_row(brand_layer="domain_general", tone="DOMAIN_TRY_OVERRIDE"),
        ]}
        r = mc.merge_context(resolved_brand_layer="brand_faye", overlay=ov)
        assert r["merged_overlay_payload"]["tone"] == "elegant"
        assert any(e["conflict_key"] == "tone" and e["decision"] == "brand_overrides_domain"
                   for e in r["conflict_log"])

    def test_domain_cannot_override_brand_on_allow_override_false_field(self):
        """allow_override=false + action=block (brand_values)：双方都有 → 走 blocked log。"""
        ov = {"overlays": [
            _make_overlay_row(brand_layer="brand_faye", brand_values="brand_v"),
            _make_overlay_row(brand_layer="domain_general", brand_values="domain_v_try"),
        ]}
        r = mc.merge_context(resolved_brand_layer="brand_faye", overlay=ov)
        # brand 胜
        assert r["merged_overlay_payload"]["brand_values"] == "brand_v"
        # 真冲突落 conflict_log
        assert any(e["conflict_key"] == "brand_values" and e["decision"] == "blocked"
                   for e in r["conflict_log"])

    def test_block_raises_when_requested(self):
        ov = {"overlays": [
            _make_overlay_row(brand_layer="brand_faye", brand_values="brand_v"),
            _make_overlay_row(brand_layer="domain_general", brand_values="domain_v"),
        ]}
        with pytest.raises(mc.MergeConflictBlocked):
            mc.merge_context(resolved_brand_layer="brand_faye", overlay=ov, block_raises=True)

    def test_append_action_concatenates_brand_then_domain(self):
        """forbidden_words 是 append；brand 在前，domain 在后，去重。"""
        ov = {"overlays": [
            _make_overlay_row(brand_layer="brand_faye", forbidden_words=["A", "B"]),
            _make_overlay_row(brand_layer="domain_general", forbidden_words=["B", "C"]),
        ]}
        r = mc.merge_context(resolved_brand_layer="brand_faye", overlay=ov)
        fw = r["merged_overlay_payload"]["forbidden_words"]
        # 保序去重：A, B 来自 brand，C 来自 domain
        assert fw == ["A", "B", "C"]
        # append 不进 conflict_log
        assert not any(e["conflict_key"] == "forbidden_words" for e in r["conflict_log"])

    def test_needs_review_action_pushes_to_queue(self):
        """tagline 是 needs_review；双方有取值时进 needs_review_queue。"""
        ov = {"overlays": [
            _make_overlay_row(brand_layer="brand_faye"),  # 占位，tone_constraints_json 内填 tagline
            _make_overlay_row(brand_layer="domain_general"),
        ]}
        # 手动注入 tagline
        ov["overlays"][0]["tone_constraints_json"] = json.dumps({"tagline": "brand_tag"})
        ov["overlays"][1]["tone_constraints_json"] = json.dumps({"tagline": "domain_tag"})
        r = mc.merge_context(resolved_brand_layer="brand_faye", overlay=ov)
        assert any(item["conflict_key"] == "tagline" for item in r["needs_review_queue"])

    def test_empty_overlay_yields_empty_payload_no_crash(self):
        r = mc.merge_context(resolved_brand_layer="domain_general",
                             overlay={"overlays": []})
        assert r["merged_overlay_payload"] == {}
        assert r["conflict_log"] == []
        assert r["needs_review_queue"] == []

    def test_no_llm_token_in_source(self):
        """硬纪律：源文件不得调 LLM。"""
        src = (REPO_ROOT / "knowledge_serving" / "serving" / "merge_context.py").read_text(encoding="utf-8")
        for forbidden in ("anthropic", "openai", "dashscope.Generation", "llm_judge"):
            assert forbidden not in src, f"merge_context.py 不得调 {forbidden}"


# ========================================================================
# Section 3 · fallback_decider · 5 状态用例全覆盖
# ========================================================================

class TestFallbackDecider:
    def test_brand_full_applied(self):
        d = fbd.decide_fallback(
            business_brief_status="complete",
            brand_required_fields_status="complete",
            brand_soft_fields_status="complete",
            brand_overlay_resolved=True,
        )
        assert d["status"] == "brand_full_applied"
        assert d["is_blocking"] is False
        assert d["downstream_signal"]["log_marker"] == "FALLBACK_NONE_BRAND_FULL"

    def test_brand_partial_fallback(self):
        d = fbd.decide_fallback(
            business_brief_status="complete",
            brand_required_fields_status="complete",
            brand_soft_fields_status="partial_missing",
            brand_overlay_resolved=True,
        )
        assert d["status"] == "brand_partial_fallback"
        assert d["is_blocking"] is False

    def test_domain_only(self):
        d = fbd.decide_fallback(
            business_brief_status="complete",
            brand_required_fields_status="not_applicable",
            brand_soft_fields_status="not_applicable",
            brand_overlay_resolved=False,
        )
        assert d["status"] == "domain_only"
        assert d["output_strategy"]["brand_layer_scope"] == ["domain_general"]

    def test_blocked_missing_required_brand_fields(self):
        d = fbd.decide_fallback(
            business_brief_status="complete",
            brand_required_fields_status="missing",
            brand_soft_fields_status="complete",
            brand_overlay_resolved=True,
        )
        assert d["status"] == "blocked_missing_required_brand_fields"
        assert d["is_blocking"] is True
        assert d["output_strategy"]["emit_ask_user_question"] is True

    def test_blocked_missing_business_brief(self):
        d = fbd.decide_fallback(
            business_brief_status="missing",
            brand_required_fields_status="complete",
            brand_soft_fields_status="complete",
            brand_overlay_resolved=True,
        )
        assert d["status"] == "blocked_missing_business_brief"
        assert d["is_blocking"] is True

    def test_business_brief_missing_dominates_other_failures(self):
        """优先级最高：即使其他字段也缺，brief missing 仍是 final state。"""
        d = fbd.decide_fallback(
            business_brief_status="missing",
            brand_required_fields_status="missing",
            brand_soft_fields_status="partial_missing",
            brand_overlay_resolved=False,
        )
        assert d["status"] == "blocked_missing_business_brief"

    def test_required_missing_dominates_overlay_miss(self):
        d = fbd.decide_fallback(
            business_brief_status="complete",
            brand_required_fields_status="missing",
            brand_soft_fields_status="complete",
            brand_overlay_resolved=False,
        )
        assert d["status"] == "blocked_missing_required_brand_fields"

    def test_rejects_illegal_brief_status(self):
        with pytest.raises(ValueError):
            fbd.decide_fallback(
                business_brief_status="unknown",
                brand_required_fields_status="complete",
                brand_soft_fields_status="complete",
                brand_overlay_resolved=True,
            )

    def test_rejects_illegal_required_status(self):
        with pytest.raises(ValueError):
            fbd.decide_fallback(
                business_brief_status="complete",
                brand_required_fields_status="dunno",
                brand_soft_fields_status="complete",
                brand_overlay_resolved=True,
            )

    def test_fallback_states_enum_locked(self):
        """枚举 5 状态严格 == policy.runtime_contract.log_field_enum。"""
        import yaml
        policy = yaml.safe_load((REPO_ROOT / "knowledge_serving" / "policies" / "fallback_policy.yaml").read_text())
        assert set(fbd.FALLBACK_STATES) == set(policy["runtime_contract"]["log_field_enum"])

    def test_no_llm_in_decision(self):
        src = (REPO_ROOT / "knowledge_serving" / "serving" / "fallback_decider.py").read_text(encoding="utf-8")
        for forbidden in ("anthropic", "openai", "dashscope.Generation", "llm_judge",
                          "prompt_inference", "model_predicted_intent"):
            assert forbidden not in src, f"fallback_decider.py 不得调 {forbidden}"

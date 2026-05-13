"""KS-DIFY-ECS-009 · guardrail 检查器测试 / guardrail tests.

覆盖卡 §6 五条对抗性 / 边缘性用例 + 确定性 + no-LLM 源码扫描 + brief 白名单豁免。
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from knowledge_serving.serving import guardrail as gr

MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "serving" / "guardrail.py"
)


def _full_brief() -> dict:
    return {
        "sku": "FAYE-OW-2026SS-001",
        "category": "outerwear",
        "season": "spring",
        "channel": ["xiaohongshu"],
        "price_band": {"currency": "CNY", "min": 1280, "max": 1680},
    }


def _bundle_for(content_type: str, extra_keys: dict | None = None) -> dict:
    """构造满足 required_evidence 的最小 bundle。"""
    keys = dict(extra_keys or {})
    return {
        "content_type": content_type,
        "domain_packs": [keys] if keys else [],
        "play_cards": [],
        "runtime_assets": [],
        "brand_overlays": [],
        "evidence": [],
    }


# ---------- §6 case 1: 干净文本 → pass ----------
def test_clean_text_passes():
    text = "今春主推外套，版型挺括，适合通勤穿搭。"
    bundle = _bundle_for("outfit_of_the_day", {"outfit_pack": "op-001"})
    res = gr.check(text, bundle, _full_brief())
    assert res["status"] == "pass"
    assert res["violations"] == []


# ---------- §6 case 2: 创始人编造 → blocked ----------
def test_founder_fabrication_blocked():
    text = "笛语的创始人是某位常春藤毕业的设计师，born in 1985。"
    bundle = _bundle_for(
        "founder_ip",
        {"brand_values": "bv-1", "founder_profile": "fp-1"},
    )
    res = gr.check(text, bundle, _full_brief())
    assert res["status"] == "blocked"
    cats = {v["category"] for v in res["violations"]}
    assert gr.V_FORBIDDEN in cats
    fp_ids = {v.get("fp_id") for v in res["violations"]}
    assert "FP-FOUNDER-FABRICATION" in fp_ids


# ---------- §6 case 3: SKU 不在 brief → blocked ----------
def test_sku_not_in_brief_blocked():
    text = "本款型号 SKU 99999 限时优惠。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "pp-1"})
    res = gr.check(text, bundle, _full_brief())
    assert res["status"] == "blocked"
    cats = [v["category"] for v in res["violations"]]
    assert gr.V_SKU_FABRICATION in cats


# ---------- §6 case 3b: SKU 在 brief → 放行 ----------
def test_sku_match_brief_passes():
    brief = _full_brief()
    text = f"SKU {brief['sku']} 已到货。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "pp-1"})
    res = gr.check(text, bundle, brief)
    # SKU 正则会命中 'SKU FAYE-OW-2026SS-001'，但 hit 含 brief.sku → 放行
    assert res["status"] == "pass"


# ---------- 对抗：连字符字母 SKU 不在 brief → blocked（reviewer finding 2）----------
def test_alphanumeric_sku_not_in_brief_blocked():
    text = "型号 SKU FAYE-OW-2026SS-999 限时优惠。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "p"})
    res = gr.check(text, bundle, _full_brief())
    assert res["status"] == "blocked"
    cats = [v["category"] for v in res["violations"]]
    assert gr.V_SKU_FABRICATION in cats


# ---------- 对抗：货号 + 字母数字连字符 不在 brief → blocked ----------
def test_huohao_alphanumeric_not_in_brief_blocked():
    text = "货号 FAYE-OW-2026SS-999 上新。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "p"})
    res = gr.check(text, bundle, _full_brief())
    assert res["status"] == "blocked"
    cats = [v["category"] for v in res["violations"]]
    assert gr.V_SKU_FABRICATION in cats


# ---------- 对抗：货号: + brief.sku → 放行 ----------
def test_huohao_match_brief_passes():
    brief = _full_brief()
    text = f"货号：{brief['sku']} 春季款。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "p"})
    res = gr.check(text, bundle, brief)
    assert res["status"] == "pass"


# ---------- 对抗：brief.sku 为空字符串 → 不能作为白名单依据 ----------
def test_empty_string_sku_brief_blocks_all_sku_shapes():
    brief = _full_brief()
    brief["sku"] = ""
    text = "型号 SKU FAYE-OW-2026SS-999 上新。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "p"})
    res = gr.check(text, bundle, brief)
    assert res["status"] == "blocked"
    cats = [v["category"] for v in res["violations"]]
    # 既要因 SKU 命中而 blocked，也要因 brief.sku 空字符串触发 missing_brief
    assert gr.V_SKU_FABRICATION in cats
    assert gr.V_MISSING_BRIEF in cats
    missing_fields = {v.get("field") for v in res["violations"] if v["category"] == gr.V_MISSING_BRIEF}
    assert "sku" in missing_fields


# ---------- §6 case 4: forbidden_pattern 命中（库存编造）→ blocked ----------
def test_inventory_fabrication_blocked():
    text = "库存仅剩 3 件，售罄在即！"
    bundle = _bundle_for("product_copy_general", {"product_pack": "pp-1"})
    res = gr.check(text, bundle, _full_brief())
    assert res["status"] == "blocked"
    fp_ids = {v.get("fp_id") for v in res["violations"]}
    assert "FP-INVENTORY-FABRICATION" in fp_ids


# ---------- §6 case 5: 空文本 → blocked ----------
def test_empty_text_blocked():
    res = gr.check("", _bundle_for("product_copy_general", {"product_pack": "p"}), _full_brief())
    assert res["status"] == "blocked"
    assert any(v["category"] == gr.V_EMPTY for v in res["violations"])

    res2 = gr.check("   \n  ", _bundle_for("product_copy_general", {"product_pack": "p"}), _full_brief())
    assert res2["status"] == "blocked"
    assert any(v["category"] == gr.V_EMPTY for v in res2["violations"])


# ---------- 价格：在 price_band 内 → 放行 ----------
def test_price_within_band_passes():
    text = "本款建议价位 ¥1380，性价比高。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "p"})
    res = gr.check(text, bundle, _full_brief())
    assert res["status"] == "pass"


# ---------- 价格：超出 price_band → blocked ----------
def test_price_out_of_band_blocked():
    text = "本款建议价位 ¥9999。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "p"})
    res = gr.check(text, bundle, _full_brief())
    assert res["status"] == "blocked"
    cats = [v["category"] for v in res["violations"]]
    assert gr.V_PRICE_FABRICATION in cats


# ---------- 价格：brief 无 price_band → 任意价格视为编造 ----------
def test_price_without_band_blocked():
    brief = _full_brief()
    del brief["price_band"]
    text = "本款 ¥1380。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "p"})
    res = gr.check(text, bundle, brief)
    assert res["status"] == "blocked"


# ---------- required_evidence：content_type 缺 hard_field → blocked ----------
def test_missing_required_evidence_blocked():
    text = "今春主推外套。"
    bundle = _bundle_for("founder_ip", {"brand_values": "bv-only"})  # 缺 founder_profile
    res = gr.check(text, bundle, _full_brief())
    assert res["status"] == "blocked"
    cats = [v for v in res["violations"] if v["category"] == gr.V_MISSING_EVIDENCE]
    assert any(v["field"] == "founder_profile" for v in cats)


# ---------- required_evidence：content_type 不在策略 → 不强制 ----------
def test_unknown_content_type_not_enforced_for_evidence():
    text = "干净文本。"
    bundle = _bundle_for("ad_hoc_unknown_type", {})
    res = gr.check(text, bundle, _full_brief())
    # 不应因 content_type 不在 required_evidence 中而 blocked
    assert all(v["category"] != gr.V_MISSING_EVIDENCE for v in res["violations"])
    assert res["status"] == "pass"


# ---------- business_brief hard 缺失 → blocked ----------
def test_missing_brief_hard_field_blocked():
    brief = _full_brief()
    del brief["sku"]
    text = "干净文本。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "p"})
    res = gr.check(text, bundle, brief)
    assert res["status"] == "blocked"
    miss = [v for v in res["violations"] if v["category"] == gr.V_MISSING_BRIEF]
    assert any(v["field"] == "sku" for v in miss)


# ---------- 入参类型错 ----------
def test_type_errors():
    with pytest.raises(TypeError):
        gr.check(None, {}, {})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        gr.check("x", None, {})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        gr.check("x", {}, None)  # type: ignore[arg-type]


# ---------- 确定性：同入参 5 次结果一致 ----------
def test_deterministic_repeat():
    text = "库存仅剩 2 件。"
    bundle = _bundle_for("product_copy_general", {"product_pack": "p"})
    brief = _full_brief()
    results = [
        gr.check(text, copy.deepcopy(bundle), copy.deepcopy(brief))
        for _ in range(5)
    ]
    for r in results[1:]:
        assert r == results[0]


# ---------- no-LLM 源码扫描 ----------
def test_no_llm_in_source():
    src = MODULE_PATH.read_text(encoding="utf-8").lower()
    for kw in ("dashscope", "openai", "anthropic", "completion(", "chat("):
        assert kw not in src, f"forbidden keyword {kw!r} in guardrail source"

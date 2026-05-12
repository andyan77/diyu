"""KS-RETRIEVAL-003 · business_brief_checker tests.

覆盖卡 §6 全部 8 项 + 确定性 + no-LLM 源码扫描。
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
from jsonschema import ValidationError

from knowledge_serving.serving import business_brief_checker as bbc

MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "serving" / "business_brief_checker.py"
)


def _full_brief() -> dict:
    """完整合法 brief / fully valid brief。"""
    return {
        "sku": "FAYE-OW-2026SS-001",
        "category": "outerwear",
        "season": "spring",
        "channel": ["xiaohongshu", "douyin"],
        "inventory_pressure": "normal",
        "price_band": {"currency": "CNY", "min": 1280, "max": 1680},
        "cta": "立即下单 / shop now",
        "compliance_redlines": ["不要医疗承诺", "不要绝对化用语"],
    }


# ---------- §6 case 1: 完整合法 ----------
def test_full_valid_brief_returns_ok():
    res = bbc.check(_full_brief())
    assert res["status"] == "ok"
    assert res["missing_fields"] == []
    assert res["blocked_fields"] == []


# ---------- §6 case 2: 缺 SKU → blocked ----------
def test_missing_sku_blocks():
    brief = _full_brief()
    del brief["sku"]
    res = bbc.check(brief)
    assert res["status"] == "blocked_missing_business_brief"
    assert "sku" in res["blocked_fields"]


# ---------- §6 case 3: 缺 CTA（soft） ----------
def test_missing_cta_soft_warning():
    brief = _full_brief()
    del brief["cta"]
    res = bbc.check(brief)
    assert res["status"] == "ok"
    assert "cta" in res["missing_fields"]
    assert res["blocked_fields"] == []


# ---------- §6 case 4: 缺 inventory_pressure（soft） ----------
def test_missing_inventory_pressure_soft_warning():
    brief = _full_brief()
    del brief["inventory_pressure"]
    res = bbc.check(brief)
    assert res["status"] == "ok"
    assert "inventory_pressure" in res["missing_fields"]


# ---------- §6 case 5: 缺 price_band（soft） ----------
def test_missing_price_band_soft_warning():
    brief = _full_brief()
    del brief["price_band"]
    res = bbc.check(brief)
    assert res["status"] == "ok"
    assert "price_band" in res["missing_fields"]


# ---------- §6 case 6: compliance_redlines=[] ----------
def test_empty_compliance_redlines_warning():
    brief = _full_brief()
    brief["compliance_redlines"] = []
    res = bbc.check(brief)
    assert res["status"] == "ok"
    assert "compliance_redlines" in res["missing_fields"]
    assert res["blocked_fields"] == []


# ---------- §6 case 7: 缺 compliance_redlines 字段 ----------
def test_missing_compliance_redlines_field_warning():
    brief = _full_brief()
    del brief["compliance_redlines"]
    res = bbc.check(brief)
    assert res["status"] == "ok"
    assert "compliance_redlines" in res["missing_fields"]


# ---------- §6 case 8: 非法 season → raise ----------
def test_illegal_season_raises():
    brief = _full_brief()
    brief["season"] = "monsoon"
    with pytest.raises(ValidationError):
        bbc.check(brief)


# ---------- §6 case 9: 空 brief → blocked，所有 hard required ----------
def test_empty_brief_blocks_all_hard_required():
    res = bbc.check({})
    assert res["status"] == "blocked_missing_business_brief"
    for key in ("sku", "category", "season", "channel"):
        assert key in res["blocked_fields"]


# ---------- §6 case 10: 多余字段 → warning ----------
def test_unknown_field_warning_not_blocked():
    brief = _full_brief()
    brief["bogus"] = "x"
    res = bbc.check(brief)
    assert res["status"] == "ok"
    assert "unknown:bogus" in res["missing_fields"]
    assert res["blocked_fields"] == []


# ---------- 确定性：同入参 5 次结果一致 ----------
def test_deterministic_repeat():
    brief = _full_brief()
    del brief["cta"]
    results = [bbc.check(copy.deepcopy(brief)) for _ in range(5)]
    first = results[0]
    for r in results[1:]:
        assert r == first


# ---------- no-LLM 源码扫描 ----------
def test_no_llm_in_source():
    src = MODULE_PATH.read_text(encoding="utf-8").lower()
    for kw in ("dashscope", "openai", "anthropic", "llm", "completion", "chat("):
        assert kw not in src, f"forbidden keyword {kw!r} found in checker source"


# ---------- 额外：hard required + soft 同时缺，blocked 优先但 soft 仍报 ----------
def test_blocked_with_soft_missing():
    brief = _full_brief()
    del brief["sku"]
    del brief["cta"]
    res = bbc.check(brief)
    assert res["status"] == "blocked_missing_business_brief"
    assert "sku" in res["blocked_fields"]
    assert "cta" in res["missing_fields"]


# ---------- 额外：price_band 内部字段缺 → raise ----------
def test_price_band_incomplete_raises():
    brief = _full_brief()
    brief["price_band"] = {"currency": "CNY", "min": 100}  # 缺 max
    with pytest.raises(ValidationError):
        bbc.check(brief)


# ---------- 额外：channel 空数组 → raise（minItems=1） ----------
def test_channel_empty_raises():
    brief = _full_brief()
    brief["channel"] = []
    with pytest.raises(ValidationError):
        bbc.check(brief)

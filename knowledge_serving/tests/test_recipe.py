"""KS-RETRIEVAL-004 · recipe_selector + requirement_checker tests.

覆盖卡 §6 全部用例 + no-LLM 源码扫描 + 确定性。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from knowledge_serving.serving import recipe_selector as rs
from knowledge_serving.serving import requirement_checker as rc

SERVING_DIR = Path(__file__).resolve().parent.parent / "serving"
MODULE_PATHS = [
    SERVING_DIR / "recipe_selector.py",
    SERVING_DIR / "requirement_checker.py",
]


# ---------- recipe_selector ----------


def test_select_basic_match_returns_recipe_row():
    recipe = rs.select("behind_the_scenes", "xiaohongshu", "text")
    assert recipe["content_type"] == "behind_the_scenes"
    assert recipe["platform"] == "xiaohongshu"
    assert recipe["output_format"] == "text"
    assert recipe["gate_status"] == "active"
    assert recipe["review_status"] == "approved"
    # JSON 字段被 parse 成 dict / list
    assert isinstance(recipe["retrieval_plan_json"], dict)
    assert isinstance(recipe["required_views"], list)


def test_select_deterministic_repeat():
    a = rs.select("daily_fragment", "xiaohongshu", "text")
    b = rs.select("daily_fragment", "xiaohongshu", "text")
    assert a["recipe_id"] == b["recipe_id"]


def test_select_no_match_raises():
    with pytest.raises(rs.RecipeNotFoundError):
        rs.select("behind_the_scenes", "douyin", "text")
    with pytest.raises(rs.RecipeNotFoundError):
        rs.select("nonexistent_ct", "xiaohongshu", "text")


def test_select_rejects_empty_or_non_str_inputs():
    with pytest.raises(TypeError):
        rs.select("", "xiaohongshu", "text")
    with pytest.raises(TypeError):
        rs.select("behind_the_scenes", None, "text")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        rs.select("behind_the_scenes", "xiaohongshu", 123)  # type: ignore[arg-type]


def test_select_brand_layer_filter_falls_back_to_domain_general():
    # 当前 view 内全部行均为 domain_general；传 brand_faye 应仍命中 domain_general 行
    recipe = rs.select(
        "outfit_of_the_day",
        "xiaohongshu",
        "text",
        brand_layer="brand_faye",
    )
    assert recipe["brand_layer"] == "domain_general"
    assert recipe["content_type"] == "outfit_of_the_day"


def test_priority_key_prefers_active_approved_and_brand_match():
    # 构造模拟多 recipe 命中场景，验证 _priority_key 排序
    rows = [
        {"gate_status": "deprecated", "review_status": "approved",
         "brand_layer": "domain_general", "recipe_id": "R-1"},
        {"gate_status": "active", "review_status": "pending",
         "brand_layer": "domain_general", "recipe_id": "R-2"},
        {"gate_status": "active", "review_status": "approved",
         "brand_layer": "brand_faye", "recipe_id": "R-3"},
        {"gate_status": "active", "review_status": "approved",
         "brand_layer": "domain_general", "recipe_id": "R-4"},
    ]
    rows.sort(key=lambda r: rs._priority_key(r, brand_layer="brand_faye"))
    assert rows[0]["recipe_id"] == "R-3"
    assert rows[-1]["recipe_id"] == "R-1"


# ---------- requirement_checker ----------


def _recipe_for(ct: str) -> dict:
    return rs.select(ct, "xiaohongshu", "text")


def test_check_hard_missing_blocks():
    # outfit_of_the_day 要求 outfit_pack (hard)
    recipe = _recipe_for("outfit_of_the_day")
    res = rc.check(recipe, available_fields=[])
    assert res["fallback_status"] == rc.STATUS_BLOCKED_HARD
    assert "outfit_pack" in res["missing_hard"]
    assert res["satisfied"] is False
    assert res["block_reasons"]  # 非空


def test_check_soft_missing_triggers_partial_fallback():
    # behind_the_scenes 仅 soft: process_detail
    recipe = _recipe_for("behind_the_scenes")
    res = rc.check(recipe, available_fields=[])
    assert res["fallback_status"] == rc.STATUS_BRAND_PARTIAL
    assert "process_detail" in res["missing_soft"]
    assert res["missing_hard"] == []
    assert res["satisfied"] is False


def test_check_all_satisfied_returns_brand_full():
    recipe = _recipe_for("outfit_of_the_day")
    res = rc.check(recipe, available_fields=["outfit_pack"])
    assert res["fallback_status"] == rc.STATUS_BRAND_FULL
    assert res["satisfied"] is True
    assert res["missing_hard"] == []
    assert res["missing_soft"] == []


def test_check_founder_ip_two_hard_fields_all_missing():
    recipe = _recipe_for("founder_ip")
    res = rc.check(recipe, available_fields=[])
    assert res["fallback_status"] == rc.STATUS_BLOCKED_HARD
    assert set(res["missing_hard"]) == {"brand_values", "founder_profile"}


def test_check_founder_ip_partial_hard_satisfied_still_blocks():
    recipe = _recipe_for("founder_ip")
    res = rc.check(recipe, available_fields=["brand_values"])
    assert res["fallback_status"] == rc.STATUS_BLOCKED_HARD
    assert res["missing_hard"] == ["founder_profile"]


def test_check_unknown_content_type_conservative_block():
    fake = {"content_type": "no_such_content_type"}
    res = rc.check(fake, available_fields=["anything"])
    assert res["fallback_status"] == rc.STATUS_BLOCKED_HARD
    assert rc.WARNING_MATRIX_MISS in res["warnings"]
    assert res["satisfied"] is False
    assert res["block_reasons"]


def test_check_daily_fragment_none_level_skipped():
    # daily_fragment 唯一字段 scene_anchor required_level=none → 不进入降级
    recipe = _recipe_for("daily_fragment")
    res = rc.check(recipe, available_fields=[])
    assert res["fallback_status"] == rc.STATUS_BRAND_FULL
    assert res["satisfied"] is True


def test_check_rejects_invalid_recipe():
    with pytest.raises(TypeError):
        rc.check("not-a-dict", available_fields=[])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        rc.check({"content_type": ""}, available_fields=[])


# ---------- no-LLM 源码扫描 ----------


_FORBIDDEN = re.compile(
    r"\b(anthropic|openai|llm_judge|model\.complete|completion|chat\.completions)\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize("path", MODULE_PATHS, ids=lambda p: p.name)
def test_modules_have_no_llm_calls(path: Path):
    src = path.read_text(encoding="utf-8")
    # 允许在注释 / docstring 提及 "LLM" / "no-LLM"——只禁实际客户端 / 端点 / 判定调用
    assert not _FORBIDDEN.search(src), (
        f"{path.name} contains forbidden LLM client/endpoint reference"
    )

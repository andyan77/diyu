"""KS-RETRIEVAL-002 · 跨文件回归 / cross-file regression for intent ↔ policy bridge.

修复 R3（intent 枚举与 retrieval_policy_view.csv 不闭合）的硬护栏。

测试目标：
1. intent_classifier.intent_to_policy_key 是显式 transitional bridge，
   `content_generation` 必须直通到 retrieval_policy_view 的某个 intent；
   其余 4 类业务 intent 必须返回 unsupported_intent_no_policy，**不允许**
   被静默折叠为 generate / 其它 policy_key。
2. content_type_router.route 在 canonical 直通模式下返回的 content_type，
   必须 100% 落在 retrieval_policy_view.csv 的 content_type 列集合内
   （spec-drift 修复 —— 卡 §3 输入契约的测试层闭合）。
3. 当 KS-RETRIEVAL-007 扩 retrieval_policy_view 后，本测试会自动放过
   新增的 bridge map；新增了未声明的 bridge_status 也会被 fail-closed。

红线：本测试只读 csv，不调 LLM，不写任何文件。
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVING_DIR = REPO_ROOT / "knowledge_serving" / "serving"
POLICY_VIEW_CSV = REPO_ROOT / "knowledge_serving" / "control" / "retrieval_policy_view.csv"
CONTENT_TYPE_CANONICAL_CSV = REPO_ROOT / "knowledge_serving" / "control" / "content_type_canonical.csv"


def _load(name: str):
    """从绝对路径加载模块（仓库无 __init__.py，沿用 W3 importlib 模式）。"""
    path = SERVING_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"无法加载 {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def classifier():
    return _load("intent_classifier")


@pytest.fixture(scope="module")
def router():
    return _load("content_type_router")


@pytest.fixture(scope="module")
def policy_intents() -> set[str]:
    """retrieval_policy_view.csv 实存的 distinct intent 集合。"""
    with POLICY_VIEW_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["intent"].strip() for row in reader if row.get("intent", "").strip()}


@pytest.fixture(scope="module")
def policy_content_types() -> set[str]:
    """retrieval_policy_view.csv 实存的 distinct content_type 集合。"""
    with POLICY_VIEW_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["content_type"].strip() for row in reader if row.get("content_type", "").strip()}


@pytest.fixture(scope="module")
def canonical_content_type_ids() -> set[str]:
    """content_type_canonical.csv 的 canonical id 集合。"""
    with CONTENT_TYPE_CANONICAL_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {row["canonical_content_type_id"].strip() for row in reader}


# ----------------------------------------------------------------------------
# 1. mapper 闭合
# ----------------------------------------------------------------------------
def test_bridge_content_generation_maps_to_policy_intent(classifier, policy_intents):
    """`content_generation` 经 bridge → policy_key 必须落在 policy_view.intent 集合内。"""
    result = classifier.intent_to_policy_key("content_generation")
    assert result["bridge_status"] == classifier.BRIDGE_STATUS_DIRECT
    assert result["policy_key"] is not None
    assert result["policy_key"] in policy_intents, (
        f"bridge 直通的 policy_key={result['policy_key']!r} 必须在 "
        f"retrieval_policy_view.csv 的 intent 集合 {policy_intents} 内"
    )


@pytest.mark.parametrize(
    "biz_intent",
    ["quality_check", "strategy_advice", "training", "sales_script"],
)
def test_bridge_other_intents_are_unsupported_not_silently_mapped(classifier, biz_intent):
    """除 content_generation 外的 4 类业务 intent 必须 unsupported，
    不允许被静默折叠到 generate 或其它 policy_key。"""
    result = classifier.intent_to_policy_key(biz_intent)
    assert result["policy_key"] is None, (
        f"业务 intent {biz_intent!r} 在 policy_view 扩之前必须 policy_key=None；"
        f"实际拿到 {result['policy_key']!r}（疑似静默折叠）"
    )
    assert result["bridge_status"] == classifier.BRIDGE_STATUS_UNSUPPORTED


def test_bridge_none_returns_no_intent(classifier):
    result = classifier.intent_to_policy_key(None)
    assert result == {
        "policy_key": None,
        "bridge_status": classifier.BRIDGE_STATUS_NO_INTENT,
    }


def test_bridge_unknown_string_returns_unknown(classifier):
    result = classifier.intent_to_policy_key("totally_made_up")
    assert result == {
        "policy_key": None,
        "bridge_status": classifier.BRIDGE_STATUS_UNKNOWN,
    }


def test_bridge_status_enum_closed(classifier):
    """bridge_status 取值必须落在显式声明的 4 个常量内，不许漂移。"""
    allowed = {
        classifier.BRIDGE_STATUS_DIRECT,
        classifier.BRIDGE_STATUS_UNSUPPORTED,
        classifier.BRIDGE_STATUS_NO_INTENT,
        classifier.BRIDGE_STATUS_UNKNOWN,
    }
    samples = [None, "content_generation", "quality_check", "made_up", ""]
    for s in samples:
        st = classifier.intent_to_policy_key(s)["bridge_status"]
        assert st in allowed, f"非法 bridge_status={st!r} (input={s!r})"


def test_bridge_map_coverage_or_unsupported(classifier):
    """每个 INTENT_ENUM 成员要么在 _POLICY_BRIDGE_MAP 有映射，要么显式 unsupported；
    不允许第 3 条路径。"""
    for biz_intent in classifier.INTENT_ENUM:
        result = classifier.intent_to_policy_key(biz_intent)
        if biz_intent in classifier._POLICY_BRIDGE_MAP:
            assert result["bridge_status"] == classifier.BRIDGE_STATUS_DIRECT
            assert result["policy_key"] == classifier._POLICY_BRIDGE_MAP[biz_intent]
        else:
            assert result["bridge_status"] == classifier.BRIDGE_STATUS_UNSUPPORTED
            assert result["policy_key"] is None


# ----------------------------------------------------------------------------
# 2. router 直通的 canonical_content_type_id 必须 ⊆ policy_view.content_type
# ----------------------------------------------------------------------------
def test_router_canonical_ids_subset_of_policy_content_types(
    router, canonical_content_type_ids, policy_content_types
):
    """每个 canonical_content_type_id 直通 router 后得到的 content_type，
    必须落在 retrieval_policy_view.csv 的 content_type 集合内 —— 修
    KS-RETRIEVAL-002 §3 输入契约要求的 retrieval_policy_view 闭合。"""
    routed: set[str] = set()
    unmatched_router: list[str] = []
    for cid in canonical_content_type_ids:
        r = router.route(cid)
        if r["status"] != "ok":
            unmatched_router.append(cid)
            continue
        routed.add(r["content_type"])
    assert not unmatched_router, (
        f"canonical id 直通 router 失败 / canonical not routed: {unmatched_router}"
    )
    missing_in_policy = routed - policy_content_types
    assert not missing_in_policy, (
        f"router 输出的 content_type 未在 retrieval_policy_view.csv 登记 / "
        f"router canonical not covered by policy: {sorted(missing_in_policy)}"
    )


def test_policy_content_types_all_known_canonical(
    canonical_content_type_ids, policy_content_types
):
    """反方向：retrieval_policy_view 列出的 content_type 必须都是 canonical 注册过的；
    防止 policy_view 引入未注册 content_type。"""
    stray = policy_content_types - canonical_content_type_ids
    assert not stray, (
        f"retrieval_policy_view 引用了未在 content_type_canonical 注册的 id: {sorted(stray)}"
    )

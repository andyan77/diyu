"""KS-RETRIEVAL-002 · intent_classifier + content_type_router 测试。

覆盖任务卡 §6 全部对抗性 / 边缘性测试：
- 枚举全覆盖（intent 5 个 / content_type alias + canonical）
- None / 未知 → needs_review，无兜底
- 确定性（同入参多次结果一致）
- 不读 user_query；不推断 brand
- 静态扫描：源码 grep 无任何 LLM 关键词
- mock 注入 LLM client 模块，断言 call_count == 0
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INTENT_PATH = REPO_ROOT / "knowledge_serving" / "serving" / "intent_classifier.py"
ROUTER_PATH = REPO_ROOT / "knowledge_serving" / "serving" / "content_type_router.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def intent_mod():
    return _load("intent_classifier", INTENT_PATH)


@pytest.fixture(scope="module")
def router_mod():
    return _load("content_type_router", ROUTER_PATH)


# ---------- intent_classifier ----------

@pytest.mark.parametrize("val", [
    "content_generation",
    "quality_check",
    "strategy_advice",
    "training",
    "sales_script",
])
def test_classify_enum_all_covered(intent_mod, val):
    r = intent_mod.classify(val)
    assert r == {"intent": val, "source": "input", "status": "ok", "missing": None}


def test_classify_none(intent_mod):
    r = intent_mod.classify(None)
    assert r["status"] == "needs_review"
    assert r["missing"] == "intent"
    assert r["intent"] is None
    assert r["source"] is None


def test_classify_unknown(intent_mod):
    r = intent_mod.classify("foo_bar")
    assert r["status"] == "needs_review"
    assert r["intent"] is None
    assert r["missing"] == "intent"


def test_classify_case_sensitive(intent_mod):
    """canonical 一律小写；大写视为未识别 → needs_review（前端必须传 canonical）。"""
    r = intent_mod.classify("CONTENT_GENERATION")
    assert r["status"] == "needs_review"
    assert r["intent"] is None


def test_classify_non_string(intent_mod):
    r = intent_mod.classify(123)  # type: ignore[arg-type]
    assert r["status"] == "needs_review"


def test_classify_deterministic(intent_mod):
    """同入参多次跑结果完全一致。"""
    out = [intent_mod.classify("training") for _ in range(5)]
    assert all(o == out[0] for o in out)


def test_classify_signature_no_user_query(intent_mod):
    import inspect
    sig = inspect.signature(intent_mod.classify)
    forbidden = {"user_query", "query", "text"}
    assert not (forbidden & set(sig.parameters.keys()))


# ---------- content_type_router ----------

def test_route_canonical_direct(router_mod):
    r = router_mod.route("behind_the_scenes")
    assert r == {
        "content_type": "behind_the_scenes",
        "source": "input",
        "status": "ok",
        "missing": None,
        "matched_alias": None,
    }


def test_route_alias_zh_simple(router_mod):
    r = router_mod.route("幕后")
    assert r["status"] == "ok"
    assert r["content_type"] == "behind_the_scenes"
    assert r["matched_alias"] == "幕后"


def test_route_alias_zh_compound(router_mod):
    r = router_mod.route("后台揭秘")
    assert r["status"] == "ok"
    assert r["content_type"] == "behind_the_scenes"
    assert r["matched_alias"] == "后台揭秘"


def test_route_alias_en_case_insensitive(router_mod):
    """alias 大小写不敏感命中。"""
    r = router_mod.route("OOTD")
    assert r["status"] == "ok"
    assert r["content_type"] == "outfit_of_the_day"
    r2 = router_mod.route("ootd")
    assert r2["content_type"] == "outfit_of_the_day"


def test_route_alias_with_space(router_mod):
    """alias 中含空格的 '创始人 IP' 应能命中。"""
    r = router_mod.route("创始人 IP")
    assert r["status"] == "ok"
    assert r["content_type"] == "founder_ip"


def test_route_strip(router_mod):
    r = router_mod.route("  穿搭  ")
    assert r["status"] == "ok"
    assert r["content_type"] == "outfit_of_the_day"


def test_route_none(router_mod):
    r = router_mod.route(None)
    assert r["status"] == "needs_review"
    assert r["content_type"] is None
    assert r["missing"] == "content_type"
    assert r["matched_alias"] is None


def test_route_empty_string(router_mod):
    r = router_mod.route("")
    assert r["status"] == "needs_review"


def test_route_unknown_alias(router_mod):
    r = router_mod.route("不存在的别名")
    assert r["status"] == "needs_review"
    assert r["content_type"] is None
    assert r["missing"] == "content_type"


def test_route_brand_keyword_not_inferred(router_mod):
    """含品牌关键词 '笛语' 不能被 alias 匹配；router 不返回 brand。"""
    r = router_mod.route("笛语日常")
    assert r["status"] == "needs_review"
    assert r["content_type"] is None
    # router 返回 dict 中不含 brand 字段
    assert "brand_layer" not in r
    assert "brand" not in r


def test_route_deterministic(router_mod):
    """同入参连跑 3 次结果完全一致。"""
    out = [router_mod.route("幕后") for _ in range(3)]
    assert all(o == out[0] for o in out)


def test_route_signature_no_user_query(router_mod):
    import inspect
    sig = inspect.signature(router_mod.route)
    forbidden = {"user_query", "query", "text"}
    assert not (forbidden & set(sig.parameters.keys()))


# ---------- 反 LLM 硬断言 ----------

LLM_PATTERN = re.compile(
    r"dashscope|openai|anthropic|langchain|llm_assist|completion|requests\.post|httpx|\.chat\(",
    re.IGNORECASE,
)


@pytest.mark.parametrize("path", [INTENT_PATH, ROUTER_PATH])
def test_source_grep_no_llm(path):
    """模块源码静态扫描：禁止任何 LLM 关键词。

    注释和 docstring 中只允许出现在反向描述（禁止 / no-LLM）的语境；
    为避免误伤合法 docstring，本测试只检查非注释非 docstring 行——
    简化做法：扫描所有逻辑行，但容忍 'no-LLM'/'禁止' 上下文：
    实际策略——直接断言匹配命中后再人工审查；这里采用更严格的：禁止任何匹配。
    """
    text = path.read_text(encoding="utf-8")
    # 剔除注释行和 docstring 内的允许性提及
    # 简化：逐行剔除以 # 开头的行 + 三引号内被标识为禁止性描述的行
    # 为可移植性，直接断言"代码体"中不出现这些 token——
    # 我们使用 ast 提取"非字符串非注释"内容
    import ast
    tree = ast.parse(text)
    # 把所有 string literals (含 docstring) 替换为占位
    class StripStrings(ast.NodeTransformer):
        def visit_Constant(self, node):
            if isinstance(node.value, str):
                return ast.copy_location(ast.Constant(value=""), node)
            return node
    stripped = ast.unparse(StripStrings().visit(tree))
    matches = LLM_PATTERN.findall(stripped)
    assert matches == [], f"{path.name} 代码体出现 LLM 关键词: {matches}"


def test_mock_llm_clients_never_called(intent_mod, router_mod):
    """注入 mock LLM client 到 sys.modules，跑 100 次 classify+route，断言 call_count==0。"""
    mocks = {
        "dashscope": MagicMock(),
        "openai": MagicMock(),
        "anthropic": MagicMock(),
        "httpx": MagicMock(),
        "requests": MagicMock(),
    }
    saved = {k: sys.modules.get(k) for k in mocks}
    try:
        for k, m in mocks.items():
            sys.modules[k] = m
        # 重新加载（确保即使后续动态 import 也会拿到 mock）
        for _ in range(100):
            intent_mod.classify("training")
            intent_mod.classify(None)
            intent_mod.classify("unknown")
            router_mod.route("幕后")
            router_mod.route(None)
            router_mod.route("不存在")
            router_mod.route("behind_the_scenes")
        for k, m in mocks.items():
            # 任何调用都视为违规
            assert m.call_count == 0, f"{k} mock 被调用了 {m.call_count} 次"
            # method 链式调用也算
            assert not m.method_calls, f"{k} mock 有方法调用: {m.method_calls}"
    finally:
        for k, original in saved.items():
            if original is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = original

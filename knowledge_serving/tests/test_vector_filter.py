"""KS-RETRIEVAL-006 · vector_retrieval + payload filter 测试.

覆盖卡 §6 对抗测试 + §10 审查员阻断项：
- payload hard filter 三条最少元素（brand_layer / gate_status / granularity_layer）
- 跨租户硬隔离：brand_a 请求 0 命中 brand_b chunk
- gate_status=deprecated chunk 不命中（filter 只接受 active）
- Qdrant down → structured-only fallback
- embedding 维度不匹配 → raise（KS-POLICY-005 联动）
- rerank 引入新候选 → 拒绝（rerank 不得扩大召回范围）
- 入参校验（query / allowed_layers）
- 不调 LLM；不写 clean_output
- 确定性：filter 字段顺序稳定
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "knowledge_serving" / "serving" / "vector_retrieval.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "vector_retrieval_under_test", MODULE_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vr = _load_module()


# ---------- fakes ----------

class FakePoint:
    def __init__(self, point_id: str, score: float, payload: dict):
        self.id = point_id
        self.score = score
        self.payload = payload


class FakeQdrantClient:
    """模拟 Qdrant：服务端按 filter 真实过滤，验证 hard filter 生效。"""

    def __init__(self, corpus: list[FakePoint]):
        self.corpus = corpus
        self.last_call: dict | None = None

    def search(self, *, collection_name, query_vector, query_filter, limit, with_payload=True):
        self.last_call = {
            "collection_name": collection_name,
            "query_vector": query_vector,
            "query_filter": query_filter,
            "limit": limit,
        }
        return [p for p in self.corpus if _matches(p.payload, query_filter)][:limit]


def _matches(payload: dict, qf: dict) -> bool:
    for cond in qf.get("must", []):
        key = cond["key"]
        m = cond["match"]
        val = payload.get(key)
        if "value" in m and val != m["value"]:
            return False
        if "any" in m and val not in set(m["any"]):
            return False
    return True


class FakeDownClient:
    def search(self, **kwargs):
        raise ConnectionError("simulated qdrant unreachable")


def _embed_factory(dim: int):
    return lambda text: [0.01] * dim


# ---------- fixtures ----------

@pytest.fixture
def policy_dim():
    """从真实 policy 读 dimension，保持与 KS-POLICY-005 联动。"""
    pol = vr._load_policy(None)
    return pol["embedding"]["dimension"]


@pytest.fixture
def corpus():
    """构造跨租户 + gate / granularity 多样的语料。"""
    def _pl(brand, gate="active", gran="L2", chunk_id="c", content_type="ct_default"):
        return {
            "chunk_id": chunk_id,
            "brand_layer": brand,
            "gate_status": gate,
            "granularity_layer": gran,
            "content_type": content_type,
            "source_pack_id": f"pack_{chunk_id}",
        }
    return [
        FakePoint("p1", 0.9, _pl("brand_faye", chunk_id="faye_active")),
        FakePoint("p2", 0.88, _pl("domain_general", chunk_id="domain_active")),
        FakePoint("p3", 0.85, _pl("brand_b", chunk_id="b_active")),  # 串味检查
        FakePoint("p4", 0.8, _pl("brand_faye", gate="deprecated", chunk_id="faye_deprecated")),
        FakePoint("p5", 0.78, _pl("brand_faye", gran="L4", chunk_id="faye_bad_gran")),
    ]


# ---------- §6 payload hard filter ----------

def test_filter_contains_three_hard_conditions():
    qf = vr.build_payload_filter(allowed_layers=["brand_faye", "domain_general"])
    keys = [c["key"] for c in qf["must"]]
    assert "brand_layer" in keys
    assert "gate_status" in keys
    assert "granularity_layer" in keys
    # brand_layer 用 any（集合匹配）
    bl = [c for c in qf["must"] if c["key"] == "brand_layer"][0]
    assert set(bl["match"]["any"]) == {"brand_faye", "domain_general"}
    # gate_status 用 value（恒等 active）
    gs = [c for c in qf["must"] if c["key"] == "gate_status"][0]
    assert gs["match"]["value"] == "active"
    # granularity 限 L1/L2/L3
    gr = [c for c in qf["must"] if c["key"] == "granularity_layer"][0]
    assert set(gr["match"]["any"]) == {"L1", "L2", "L3"}


def test_filter_includes_content_type_when_given():
    qf = vr.build_payload_filter(allowed_layers=["brand_faye"], content_type="ct_xyz")
    ct_conds = [c for c in qf["must"] if c["key"] == "content_type"]
    assert len(ct_conds) == 1
    assert ct_conds[0]["match"]["value"] == "ct_xyz"


def test_filter_omits_content_type_when_none():
    qf = vr.build_payload_filter(allowed_layers=["brand_faye"])
    assert not any(c["key"] == "content_type" for c in qf["must"])


# ---------- §10 跨租户硬隔离 ----------

def test_no_cross_tenant_leak(policy_dim, corpus):
    client = FakeQdrantClient(corpus)
    res = vr.vector_retrieve(
        query="如何陈列大衣",
        allowed_layers=["brand_faye", "domain_general"],
        embed_fn=_embed_factory(policy_dim),
        qdrant_client=client,
    )
    assert res["mode"] == "vector"
    cids = [c["payload"]["chunk_id"] for c in res["candidates"]]
    # brand_b 永不命中
    assert "b_active" not in cids
    # 命中 brand_faye + domain_general
    assert "faye_active" in cids
    assert "domain_active" in cids


def test_brand_a_request_zero_hits_brand_b_chunk(policy_dim):
    """卡 §10 阻断项：brand_a 请求对 brand_b chunk 永不命中。"""
    brand_b_only = [FakePoint("p", 0.9, {
        "chunk_id": "b_only",
        "brand_layer": "brand_b",
        "gate_status": "active",
        "granularity_layer": "L2",
    })]
    res = vr.vector_retrieve(
        query="任意 query",
        allowed_layers=["brand_a"],
        embed_fn=_embed_factory(policy_dim),
        qdrant_client=FakeQdrantClient(brand_b_only),
    )
    assert res["candidates"] == []


# ---------- §6 gate_status / granularity 过滤 ----------

def test_deprecated_chunk_not_hit(policy_dim, corpus):
    client = FakeQdrantClient(corpus)
    res = vr.vector_retrieve(
        query="x",
        allowed_layers=["brand_faye"],
        embed_fn=_embed_factory(policy_dim),
        qdrant_client=client,
    )
    cids = [c["payload"]["chunk_id"] for c in res["candidates"]]
    assert "faye_deprecated" not in cids


def test_invalid_granularity_filtered(policy_dim, corpus):
    res = vr.vector_retrieve(
        query="x",
        allowed_layers=["brand_faye"],
        embed_fn=_embed_factory(policy_dim),
        qdrant_client=FakeQdrantClient(corpus),
    )
    cids = [c["payload"]["chunk_id"] for c in res["candidates"]]
    assert "faye_bad_gran" not in cids


# ---------- §6 Qdrant down fallback ----------

def test_qdrant_down_returns_structured_only(policy_dim):
    res = vr.vector_retrieve(
        query="x",
        allowed_layers=["brand_faye"],
        embed_fn=_embed_factory(policy_dim),
        qdrant_client=FakeDownClient(),
    )
    assert res["mode"] == "structured_only"
    assert res["candidates"] == []
    assert res["_meta"]["fallback_reason"].startswith("qdrant_search_failed")
    assert res["_meta"]["fallback_log_marker"] == "FALLBACK_STRUCTURED_ONLY"


class FakeHTTPErrorClient:
    """模拟 qdrant-client 抛 ApiException / UnexpectedResponse + HTTP status。"""

    def __init__(self, status_code: int, exc_name: str = "UnexpectedResponse"):
        self.status_code = status_code
        self.exc_name = exc_name

    def search(self, **kwargs):
        exc_cls = type(self.exc_name, (Exception,), {})
        exc = exc_cls(f"simulated HTTP {self.status_code}")
        exc.status_code = self.status_code
        raise exc


def test_qdrant_401_auth_error_propagates(policy_dim):
    """凭据错（401）必须 propagate，不得被当成 down 掩盖。"""
    with pytest.raises(Exception) as exc_info:
        vr.vector_retrieve(
            query="x",
            allowed_layers=["brand_faye"],
            embed_fn=_embed_factory(policy_dim),
            qdrant_client=FakeHTTPErrorClient(401, "ApiException"),
        )
    assert "401" in str(exc_info.value)


def test_qdrant_400_bad_request_propagates(policy_dim):
    """请求错（400）必须 propagate。"""
    with pytest.raises(Exception) as exc_info:
        vr.vector_retrieve(
            query="x",
            allowed_layers=["brand_faye"],
            embed_fn=_embed_factory(policy_dim),
            qdrant_client=FakeHTTPErrorClient(400, "UnexpectedResponse"),
        )
    assert "400" in str(exc_info.value)


def test_qdrant_404_not_found_propagates(policy_dim):
    """404（collection 不存在）是配置错，必须 propagate。"""
    with pytest.raises(Exception):
        vr.vector_retrieve(
            query="x",
            allowed_layers=["brand_faye"],
            embed_fn=_embed_factory(policy_dim),
            qdrant_client=FakeHTTPErrorClient(404, "UnexpectedResponse"),
        )


def test_qdrant_503_server_error_falls_back(policy_dim):
    """5xx 服务端崩 → fallback structured_only（区别于 4xx 配置错）。"""
    res = vr.vector_retrieve(
        query="x",
        allowed_layers=["brand_faye"],
        embed_fn=_embed_factory(policy_dim),
        qdrant_client=FakeHTTPErrorClient(503, "UnexpectedResponse"),
    )
    assert res["mode"] == "structured_only"
    assert res["_meta"]["fallback_reason"].startswith("qdrant_search_failed")


def test_qdrant_down_does_not_5xx(policy_dim):
    """卡 §10 阻断项：Qdrant down 时不得抛 5xx（即不得抛连通性异常）。"""
    # 直接调用，不应抛 ConnectionError / TimeoutError
    res = vr.vector_retrieve(
        query="x",
        allowed_layers=["brand_faye"],
        embed_fn=_embed_factory(policy_dim),
        qdrant_client=FakeDownClient(),
    )
    assert res["mode"] == "structured_only"


# ---------- §6 embedding 维度 ----------

def test_embedding_dimension_mismatch_raises(policy_dim):
    wrong_dim = policy_dim + 1
    with pytest.raises(vr.EmbeddingDimensionMismatch):
        vr.vector_retrieve(
            query="x",
            allowed_layers=["brand_faye"],
            embed_fn=_embed_factory(wrong_dim),
            qdrant_client=FakeQdrantClient([]),
        )


# ---------- §6 rerank 不得扩范围 ----------

def test_rerank_cannot_introduce_new_candidates(policy_dim, corpus):
    fake_extra = FakePoint("intruder", 1.0, {
        "chunk_id": "intruder_chunk",
        "brand_layer": "brand_faye",
        "gate_status": "active",
        "granularity_layer": "L2",
    })

    def bad_rerank(query, candidates):
        return [vr._point_to_candidate(fake_extra)] + candidates

    with pytest.raises(vr.RerankExpandedCandidatesError):
        vr.vector_retrieve(
            query="x",
            allowed_layers=["brand_faye"],
            embed_fn=_embed_factory(policy_dim),
            qdrant_client=FakeQdrantClient(corpus),
            rerank_fn=bad_rerank,
        )


def test_rerank_subset_ok(policy_dim, corpus):
    """rerank 返回原集合子集 + 重排序 → 允许。"""
    def good_rerank(query, candidates):
        return list(reversed(candidates))[:2]

    res = vr.vector_retrieve(
        query="x",
        allowed_layers=["brand_faye", "domain_general"],
        embed_fn=_embed_factory(policy_dim),
        qdrant_client=FakeQdrantClient(corpus),
        rerank_fn=good_rerank,
    )
    assert res["_meta"]["rerank_applied"] is True
    assert len(res["candidates"]) <= 2


# ---------- 入参校验 ----------

def test_empty_allowed_layers_raises(policy_dim):
    with pytest.raises(ValueError):
        vr.vector_retrieve(
            query="x",
            allowed_layers=[],
            embed_fn=_embed_factory(policy_dim),
            qdrant_client=FakeQdrantClient([]),
        )


def test_invalid_brand_layer_raises(policy_dim):
    with pytest.raises(ValueError):
        vr.vector_retrieve(
            query="x",
            allowed_layers=["Brand_FAYE"],  # 大写非法
            embed_fn=_embed_factory(policy_dim),
            qdrant_client=FakeQdrantClient([]),
        )


def test_empty_query_raises(policy_dim):
    with pytest.raises(ValueError):
        vr.vector_retrieve(
            query="",
            allowed_layers=["brand_faye"],
            embed_fn=_embed_factory(policy_dim),
            qdrant_client=FakeQdrantClient([]),
        )


# ---------- 治理一致性 ----------

def test_function_signature_no_user_query_brand_layer():
    """函数签名禁用 user_query / brand_layer 入参名（治理纪律）。"""
    sig = inspect.signature(vr.vector_retrieve)
    assert "user_query" not in sig.parameters
    assert "brand_layer" not in sig.parameters
    # allowed_layers 必须存在（由 tenant_scope_resolver 提供）
    assert "allowed_layers" in sig.parameters


def test_no_llm_call_in_source():
    """源码不得调用 LLM 做最终判断。"""
    src = MODULE_PATH.read_text(encoding="utf-8")
    # 允许 dashscope embedding（用途已声明）；禁止 chat completion
    assert "qwen-plus" not in src
    assert "ChatCompletion" not in src
    assert "deepseek-chat" not in src


def test_does_not_write_clean_output():
    """源码不得写 clean_output 目录（注释提及 clean_output 不算写入）。"""
    src = MODULE_PATH.read_text(encoding="utf-8")
    # 禁止任何写入 clean_output 的 IO 调用
    forbidden = [
        '"clean_output"',
        "'clean_output'",
        "clean_output/",
        ".write_text",
        ".write_bytes",
        "open(",
    ]
    for token in forbidden:
        assert token not in src, f"源码出现禁用 token: {token!r}"


def test_filter_field_order_deterministic():
    """同输入 → filter 字段顺序稳定（确定性）。"""
    f1 = vr.build_payload_filter(allowed_layers=["brand_faye", "domain_general"])
    f2 = vr.build_payload_filter(allowed_layers=["brand_faye", "domain_general"])
    assert f1 == f2
    assert [c["key"] for c in f1["must"]] == [c["key"] for c in f2["must"]]

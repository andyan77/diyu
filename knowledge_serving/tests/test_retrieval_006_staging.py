"""KS-FIX-12 · /v1/retrieve_context API 真实 vector 路径 staging e2e.

覆盖 FIX-12 §6 对抗矩阵 + §11 DoD：
  1. mode=vector 默认（structured_only=False）→ bundle.vector_res 非 None，
     candidates>0，真 dashscope embed + 真 staging Qdrant search
  2. Qdrant 不可达 → API 返 503（不静默 None / 不退化到 structured_only）
  3. structured_only=True 显式开 → 不调 vector（兼容路径）

运行前置 / preconditions:
  - source scripts/load_env.sh（注入 DASHSCOPE_API_KEY + QDRANT_URL_STAGING）
  - bash scripts/qdrant_tunnel.sh up（ECS Qdrant 隧道）
  - chunks 已灌进 staging collection（KS-DIFY-ECS-004 / KS-FIX-10）

边界 / scope:
  - 本测试用 fastapi TestClient（in-process ASGI）+ 真 dashscope + 真 Qdrant：
    被测路径（API → vector_retrieve → Qdrant）全是真路径，只有 HTTP transport 是
    in-process。这不算 mock SUT，符合 KS-FIX-12 "真路径 runtime_verified" 标准。
  - canonical live audit 由 scripts/staging_audit_retrieval_006.py 单独跑（spawn
    uvicorn，真 HTTP），不在本 pytest 内。本 pytest 是回归网。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


pytestmark = pytest.mark.skipif(
    not os.environ.get("QDRANT_URL_STAGING") or not os.environ.get("DASHSCOPE_API_KEY"),
    reason="staging e2e 需要 QDRANT_URL_STAGING + DASHSCOPE_API_KEY；先 source scripts/load_env.sh",
)


@pytest.fixture(autouse=True)
def _clear_socks_proxy(monkeypatch):
    """WSL2 SOCKS proxy 会让 httpx ValueError；测试前清理（同 smoke 脚本约定）。"""
    monkeypatch.delenv("ALL_PROXY", raising=False)
    monkeypatch.delenv("all_proxy", raising=False)


@pytest.fixture(autouse=True)
def _isolate_log(monkeypatch, tmp_path):
    """每个 test 用临时 canonical 路径，避免污染真 canonical CSV / outbox。"""
    from knowledge_serving.serving import log_writer as lw
    tmp_csv = tmp_path / "context_bundle_log.csv"
    monkeypatch.setattr(lw, "CANONICAL_LOG_PATH", tmp_csv)
    tmp_outbox = tmp_path / "context_bundle_log_outbox.jsonl"
    monkeypatch.setattr(lw, "CANONICAL_OUTBOX_PATH", tmp_outbox)
    yield


@pytest.fixture
def client() -> TestClient:
    from knowledge_serving.serving.api.retrieve_context import create_app
    return TestClient(create_app())


def test_vector_path_real_qdrant_hits_present(client):
    """KS-FIX-12 §11 DoD 第 1 项：默认走 vector，bundle.vector_res 非 None 且 candidates>0."""
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "user_query": "大衣搭配陈列要点",
        "content_type": "product_review",
        "intent_hint": "content_generation",
        # 不传 structured_only → 缺省 False → 走 vector 真路径
        "business_brief": {
            "sku": "SKU-API-FIX12",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    vector_meta = body["meta"]["vector_meta"]
    # FIX-12 §1 红线：默认路径 mode 必须 == "vector"（非 structured_only_opt_in，非 fallback）
    assert vector_meta["mode"] == "vector", (
        f"meta.vector_meta.mode={vector_meta.get('mode')} 不是 vector；"
        "FIX-12 §6 要求 Qdrant 不可达时 503 而非静默退化"
    )
    # candidate_count>0：真 Qdrant 真有命中
    assert vector_meta["candidate_count"] > 0, (
        f"vector candidate_count={vector_meta['candidate_count']}；FIX-12 §11 DoD 要求 vector_hits>0"
    )
    # collection_name 应该指向 staging chunks（alias ks_chunks_current 或 直连版本 ks_chunks__<ver>）
    coll = vector_meta.get("collection_name") or ""
    assert coll.startswith("ks_chunks"), f"collection_name 漂移：{coll}"


def test_structured_only_opt_in_skips_vector(client):
    """KS-FIX-12 §6 row 2：structured_only=True 显式开 → 不调 vector，兼容路径."""
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "user_query": "大衣搭配陈列要点",
        "content_type": "product_review",
        "intent_hint": "content_generation",
        "structured_only": True,
        "business_brief": {
            "sku": "SKU-API-FIX12-SO",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
    })
    assert r.status_code == 200, r.text
    vector_meta = r.json()["meta"]["vector_meta"]
    # structured_only=True → mode 应为 structured_only_opt_in（vector_retrieve 未被调）
    assert vector_meta["mode"] == "structured_only_opt_in", (
        f"structured_only=True 但 mode={vector_meta['mode']}：vector_retrieve 不该被调"
    )
    assert vector_meta["candidate_count"] == 0


def test_qdrant_unreachable_returns_503(client, monkeypatch):
    """KS-FIX-12 §6 row 1：mode=vector + Qdrant 不可达 → 503 fail-closed，不静默 None."""
    # 把 QDRANT_URL_STAGING 指到不存在的端口；real dashscope embed 仍 OK，但 Qdrant 必挂
    monkeypatch.setenv("QDRANT_URL_STAGING", "http://127.0.0.1:1")
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "user_query": "大衣搭配陈列要点",
        "content_type": "product_review",
        "intent_hint": "content_generation",
        # 不传 structured_only → 走 vector 路径 → Qdrant 必挂 → 503
        "business_brief": {
            "sku": "SKU-API-FIX12-DOWN",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
    })
    assert r.status_code == 503, f"Qdrant 不可达应 503 fail-closed，实际 status={r.status_code} body={r.text}"
    detail = r.json()["detail"]
    assert detail["error"] == "qdrant_unreachable"
    assert "request_id" in detail
    assert detail["request_id"].startswith("req_api_")


def test_no_silent_none_in_default_path(client):
    """红线回归：default 路径绝不能再出现 vector_res=None（除非客户端显式开 structured_only）."""
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "user_query": "测一下默认路径",
        "content_type": "product_review",
        "intent_hint": "content_generation",
        "business_brief": {
            "sku": "SKU-FIX12-DEFAULT",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
    })
    # default 路径必须要么 200 + mode=vector，要么 503 fail-closed
    # 绝不允许 200 + mode=structured_only_opt_in（那是静默退化）
    if r.status_code == 200:
        vector_meta = r.json()["meta"]["vector_meta"]
        assert vector_meta["mode"] == "vector", (
            f"200 OK 但 vector_meta.mode={vector_meta['mode']}：FIX-12 红线 — 默认路径禁止静默退化"
        )
    elif r.status_code == 503:
        assert r.json()["detail"]["error"] == "qdrant_unreachable"
    else:
        pytest.fail(f"非预期 status={r.status_code} body={r.text}")

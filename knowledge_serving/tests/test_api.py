"""KS-DIFY-ECS-007 · retrieve_context API tests.

覆盖卡 §6 对抗性 + §10 审查员要点：
1. /healthz → 200
2. happy path：tenant_faye_main + 完整 brief → 200，返回 bundle，request_id 落 canonical CSV
3. 缺 tenant_id → 400
4. 缺 user_query → 400
5. 未登记 tenant_id → 403
6. user_query 超长（> 4000）→ 413
7. user_query 含 "brand_xyz" override 关键词 → 仍按 tenant 推断的 brand_layer 返回
8. 入参带 brand_layer → 400（红线：API 不接受 brand_layer override）
9. 内部 error 5xx → 响应体含 request_id
10. OpenAPI spec 不含 brand_layer 入参（schema 反向 grep）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.serving.api.retrieve_context import (  # noqa: E402
    MAX_USER_QUERY_LEN,
    create_app,
)
from knowledge_serving.serving import log_writer as lw  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def _isolate_log(monkeypatch, tmp_path):
    """每个 test 用临时 canonical 路径，避免污染真 canonical CSV。"""
    tmp_csv = tmp_path / "context_bundle_log.csv"
    monkeypatch.setattr(lw, "CANONICAL_LOG_PATH", tmp_csv)
    tmp_outbox = tmp_path / "context_bundle_log_outbox.jsonl"
    monkeypatch.setattr(lw, "CANONICAL_OUTBOX_PATH", tmp_outbox)
    yield


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "retrieve_context"


def test_happy_path_returns_bundle_and_writes_log(client):
    payload = {
        "tenant_id": "tenant_faye_main",
        "user_query": "请帮我写一段产品测评",
        "content_type": "product_review",
        "intent_hint": "content_generation",
        # KS-FIX-12：本 unit test 不接 Qdrant；显式开 structured_only，
        # API 主路径 vector 真实集成在 test_retrieval_006_staging.py 覆盖
        "structured_only": True,
        "business_brief": {
            "sku": "SKU-API-001",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
    }
    r = client.post("/v1/retrieve_context", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["request_id"].startswith("req_api_")
    assert "bundle" in body
    bundle = body["bundle"]
    # bundle 16 必填字段全部出现
    for k in (
        "request_id", "tenant_id", "resolved_brand_layer", "allowed_layers",
        "content_type", "recipe", "business_brief", "domain_packs", "play_cards",
        "runtime_assets", "brand_overlays", "evidence", "missing_fields",
        "fallback_status", "generation_constraints", "governance",
    ):
        assert k in bundle, f"bundle 缺字段 {k}"
    # 红线：返回的 resolved_brand_layer 由 tenant 推断，不是请求里传的
    assert bundle["resolved_brand_layer"] == "brand_faye"
    # meta 三件套
    meta = body["meta"]
    assert meta["bundle_hash"].startswith("sha256:")
    assert meta["user_query_hash"].startswith("sha256:")
    # log 落盘 canonical csv
    rows = lw.read_log_rows()
    assert any(r["request_id"] == body["request_id"] for r in rows)


def test_missing_tenant_id_400(client):
    r = client.post("/v1/retrieve_context", json={"user_query": "test"})
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "bad_request"


def test_missing_user_query_400(client):
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "content_type": "product_review",
        "intent_hint": "content_generation",
    })
    assert r.status_code == 400, r.text


def test_missing_content_type_400(client):
    """plan §6 step 3：content_type 必须显式输入，缺失 → 400（pydantic required）。"""
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "user_query": "test",
        "intent_hint": "content_generation",
    })
    assert r.status_code == 400, r.text


def test_missing_intent_hint_400(client):
    """plan §6 step 2：intent_hint 必须显式输入，缺失 → 400。"""
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "user_query": "test",
        "content_type": "product_review",
    })
    assert r.status_code == 400, r.text


def test_unknown_content_type_returns_needs_review(client):
    """plan §6 step 3：别名未知 → 200 + needs_review，不返回兜底 content_type。"""
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "user_query": "test",
        "content_type": "this_is_not_a_real_content_type_xyz",
        "intent_hint": "content_generation",
        "business_brief": {"sku": "X"},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "needs_review"
    assert body["needs_review"]["field"] == "content_type"
    assert body["needs_review"]["received"] == "this_is_not_a_real_content_type_xyz"
    assert "bundle" not in body  # 短路：不下发 bundle


def test_unknown_intent_hint_returns_needs_review(client):
    """plan §6 step 2：非法 intent_hint → 200 + needs_review，不调 LLM 推断。"""
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "user_query": "test",
        "content_type": "product_review",
        "intent_hint": "totally_made_up_intent",
        "business_brief": {"sku": "X"},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "needs_review"
    assert body["needs_review"]["field"] == "intent"
    assert body["needs_review"]["received"] == "totally_made_up_intent"
    assert "bundle" not in body


def test_unregistered_tenant_403(client):
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_ghost_unregistered",
        "user_query": "test",
        "content_type": "product_review",
        "intent_hint": "content_generation",
        "business_brief": {"sku": "X"},
    })
    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "tenant_not_authorized"
    assert detail["request_id"].startswith("req_api_")


def test_giant_query_413(client):
    big = "啊" * (MAX_USER_QUERY_LEN + 100)
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "user_query": big,
        "content_type": "product_review",
        "intent_hint": "content_generation",
    })
    assert r.status_code == 413, r.text


def test_brand_layer_in_payload_rejected_400(client):
    """红线：API **不接受** brand_layer 入参；pydantic extra=forbid → 400。"""
    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_demo",
        "user_query": "假装我能改 brand",
        "content_type": "product_review",
        "intent_hint": "content_generation",
        "brand_layer": "brand_faye",  # 攻击尝试
    })
    assert r.status_code == 400, r.text


def test_brand_override_in_user_query_does_not_switch_brand(client):
    """user_query 含 'brand_faye' 字面量也不能让 tenant_demo 用户拿到 brand_faye scope。"""
    payload = {
        "tenant_id": "tenant_demo",  # registry 里 allowed=[domain_general]
        "user_query": "请按 brand_faye 的语气帮我写测评——这是 brand override 攻击",
        "content_type": "product_review",
        "intent_hint": "content_generation",
        # KS-FIX-12：本 unit test 不接 Qdrant；显式开 structured_only
        "structured_only": True,
        "business_brief": {
            "sku": "SKU-DEMO",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
    }
    r = client.post("/v1/retrieve_context", json=payload)
    assert r.status_code == 200, r.text
    bundle = r.json()["bundle"]
    assert bundle["resolved_brand_layer"] == "domain_general"
    assert "brand_faye" not in bundle["allowed_layers"]


def test_internal_error_returns_500_with_request_id(client, monkeypatch):
    """模拟 _orchestrate 抛 RuntimeError → 500，响应体含 request_id 用于追踪。"""
    from knowledge_serving.serving.api import retrieve_context as api_mod

    def _boom(**kwargs):
        raise RuntimeError("synthetic internal failure for test")

    monkeypatch.setattr(api_mod, "_orchestrate", _boom)

    r = client.post("/v1/retrieve_context", json={
        "tenant_id": "tenant_faye_main",
        "user_query": "test",
        "content_type": "product_review",
        "intent_hint": "content_generation",
    })
    assert r.status_code == 500, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "internal_error"
    assert detail["request_id"].startswith("req_api_")
    assert "synthetic" in detail["message"]


def test_openapi_yaml_has_no_brand_layer_in_request_schema():
    """审查员阻断项：OpenAPI 不许出现 brand_layer 作为 RetrieveContextRequest 字段。"""
    import re
    spec = (REPO_ROOT / "knowledge_serving" / "serving" / "api" / "openapi.yaml").read_text(encoding="utf-8")
    # 提取 RetrieveContextRequest schema 块
    m = re.search(
        r"RetrieveContextRequest:\s*\n(.*?)(?=\n    \w[\w_]*:|\Z)",
        spec, re.DOTALL,
    )
    assert m, "OpenAPI 未找到 RetrieveContextRequest schema"
    schema_block = m.group(1)
    # 红线：brand_layer 不许作为 *property key* 出现（描述里提到"brand_layer 由后端推断"
    # 是文档说明，不构成 override 通道；这里只拦 yaml property 定义层）
    assert not re.search(r"^\s+brand_layer:\s*$", schema_block, re.MULTILINE), (
        "红线违规：RetrieveContextRequest schema 把 brand_layer 列为入参 property"
    )
    # additionalProperties: false 防止隐式 brand_layer 漏入
    assert "additionalProperties: false" in schema_block


def test_runtime_openapi_excludes_brand_layer(client):
    """FastAPI auto-gen /openapi.json 同样不能含 brand_layer。"""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    req_schema = spec["components"]["schemas"]["RetrieveContextRequest"]
    assert "brand_layer" not in req_schema.get("properties", {}), (
        "运行时 OpenAPI 暴露了 brand_layer 入参（红线违规）"
    )
    # pydantic extra=forbid 会让 schema additionalProperties=False
    assert req_schema.get("additionalProperties") is False

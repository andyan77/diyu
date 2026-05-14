"""KS-CD-003 Layer 2 · endpoint wrapper 单元测试 / endpoint unit tests.

执行 task_cards/KS-CD-003.md §6 + §10：
  - 两条新 endpoint 已挂载到 FastAPI app
  - guardrail wrapper 不调 LLM（即使 dashscope 不可达也能 200）
  - log_write wrapper 真写 canonical CSV
  - 既有 /v1/retrieve_context 行为不被 wrapper 挂载破坏

被测对象（实现还没写时 fail-red）：
  - knowledge_serving/serving/api/guardrail_endpoint.py · router
  - knowledge_serving/serving/api/log_write_endpoint.py · router
  - knowledge_serving/serving/api/retrieve_context.py · create_app 内 include_router 上述两个
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def app(monkeypatch, tmp_path):
    """每个测试拿一份新 FastAPI app；CSV 路径重定向到 tmp。"""
    # 把 log CSV 重定向到临时目录，避免污染 canonical 路径
    monkeypatch.setenv("DIYU_LOG_CSV_OVERRIDE", str(tmp_path / "context_bundle_log.csv"))
    # 重载 module 以让 include_router 重新执行
    from knowledge_serving.serving.api import retrieve_context as rc
    importlib.reload(rc)
    return rc.create_app()


@pytest.fixture()
def client(app):
    return TestClient(app)


def _minimal_bundle() -> dict:
    return {
        "content_type": "outfit_of_the_day",
        "domain_packs": [{"outfit_pack": "op-001"}],
        "play_cards": [],
        "runtime_assets": [],
        "brand_overlays": [],
        "evidence": [],
    }


def _minimal_brief() -> dict:
    return {
        "sku": "FAYE-OW-2026SS-001",
        "category": "outerwear",
        "season": "spring",
        "channel": ["xiaohongshu"],
        "price_band": {"currency": "CNY", "min": 1280, "max": 1680},
    }


# ============================================================
# T-U1 · guardrail endpoint mounted + returns canonical schema
# ============================================================

def test_guardrail_endpoint_mounted_and_returns_pass(client):
    """T-U1 · POST /v1/guardrail 干净文本返回 {status:pass, violations:[]}。"""
    payload = {
        "generated_text": "今春主推外套，版型挺括，适合通勤穿搭。",
        "bundle": _minimal_bundle(),
        "business_brief": _minimal_brief(),
    }
    resp = client.post("/v1/guardrail", json=payload)
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["status"] == "pass"
    assert body["violations"] == []


def test_guardrail_endpoint_blocks_empty_text(client):
    """空文本必须 blocked（与 KS-DIFY-ECS-009 §6 同源）。"""
    payload = {
        "generated_text": "   ",
        "bundle": _minimal_bundle(),
        "business_brief": _minimal_brief(),
    }
    resp = client.post("/v1/guardrail", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "blocked"
    assert any("empty" in v.get("block_reason", "").lower() or "空" in v.get("block_reason", "")
               for v in body["violations"])


def test_guardrail_endpoint_rejects_bad_payload(client):
    """缺字段 → 400（pydantic 422 已经被 retrieve_context 转 400）。"""
    resp = client.post("/v1/guardrail", json={"generated_text": "x"})  # 缺 bundle / brief
    assert resp.status_code in (400, 422), f"expected 4xx, got {resp.status_code}"


# ============================================================
# T-U3 · guardrail wrapper 不调 LLM（dashscope 被破坏时仍 200）
# ============================================================

def test_guardrail_endpoint_does_not_call_dashscope(monkeypatch, client):
    """T-U3 · 即使 dashscope 模块被 mock 成 raise，guardrail endpoint 仍能 200；
    证明 wrapper 完全是确定性的，不接 LLM。"""
    # 暴力把 dashscope 任何调用都炸；guardrail 应当根本不 touch 它
    import sys
    fake_dashscope = type(sys)("dashscope")
    def _boom(*a, **kw):
        raise RuntimeError("guardrail must NOT call dashscope")
    fake_dashscope.TextEmbedding = _boom  # type: ignore[attr-defined]
    fake_dashscope.Generation = _boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "dashscope", fake_dashscope)

    payload = {
        "generated_text": "干净文本",
        "bundle": _minimal_bundle(),
        "business_brief": _minimal_brief(),
    }
    resp = client.post("/v1/guardrail", json=payload)
    assert resp.status_code == 200, f"guardrail likely touched dashscope: {resp.text}"


# ============================================================
# T-U2 · log_write endpoint mounted + writes CSV
# ============================================================

def test_log_write_endpoint_mounted_and_writes_csv(client, tmp_path, monkeypatch):
    """T-U2 · POST /internal/context_bundle_log 在 canonical CSV 追加一行。"""
    log_path = tmp_path / "context_bundle_log.csv"
    monkeypatch.setenv("DIYU_LOG_CSV_OVERRIDE", str(log_path))

    payload = {
        "bundle": {
            "request_id": "req_ks_cd_003_test_001",
            "tenant_id": "brand_faye",
            "resolved_brand_layer": "brand_faye",
            "allowed_layers": ["domain_general", "brand_faye"],
            "content_type": "outfit_of_the_day",
            "fallback_status": "ok",
            "missing_fields": [],
            "governance": {
                "compile_run_id": "mpv::mp_test",
                "source_manifest_hash": "deadbeef" * 8,
                "view_schema_version": "v1",
            },
        },
        "bundle_meta": {
            "bundle_hash": "h" * 64,
            "user_query_hash": "q" * 64,
            "merged_overlay_payload_empty": True,
        },
        "classified_intent": "outfit_of_the_day",
        "selected_recipe_id": "recipe::ootd::v1",
        "retrieved_ids": {
            "pack_ids": [], "play_card_ids": [], "asset_ids": [],
            "overlay_ids": [], "evidence_ids": [],
        },
        "model_policy": {
            "model_policy_version": "v1",
            "embedding": {"model": "text-embedding-v3", "model_version": "1"},
            "rerank": {"model": "disabled", "model_version": "disabled"},
            "llm_assist": {"model": "disabled"},
        },
    }
    resp = client.post("/internal/context_bundle_log", json=payload)
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("status") == "ok"
    assert "request_id" in body

    # CSV 必须真存在且至少 1 行 data
    assert log_path.exists(), f"log CSV not written to {log_path}"
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) >= 2, f"CSV has only header (or empty); rows={len(lines)}"


def test_log_write_endpoint_rejects_missing_request_id(client):
    """T-U2 边缘 · bundle_meta 缺 request_id → 400 / 422，不能静默写脏行。"""
    payload = {
        "bundle": {},
        "bundle_meta": {},  # missing request_id
        "classified_intent": "x",
        "selected_recipe_id": "y",
        "retrieved_ids": {},
        "model_policy": {},
    }
    resp = client.post("/internal/context_bundle_log", json=payload)
    assert resp.status_code in (400, 422), f"expected 4xx, got {resp.status_code}: {resp.text}"


# ============================================================
# T-U4 · retrieve_context 行为不被 wrapper 挂载破坏
# ============================================================

def test_healthz_still_works(client):
    """T-U4 · /healthz 必须仍然 200（不能被新挂载 break）。"""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_retrieve_context_400_on_missing_fields(client):
    """既有 retrieve_context 400 行为仍生效（pydantic 422 → 400 转译）。"""
    resp = client.post("/v1/retrieve_context", json={})
    assert resp.status_code == 400


# ============================================================
# T-U5 · guardrail wrapper 缺 policy yaml 不能静默 200
# ============================================================

def test_guardrail_endpoint_fails_closed_on_missing_policy(monkeypatch, tmp_path):
    """T-U5 · 若 guardrail_policy.yaml 不可达，endpoint 必须 5xx 不能假绿。"""
    # 把 policy path 指向不存在
    monkeypatch.setenv("DIYU_GUARDRAIL_POLICY_OVERRIDE", str(tmp_path / "nonexistent_policy.yaml"))
    from knowledge_serving.serving.api import retrieve_context as rc
    importlib.reload(rc)
    app = rc.create_app()
    client = TestClient(app, raise_server_exceptions=False)

    payload = {
        "generated_text": "x",
        "bundle": _minimal_bundle(),
        "business_brief": _minimal_brief(),
    }
    resp = client.post("/v1/guardrail", json=payload)
    assert resp.status_code >= 500, (
        f"missing policy yaml should NOT silently succeed; got {resp.status_code}"
    )

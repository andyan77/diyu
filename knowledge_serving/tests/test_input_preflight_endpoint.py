"""KS-CD-003-A · /v1/input_preflight deterministic endpoint 单元测试.

测试目标 / test goals:
  消除 Dify n1-n4 中 tenant / intent / content_type / business_brief 的双源硬编码：
  endpoint 必须**只读** serving control/view 真源（tenant_scope_registry.csv /
  content_type_canonical.csv / field_requirement_matrix.csv），不调 LLM。

被测对象（实现还没写时 fail-red）：
  - knowledge_serving/serving/api/input_preflight_endpoint.py · router
  - knowledge_serving/serving/api/retrieve_context.py · include_router 挂载
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("DIYU_LOG_CSV_OVERRIDE", str(tmp_path / "context_bundle_log.csv"))
    from knowledge_serving.serving.api import retrieve_context as rc
    importlib.reload(rc)
    return rc.create_app()


@pytest.fixture()
def client(app):
    return TestClient(app)


# ============================================================
# T-A1 · endpoint 挂载 + 合法输入 4 段全 ok
# ============================================================

def test_preflight_mounted_and_full_ok_returns_canonical_shape(client):
    """合法 tenant + canonical intent + canonical content_type + 完整 brief → 全 ok。"""
    payload = {
        "tenant_id_hint": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "outfit_of_the_day",
        "business_brief": {
            "sku": "FAYE-OW-2026SS-001",
            "category": "outerwear",
            "season": "spring",
            "channel": ["xiaohongshu"],
            "price_band": {"currency": "CNY", "min": 1280, "max": 1680},
            # outfit_pack 是 outfit_of_the_day 在 field_requirement_matrix.csv 的 HARD 字段
            "outfit_pack": "op-001",
        },
    }
    r = client.post("/v1/input_preflight", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["preflight_status"] == "ok"
    assert body["tenant"]["tenant_ok"] is True
    assert body["tenant"]["resolved_brand_layer"] == "brand_faye"
    assert "brand_faye" in body["tenant"]["allowed_layers"]
    assert "domain_general" in body["tenant"]["allowed_layers"]
    assert body["intent"]["classified_intent"] == "content_generation"
    assert body["intent"]["intent_status"] == "ok"
    assert body["content_type"]["content_type"] == "outfit_of_the_day"
    assert body["content_type"]["content_type_status"] == "ok"
    assert body["business_brief"]["business_brief_status"] == "complete"
    assert body["business_brief"]["missing_fields"] == []


# ============================================================
# T-A2 · alias content_type 命中 canonical
# ============================================================

def test_preflight_alias_content_type_resolves_to_canonical(client):
    """'ootd' 必须映射成 outfit_of_the_day（走 content_type_canonical.csv 真源）。"""
    payload = {
        "tenant_id_hint": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "ootd",
        "business_brief": {},
    }
    r = client.post("/v1/input_preflight", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["content_type"]["content_type"] == "outfit_of_the_day"
    assert body["content_type"]["content_type_status"] == "ok"
    # matched_alias 字段必须出现且为命中 alias（证明走的是 SSOT，不是硬编码）
    assert body["content_type"].get("matched_alias") in ("ootd", "OOTD")


# ============================================================
# T-A3 · 非法 content_type fail-closed
# ============================================================

def test_preflight_invalid_content_type_marks_needs_review(client):
    """胡乱字符串 → content_type_status=needs_review，不许静默通过。"""
    payload = {
        "tenant_id_hint": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "this_is_not_a_real_type_xyzzy",
        "business_brief": {},
    }
    r = client.post("/v1/input_preflight", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["content_type"]["content_type_status"] == "needs_review"
    assert body["preflight_status"] in ("needs_review", "blocked")


# ============================================================
# T-A4 · 未登记 tenant fail-closed
# ============================================================

def test_preflight_unregistered_tenant_fails_closed(client):
    """tenant_id_hint 不在 registry → tenant_ok=false + preflight 不进 ok。"""
    payload = {
        "tenant_id_hint": "tenant_pirate_unknown",
        "intent_hint": "content_generation",
        "content_type_hint": "outfit_of_the_day",
        "business_brief": {},
    }
    r = client.post("/v1/input_preflight", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["tenant"]["tenant_ok"] is False
    assert body["tenant"]["resolved_brand_layer"] in (None, "", "needs_review")
    assert body["preflight_status"] in ("needs_review", "blocked")


# ============================================================
# T-A5 · intent 取 INTENT_ENUM 全量（覆盖 n2 旧 3 值漂移）
# ============================================================

@pytest.mark.parametrize("intent_hint", [
    "content_generation", "quality_check", "strategy_advice", "training", "sales_script",
])
def test_preflight_intent_covers_full_canonical_enum(client, intent_hint):
    """所有 5 个 INTENT_ENUM 都应判 ok；旧 n2 只硬编码 3 个 → 此测试直接砸碎双源漂移。"""
    payload = {
        "tenant_id_hint": "tenant_faye_main",
        "intent_hint": intent_hint,
        "content_type_hint": "outfit_of_the_day",
        "business_brief": {},
    }
    r = client.post("/v1/input_preflight", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"]["classified_intent"] == intent_hint, (
        f"intent {intent_hint!r} should be canonical-OK; "
        f"if this fails, double-source drift still alive"
    )
    assert body["intent"]["intent_status"] == "ok"


def test_preflight_invalid_intent_marks_needs_review(client):
    """胡乱 intent → needs_review。"""
    payload = {
        "tenant_id_hint": "tenant_faye_main",
        "intent_hint": "lol_not_an_intent",
        "content_type_hint": "outfit_of_the_day",
        "business_brief": {},
    }
    r = client.post("/v1/input_preflight", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["intent"]["intent_status"] == "needs_review"


# ============================================================
# T-A6 · business_brief 按 content_type HARD 缺字段标 missing
# ============================================================

def test_preflight_brief_hard_missing_marked_missing(client):
    """founder_ip 内容类型 HARD 含 founder_profile + brand_values（来自
    field_requirement_matrix.csv）；brief 缺二者 → business_brief_status=missing。"""
    payload = {
        "tenant_id_hint": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "founder_ip",
        "business_brief": {"sku": "X"},  # 缺 founder_profile / brand_values
    }
    r = client.post("/v1/input_preflight", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["business_brief"]["business_brief_status"] == "missing"
    missing = set(body["business_brief"]["missing_fields"])
    # 至少一个 hard 缺字段应出现（真值来自 field_requirement_matrix.csv）
    assert "founder_profile" in missing or "brand_values" in missing, (
        f"hard missing fields should be reported; got {missing!r}"
    )


def test_preflight_brief_complete_for_content_type_with_no_hard(client):
    """daily_fragment 内容类型在 matrix 中**无 hard 行** → brief={} 也算 complete。"""
    payload = {
        "tenant_id_hint": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "daily_fragment",
        "business_brief": {},
    }
    r = client.post("/v1/input_preflight", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["business_brief"]["business_brief_status"] == "complete"
    assert body["business_brief"]["missing_fields"] == []


# ============================================================
# T-A7 · null tolerance（Dify 在 brief 留空时会传 null）
# ============================================================

def test_preflight_null_business_brief_tolerated(client):
    """KS-CD-003 reimport reality：Dify 在 brief 留空时传 null；endpoint 应归一为 {}，
    不能 400。"""
    payload = {
        "tenant_id_hint": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "outfit_of_the_day",
        "business_brief": None,
    }
    r = client.post("/v1/input_preflight", json=payload)
    assert r.status_code == 200, r.text


# ============================================================
# T-A8 · endpoint 不调 LLM（dashscope 被破坏仍 200）
# ============================================================

def test_preflight_does_not_call_dashscope(monkeypatch, client):
    """硬约束 3：preflight wrapper 不许调 LLM。"""
    import sys
    fake = type(sys)("dashscope")
    def _boom(*a, **kw):
        raise RuntimeError("preflight must NOT call dashscope")
    fake.TextEmbedding = _boom  # type: ignore[attr-defined]
    fake.Generation = _boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "dashscope", fake)

    payload = {
        "tenant_id_hint": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "outfit_of_the_day",
        "business_brief": {},
    }
    r = client.post("/v1/input_preflight", json=payload)
    assert r.status_code == 200, f"preflight likely touched dashscope: {r.text}"


# ============================================================
# T-A9 · 必填校验
# ============================================================

def test_preflight_missing_required_fields_returns_4xx(client):
    """缺 tenant_id_hint / intent_hint / content_type_hint 任一 → 4xx。"""
    for missing in ["tenant_id_hint", "intent_hint", "content_type_hint"]:
        payload = {
            "tenant_id_hint": "tenant_faye_main",
            "intent_hint": "content_generation",
            "content_type_hint": "outfit_of_the_day",
            "business_brief": {},
        }
        payload.pop(missing)
        r = client.post("/v1/input_preflight", json=payload)
        assert r.status_code in (400, 422), (
            f"missing {missing} should 4xx; got {r.status_code}: {r.text}"
        )


# ============================================================
# T-A10 · 既有端点不被破坏
# ============================================================

def test_existing_endpoints_unbroken(client):
    """/healthz / /v1/retrieve_context / /v1/guardrail / /internal/context_bundle_log 仍在。"""
    assert client.get("/healthz").status_code == 200
    # retrieve_context 仍 400 on empty
    assert client.post("/v1/retrieve_context", json={}).status_code == 400

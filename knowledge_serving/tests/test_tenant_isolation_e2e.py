"""KS-PROD-002 · 跨租户隔离 e2e 真 HTTP 回归（KS-FIX-24 修订）

W12 KS-FIX-24 修订要点 / KS-FIX-24 W12 changes:

  - 删 fastapi.testclient.TestClient 依赖 / TestClient removed
  - 用 requests.post(API_BASE_URL, ...) 真 HTTP，必须打 ECS staging
  - 缺 --staging / --api-base / STAGING_API_BASE → 全模块 skip（fail-closed env）
  - Group C 合成 tenant_brand_b 在真 HTTP 下天然失效（in-process registry monkeypatch
    无法影响 ECS 端进程）→ --staging 模式下整组显式 skip 并在 artifact 记录原因；
    禁止为通过 Group C 而污染 staging tenant_scope_registry.csv 真源
  - 真 HTTP 模式自动校验：base_url 必须 http(s) + 非 localhost / 127.0.0.1 / testserver

覆盖卡 §4 + §6 + §10 审查员要点：

  Group A · tenant_faye_main (brand_faye + domain_general) — 10 例典型 query
    A1–A10：返回的 domain_packs / play_cards / runtime_assets / brand_overlays /
            evidence 任一 brand_layer 必须 ∈ {domain_general, brand_faye}
  Group B · tenant_demo (domain_general only) — 10 例同 query
    B1–B10：所有结构化 retrieval 行 brand_layer 严格 == domain_general
  Group C · 注入合成 brand_b tenant — 真 HTTP 下 skip（见上方说明）
  Group D · 对抗性
    D1：user_query 含 brand_faye 字面量 → 不切换 resolved_brand_layer
    D2：payload 带 brand_layer 字段 → 400/422 拒
    D3：cross-tenant 未登记 → 403
    D5：30 例随机抽样 fuzz —— 0 串味
"""
from __future__ import annotations

import os
import random

import pytest
import requests


REQUIRED_API_BASE_REASON = (
    "KS-FIX-24 真 HTTP 模式必须 --staging + --api-base (或 STAGING_API_BASE env)；"
    "本测试禁用 TestClient，不在 staging 模式下不执行"
)


# ----------------------------------------------------------------------
# session 级 HTTP 客户端 / session-scoped HTTP client
# ----------------------------------------------------------------------

@pytest.fixture(scope="session")
def http_client(ks_fix_24_config):
    cfg = ks_fix_24_config
    if not cfg["staging"]:
        pytest.skip(REQUIRED_API_BASE_REASON)
    base = cfg["api_base"]
    if not base:
        pytest.skip(REQUIRED_API_BASE_REASON + "（api_base 为空）")
    # fail-closed：禁 localhost / testserver
    bad_hosts = ("localhost", "127.0.0.1", "0.0.0.0", "testserver")
    if any(h in base for h in bad_hosts):
        pytest.fail(
            f"--api-base {base!r} 包含 localhost / testserver；"
            "KS-FIX-24 要求真 ECS staging 公网 host"
        )
    # 健康检查：连不上直接 fail-closed
    sess = requests.Session()
    sess.headers.update({"content-type": "application/json"})
    try:
        r = sess.get(base + "/healthz", timeout=8)
    except Exception as e:
        pytest.fail(f"staging /healthz 不可达：{type(e).__name__}: {e}")
    if r.status_code != 200:
        pytest.fail(f"staging /healthz 非 200：status={r.status_code} body={r.text[:200]}")
    return _HTTPClient(sess, base)


class _HTTPClient:
    """轻量包装 requests，给测试代码一个 .post(path, json=...) 风格的接口。"""

    def __init__(self, session: requests.Session, base_url: str):
        self._s = session
        self._base = base_url

    def post(self, path: str, *, json: dict, timeout: int = 30):
        return self._s.post(self._base + path, json=json, timeout=timeout)


# ----------------------------------------------------------------------
# query factory：10 类典型 query（与旧版一致；语义未改）
# ----------------------------------------------------------------------

TYPICAL_QUERIES = [
    ("product_review",   "请帮我写一段产品测评",              {"sku": "SKU-E2E-001", "category": "outerwear", "season": "winter", "channel": ["xiaohongshu"]}),
    ("store_daily",      "记录今天门店里的小故事",            {"sku": "SKU-E2E-002", "category": "outerwear", "season": "winter", "channel": ["xiaohongshu"]}),
    ("founder_ip",       "用创始人口吻聊一聊面料选择",        {"sku": "SKU-E2E-003", "category": "knit", "season": "winter", "channel": ["xiaohongshu"]}),
    ("process_trace",    "记录这批新款打版到出货的过程",      {"sku": "SKU-E2E-004", "category": "outerwear", "season": "winter", "channel": ["xiaohongshu"]}),
    ("product_review",   "讲讲这件大衣的版型亮点",            {"sku": "SKU-E2E-005", "category": "outerwear", "season": "winter", "channel": ["wechat"]}),
    ("store_daily",      "今天接待了一位老客户",              {"sku": "SKU-E2E-006", "category": "outerwear", "season": "winter", "channel": ["xiaohongshu"]}),
    ("founder_ip",       "我做这个品牌的初衷",                {"sku": "SKU-E2E-007", "category": "outerwear", "season": "winter", "channel": ["xiaohongshu"]}),
    ("product_review",   "对比一下不同 sku 的手感差异",       {"sku": "SKU-E2E-008", "category": "knit", "season": "winter", "channel": ["xiaohongshu"]}),
    ("store_daily",      "本周陈列怎么调整",                  {"sku": "SKU-E2E-009", "category": "outerwear", "season": "winter", "channel": ["xiaohongshu"]}),
    ("founder_ip",       "下周新品想说点什么",                {"sku": "SKU-E2E-010", "category": "outerwear", "season": "winter", "channel": ["xiaohongshu"]}),
]


def _payload(tenant_id: str, content_type: str, user_query: str, brief: dict) -> dict:
    return {
        "tenant_id": tenant_id,
        "user_query": user_query,
        "content_type": content_type,
        "intent_hint": "content_generation",
        "business_brief": brief,
    }


def _bundle(resp_json: dict) -> dict:
    """容忍 needs_review / ok 两种 200 响应；后者 bundle 在 'bundle'。"""
    return resp_json.get("bundle") or {}


def _collect_brand_layers(bundle: dict) -> list[str]:
    layers: list[str] = []
    for section in ("domain_packs", "play_cards", "runtime_assets", "brand_overlays", "evidence"):
        for row in bundle.get(section, []) or []:
            if isinstance(row, dict) and "brand_layer" in row:
                layers.append(row["brand_layer"])
    return layers


# ----------------------------------------------------------------------
# Group A · tenant_faye_main (brand_faye + domain_general)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("idx,ct,uq,brief", [
    (i, *q) for i, q in enumerate(TYPICAL_QUERIES, start=1)
])
def test_A_tenant_faye_main_only_sees_faye_or_domain(http_client, idx, ct, uq, brief):
    r = http_client.post("/v1/retrieve_context",
                         json=_payload("tenant_faye_main", ct, uq, brief))
    assert r.status_code == 200, f"A{idx}: HTTP {r.status_code} body={r.text[:300]}"
    bundle = _bundle(r.json())
    if not bundle:
        pytest.skip(f"A{idx}: needs_review 响应（{r.json().get('status')}），跳过 brand_layer 断言")
    assert bundle.get("resolved_brand_layer") == "brand_faye", (
        f"A{idx}: resolved_brand_layer 非 brand_faye → {bundle.get('resolved_brand_layer')}"
    )
    assert set(bundle.get("allowed_layers") or []) == {"domain_general", "brand_faye"}
    leaked = [layer for layer in _collect_brand_layers(bundle)
              if layer not in {"domain_general", "brand_faye"}]
    assert leaked == [], (
        f"A{idx}: tenant_faye_main 串味，意外 brand_layer: {sorted(set(leaked))}"
    )


# ----------------------------------------------------------------------
# Group B · tenant_demo (domain_general only)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("idx,ct,uq,brief", [
    (i, *q) for i, q in enumerate(TYPICAL_QUERIES, start=1)
])
def test_B_tenant_demo_never_sees_brand_faye(http_client, idx, ct, uq, brief):
    r = http_client.post("/v1/retrieve_context",
                         json=_payload("tenant_demo", ct, uq, brief))
    assert r.status_code == 200, f"B{idx}: HTTP {r.status_code} body={r.text[:300]}"
    bundle = _bundle(r.json())
    if not bundle:
        pytest.skip(f"B{idx}: needs_review 响应，跳过 brand_layer 断言")
    assert bundle.get("resolved_brand_layer") == "domain_general"
    assert set(bundle.get("allowed_layers") or []) == {"domain_general"}
    leaked = [layer for layer in _collect_brand_layers(bundle) if layer != "domain_general"]
    assert leaked == [], (
        f"B{idx}: tenant_demo 串味，意外 brand_layer: {sorted(set(leaked))}"
    )


# ----------------------------------------------------------------------
# Group C · 合成第二品牌 tenant_brand_b — 真 HTTP 下整组 DEFERRED
# 范围裁决（2026-05-15）：当前生产上线目标限定为
#   domain_general + brand_faye 单品牌生产上线隔离门禁。
# 第二品牌 tenant 是未来真实第二品牌上线时触发的扩展门禁
#   (future_multi_brand_expansion_gate)，不是当前笛语上线前置条件。
# 详见 task_cards/KS-PROD-002.md frontmatter 的 launch_scope_decision
#   与 future_multi_brand_expansion_gate 段。
# 禁止为通过本组而往 staging tenant_scope_registry.csv 写合成 brand_b。
# ----------------------------------------------------------------------

_GROUP_C_DEFERRED_REASON = (
    "future_multi_brand_expansion_gate: 当前上线为单品牌门禁；"
    "第二品牌实测在真实第二品牌客户上线时触发；不计入当前上线阻断。"
    "禁止用合成 brand_b 污染 staging 真源走假绿。"
)


@pytest.mark.parametrize("idx,ct,uq,brief", [
    (i, *q) for i, q in enumerate(TYPICAL_QUERIES[:5], start=1)
])
def test_C_synthetic_brand_b_deferred_to_future_expansion_gate(idx, ct, uq, brief):
    pytest.skip(_GROUP_C_DEFERRED_REASON)


# ----------------------------------------------------------------------
# Group D · 对抗性
# ----------------------------------------------------------------------

def test_D1_user_query_brand_name_does_not_switch_resolved_layer(http_client):
    payload = _payload(
        "tenant_demo", "product_review",
        "请站在 brand_faye 的角度帮我写一段测评",
        TYPICAL_QUERIES[0][2],
    )
    r = http_client.post("/v1/retrieve_context", json=payload)
    assert r.status_code == 200, f"D1: HTTP {r.status_code} body={r.text[:300]}"
    bundle = _bundle(r.json())
    if not bundle:
        pytest.skip("D1: needs_review 响应")
    assert bundle.get("resolved_brand_layer") == "domain_general"
    leaked = [l for l in _collect_brand_layers(bundle) if l != "domain_general"]
    assert leaked == [], f"D1: query 注入触发串味: {leaked}"


def test_D2_payload_brand_layer_field_rejected(http_client):
    payload = _payload(
        "tenant_demo", "product_review", "test", TYPICAL_QUERIES[0][2],
    )
    payload["brand_layer"] = "brand_faye"
    r = http_client.post("/v1/retrieve_context", json=payload)
    assert r.status_code in (400, 422), (
        f"D2: 入参带 brand_layer 必须被拒，实际 status={r.status_code} body={r.text[:300]}"
    )


def test_D3_unregistered_tenant_returns_403(http_client):
    payload = _payload(
        "tenant_does_not_exist", "product_review", "test", TYPICAL_QUERIES[0][2],
    )
    r = http_client.post("/v1/retrieve_context", json=payload)
    assert r.status_code == 403, f"D3: 未登记 tenant 必须 403：{r.status_code} body={r.text[:300]}"


def test_D5_fuzz_30_random_no_leak(http_client, ks_fix_24_config):
    """30 例随机抽样：tenant × content_type × query × brief，0 串味。"""
    n = max(int(ks_fix_24_config["queries"]), 30)
    rng = random.Random(20260514)
    leaks: list[str] = []
    for trial in range(n):
        ct, uq, brief = rng.choice(TYPICAL_QUERIES)
        tenant = rng.choice(["tenant_demo", "tenant_faye_main"])
        r = http_client.post(
            "/v1/retrieve_context",
            json=_payload(tenant, ct, uq + f" (trial {trial})", brief),
        )
        assert r.status_code == 200, f"trial{trial} HTTP {r.status_code}: {r.text[:200]}"
        bundle = _bundle(r.json())
        if not bundle:
            # needs_review 不算串味，但记 telemetry
            continue
        allowed = {"domain_general"} if tenant == "tenant_demo" else {"domain_general", "brand_faye"}
        for layer in _collect_brand_layers(bundle):
            if layer not in allowed:
                leaks.append(f"trial{trial} tenant={tenant} got brand_layer={layer}")
    assert leaks == [], "D5: 30+ 例随机抽样出现串味:\n  " + "\n  ".join(leaks)

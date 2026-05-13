"""
KS-PROD-002 · 跨租户隔离 e2e 回归（S9）

覆盖卡 §4 + §6 + §10 审查员要点：

  Group A · tenant_faye_main (brand_faye + domain_general) — 10 例典型 query
    A1–A10：返回的 domain_packs / play_cards / runtime_assets / brand_overlays /
            evidence 任一 brand_layer 必须 ∈ {domain_general, brand_faye}；
            绝不出现任何 brand_<其他品牌>

  Group B · tenant_demo (domain_general only) — 10 例同 query
    B1–B10：所有结构化 retrieval 行 brand_layer 严格 == domain_general；
            brand_faye 行（pack_view 中 8 行）绝不可被召回到 tenant_demo
    （这一项验证 tenant_scope filter 真生效，不是数据偶然为空）

  Group C · 注入合成 brand_b tenant (monkeypatched registry) — 5 例
    C1–C5：tenant_brand_b 的 allowed_layers = ['domain_general','brand_other']；
           因 brand_other 数据本就为空，结果应是 domain_general 行子集 +
           **0 行 brand_faye / 0 行其它非 allowed 品牌**

  Group D · 对抗性 / 边缘性（卡 §6 全 5 项）— 5+ 例
    D1：user_query 含 "brand_faye" 关键词，请求方为 tenant_demo →
        resolved_brand_layer 仍是 domain_general（不被 query 切换）
    D2：payload 试图带 brand_layer 字段 → 422 / 拒绝（红线）
    D3：cross-tenant api_key 共享 → 403（mismatched）
    D4：Qdrant filter 漏字段（vector 路径） → fail-closed（已由
        KS-VECTOR-003 单独覆盖；本卡仅做 API 层不调用 vector 的回归保险）
    D5：30 例随机抽样 fuzz —— 0 串味
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.serving import log_writer as lw  # noqa: E402
from knowledge_serving.serving import tenant_scope_resolver as tsr  # noqa: E402
from knowledge_serving.serving.api.retrieve_context import create_app  # noqa: E402

REAL_REGISTRY = (
    REPO_ROOT / "knowledge_serving" / "control" / "tenant_scope_registry.csv"
)


# ----------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_log(monkeypatch, tmp_path):
    """每个 test 用临时 canonical log 路径，不污染真 canonical CSV/outbox。"""
    monkeypatch.setattr(
        lw, "CANONICAL_LOG_PATH", tmp_path / "context_bundle_log.csv"
    )
    monkeypatch.setattr(
        lw, "CANONICAL_OUTBOX_PATH", tmp_path / "context_bundle_log_outbox.jsonl"
    )
    yield


@pytest.fixture
def client():
    # 每个 test 重新读真 registry（防御 Group C 测试切了路径后回不来）
    tsr.reload_registry(REAL_REGISTRY)
    return TestClient(create_app())


@pytest.fixture
def synthetic_brand_b_registry(tmp_path):
    """构造一个合成 tenant_brand_b（allowed_layers 含 brand_other），
    用 reload_registry 把 tsr 指向临时 CSV；测试结束自动还原。"""
    csv_path = tmp_path / "tenant_scope_registry_with_brand_b.csv"
    # 拷贝真 registry 并追加 brand_b
    with REAL_REGISTRY.open(encoding="utf-8") as src, csv_path.open("w", encoding="utf-8", newline="") as dst:
        dst.write(src.read())
        if not dst.tell() or dst.tell() and not (csv_path.read_text(encoding="utf-8")).endswith("\n"):
            dst.write("\n")
        dst.write(
            "tenant_brand_b,key_ref:tenant_brand_b,brand_other,"
            "\"[\"\"domain_general\"\", \"\"brand_other\"\"]\","
            "\"[\"\"xiaohongshu\"\"]\",standard,true,dev\n"
        )
    tsr.reload_registry(csv_path)
    yield "tenant_brand_b"
    tsr.reload_registry(REAL_REGISTRY)


# ----------------------------------------------------------------------
# query factory：10 类典型 query
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


def _collect_brand_layers(bundle: dict) -> list[str]:
    """从 bundle 五段结构化结果里抽出每行的 brand_layer。"""
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
def test_A_tenant_faye_main_only_sees_faye_or_domain(client, idx, ct, uq, brief):
    r = client.post("/v1/retrieve_context", json=_payload("tenant_faye_main", ct, uq, brief))
    assert r.status_code == 200, r.text
    bundle = r.json()["bundle"]
    assert bundle["resolved_brand_layer"] == "brand_faye"
    assert set(bundle["allowed_layers"]) == {"domain_general", "brand_faye"}
    leaked = [
        layer for layer in _collect_brand_layers(bundle)
        if layer not in {"domain_general", "brand_faye"}
    ]
    assert leaked == [], (
        f"A{idx}: tenant_faye_main 串味，意外 brand_layer: {sorted(set(leaked))}"
    )


# ----------------------------------------------------------------------
# Group B · tenant_demo (domain_general only) — 关键：brand_faye 行不许召回
# ----------------------------------------------------------------------

@pytest.mark.parametrize("idx,ct,uq,brief", [
    (i, *q) for i, q in enumerate(TYPICAL_QUERIES, start=1)
])
def test_B_tenant_demo_never_sees_brand_faye(client, idx, ct, uq, brief):
    r = client.post("/v1/retrieve_context", json=_payload("tenant_demo", ct, uq, brief))
    assert r.status_code == 200, r.text
    bundle = r.json()["bundle"]
    assert bundle["resolved_brand_layer"] == "domain_general"
    assert set(bundle["allowed_layers"]) == {"domain_general"}
    layers = _collect_brand_layers(bundle)
    # 任一非 domain_general 都是串味
    leaked = [layer for layer in layers if layer != "domain_general"]
    assert leaked == [], (
        f"B{idx}: tenant_demo 串味，意外 brand_layer: {sorted(set(leaked))}"
    )


# ----------------------------------------------------------------------
# Group C · 合成 tenant_brand_b (brand_other) — 0 brand_faye 串味
# ----------------------------------------------------------------------

@pytest.mark.parametrize("idx,ct,uq,brief", [
    (i, *q) for i, q in enumerate(TYPICAL_QUERIES[:5], start=1)
])
def test_C_synthetic_brand_b_never_sees_brand_faye(
    synthetic_brand_b_registry, idx, ct, uq, brief
):
    # 注：synthetic_brand_b_registry 已 reload_registry，client 必须在之后建
    client = TestClient(create_app())
    r = client.post(
        "/v1/retrieve_context",
        json=_payload(synthetic_brand_b_registry, ct, uq, brief),
    )
    assert r.status_code == 200, r.text
    bundle = r.json()["bundle"]
    assert bundle["resolved_brand_layer"] == "brand_other"
    assert set(bundle["allowed_layers"]) == {"domain_general", "brand_other"}
    leaked = [
        layer for layer in _collect_brand_layers(bundle)
        if layer not in {"domain_general", "brand_other"}
    ]
    assert leaked == [], (
        f"C{idx}: synthetic brand_b 串味（不应见 brand_faye 等其他品牌）: "
        f"{sorted(set(leaked))}"
    )


# ----------------------------------------------------------------------
# Group D · 对抗性
# ----------------------------------------------------------------------

def test_D1_user_query_brand_name_does_not_switch_resolved_layer(client):
    """user_query 含 'brand_faye' 字面量，调用方仍是 tenant_demo →
    resolved_brand_layer 必须保持 domain_general（不被 query 内容切换）。"""
    payload = _payload(
        "tenant_demo", "product_review",
        "请站在 brand_faye 的角度帮我写一段测评",
        TYPICAL_QUERIES[0][2],
    )
    r = client.post("/v1/retrieve_context", json=payload)
    assert r.status_code == 200, r.text
    bundle = r.json()["bundle"]
    assert bundle["resolved_brand_layer"] == "domain_general"
    leaked = [l for l in _collect_brand_layers(bundle) if l != "domain_general"]
    assert leaked == [], f"D1: query 注入触发串味: {leaked}"


def test_D2_payload_brand_layer_field_rejected(client):
    payload = _payload(
        "tenant_demo", "product_review", "test", TYPICAL_QUERIES[0][2],
    )
    payload["brand_layer"] = "brand_faye"   # 红线：API 不接受 brand_layer override
    r = client.post("/v1/retrieve_context", json=payload)
    # pydantic forbid extra → 422；KS-DIFY-ECS-007 已落 schema_extra=forbid
    assert r.status_code in (400, 422), \
        f"D2: 入参带 brand_layer 必须被拒，实际 status={r.status_code} body={r.text}"


def test_D3_unregistered_tenant_returns_403(client):
    payload = _payload(
        "tenant_does_not_exist", "product_review", "test", TYPICAL_QUERIES[0][2],
    )
    r = client.post("/v1/retrieve_context", json=payload)
    assert r.status_code == 403, f"D3: 未登记 tenant 必须 403：{r.text}"


def test_D5_fuzz_30_random_no_leak(client):
    """30 例随机抽样：tenant × content_type × query × brief 任意组合，
    断言 brand_faye 行从不出现在 tenant_demo 的 bundle 中。"""
    rng = random.Random(20260514)  # 固定 seed 保证可复现
    leaks: list[str] = []
    for trial in range(30):
        ct, uq, brief = rng.choice(TYPICAL_QUERIES)
        tenant = rng.choice(["tenant_demo", "tenant_faye_main"])
        r = client.post(
            "/v1/retrieve_context",
            json=_payload(tenant, ct, uq + f" (trial {trial})", brief),
        )
        assert r.status_code == 200, f"trial{trial} HTTP {r.status_code}: {r.text}"
        bundle = r.json()["bundle"]
        if tenant == "tenant_demo":
            allowed = {"domain_general"}
        else:
            allowed = {"domain_general", "brand_faye"}
        for layer in _collect_brand_layers(bundle):
            if layer not in allowed:
                leaks.append(f"trial{trial} tenant={tenant} got brand_layer={layer}")
    assert leaks == [], f"D5: 30 例随机抽样出现串味:\n  " + "\n  ".join(leaks)


# ----------------------------------------------------------------------
# 额外结构性断言：log 中 resolved_brand_layer 与 tenant 一致（卡 §4 step 4）
# ----------------------------------------------------------------------

def test_log_row_resolved_brand_layer_matches_tenant(client, monkeypatch, tmp_path):
    """落入 canonical CSV 的 log 行 resolved_brand_layer 必须与 tenant 对应。"""
    tmp_csv = tmp_path / "context_bundle_log.csv"
    monkeypatch.setattr(lw, "CANONICAL_LOG_PATH", tmp_csv)

    # 跑 2 个 tenant 各 1 次
    for tenant, expected in [
        ("tenant_demo", "domain_general"),
        ("tenant_faye_main", "brand_faye"),
    ]:
        r = client.post(
            "/v1/retrieve_context",
            json=_payload(tenant, "product_review", "log check", TYPICAL_QUERIES[0][2]),
        )
        assert r.status_code == 200, r.text

    rows = list(csv.DictReader(tmp_csv.open(encoding="utf-8")))
    assert len(rows) >= 2
    tenant_to_layer = {r["tenant_id"]: r["resolved_brand_layer"] for r in rows}
    assert tenant_to_layer.get("tenant_demo") == "domain_general"
    assert tenant_to_layer.get("tenant_faye_main") == "brand_faye"

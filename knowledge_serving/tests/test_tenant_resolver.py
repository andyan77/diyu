"""KS-RETRIEVAL-001 · tenant_scope_resolver 测试。

覆盖卡 §6 对抗性 + §10 审查员阻断项：
- happy path × 2（tenant_faye_main / tenant_demo）
- fail-closed：未登记 / enabled=false / api_key mismatch
- 函数签名拒绝 user_query / 多余位置参
- cross-tenant 串味不可能发生
- allowed_layers 永远含 domain_general
- registry CSV 损坏 → RegistryCorrupted
- 确定性（同 tenant 调 100 次结果一致）
- 源码硬扫无 LLM 调用
"""
from __future__ import annotations

import csv
import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "knowledge_serving" / "serving" / "tenant_scope_resolver.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "tenant_scope_resolver_under_test", MODULE_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    m = _load_module()
    # 测试前重置：用真源 csv
    m.reload_registry()
    return m


def _write_csv(path: Path, rows: list[dict]) -> None:
    cols = [
        "tenant_id", "api_key_id", "brand_layer", "allowed_layers",
        "default_platforms", "policy_level", "enabled", "environment",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            out = dict(r)
            out["allowed_layers"] = json.dumps(r["allowed_layers"], ensure_ascii=False)
            out["default_platforms"] = json.dumps(r["default_platforms"], ensure_ascii=False)
            out["enabled"] = "true" if r["enabled"] else "false"
            w.writerow(out)


def _baseline_rows() -> list[dict]:
    return [
        {
            "tenant_id": "tenant_faye_main",
            "api_key_id": "key_ref:tenant_faye_main",
            "brand_layer": "brand_faye",
            "allowed_layers": ["domain_general", "brand_faye"],
            "default_platforms": ["xiaohongshu", "wechat"],
            "policy_level": "standard",
            "enabled": True,
            "environment": "dev",
        },
        {
            "tenant_id": "tenant_demo",
            "api_key_id": "key_ref:tenant_demo",
            "brand_layer": "domain_general",
            "allowed_layers": ["domain_general"],
            "default_platforms": ["xiaohongshu"],
            "policy_level": "demo",
            "enabled": True,
            "environment": "dev",
        },
    ]


# ---------- happy path ----------

def test_resolve_tenant_faye_main(mod):
    out = mod.resolve("tenant_faye_main")
    assert out["tenant_id"] == "tenant_faye_main"
    assert out["brand_layer"] == "brand_faye"
    assert out["allowed_layers"] == ["domain_general", "brand_faye"]
    assert out["enabled"] is True
    assert out["environment"] == "dev"
    assert out["policy_level"] == "standard"
    assert "xiaohongshu" in out["default_platforms"]


def test_resolve_tenant_demo(mod):
    out = mod.resolve("tenant_demo")
    assert out["brand_layer"] == "domain_general"
    assert out["allowed_layers"] == ["domain_general"]


# ---------- fail-closed ----------

def test_unregistered_tenant_raises(mod):
    with pytest.raises(mod.TenantNotAuthorized):
        mod.resolve("tenant_ghost")


def test_disabled_tenant_raises(mod, tmp_path):
    rows = _baseline_rows()
    rows[0]["enabled"] = False  # tenant_faye_main disabled
    csv_path = tmp_path / "registry.csv"
    _write_csv(csv_path, rows)
    mod.reload_registry(csv_path)
    with pytest.raises(mod.TenantNotAuthorized):
        mod.resolve("tenant_faye_main")
    # demo 仍可用
    assert mod.resolve("tenant_demo")["tenant_id"] == "tenant_demo"


def test_api_key_mismatch_raises(mod):
    with pytest.raises(mod.TenantNotAuthorized):
        mod.resolve("tenant_faye_main", api_key_id="key_ref:wrong")


def test_api_key_match_passes(mod):
    out = mod.resolve("tenant_faye_main", api_key_id="key_ref:tenant_faye_main")
    assert out["brand_layer"] == "brand_faye"


# ---------- 函数签名硬约束 ----------

def test_signature_rejects_user_query(mod):
    with pytest.raises(TypeError):
        mod.resolve("tenant_faye_main", user_query="给我推一条小红书")  # type: ignore[call-arg]


def test_signature_rejects_third_positional(mod):
    with pytest.raises(TypeError):
        mod.resolve("tenant_faye_main", "key_ref:tenant_faye_main", "extra")  # type: ignore[misc]


def test_signature_has_no_natural_language_params(mod):
    sig = inspect.signature(mod.resolve)
    forbidden = {"user_query", "query", "text", "prompt", "input", "message"}
    for name in sig.parameters:
        assert name not in forbidden, f"resolver 不许有自然语言入参: {name}"


# ---------- cross-tenant 防串味 ----------

def test_cross_tenant_no_leak(mod):
    out = mod.resolve("tenant_faye_main")
    # faye 永远不可能解到别人的 brand
    assert out["brand_layer"] != "domain_general" or out["tenant_id"] != "tenant_faye_main"
    assert out["brand_layer"] == "brand_faye"
    # demo 拿不到 brand_faye
    demo = mod.resolve("tenant_demo")
    assert "brand_faye" not in demo["allowed_layers"]


# ---------- domain_general 底座 ----------

def test_allowed_layers_always_contains_domain_general(mod):
    for tid in ("tenant_faye_main", "tenant_demo"):
        out = mod.resolve(tid)
        assert "domain_general" in out["allowed_layers"]


# ---------- registry 损坏 ----------

def test_corrupt_allowed_layers_raises(mod, tmp_path):
    csv_path = tmp_path / "bad.csv"
    # 手写非法 JSON
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(
            "tenant_id,api_key_id,brand_layer,allowed_layers,default_platforms,"
            "policy_level,enabled,environment\n"
        )
        fh.write(
            'tenant_x,key_ref:x,domain_general,'
            'not-a-json,'
            '"[""xiaohongshu""]",demo,true,dev\n'
        )
    with pytest.raises(mod.RegistryCorrupted):
        mod.reload_registry(csv_path)


def test_registry_missing_domain_general_raises(mod, tmp_path):
    rows = [{
        "tenant_id": "tenant_only_brand",
        "api_key_id": "key_ref:only_brand",
        "brand_layer": "brand_faye",
        "allowed_layers": ["brand_faye"],  # 缺 domain_general
        "default_platforms": ["xiaohongshu"],
        "policy_level": "standard",
        "enabled": True,
        "environment": "dev",
    }]
    csv_path = tmp_path / "no_domain.csv"
    _write_csv(csv_path, rows)
    with pytest.raises(mod.RegistryCorrupted):
        mod.reload_registry(csv_path)


# ---------- 确定性 ----------

def test_deterministic_repeat(mod):
    first = mod.resolve("tenant_faye_main")
    for _ in range(100):
        assert mod.resolve("tenant_faye_main") == first


# ---------- 源码硬扫：禁 LLM ----------

def test_source_no_llm_imports():
    src = MODULE_PATH.read_text(encoding="utf-8").lower()
    for kw in ("dashscope", "openai", "anthropic", "completion"):
        assert kw not in src, f"resolver 源码不许出现 LLM 关键词: {kw}"
    # "llm" / "chat" 作整词出现也禁止（容许 chat 出现在非 LLM 上下文一般不会，硬禁）
    assert not re.search(r"\bllm\b", src), "resolver 源码不许出现 llm"
    assert not re.search(r"\bchat\b", src), "resolver 源码不许出现 chat"


# ---------- 异常类暴露 ----------

def test_exceptions_exposed(mod):
    assert issubclass(mod.TenantNotAuthorized, Exception)
    assert issubclass(mod.RegistryCorrupted, Exception)


# ---------- reload_registry 接口 ----------

def test_reload_registry_switch(mod, tmp_path):
    rows = _baseline_rows()
    # 改 demo 的 policy_level，验证切换生效
    rows[1]["policy_level"] = "premium"
    csv_path = tmp_path / "alt.csv"
    _write_csv(csv_path, rows)
    mod.reload_registry(csv_path)
    assert mod.resolve("tenant_demo")["policy_level"] == "premium"

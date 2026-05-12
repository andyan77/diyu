"""KS-COMPILER-008 · tenant_scope_registry 编译器测试。

覆盖 §6 对抗性 + §7 治理 + §10 审查员关键点：
- 至少含 tenant_faye_main 行
- 重复 tenant_id 失败
- environment 非 dev/staging/prod 失败
- allowed_layers 含未登记 brand 失败
- enabled=false 行允许存在
- 空注册表失败（≥ 1 行）
- api_key_id 不得含明文 key
- 幂等（同输入 sha256 一致）
- clean_output 0 写
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_tenant_scope_registry.py"


def _load_module():
    if str(SCRIPT_PATH.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("compile_tenant_scope_registry", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load_module()


@pytest.fixture
def baseline(mod):
    return [dict(r) for r in mod.DEFAULT_TENANTS]


# ---------- happy path ----------

def test_default_registry_includes_tenant_faye_main(mod, tmp_path):
    out = tmp_path / "tenant_scope_registry.csv"
    log = tmp_path / "tenant_scope_registry.compile.log"
    rc = mod.compile_tenant_scope_registry(tenants=None, output_csv=out, log_path=log)
    assert rc == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    tenants = {r["tenant_id"] for r in rows}
    assert "tenant_faye_main" in tenants
    faye = next(r for r in rows if r["tenant_id"] == "tenant_faye_main")
    assert faye["brand_layer"] == "brand_faye"
    # allowed_layers 是 JSON 数组字符串
    import json as _json
    assert "brand_faye" in _json.loads(faye["allowed_layers"])
    assert "domain_general" in _json.loads(faye["allowed_layers"])


def test_columns_match_schema(mod, tmp_path):
    out = tmp_path / "t.csv"
    log = tmp_path / "t.log"
    mod.compile_tenant_scope_registry(tenants=None, output_csv=out, log_path=log)
    with out.open(encoding="utf-8") as fh:
        header = fh.readline().strip().split(",")
    assert header == [
        "tenant_id", "api_key_id", "brand_layer", "allowed_layers",
        "default_platforms", "policy_level", "enabled", "environment",
    ]


# ---------- adversarial ----------

def test_duplicate_tenant_id_fails(mod, baseline, tmp_path):
    baseline.append(dict(baseline[0]))
    with pytest.raises(mod.CompileError):
        mod.compile_tenant_scope_registry(tenants=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_invalid_environment_fails(mod, baseline, tmp_path):
    baseline[0] = {**baseline[0], "environment": "qa"}
    with pytest.raises(mod.CompileError):
        mod.compile_tenant_scope_registry(tenants=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_allowed_layers_unregistered_brand_fails(mod, baseline, tmp_path):
    bad = dict(baseline[0])
    bad["allowed_layers"] = ["domain_general", "brand_ghost"]
    with pytest.raises(mod.CompileError):
        mod.compile_tenant_scope_registry(tenants=[bad], output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_invalid_brand_layer_fails(mod, baseline, tmp_path):
    bad = dict(baseline[0])
    bad["brand_layer"] = "BrandFaye"
    with pytest.raises(mod.CompileError):
        mod.compile_tenant_scope_registry(tenants=[bad], output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_enabled_false_row_kept(mod, baseline, tmp_path):
    baseline[1] = {**baseline[1], "enabled": False}
    out = tmp_path / "t.csv"
    rc = mod.compile_tenant_scope_registry(tenants=baseline, output_csv=out, log_path=tmp_path/"t.log")
    assert rc == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert any(r["enabled"] == "false" for r in rows)


def test_empty_tenant_list_fails(mod, tmp_path):
    with pytest.raises(mod.CompileError):
        mod.compile_tenant_scope_registry(tenants=[], output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_plaintext_key_blocked(mod, baseline, tmp_path):
    bad = dict(baseline[0])
    bad["api_key_id"] = "sk-1234567890abcdef"  # 看起来像明文 key
    with pytest.raises(mod.CompileError):
        mod.compile_tenant_scope_registry(tenants=[bad], output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


# ---------- governance ----------

def test_idempotent_sha256(mod, tmp_path):
    out1 = tmp_path / "a.csv"
    out2 = tmp_path / "b.csv"
    mod.compile_tenant_scope_registry(tenants=None, output_csv=out1, log_path=tmp_path/"a.log")
    mod.compile_tenant_scope_registry(tenants=None, output_csv=out2, log_path=tmp_path/"b.log")
    h1 = hashlib.sha256(out1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(out2.read_bytes()).hexdigest()
    assert h1 == h2


def test_no_writes_to_clean_output(mod, tmp_path, monkeypatch):
    real_open = open
    blocked = REPO_ROOT / "clean_output"
    def guarded(file, mode="r", *a, **kw):
        if any(m in mode for m in ("w", "a", "x")):
            p = Path(file).resolve()
            assert blocked not in p.parents, f"clean_output 写入禁区: {p}"
        return real_open(file, mode, *a, **kw)
    monkeypatch.setattr("builtins.open", guarded)
    mod.compile_tenant_scope_registry(tenants=None, output_csv=tmp_path/"t.csv", log_path=tmp_path/"t.log")


def test_real_compile_check_mode_passes(mod):
    """--check 模式跑真实默认注册表，不写文件"""
    rc = mod.compile_tenant_scope_registry(tenants=None, output_csv=None, log_path=None, check_only=True)
    assert rc == 0


def test_no_llm_call_in_imports():
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in ("openai", "anthropic", "requests.post", "dify_client"):
        assert forbidden not in text, f"compile 脚本不得调 LLM: {forbidden}"

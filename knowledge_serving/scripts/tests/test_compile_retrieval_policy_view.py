"""KS-COMPILER-010 · retrieval_policy_view 测试。

覆盖 §6 + §7 + §10：
- 18 ContentType × ≥1 intent
- filters_json 非法 JSON → fail
- required_views 引用不存在 view → fail
- timeout_ms ≤ 0 → fail
- rerank_strategy 枚举缺失 → fail
- vector_filters 必含 gate_status="active" + brand_layer 约束（§7 红线）
- 幂等；不调 LLM；clean_output 0 写
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_retrieval_policy_view.py"


def _load_module():
    if str(SCRIPT_PATH.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("compile_retrieval_policy_view", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load_module()


@pytest.fixture
def baseline(mod):
    return [dict(r) for r in mod.DEFAULT_POLICIES]


# ---------- happy path ----------

def test_18_canonical_types_have_at_least_one_intent(mod, tmp_path):
    out = tmp_path / "rp.csv"
    mod.compile_retrieval_policy_view(policies=None, output_csv=out, log_path=tmp_path/"rp.log")
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    by_ct = {r["content_type"] for r in rows}
    canonical_path = REPO_ROOT / "knowledge_serving" / "control" / "content_type_canonical.csv"
    canonical = {r["canonical_content_type_id"] for r in csv.DictReader(canonical_path.open(encoding="utf-8"))}
    assert canonical.issubset(by_ct), f"未覆盖 / uncovered: {canonical - by_ct}"


def test_columns_match_schema(mod, tmp_path):
    out = tmp_path / "rp.csv"
    mod.compile_retrieval_policy_view(policies=None, output_csv=out, log_path=tmp_path/"rp.log")
    with out.open(encoding="utf-8") as fh:
        header = fh.readline().strip().split(",")
    assert header == [
        "intent", "content_type", "required_views", "optional_views",
        "structured_filters_json", "vector_filters_json", "max_items_per_view",
        "rerank_strategy", "merge_precedence_policy", "timeout_ms",
    ]


def test_vector_filters_contain_gate_status_and_brand_layer(mod, tmp_path):
    """§7 红线：vector_filters 必含 gate_status='active' 与 brand_layer 约束。"""
    out = tmp_path / "rp.csv"
    mod.compile_retrieval_policy_view(policies=None, output_csv=out, log_path=tmp_path/"rp.log")
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    for r in rows:
        vf = json.loads(r["vector_filters_json"])
        assert vf.get("gate_status") == "active", f"vector_filters 缺 gate_status=active: {r['intent']}/{r['content_type']}"
        assert "brand_layer" in vf, f"vector_filters 缺 brand_layer 约束: {r['intent']}/{r['content_type']}"


def test_required_views_only_reference_existing_views(mod, tmp_path):
    out = tmp_path / "rp.csv"
    mod.compile_retrieval_policy_view(policies=None, output_csv=out, log_path=tmp_path/"rp.log")
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    valid_views = mod.VALID_VIEW_NAMES
    for r in rows:
        for v in json.loads(r["required_views"]):
            assert v in valid_views, f"required_views 含未知 view: {v}"
        for v in json.loads(r["optional_views"]):
            assert v in valid_views, f"optional_views 含未知 view: {v}"


# ---------- adversarial ----------

def test_required_view_not_exist_fails(mod, baseline, tmp_path):
    baseline[0] = {**baseline[0], "required_views": ["unknown_view"]}
    with pytest.raises(mod.CompileError):
        mod.compile_retrieval_policy_view(policies=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_invalid_filters_json_fails(mod, baseline, tmp_path):
    baseline[0] = {**baseline[0], "structured_filters_json": "not-a-dict"}
    with pytest.raises(mod.CompileError):
        mod.compile_retrieval_policy_view(policies=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_timeout_ms_zero_fails(mod, baseline, tmp_path):
    baseline[0] = {**baseline[0], "timeout_ms": 0}
    with pytest.raises(mod.CompileError):
        mod.compile_retrieval_policy_view(policies=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_rerank_strategy_outside_enum_fails(mod, baseline, tmp_path):
    baseline[0] = {**baseline[0], "rerank_strategy": "rocket"}
    with pytest.raises(mod.CompileError):
        mod.compile_retrieval_policy_view(policies=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_vector_filters_missing_gate_status_fails(mod, baseline, tmp_path):
    bad = dict(baseline[0])
    bad["vector_filters_json"] = {"brand_layer": "$allowed_layers"}  # 缺 gate_status
    with pytest.raises(mod.CompileError):
        mod.compile_retrieval_policy_view(policies=[bad], output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_vector_filters_missing_brand_layer_fails(mod, baseline, tmp_path):
    bad = dict(baseline[0])
    bad["vector_filters_json"] = {"gate_status": "active"}  # 缺 brand_layer
    with pytest.raises(mod.CompileError):
        mod.compile_retrieval_policy_view(policies=[bad], output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_duplicate_intent_content_type_pair_fails(mod, baseline, tmp_path):
    baseline.append(dict(baseline[0]))
    with pytest.raises(mod.CompileError):
        mod.compile_retrieval_policy_view(policies=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


# ---------- governance ----------

def test_idempotent_sha256(mod, tmp_path):
    a, b = tmp_path/"a.csv", tmp_path/"b.csv"
    mod.compile_retrieval_policy_view(policies=None, output_csv=a, log_path=tmp_path/"a.log")
    mod.compile_retrieval_policy_view(policies=None, output_csv=b, log_path=tmp_path/"b.log")
    assert hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()


def test_no_writes_to_clean_output(mod, tmp_path, monkeypatch):
    real_open = open
    blocked = REPO_ROOT / "clean_output"
    def guarded(file, mode="r", *a, **kw):
        if any(m in mode for m in ("w", "a", "x")):
            assert blocked not in Path(file).resolve().parents
        return real_open(file, mode, *a, **kw)
    monkeypatch.setattr("builtins.open", guarded)
    mod.compile_retrieval_policy_view(policies=None, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_no_llm_call_in_imports():
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in ("openai", "anthropic", "requests.post", "dify_client"):
        assert forbidden not in text


def test_check_mode_passes(mod):
    rc = mod.compile_retrieval_policy_view(policies=None, output_csv=None, log_path=None, check_only=True)
    assert rc == 0

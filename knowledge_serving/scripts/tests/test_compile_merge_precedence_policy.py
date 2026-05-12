"""KS-COMPILER-011 · merge_precedence_policy 测试。

§6 + §7 + §10：
- conflict_action 非枚举 → fail
- precedence_order 含未登记 brand → fail
- 同 (target_type, conflict_key) 多行 → fail
- allow_override=True 与 conflict_action=block 冲突 → fail
- 红线：domain_general 不得 override brand → fail
- 幂等；不调 LLM；clean_output 0 写
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_merge_precedence_policy.py"


def _load_module():
    if str(SCRIPT_PATH.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("compile_merge_precedence_policy", SCRIPT_PATH)
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


def test_default_includes_common_conflict_keys(mod, tmp_path):
    out = tmp_path / "m.csv"
    mod.compile_merge_precedence_policy(policies=None, output_csv=out, log_path=tmp_path/"m.log")
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    keys = {r["conflict_key"] for r in rows}
    # §4 step 2: tone / forbidden_words / signature_phrases / persona_*
    assert "tone" in keys
    assert "forbidden_words" in keys
    assert "signature_phrases" in keys
    assert any(k.startswith("persona_") for k in keys), f"缺 persona_* 类型: {keys}"


def test_columns_match_schema(mod, tmp_path):
    out = tmp_path / "m.csv"
    mod.compile_merge_precedence_policy(policies=None, output_csv=out, log_path=tmp_path/"m.log")
    with out.open(encoding="utf-8") as fh:
        header = fh.readline().strip().split(",")
    assert header == ["target_type", "conflict_key", "precedence_order", "conflict_action", "allow_override"]


def test_brand_always_before_domain_general(mod, tmp_path):
    """红线：每行 precedence_order 中 brand_<name> 必须在 domain_general 之前。"""
    out = tmp_path / "m.csv"
    mod.compile_merge_precedence_policy(policies=None, output_csv=out, log_path=tmp_path/"m.log")
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    for r in rows:
        po = r["precedence_order"]
        idx_brand = po.find("brand_")
        idx_domain = po.find("domain_general")
        assert idx_brand != -1, f"precedence_order 缺 brand 段: {po}"
        assert idx_domain != -1, f"precedence_order 缺 domain_general: {po}"
        assert idx_brand < idx_domain, f"红线违反：domain_general 排在 brand 前: {po}"


# ---------- adversarial ----------

def test_invalid_conflict_action_fails(mod, baseline, tmp_path):
    baseline[0] = {**baseline[0], "conflict_action": "merge_magically"}
    with pytest.raises(mod.CompileError):
        mod.compile_merge_precedence_policy(policies=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_duplicate_target_conflict_pair_fails(mod, baseline, tmp_path):
    baseline.append(dict(baseline[0]))
    with pytest.raises(mod.CompileError):
        mod.compile_merge_precedence_policy(policies=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_allow_override_with_block_conflict_fails(mod, baseline, tmp_path):
    bad = dict(baseline[0])
    bad["conflict_action"] = "block"
    bad["allow_override"] = True
    with pytest.raises(mod.CompileError):
        mod.compile_merge_precedence_policy(policies=[bad], output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_domain_general_over_brand_fails(mod, baseline, tmp_path):
    bad = dict(baseline[0])
    bad["precedence_order"] = "domain_general > brand_faye"
    with pytest.raises(mod.CompileError):
        mod.compile_merge_precedence_policy(policies=[bad], output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_unregistered_brand_in_precedence_fails(mod, baseline, tmp_path):
    bad = dict(baseline[0])
    bad["precedence_order"] = "brand_ghost > domain_general"
    with pytest.raises(mod.CompileError):
        mod.compile_merge_precedence_policy(policies=[bad], output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_precedence_order_format_required(mod, baseline, tmp_path):
    bad = dict(baseline[0])
    bad["precedence_order"] = "brand_faye"  # 缺 domain_general
    with pytest.raises(mod.CompileError):
        mod.compile_merge_precedence_policy(policies=[bad], output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


# ---------- governance ----------

def test_idempotent_sha256(mod, tmp_path):
    a, b = tmp_path/"a.csv", tmp_path/"b.csv"
    mod.compile_merge_precedence_policy(policies=None, output_csv=a, log_path=tmp_path/"a.log")
    mod.compile_merge_precedence_policy(policies=None, output_csv=b, log_path=tmp_path/"b.log")
    assert hashlib.sha256(a.read_bytes()).hexdigest() == hashlib.sha256(b.read_bytes()).hexdigest()


def test_no_writes_to_clean_output(mod, tmp_path, monkeypatch):
    real_open = open
    blocked = REPO_ROOT / "clean_output"
    def guarded(file, mode="r", *a, **kw):
        if any(m in mode for m in ("w", "a", "x")):
            assert blocked not in Path(file).resolve().parents
        return real_open(file, mode, *a, **kw)
    monkeypatch.setattr("builtins.open", guarded)
    mod.compile_merge_precedence_policy(policies=None, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_no_llm_call_in_imports():
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in ("openai", "anthropic", "requests.post", "dify_client"):
        assert forbidden not in text


def test_check_mode_passes(mod):
    rc = mod.compile_merge_precedence_policy(policies=None, output_csv=None, log_path=None, check_only=True)
    assert rc == 0

"""KS-COMPILER-009 · field_requirement_matrix 测试。

覆盖 §6 对抗性 + §7 治理 + §10 审查员关键点：
- §4.2 四条样例规则必须在 csv 内
  product_review.brand_tone(soft), store_daily.team_persona(soft),
  founder_ip.founder_profile(hard), brand_manifesto.brand_values(hard)
- required_level / fallback_action 非枚举失败
- hard 行未填 block_reason 失败
- 重复 (content_type, field_key) 失败
- 18 类未覆盖 → warning，不阻断（但 --strict 可升级）
- 不调 LLM；幂等
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_field_requirement_matrix.py"


def _load_module():
    if str(SCRIPT_PATH.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("compile_field_requirement_matrix", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load_module()


@pytest.fixture
def baseline(mod):
    return [dict(r) for r in mod.DEFAULT_RULES]


# ---------- happy path ----------

def test_four_sample_rules_present(mod, tmp_path):
    out = tmp_path / "m.csv"
    mod.compile_field_requirement_matrix(rules=None, output_csv=out, log_path=tmp_path/"m.log")
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    keys = {(r["content_type"], r["field_key"]) for r in rows}
    assert ("product_review", "brand_tone") in keys
    assert ("store_daily", "team_persona") in keys
    assert ("founder_ip", "founder_profile") in keys
    assert ("brand_manifesto", "brand_values") in keys
    # 检查 4 条样例级别
    by_key = {(r["content_type"], r["field_key"]): r for r in rows}
    assert by_key[("product_review", "brand_tone")]["required_level"] == "soft"
    assert by_key[("store_daily", "team_persona")]["required_level"] == "soft"
    assert by_key[("founder_ip", "founder_profile")]["required_level"] == "hard"
    assert by_key[("brand_manifesto", "brand_values")]["required_level"] == "hard"


def test_columns_match_schema(mod, tmp_path):
    out = tmp_path / "m.csv"
    mod.compile_field_requirement_matrix(rules=None, output_csv=out, log_path=tmp_path/"m.log")
    with out.open(encoding="utf-8") as fh:
        header = fh.readline().strip().split(",")
    assert header == [
        "content_type", "field_key", "required_level",
        "fallback_action", "ask_user_question", "block_reason",
    ]


def test_18_canonical_types_all_covered(mod, tmp_path):
    """S7 全覆盖：每个 canonical content_type 至少 1 行。"""
    out = tmp_path / "m.csv"
    mod.compile_field_requirement_matrix(rules=None, output_csv=out, log_path=tmp_path/"m.log")
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    covered = {r["content_type"] for r in rows}
    canonical_path = REPO_ROOT / "knowledge_serving" / "control" / "content_type_canonical.csv"
    canonical = {r["canonical_content_type_id"] for r in csv.DictReader(canonical_path.open(encoding="utf-8"))}
    # 至少 18 类全覆盖（brand_manifesto 是 §4.2 引入的额外类，可以多覆盖）
    assert canonical.issubset(covered), f"未覆盖 canonical types: {canonical - covered}"


# ---------- adversarial ----------

def test_invalid_required_level_fails(mod, baseline, tmp_path):
    baseline[0] = {**baseline[0], "required_level": "maybe"}
    with pytest.raises(mod.CompileError):
        mod.compile_field_requirement_matrix(rules=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_invalid_fallback_action_fails(mod, baseline, tmp_path):
    baseline[0] = {**baseline[0], "fallback_action": "magic"}
    with pytest.raises(mod.CompileError):
        mod.compile_field_requirement_matrix(rules=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_hard_without_block_reason_fails(mod, tmp_path):
    bad = [{
        "content_type": "founder_ip", "field_key": "founder_profile",
        "required_level": "hard", "fallback_action": "block_brand_output",
        "ask_user_question": "", "block_reason": "",
    }]
    with pytest.raises(mod.CompileError):
        mod.compile_field_requirement_matrix(rules=bad, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_soft_without_fallback_action_fails(mod, tmp_path):
    """soft 缺 fallback_action ≠ neutral_tone/ask_user/use_domain_general → fail (§7: soft 必须有 fallback)"""
    bad = [{
        "content_type": "product_review", "field_key": "brand_tone",
        "required_level": "soft", "fallback_action": "block_brand_output",  # soft 不能 block
        "ask_user_question": "", "block_reason": "",
    }]
    with pytest.raises(mod.CompileError):
        mod.compile_field_requirement_matrix(rules=bad, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


def test_duplicate_content_field_pair_fails(mod, baseline, tmp_path):
    baseline.append(dict(baseline[0]))
    with pytest.raises(mod.CompileError):
        mod.compile_field_requirement_matrix(rules=baseline, output_csv=tmp_path/"x.csv", log_path=tmp_path/"x.log")


# ---------- governance ----------

def test_idempotent_sha256(mod, tmp_path):
    out1, out2 = tmp_path/"a.csv", tmp_path/"b.csv"
    mod.compile_field_requirement_matrix(rules=None, output_csv=out1, log_path=tmp_path/"a.log")
    mod.compile_field_requirement_matrix(rules=None, output_csv=out2, log_path=tmp_path/"b.log")
    assert hashlib.sha256(out1.read_bytes()).hexdigest() == hashlib.sha256(out2.read_bytes()).hexdigest()


def test_no_writes_to_clean_output(mod, tmp_path, monkeypatch):
    real_open = open
    blocked = REPO_ROOT / "clean_output"
    def guarded(file, mode="r", *a, **kw):
        if any(m in mode for m in ("w", "a", "x")):
            p = Path(file).resolve()
            assert blocked not in p.parents
        return real_open(file, mode, *a, **kw)
    monkeypatch.setattr("builtins.open", guarded)
    mod.compile_field_requirement_matrix(rules=None, output_csv=tmp_path/"m.csv", log_path=tmp_path/"m.log")


def test_no_llm_call_in_imports():
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in ("openai", "anthropic", "requests.post", "dify_client"):
        assert forbidden not in text


def test_check_mode_passes(mod):
    rc = mod.compile_field_requirement_matrix(rules=None, output_csv=None, log_path=None, check_only=True)
    assert rc == 0

"""
KS-POLICY-002 · test suite (test-first / RED → GREEN)

校验器入口 / entry:
  python3 scripts/validate_policy_yaml.py guardrail_policy [--policy-path PATH]

覆盖 §6 表共 12 case + 1 happy path = 13 tests。
"""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "validate_policy_yaml.py"
REAL_POLICY = REPO_ROOT / "knowledge_serving" / "policies" / "guardrail_policy.yaml"


def _run(policy_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "guardrail_policy", "--policy-path", str(policy_path)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


# ---------- minimal valid baseline（happy path 模板，子用例从这里 mutate）----------

def _baseline() -> dict[str, Any]:
    return {
        "policy_version": "1.0.0",
        "forbidden_patterns": [
            {
                "id": "FP-FOUNDER-FABRICATION",
                "category": "founder_identity",
                "pattern_kind": "keyword",
                "patterns": ["创始人是", "founder is"],
                "block_reason": "禁止 LLM 编造创始人画像",
                "severity": "hard_block",
            },
            {
                "id": "FP-SKU-FABRICATION",
                "category": "product_fact",
                "pattern_kind": "regex",
                "patterns": [r"SKU[\s_-]?\d{4,}"],
                "block_reason": "SKU 必须来自 business_brief",
                "severity": "hard_block",
            },
            {
                "id": "FP-INVENTORY-FABRICATION",
                "category": "inventory_fact",
                "pattern_kind": "keyword",
                "patterns": ["库存仅剩", "限量"],
                "block_reason": "库存事实必须来自 business_brief",
                "severity": "hard_block",
            },
        ],
        "required_evidence": {
            "event_documentary": {"hard_fields": ["event_anchor"]},
            "founder_ip": {"hard_fields": ["brand_values", "founder_profile"]},
            "knowledge_sharing": {"hard_fields": ["knowledge_pack"]},
            "outfit_of_the_day": {"hard_fields": ["outfit_pack"]},
            "process_trace": {"hard_fields": ["process_anchor"]},
            "product_copy_general": {"hard_fields": ["product_pack"]},
            "product_journey": {"hard_fields": ["product_origin"]},
            "training_material": {"hard_fields": ["training_anchor"]},
        },
        "business_brief_required": {
            "hard_fields": ["sku", "category", "season", "channel"],
            "soft_fields_warning_only": ["inventory_pressure", "price_band", "cta"],
            "block_reason": "business_brief hard 字段缺失，禁止进入最终成稿（S11）",
        },
    }


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    p = tmp_path / "guardrail_policy.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


# ---------- happy path ----------

def test_real_policy_passes():
    """真实落盘 yaml 必须 pass。"""
    assert REAL_POLICY.exists(), f"真源 yaml 缺失: {REAL_POLICY}"
    result = _run(REAL_POLICY)
    assert result.returncode == 0, f"真源 yaml 应该 pass:\n{result.stdout}\n{result.stderr}"


def test_baseline_passes(tmp_path):
    p = _write(tmp_path, _baseline())
    result = _run(p)
    assert result.returncode == 0, f"baseline 应该 pass:\n{result.stdout}\n{result.stderr}"


# ---------- §6 表 12 个 case ----------

def test_case1_forbidden_patterns_empty(tmp_path):
    d = _baseline()
    d["forbidden_patterns"] = []
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "forbidden_patterns" in (result.stdout + result.stderr)


def test_case2_pattern_missing_block_reason(tmp_path):
    d = _baseline()
    del d["forbidden_patterns"][0]["block_reason"]
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "block_reason" in (result.stdout + result.stderr)


def test_case3_pattern_invalid_severity(tmp_path):
    d = _baseline()
    d["forbidden_patterns"][0]["severity"] = "warn_only"
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "severity" in (result.stdout + result.stderr)


def test_case4_required_evidence_extra_hard_field(tmp_path):
    """yaml 给 founder_ip 加 matrix 没有的 hard field → fail。"""
    d = _baseline()
    d["required_evidence"]["founder_ip"]["hard_fields"].append("phantom_field")
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "phantom_field" in (result.stdout + result.stderr) or "matrix" in (result.stdout + result.stderr).lower()


def test_case5_required_evidence_missing_matrix_row(tmp_path):
    """yaml 漏写 matrix 中的 hard 行 → fail（双向闭环）。"""
    d = _baseline()
    del d["required_evidence"]["training_material"]
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "training_material" in (result.stdout + result.stderr)


def test_case6_non_canonical_content_type(tmp_path):
    """required_evidence 含 canonical 18 之外的 content_type → fail。"""
    d = _baseline()
    d["required_evidence"]["fake_content_type"] = {"hard_fields": ["x"]}
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "fake_content_type" in (result.stdout + result.stderr) or "canonical" in (result.stdout + result.stderr).lower()


def test_case7_business_brief_hard_not_equal_schema(tmp_path):
    d = _baseline()
    d["business_brief_required"]["hard_fields"] = ["sku", "category"]  # 漏 season / channel
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "business_brief" in (result.stdout + result.stderr) or "season" in (result.stdout + result.stderr)


def test_case8_business_brief_treats_soft_as_hard(tmp_path):
    d = _baseline()
    d["business_brief_required"]["hard_fields"] = ["sku", "category", "season", "channel", "cta"]
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "cta" in (result.stdout + result.stderr) or "soft" in (result.stdout + result.stderr).lower()


def test_case9_yaml_syntax_error(tmp_path):
    p = tmp_path / "guardrail_policy.yaml"
    p.write_text("policy_version: 1.0.0\n  bad: indent\n: malformed", encoding="utf-8")
    result = _run(p)
    assert result.returncode != 0


def test_case10_llm_judgment_keyword_present(tmp_path):
    d = _baseline()
    d["llm_assist"] = {"enabled": True, "model": "gpt-4"}
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "llm" in (result.stdout + result.stderr).lower()


def test_case11_policy_version_missing(tmp_path):
    d = _baseline()
    del d["policy_version"]
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "policy_version" in (result.stdout + result.stderr)


def test_case12_duplicate_pattern_id(tmp_path):
    d = _baseline()
    dup = copy.deepcopy(d["forbidden_patterns"][0])
    d["forbidden_patterns"].append(dup)
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "duplicate" in (result.stdout + result.stderr).lower() or "重复" in (result.stdout + result.stderr)


# ---------- 额外守护：三大 category 必须齐 ----------

def test_missing_inventory_category_fails(tmp_path):
    """forbidden_patterns 必须覆盖 founder / sku / inventory 三类（plan §A3）。"""
    d = _baseline()
    d["forbidden_patterns"] = [p for p in d["forbidden_patterns"] if p["category"] != "inventory_fact"]
    result = _run(_write(tmp_path, d))
    assert result.returncode == 1
    assert "inventory" in (result.stdout + result.stderr).lower()

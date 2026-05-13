"""KS-VECTOR-003 · offline filter smoke 单元测试.

覆盖卡 §6 对抗矩阵 + §10 审查员阻断项：
- 4 类抽样 filter（brand_faye / domain_general / gate=active / cross-tenant）
- 第 5 类批次锚定 filter（compile_run_id），旧批次必须 0 命中
- fail-closed：payload 缺 hard filter 字段 0 命中
- 入参校验：allowed_layers 空 → raise
- 不调 LLM；不写 clean_output
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "knowledge_serving" / "scripts" / "qdrant_filter_smoke.py"
CHUNKS = REPO_ROOT / "knowledge_serving" / "vector_payloads" / "qdrant_chunks.jsonl"


def _load_module():
    spec = importlib.util.spec_from_file_location("qfs_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


qfs = _load_module()


# ---------- build_payload_filter ----------

def test_filter_contains_three_hard_conditions():
    qf = qfs.build_payload_filter(allowed_layers=["brand_faye", "domain_general"])
    keys = [c["key"] for c in qf["must"]]
    assert keys[:3] == ["brand_layer", "gate_status", "granularity_layer"]
    gs = next(c for c in qf["must"] if c["key"] == "gate_status")
    assert gs["match"]["value"] == "active"
    gr = next(c for c in qf["must"] if c["key"] == "granularity_layer")
    assert set(gr["match"]["any"]) == {"L1", "L2", "L3"}


def test_filter_with_compile_run_id_appends_condition():
    qf = qfs.build_payload_filter(
        allowed_layers=["brand_faye"], compile_run_id="abc123"
    )
    cri = [c for c in qf["must"] if c["key"] == "compile_run_id"]
    assert len(cri) == 1 and cri[0]["match"]["value"] == "abc123"


def test_empty_allowed_layers_raises():
    with pytest.raises(ValueError):
        qfs.build_payload_filter(allowed_layers=[])


# ---------- match / fail-closed ----------

def test_match_fail_closed_when_brand_layer_missing():
    qf = qfs.build_payload_filter(allowed_layers=["brand_faye"])
    payload = {"gate_status": "active", "granularity_layer": "L2"}
    assert qfs.match(payload, qf) is False


def test_match_rejects_deprecated_gate():
    qf = qfs.build_payload_filter(allowed_layers=["brand_faye"])
    payload = {"brand_layer": "brand_faye", "gate_status": "deprecated", "granularity_layer": "L2"}
    assert qfs.match(payload, qf) is False


def test_match_rejects_l4_granularity():
    qf = qfs.build_payload_filter(allowed_layers=["brand_faye"])
    payload = {"brand_layer": "brand_faye", "gate_status": "active", "granularity_layer": "L4"}
    assert qfs.match(payload, qf) is False


def test_match_accepts_valid_payload():
    qf = qfs.build_payload_filter(allowed_layers=["brand_faye", "domain_general"])
    payload = {"brand_layer": "domain_general", "gate_status": "active", "granularity_layer": "L1"}
    assert qfs.match(payload, qf) is True


# ---------- run_offline_cases （真语料） ----------

@pytest.fixture(scope="module")
def corpus():
    assert CHUNKS.exists(), f"前置 KS-VECTOR-001 未落盘 / missing chunks: {CHUNKS}"
    return qfs.load_chunks(CHUNKS)


def test_all_offline_cases_pass(corpus):
    result = qfs.run_offline_cases(corpus)
    failed = [c["case_id"] for c in result["cases"] if not c["pass"]]
    assert failed == [], f"offline cases failed: {failed}"


def test_cross_tenant_zero_hit(corpus):
    result = qfs.run_offline_cases(corpus)
    c4 = next(c for c in result["cases"] if c["case_id"] == "C4_cross_tenant_zero_hit")
    assert c4["hits_count"] == 0


def test_batch_anchor_stale_run_zero_hit(corpus):
    result = qfs.run_offline_cases(corpus)
    c5 = next(c for c in result["cases"] if c["case_id"] == "C5_batch_anchor_stale_run_zero_hit")
    assert c5["hits_count"] == 0
    assert c5["stale_compile_run_id"] != c5["current_compile_run_id"]


def test_batch_anchor_current_run_positive(corpus):
    """防 case 5 因 filter 写挂而恒过：当前批次必须有命中。"""
    result = qfs.run_offline_cases(corpus)
    c5b = next(c for c in result["cases"] if c["case_id"] == "C5b_batch_anchor_current_run_positive")
    assert c5b["hits_count"] > 0


def test_content_type_positive_hits_only_probe(corpus):
    """C7p：content_type 正例必须命中 >0 且全部等于 probe。"""
    result = qfs.run_offline_cases(corpus)
    c7p = next(c for c in result["cases"] if c["case_id"] == "C7p_content_type_positive")
    assert c7p["hits_count"] > 0
    assert c7p["content_types_hit"] == [c7p["content_type_probe"]]


def test_content_type_negative_zero_hit(corpus):
    """C7n：未知 content_type 必须 0 命中（hard filter 真生效）。"""
    result = qfs.run_offline_cases(corpus)
    c7n = next(c for c in result["cases"] if c["case_id"] == "C7n_content_type_negative_zero_hit")
    assert c7n["hits_count"] == 0


# ---------- 端到端 CI 命令 ----------

def test_cli_offline_exit_zero(tmp_path, monkeypatch):
    """卡 §8 CI 命令：python3 qdrant_filter_smoke.py --offline 退码 0。"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--offline"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "SMOKE PASS" in proc.stdout


def test_audit_report_written():
    audit = REPO_ROOT / "knowledge_serving" / "audit" / "qdrant_filter_smoke_KS-VECTOR-003.json"
    assert audit.exists(), "audit 报告未落盘"
    data = json.loads(audit.read_text(encoding="utf-8"))
    assert data["task_card"] == "KS-VECTOR-003"
    assert data["mode"] == "offline"
    assert data["verdict"] == "pass"
    assert data["cross_tenant_hits"] == 0


# ---------- 治理：不调 LLM / 不写 clean_output ----------

def test_no_llm_and_no_clean_output_write():
    src = SCRIPT.read_text(encoding="utf-8")
    for token in ("qwen-plus", "ChatCompletion", "deepseek-chat"):
        assert token not in src, f"源码出现 LLM 调用 token: {token!r}"
    # 不得写 clean_output；允许注释提及
    for token in ('"clean_output"', "'clean_output'", "clean_output/"):
        assert token not in src, f"源码可能写 clean_output: {token!r}"

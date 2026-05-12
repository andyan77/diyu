"""KS-COMPILER-007 · test suite"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_evidence_view.py"
REAL_SCHEMA = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"

HEADER = "evidence_id,source_md,source_anchor,evidence_quote,source_type,inference_level,brand_layer,source_pack_id"


def ev_row(eid: str, *, source_md: str = "t.md", inf: str = "direct_quote", brand: str = "domain_general", pack: str = "KP-x", quote: str = "q", anchor: str = "a") -> str:
    return f"{eid},{source_md},{anchor},{quote},explicit_business_decision,{inf},{brand},{pack}"


MANIFEST = {"manifest_hash": "ffff" * 16, "entries": []}


def setup(tmp_path: Path, evidence_csv: str | None = None) -> dict[str, Path]:
    manifest_path = tmp_path / "audit" / "source_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(MANIFEST), encoding="utf-8")
    schema_path = tmp_path / "schema" / "serving_views.schema.json"
    schema_path.parent.mkdir(parents=True)
    shutil.copy(REAL_SCHEMA, schema_path)
    evidence_path = tmp_path / "nine_tables" / "07_evidence.csv"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(evidence_csv if evidence_csv is not None else HEADER + "\n", encoding="utf-8")
    return {
        "manifest": manifest_path,
        "schema": schema_path,
        "evidence": evidence_path,
        "output": tmp_path / "views" / "evidence_view.csv",
        "log": tmp_path / "audit" / "evidence_view.compile.log",
    }


def run(ws: dict[str, Path], *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT),
         "--evidence", str(ws["evidence"]),
         "--manifest", str(ws["manifest"]),
         "--schema", str(ws["schema"]),
         "--output", str(ws["output"]),
         "--log", str(ws["log"]),
         "--quiet", *extra],
        capture_output=True, text=True,
    )


def test_happy_path(tmp_path):
    ev_csv = HEADER + "\n" + ev_row("EV-001") + "\n"
    ws = setup(tmp_path, ev_csv)
    r = run(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    row = rows[0]
    assert row["evidence_id"] == "EV-001"
    assert row["inference_level"] == "direct_quote"
    assert row["trace_quality"] == "high"
    assert row["traceability_status"] == "full"
    assert row["adjudication_status"] == "approved"
    assert row["line_no"] == "0"


def test_inference_level_low_normalized(tmp_path):
    """'low' 非 schema 枚举，应映射到 paraphrase_low。"""
    ev_csv = HEADER + "\n" + ev_row("EV-low", inf="low") + "\n"
    ws = setup(tmp_path, ev_csv)
    r = run(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["inference_level"] == "paraphrase_low"
    assert rows[0]["trace_quality"] == "low"


def test_missing_source_md_fails(tmp_path):
    """§6: 缺 source_md → fail。"""
    ev_csv = HEADER + "\n" + ev_row("EV-x", source_md="") + "\n"
    ws = setup(tmp_path, ev_csv)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "source_md" in log["message"]


def test_duplicate_evidence_id_fails(tmp_path):
    ev_csv = HEADER + "\n" + ev_row("EV-dup") + "\n" + ev_row("EV-dup") + "\n"
    ws = setup(tmp_path, ev_csv)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "重复" in log["message"] or "duplicate" in log["message"]


def test_invalid_inference_level_fails(tmp_path):
    """§6: inference_level 非枚举且无映射登记 → fail。"""
    ev_csv = HEADER + "\n" + ev_row("EV-bad", inf="unknown_level") + "\n"
    ws = setup(tmp_path, ev_csv)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "inference_level" in log["message"]


def test_empty_evidence_table_fails_S5(tmp_path):
    """§6: 空 source 表 → fail (S5)"""
    ws = setup(tmp_path)  # 只有 header
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "S5" in log["message"] or "空表" in log["message"]


def test_invalid_brand_layer_fails(tmp_path):
    ev_csv = HEADER + "\n" + ev_row("EV-b", brand="FAYE") + "\n"
    ws = setup(tmp_path, ev_csv)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "brand_layer" in log["message"]


def test_idempotent(tmp_path):
    ev_csv = HEADER + "\n" + ev_row("EV-i") + "\n"
    ws = setup(tmp_path, ev_csv)
    assert run(ws).returncode == 0
    s1 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    ws["output"].unlink()
    assert run(ws).returncode == 0
    s2 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    assert s1 == s2


def test_governance_13_and_S5_completeness(tmp_path):
    """S5: inference_level + trace_quality 全填 + governance 13 字段非空。"""
    ev_csv = HEADER + "\n" + ev_row("EV-g") + "\n"
    ws = setup(tmp_path, ev_csv)
    assert run(ws).returncode == 0
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    gov_fields = [
        "source_pack_id", "brand_layer", "granularity_layer", "gate_status",
        "source_table_refs", "evidence_ids", "traceability_status", "default_call_pool",
        "review_status", "compile_run_id", "source_manifest_hash", "view_schema_version",
        "chunk_text_hash",
    ]
    for r in rows:
        for col in gov_fields:
            assert r[col] != "", f"empty: {col}"
        assert r["inference_level"] != ""
        assert r["trace_quality"] != ""


def test_unique_evidence_id_across_rows(tmp_path):
    """S5: evidence_id 唯一性"""
    ev_csv = HEADER + "\n" + ev_row("EV-a") + "\n" + ev_row("EV-b") + "\n" + ev_row("EV-c") + "\n"
    ws = setup(tmp_path, ev_csv)
    assert run(ws).returncode == 0
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    ids = [r["evidence_id"] for r in rows]
    assert len(ids) == len(set(ids))


def test_no_llm():
    txt = SCRIPT.read_text()
    for f in ("import anthropic", "import openai", "from anthropic", "from openai"):
        assert f not in txt

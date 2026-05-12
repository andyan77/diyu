"""KS-COMPILER-005 · test suite"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_runtime_asset_view.py"
REAL_SCHEMA = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"

REGISTER_HEADER = "runtime_asset_id,pack_id,granularity_layer,asset_type,source_md,source_anchor,line_no,title,summary,source_pointer,brand_layer,registered_at"


def row(rid: str, pid: str, atype: str = "role_split", title: str = "T", summary: str = "S",
        source_pointer: str = "candidates/x.yaml#a", brand: str = "domain_general",
        granularity: str = "L3") -> str:
    return f"{rid},{pid},{granularity},{atype},,,-1,{title},{summary},{source_pointer},{brand},2026-05-12T00:00:00Z"


MANIFEST = {"manifest_hash": "abcd" * 16, "entries": []}


def setup_workspace(tmp_path: Path, register_csv: str | None = None) -> dict[str, Path]:
    manifest_path = tmp_path / "audit" / "source_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(MANIFEST), encoding="utf-8")
    schema_path = tmp_path / "schema" / "serving_views.schema.json"
    schema_path.parent.mkdir(parents=True)
    shutil.copy(REAL_SCHEMA, schema_path)
    register_path = tmp_path / "runtime_assets" / "runtime_asset_index.csv"
    register_path.parent.mkdir(parents=True)
    register_path.write_text(register_csv if register_csv is not None else REGISTER_HEADER + "\n", encoding="utf-8")
    return {
        "manifest": manifest_path,
        "schema": schema_path,
        "register": register_path,
        "output": tmp_path / "views" / "runtime_asset_view.csv",
        "log": tmp_path / "audit" / "runtime_asset_view.compile.log",
    }


def run(ws: dict[str, Path], *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT),
         "--register", str(ws["register"]),
         "--manifest", str(ws["manifest"]),
         "--schema", str(ws["schema"]),
         "--output", str(ws["output"]),
         "--log", str(ws["log"]),
         "--quiet", *extra],
        capture_output=True, text=True,
    )


def test_happy_path(tmp_path):
    reg = REGISTER_HEADER + "\n" + row("RA-test-001", "KP-test-001") + "\n"
    ws = setup_workspace(tmp_path, reg)
    r = run(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["runtime_asset_id"] == "RA-test-001"
    assert rows[0]["traceability_status"] == "partial"
    assert rows[0]["source_pointer"] == "candidates/x.yaml#a"


def test_missing_source_pointer_fails(tmp_path):
    """§6: 缺 source_pointer → fail (S1)"""
    reg = REGISTER_HEADER + "\n" + row("RA-no-ptr", "KP-x", source_pointer="") + "\n"
    ws = setup_workspace(tmp_path, reg)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "source_pointer" in log["message"]


def test_duplicate_id_fails(tmp_path):
    reg = REGISTER_HEADER + "\n" + row("RA-d", "KP-d") + "\n" + row("RA-d", "KP-d") + "\n"
    ws = setup_workspace(tmp_path, reg)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "重复" in log["message"] or "duplicate" in log["message"]


def test_invalid_asset_type_fails(tmp_path):
    reg = REGISTER_HEADER + "\n" + row("RA-x", "KP-x", atype="totally_unknown") + "\n"
    ws = setup_workspace(tmp_path, reg)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "asset_type" in log["message"]


def test_empty_register_zero_rows(tmp_path):
    ws = setup_workspace(tmp_path)
    r = run(ws)
    assert r.returncode == 0
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows == []


def test_idempotent(tmp_path):
    reg = REGISTER_HEADER + "\n" + row("RA-i", "KP-i") + "\n"
    ws = setup_workspace(tmp_path, reg)
    assert run(ws).returncode == 0
    s1 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    ws["output"].unlink()
    assert run(ws).returncode == 0
    s2 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    assert s1 == s2


def test_invalid_brand_layer_fails(tmp_path):
    reg = REGISTER_HEADER + "\n" + row("RA-bl", "KP-bl", brand="FAYE") + "\n"
    ws = setup_workspace(tmp_path, reg)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "brand_layer" in log["message"]


def test_no_llm_call_imports():
    txt = SCRIPT.read_text()
    for f in ("import anthropic", "import openai", "from anthropic", "from openai"):
        assert f not in txt


def test_governance_13_fields_and_traceability(tmp_path):
    """S1 硬门 + governance 13 字段全行非空。"""
    reg = REGISTER_HEADER + "\n" + row("RA-g", "KP-g") + "\n"
    ws = setup_workspace(tmp_path, reg)
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
            assert r[col] != "", f"governance empty: {col}"
        assert r["traceability_status"] != ""
        assert r["source_pointer"] != ""

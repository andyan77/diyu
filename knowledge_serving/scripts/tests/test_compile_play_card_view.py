"""KS-COMPILER-004 · test suite"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_play_card_view.py"
REAL_SCHEMA = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"

PACK_TPL = dedent(
    """
    pack_id: {pack_id}
    granularity_layer: L1
    schema_version: candidate_v1
    pack_type: craft_quality
    brand_layer: {brand}
    state: drafted

    knowledge_assertion: stub
    scenario:
      boundary:
        applicable_when: any
        not_applicable_when: never
      alternative_path:
        - fallback
      result:
        success_pattern: ok
        flip_pattern: ng
    evidence:
      source_md: t.md
      source_anchor: a
      source_type: explicit_business_decision
      inference_level: direct_quote
      evidence_quote: q
    gate_self_check:
      gate_1_closed_scenario: pass
      gate_2_reverse_infer: pass
      gate_3_rule_generalizable: {gate3}
      gate_4_production_feasible: pass
    nine_table_projection:
      evidence:
        - {{evidence_id: EV-{pack_id}, source_md: t.md, source_anchor: a, source_type: explicit_business_decision, inference_level: direct_quote}}
    """
).strip()

REGISTER_HEADER = "play_card_id,pack_id,granularity_layer,consumption_purpose,production_difficulty,production_tier,resource_baseline,default_call_pool,hook,steps_count,anti_pattern,duration,audience,source_pack_id,brand_layer"


def reg_row(pc_id: str, pack_id: str, brand: str = "domain_general", granularity: str = "L2", anti: str = "anti", duration: str = "short", steps: int = 3) -> str:
    return f"{pc_id},{pack_id},{granularity},generation,medium,instant,1人+手机+200元+4h,true,hook-{pc_id},{steps},{anti},{duration},audience,{pack_id},{brand}"


MANIFEST = {"manifest_hash": "fffe" * 16, "generated_at": "2026-05-12", "task_card": "KS-S0-006", "entries": []}


def setup_workspace(tmp_path: Path, packs: dict[str, dict] | None = None, register_csv: str | None = None) -> dict[str, Path]:
    candidates_dir = tmp_path / "clean_output" / "candidates" / "domain_general"
    candidates_dir.mkdir(parents=True)
    if packs:
        for pid, opts in packs.items():
            (candidates_dir / f"{pid}.yaml").write_text(
                PACK_TPL.format(pack_id=pid, brand=opts.get("brand", "domain_general"), gate3=opts.get("gate3", "pass")),
                encoding="utf-8",
            )
    nine_tables_dir = tmp_path / "clean_output" / "nine_tables"
    nine_tables_dir.mkdir(parents=True)
    (nine_tables_dir / "07_evidence.csv").write_text(
        "evidence_id,source_md,source_anchor,evidence_quote,source_type,inference_level,brand_layer,source_pack_id\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "clean_output" / "audit" / "source_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(MANIFEST), encoding="utf-8")
    schema_path = tmp_path / "knowledge_serving" / "schema" / "serving_views.schema.json"
    schema_path.parent.mkdir(parents=True)
    shutil.copy(REAL_SCHEMA, schema_path)
    register_path = tmp_path / "clean_output" / "play_cards" / "play_card_register.csv"
    register_path.parent.mkdir(parents=True)
    if register_csv is None:
        register_path.write_text(REGISTER_HEADER + "\n", encoding="utf-8")
    else:
        register_path.write_text(register_csv, encoding="utf-8")
    return {
        "candidates_dir": tmp_path / "clean_output" / "candidates",
        "nine_tables_dir": nine_tables_dir,
        "manifest": manifest_path,
        "schema": schema_path,
        "register": register_path,
        "output": tmp_path / "knowledge_serving" / "views" / "play_card_view.csv",
        "log": tmp_path / "knowledge_serving" / "audit" / "play_card_view.compile.log",
    }


def run(ws: dict[str, Path], *extra: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable, str(SCRIPT),
        "--candidates-dir", str(ws["candidates_dir"]),
        "--nine-tables-dir", str(ws["nine_tables_dir"]),
        "--register", str(ws["register"]),
        "--manifest", str(ws["manifest"]),
        "--schema", str(ws["schema"]),
        "--output", str(ws["output"]),
        "--log", str(ws["log"]),
        "--quiet",
        *extra,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


# ---- §6 adversarial ----

def test_happy_path_with_pack_fk(tmp_path):
    register = REGISTER_HEADER + "\n" + reg_row("PC-craft-test-001", "KP-craft-test-001") + "\n"
    ws = setup_workspace(tmp_path, packs={"KP-craft-test-001": {}}, register_csv=register)
    r = run(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    row = rows[0]
    assert row["play_card_id"] == "PC-craft-test-001"
    assert row["pack_id"] == "KP-craft-test-001"
    assert row["completeness_status"] == "complete"  # 5 字段齐
    assert row["gate_status"] == "active"
    assert json.loads(row["evidence_ids"]) == ["EV-KP-craft-test-001"]
    assert row["default_call_pool"] == "true"


def test_invalid_brand_layer_fails(tmp_path):
    """§6: brand_layer=FAYE → fail-closed"""
    register = REGISTER_HEADER + "\n" + reg_row("PC-x-001", "KP-x-001", brand="FAYE") + "\n"
    ws = setup_workspace(tmp_path, packs={"KP-x-001": {}}, register_csv=register)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "brand_layer" in log["message"]


def test_empty_register_zero_rows(tmp_path):
    """§6: 空 register → 0 行 + warning + exit 0"""
    ws = setup_workspace(tmp_path)  # register 只有 header
    r = run(ws)
    assert r.returncode == 0
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows == []


def test_duplicate_play_card_id_fails(tmp_path):
    register = REGISTER_HEADER + "\n" + reg_row("PC-dup-001", "KP-dup-001") + "\n" + reg_row("PC-dup-001", "KP-dup-001") + "\n"
    ws = setup_workspace(tmp_path, packs={"KP-dup-001": {}}, register_csv=register)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "重复" in log["message"] or "duplicate" in log["message"]


def test_dangling_pack_id_fk_fails(tmp_path):
    """§6: 断 FK pack_id → fail"""
    register = REGISTER_HEADER + "\n" + reg_row("PC-orphan", "KP-not-in-index") + "\n"
    ws = setup_workspace(tmp_path, packs={"KP-other": {}}, register_csv=register)
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "FK" in log["message"] or "dangling" in log["message"]


def test_deprecated_pack_filtered_by_default(tmp_path):
    """§6: deprecated pack 默认过滤 — 把 pack gate3 改成 fail → gate_status=draft → 过滤"""
    register = REGISTER_HEADER + "\n" + reg_row("PC-dep-001", "KP-dep-001") + "\n"
    ws = setup_workspace(
        tmp_path,
        packs={"KP-dep-001": {"gate3": "fail"}},  # universal_pass requires gate_3 not consulted? actually gate_4 OK but gate_3=fail makes domain_general draft
        register_csv=register,
    )
    r = run(ws)
    assert r.returncode == 0
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 0
    # --include-inactive-pack 才能纳入
    r2 = run(ws, "--include-inactive-pack")
    assert r2.returncode == 0
    with ws["output"].open() as fh:
        rows2 = list(csv.DictReader(fh))
    assert len(rows2) == 1


def test_missing_steps_completeness_not_complete(tmp_path):
    """§6: 缺 steps_json (steps_count=0) → completeness=partial/stub，不抛"""
    register = REGISTER_HEADER + "\n" + reg_row("PC-nostep-001", "KP-nostep-001", steps=0) + "\n"
    ws = setup_workspace(tmp_path, packs={"KP-nostep-001": {}}, register_csv=register)
    r = run(ws)
    assert r.returncode == 0
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["completeness_status"] in ("partial", "stub")


def test_idempotent_sha256(tmp_path):
    register = REGISTER_HEADER + "\n" + reg_row("PC-idem-001", "KP-idem-001") + "\n"
    ws = setup_workspace(tmp_path, packs={"KP-idem-001": {}}, register_csv=register)
    assert run(ws).returncode == 0
    s1 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    ws["output"].unlink()
    assert run(ws).returncode == 0
    s2 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    assert s1 == s2


def test_no_clean_output_write(tmp_path):
    register = REGISTER_HEADER + "\n" + reg_row("PC-w-001", "KP-w-001") + "\n"
    ws = setup_workspace(tmp_path, packs={"KP-w-001": {}}, register_csv=register)
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in ws["candidates_dir"].rglob("*") if p.is_file()}
    reg_before = hashlib.sha256(ws["register"].read_bytes()).hexdigest()
    assert run(ws).returncode == 0
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in ws["candidates_dir"].rglob("*") if p.is_file()}
    reg_after = hashlib.sha256(ws["register"].read_bytes()).hexdigest()
    assert before == after
    assert reg_before == reg_after


def test_governance_13_fields_present(tmp_path):
    register = REGISTER_HEADER + "\n" + reg_row("PC-g-001", "KP-g-001") + "\n"
    ws = setup_workspace(tmp_path, packs={"KP-g-001": {}}, register_csv=register)
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


def test_no_llm_call_imports():
    txt = SCRIPT.read_text()
    for f in ("import anthropic", "import openai", "from anthropic", "from openai"):
        assert f not in txt


def test_completeness_status_field_always_present(tmp_path):
    """S6 硬门：completeness_status 全行非空。"""
    register = REGISTER_HEADER + "\n" + reg_row("PC-s6-001", "KP-s6-001") + "\n"
    ws = setup_workspace(tmp_path, packs={"KP-s6-001": {}}, register_csv=register)
    assert run(ws).returncode == 0
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        assert r["completeness_status"] in ("complete", "partial", "stub")

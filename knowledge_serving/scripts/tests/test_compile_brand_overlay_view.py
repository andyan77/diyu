"""KS-COMPILER-006 · test suite"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_brand_overlay_view.py"
REAL_SCHEMA = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"

CANDIDATE_TPL = dedent(
    """
    pack_id: {pack_id}
    granularity_layer: L1
    schema_version: candidate_v1
    pack_type: product_attribute
    brand_layer: {brand}
    brand_overlay_kind: {kind}
    state: drafted

    knowledge_assertion: |
      {assertion}

    evidence:
      source_md: t.md
      source_anchor: a
      source_type: explicit_business_decision
      inference_level: direct_quote
      evidence_quote: q
    """
).strip()

MANIFEST = {"manifest_hash": "1234" * 16, "entries": []}


def write_candidate(dir_path: Path, pack_id: str, brand: str, kind: str, assertion: str = "笛语品牌调性 stub") -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / f"{pack_id}.yaml").write_text(
        CANDIDATE_TPL.format(pack_id=pack_id, brand=brand, kind=kind, assertion=assertion),
        encoding="utf-8",
    )


def setup(tmp_path: Path) -> dict[str, Path]:
    candidates_dir = tmp_path / "clean_output" / "candidates"
    (candidates_dir / "domain_general").mkdir(parents=True)
    manifest_path = tmp_path / "audit" / "source_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(MANIFEST), encoding="utf-8")
    schema_path = tmp_path / "schema" / "serving_views.schema.json"
    schema_path.parent.mkdir(parents=True)
    shutil.copy(REAL_SCHEMA, schema_path)
    return {
        "candidates_dir": candidates_dir,
        "manifest": manifest_path,
        "schema": schema_path,
        "output": tmp_path / "views" / "brand_overlay_view.csv",
        "log": tmp_path / "audit" / "brand_overlay_view.compile.log",
    }


def run(ws: dict[str, Path], *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT),
         "--candidates-dir", str(ws["candidates_dir"]),
         "--manifest", str(ws["manifest"]),
         "--schema", str(ws["schema"]),
         "--output", str(ws["output"]),
         "--log", str(ws["log"]),
         "--quiet", *extra],
        capture_output=True, text=True,
    )


def test_happy_path_brand_voice(tmp_path):
    ws = setup(tmp_path)
    write_candidate(ws["candidates_dir"] / "brand_faye", "KP-test-001", "brand_faye", "brand_voice")
    r = run(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["brand_overlay_kind"] == "brand_voice"
    assert rows[0]["brand_layer"] == "brand_faye"
    assert int(rows[0]["precedence"]) == 2


def test_domain_general_input_fails_S3(tmp_path):
    """§6 + §10 阻断项: brand_layer=domain_general 必须 fail。"""
    ws = setup(tmp_path)
    # 直接放 domain_general 子目录会被 discover 跳过；放 brand_xxx 但写错 brand_layer=domain_general
    write_candidate(ws["candidates_dir"] / "brand_evil", "KP-evil-001", "domain_general", "brand_voice")
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "S3" in log["message"] or "domain_general" in log["message"]


def test_invalid_overlay_kind_fails(tmp_path):
    """§6: overlay_kind 非 4 枚举 → fail。"""
    ws = setup(tmp_path)
    write_candidate(ws["candidates_dir"] / "brand_faye", "KP-bad-kind", "brand_faye", "marketing_overlay")
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "brand_overlay_kind" in log["message"]


def test_missing_overlay_kind_skipped_with_warning(tmp_path):
    """需 review 中无 brand_overlay_kind 字段 → 跳过 + warning，不阻断。"""
    ws = setup(tmp_path)
    # 写一个无 brand_overlay_kind 字段的候选
    nr_dir = ws["candidates_dir"] / "needs_review"
    nr_dir.mkdir(parents=True)
    (nr_dir / "KP-noslot.yaml").write_text(dedent("""
        pack_id: KP-noslot
        granularity_layer: L1
        schema_version: candidate_v1
        pack_type: service_judgment
        brand_layer: brand_faye
        state: drafted
        knowledge_assertion: 笛语定位 stub
        evidence:
          source_md: t.md
          source_anchor: a
          source_type: explicit_business_decision
          inference_level: direct_quote
          evidence_quote: q
    """).strip(), encoding="utf-8")
    r = run(ws)
    assert r.returncode == 0, r.stderr
    log = json.loads(ws["log"].read_text())
    assert log["skipped_no_kind_count"] == 1


def test_domain_general_dir_not_scanned(tmp_path):
    """硬约束：domain_general 目录不应被扫到 overlay。"""
    ws = setup(tmp_path)
    write_candidate(ws["candidates_dir"] / "domain_general", "KP-dg-001", "domain_general", "brand_voice")
    r = run(ws)
    # 该文件不在 brand_*/needs_review 下，应被 discover 跳过；rows=0
    assert r.returncode == 0
    with ws["output"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows == []


def test_duplicate_overlay_id_fails(tmp_path):
    ws = setup(tmp_path)
    write_candidate(ws["candidates_dir"] / "brand_faye", "KP-dup", "brand_faye", "brand_voice")
    write_candidate(ws["candidates_dir"] / "brand_other", "KP-dup", "brand_faye", "brand_voice")
    r = run(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text())
    assert "重复" in log["message"] or "duplicate" in log["message"]


def test_soft_redline_emits_warning(tmp_path):
    """门店纪律关键词命中 → warning，不阻断。"""
    ws = setup(tmp_path)
    write_candidate(
        ws["candidates_dir"] / "brand_faye",
        "KP-soft-001", "brand_faye", "brand_voice",
        assertion="此规则属于门店纪律 + 面料工艺品质判断 范畴",  # 故意混入
    )
    r = run(ws)
    assert r.returncode == 0
    log = json.loads(ws["log"].read_text())
    assert any("软告警" in w or "soft redline" in w for w in log["warnings"])


def test_idempotent(tmp_path):
    ws = setup(tmp_path)
    write_candidate(ws["candidates_dir"] / "brand_faye", "KP-i-001", "brand_faye", "brand_voice")
    assert run(ws).returncode == 0
    s1 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    ws["output"].unlink()
    assert run(ws).returncode == 0
    s2 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    assert s1 == s2


def test_governance_13_fields(tmp_path):
    ws = setup(tmp_path)
    write_candidate(ws["candidates_dir"] / "brand_faye", "KP-g-001", "brand_faye", "founder_persona")
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


def test_no_llm():
    txt = SCRIPT.read_text()
    for f in ("import anthropic", "import openai", "from anthropic", "from openai"):
        assert f not in txt

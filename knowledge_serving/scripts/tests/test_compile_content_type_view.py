"""
KS-COMPILER-002 · test suite

对应任务卡 §6 全部测试 + §7 治理一致性。
"""

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
SCRIPT = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_content_type_view.py"
REAL_CANONICAL = REPO_ROOT / "knowledge_serving" / "control" / "content_type_canonical.csv"
REAL_SCHEMA = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"

# 18 行 canonical 最小 fixture（每行 5 列）
FIXTURE_CANONICAL_18 = "canonical_content_type_id,name_zh,name_en,aliases,coverage_status\n" + "\n".join(
    f"ct_{i:02d},类型{i},Type {i},alias_{i}a|alias_{i}b,partial"
    for i in range(18)
) + "\n"

# 17 行 canonical（用于测试 18 类不全 warning）
FIXTURE_CANONICAL_17 = "canonical_content_type_id,name_zh,name_en,aliases,coverage_status\n" + "\n".join(
    f"ct_{i:02d},类型{i},Type {i},alias_{i}a|alias_{i}b,partial"
    for i in range(17)
) + "\n"

MIN_CANDIDATE_TPL = dedent(
    """
    pack_id: {pack_id}
    granularity_layer: L1
    schema_version: candidate_v1
    pack_type: craft_quality
    brand_layer: domain_general
    state: drafted

    knowledge_assertion: minimal

    nine_table_projection:
      call_mapping:
        - {{mapping_id: CM-x-1, runtime_method: {runtime_method}, input_types: [X], output_types: [Y]}}
    """
).strip()

CONTENT_TYPE_CANDIDATE_TPL = dedent(
    """
    pack_id: {pack_id}
    granularity_layer: L1
    schema_version: candidate_v1
    pack_type: product_attribute
    brand_layer: domain_general
    state: drafted

    knowledge_assertion: minimal

    nine_table_projection:
      relation:
        - {{relation_id: RE-x-1, source_type: ContentType, target_type: ContentType, relation_kind: compatible_with_content_type, properties_json: '{{"content_type_id":"{content_type_id}"}}'}}
      call_mapping:
        - {{mapping_id: CM-x-1, runtime_method: content_generation, input_types: "ContentType={content_type_id}+Evidence", output_types: [Y]}}
    """
).strip()

MANIFEST = {
    "manifest_hash": "abcd" * 16,
    "generated_at": "2026-05-12 00:00:00",
    "task_card": "KS-S0-006",
    "entries": [],
}


def setup_workspace(tmp_path: Path, canonical_csv: str = FIXTURE_CANONICAL_18) -> dict[str, Path]:
    candidates_dir = tmp_path / "clean_output" / "candidates" / "domain_general"
    candidates_dir.mkdir(parents=True)
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
    canonical_path = tmp_path / "knowledge_serving" / "control" / "content_type_canonical.csv"
    canonical_path.parent.mkdir(parents=True)
    canonical_path.write_text(canonical_csv, encoding="utf-8")
    return {
        "candidates_dir": tmp_path / "clean_output" / "candidates",
        "domain_dir": candidates_dir,
        "nine_tables_dir": nine_tables_dir,
        "manifest": manifest_path,
        "schema": schema_path,
        "canonical": canonical_path,
        "output": tmp_path / "knowledge_serving" / "views" / "content_type_view.csv",
        "log": tmp_path / "knowledge_serving" / "audit" / "content_type_view.compile.log",
    }


def write_candidate(ws: dict[str, Path], pack_id: str, runtime_method: str) -> None:
    fp = ws["domain_dir"] / f"{pack_id}.yaml"
    fp.write_text(
        MIN_CANDIDATE_TPL.format(pack_id=pack_id, runtime_method=runtime_method),
        encoding="utf-8",
    )


def write_content_type_candidate(ws: dict[str, Path], pack_id: str, content_type_id: str) -> None:
    fp = ws["domain_dir"] / f"{pack_id}.yaml"
    fp.write_text(
        CONTENT_TYPE_CANDIDATE_TPL.format(pack_id=pack_id, content_type_id=content_type_id),
        encoding="utf-8",
    )


def run_compiler(ws: dict[str, Path], *extra: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable, str(SCRIPT),
        "--candidates-dir", str(ws["candidates_dir"]),
        "--nine-tables-dir", str(ws["nine_tables_dir"]),
        "--canonical", str(ws["canonical"]),
        "--manifest", str(ws["manifest"]),
        "--schema", str(ws["schema"]),
        "--output", str(ws["output"]),
        "--log", str(ws["log"]),
        "--quiet",
        *extra,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_happy_path_18_rows_no_candidates(tmp_path):
    """canonical 18 行 + 0 candidates → 18 行 all-missing。"""
    ws = setup_workspace(tmp_path)
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 18
    assert all(row["coverage_status"] == "missing" for row in rows)
    assert all(row["gate_status"] == "active" for row in rows)
    assert all(row["traceability_status"] == "missing" for row in rows)
    assert all(json.loads(row["source_pack_ids"]) == [] for row in rows)


def test_canonical_id_invalid_fails(tmp_path):
    """§6: canonical id 与 register 不符 → fail（id 漂移）。"""
    bad_canonical = "canonical_content_type_id,name_zh,name_en,aliases,coverage_status\nBAD-ID,A,B,x,partial\n"
    ws = setup_workspace(tmp_path, canonical_csv=bad_canonical)
    r = run_compiler(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert log["ok"] is False
    assert "漂移" in log["message"] or "drift" in log["message"]


def test_duplicate_canonical_id_fails(tmp_path):
    """canonical id 重复 → fail。"""
    dup = "canonical_content_type_id,name_zh,name_en,aliases,coverage_status\nfoo,A,B,x,partial\nfoo,C,D,y,partial\n"
    ws = setup_workspace(tmp_path, canonical_csv=dup)
    r = run_compiler(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert "重复" in log["message"] or "duplicate" in log["message"]


def test_unregistered_alias_emits_warning_not_fail(tmp_path):
    """§6: aliases 包含未登记别名 → warning（不阻断）。"""
    ws = setup_workspace(tmp_path)
    # candidate 引用一个不在 canonical 任何 alias 中的 runtime_method
    write_candidate(ws, "KP-test-001", "totally_unregistered_method")
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert log["ok"] is True
    assert log["warnings_count"] >= 1
    assert any("totally_unregistered_method" in w for w in log["warnings"])


def test_canonical_under_18_emits_warning(tmp_path):
    """§6: 18 类不全 → warning（missing 标识 / count warning）；默认不阻断。"""
    ws = setup_workspace(tmp_path, canonical_csv=FIXTURE_CANONICAL_17)
    r = run_compiler(ws)
    assert r.returncode == 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert log["ok"] is True
    assert log["canonical_rows_scanned"] == 17
    assert any("18 类不全" in w or "≠ 期望 18" in w for w in log["warnings"])


def test_canonical_under_18_strict_fails(tmp_path):
    """--strict-completeness 模式下 17 行直接 fail。"""
    ws = setup_workspace(tmp_path, canonical_csv=FIXTURE_CANONICAL_17)
    r = run_compiler(ws, "--strict-completeness")
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert log["ok"] is False


def test_alias_match_populates_source_pack_ids(tmp_path):
    """canonical alias 命中 candidate 的 runtime_method → source_pack_ids 含该 pack。"""
    ws = setup_workspace(tmp_path)
    # FIXTURE 第 0 行 ct_00 的 alias 是 alias_0a / alias_0b
    write_candidate(ws, "KP-match-001", "alias_0a")
    write_candidate(ws, "KP-match-002", "alias_0b")
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    row0 = next(r for r in rows if r["canonical_content_type_id"] == "ct_00")
    assert sorted(json.loads(row0["source_pack_ids"])) == ["KP-match-001", "KP-match-002"]
    assert row0["coverage_status"] == "partial"  # 2 packs → partial
    assert row0["traceability_status"] == "partial"
    assert row0["default_call_pool"] == "true"


def test_content_type_projection_populates_source_pack_ids(tmp_path):
    """真实采集路径：pack_id / relation.properties_json / ContentType=<id> 会生成覆盖。"""
    canonical = (
        "canonical_content_type_id,name_zh,name_en,aliases,coverage_status\n"
        + "product_review,产品评测,Product Review,product_eval,partial\n"
        + "\n".join(f"ct_{i:02d},类型{i},Type {i},alias_{i}a,partial" for i in range(17))
        + "\n"
    )
    ws = setup_workspace(tmp_path, canonical_csv=canonical)
    write_content_type_candidate(
        ws,
        "KP-product_attribute-content-type-north-star-product-review",
        "product_review",
    )
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    row = next(r for r in rows if r["canonical_content_type_id"] == "product_review")
    assert json.loads(row["source_pack_ids"]) == [
        "KP-product_attribute-content-type-north-star-product-review"
    ]
    assert row["coverage_status"] == "partial"


def test_coverage_complete_threshold(tmp_path):
    """source_pack_ids ≥ 10 → coverage_status=complete。"""
    ws = setup_workspace(tmp_path)
    for i in range(10):
        write_candidate(ws, f"KP-bulk-{i:03d}", "alias_0a")
    r = run_compiler(ws)
    assert r.returncode == 0
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    row0 = next(r for r in rows if r["canonical_content_type_id"] == "ct_00")
    assert row0["coverage_status"] == "complete"


def test_idempotent_sha256(tmp_path):
    """§6: 幂等 sha256 一致。"""
    ws = setup_workspace(tmp_path)
    write_candidate(ws, "KP-x-001", "alias_0a")
    r1 = run_compiler(ws)
    assert r1.returncode == 0
    sha1 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    ws["output"].unlink()
    r2 = run_compiler(ws)
    assert r2.returncode == 0
    sha2 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    assert sha1 == sha2


def test_no_clean_output_write(tmp_path):
    """§7: clean_output 0 写。"""
    ws = setup_workspace(tmp_path)
    write_candidate(ws, "KP-x-001", "alias_0a")
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ws["candidates_dir"].rglob("*") if p.is_file()
    }
    r = run_compiler(ws)
    assert r.returncode == 0
    after = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ws["candidates_dir"].rglob("*") if p.is_file()
    }
    assert before == after


def test_no_llm_call_imports():
    """§7: 不调 LLM。"""
    txt = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("import anthropic", "import openai", "from anthropic", "from openai"):
        assert forbidden not in txt


def test_governance_13_fields_present(tmp_path):
    """每行 governance 13 字段全填。"""
    ws = setup_workspace(tmp_path)
    r = run_compiler(ws)
    assert r.returncode == 0
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    gov_fields = [
        "source_pack_id", "brand_layer", "granularity_layer", "gate_status",
        "source_table_refs", "evidence_ids", "traceability_status", "default_call_pool",
        "review_status", "compile_run_id", "source_manifest_hash", "view_schema_version",
        "chunk_text_hash",
    ]
    for r in rows:
        for col in gov_fields:
            assert r[col] != "", f"governance field empty: {col} (row={r['canonical_content_type_id']})"


def test_real_canonical_emits_18_rows():
    """真实 canonical 表跑：必须 18 行。"""
    if not REAL_CANONICAL.exists():
        pytest.skip("real canonical not present")
    out = REPO_ROOT / "knowledge_serving" / "views" / "content_type_view.csv"
    if not out.exists():
        pytest.skip("先跑一次 compile_content_type_view.py --check")
    with out.open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 18
    ids = {r["canonical_content_type_id"] for r in rows}
    # 真表里的几个标志性 id
    for expected in ("outfit_of_the_day", "training_material", "product_review"):
        assert expected in ids

"""
KS-COMPILER-001 · 测试套 / test suite

对应 task card §6 8 项对抗性测试 + §7 治理语义 + §11 DoD 幂等。
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
SCRIPT = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_pack_view.py"

# 完整最小 candidate fixture / minimal valid candidate yaml
MIN_CANDIDATE = dedent(
    """
    pack_id: KP-test-minimal-001
    granularity_layer: L1
    schema_version: candidate_v1
    pack_type: craft_quality
    brand_layer: domain_general
    state: drafted

    knowledge_assertion: 最小断言 / minimal assertion for unit test.

    scenario:
      who:
        primary_role: tester
      when:
        trigger: t
      what:
        action_type: a
        decision_or_action: d
      result:
        success_pattern: ok
        flip_pattern: ng
      boundary:
        applicable_when: any test context
        not_applicable_when: prod
      alternative_path:
        - fallback_a

    evidence:
      source_md: test/fixture.md
      source_anchor: section-1
      source_type: explicit_business_decision
      inference_level: direct_quote
      evidence_quote: 测试证据 quote

    gate_self_check:
      gate_1_closed_scenario: pass
      gate_2_reverse_infer: pass
      gate_3_rule_generalizable: pass
      gate_4_production_feasible: pass

    brand_layer_review:
      decision_suggestion: domain_general
      faye_review_required: false

    nine_table_projection:
      object_type:
        - {type_id: OT-TestKnowledge, type_name: TestKnowledge, supertype: domain_object}
      evidence:
        - {evidence_id: EV-test-minimal-001, source_md: test/fixture.md, source_anchor: section-1, source_type: explicit_business_decision, inference_level: direct_quote}
      call_mapping:
        - {mapping_id: CM-test-minimal-001, runtime_method: store_training, input_types: [X], output_types: [Y]}
    """
).strip()

MANIFEST_FIXTURE = {
    "manifest_hash": "deadbeefcafef00d" * 4,
    "generated_at": "2026-05-12 00:00:00",
    "task_card": "KS-S0-006",
    "entry_count": 0,
    "entries": [],
}


# ---------- fixture utilities ----------

def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def setup_workspace(tmp_path: Path) -> dict[str, Path]:
    """搭一个仿 clean_output / knowledge_serving 的最小工作目录。"""
    candidates_dir = tmp_path / "clean_output" / "candidates"
    domain_dir = candidates_dir / "domain_general"
    domain_dir.mkdir(parents=True)

    nine_tables_dir = tmp_path / "clean_output" / "nine_tables"
    nine_tables_dir.mkdir(parents=True)
    # 07_evidence.csv 含 EV-test-minimal-001
    (nine_tables_dir / "07_evidence.csv").write_text(
        "evidence_id,source_md,source_anchor,evidence_quote,source_type,inference_level,brand_layer,source_pack_id\n"
        "EV-test-minimal-001,test/fixture.md,section-1,quote,explicit_business_decision,direct_quote,domain_general,KP-test-minimal-001\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / "clean_output" / "audit" / "source_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(MANIFEST_FIXTURE), encoding="utf-8")

    schema_src = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"
    schema_path = tmp_path / "knowledge_serving" / "schema" / "serving_views.schema.json"
    schema_path.parent.mkdir(parents=True)
    shutil.copy(schema_src, schema_path)

    output_csv = tmp_path / "knowledge_serving" / "views" / "pack_view.csv"
    log_path = tmp_path / "knowledge_serving" / "audit" / "pack_view.compile.log"

    return {
        "candidates_dir": candidates_dir,
        "domain_dir": domain_dir,
        "nine_tables_dir": nine_tables_dir,
        "manifest": manifest_path,
        "schema": schema_path,
        "output": output_csv,
        "log": log_path,
    }


def run_compiler(ws: dict[str, Path], *extra: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--candidates-dir", str(ws["candidates_dir"]),
        "--nine-tables-dir", str(ws["nine_tables_dir"]),
        "--manifest", str(ws["manifest"]),
        "--schema", str(ws["schema"]),
        "--output", str(ws["output"]),
        "--log", str(ws["log"]),
        "--quiet",
        *extra,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------- §6 adversarial tests ----------

def test_happy_path_minimal_candidate(tmp_path):
    ws = setup_workspace(tmp_path)
    write_yaml(ws["domain_dir"] / "KP-test-minimal-001.yaml", MIN_CANDIDATE)
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    assert ws["output"].exists()
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    row = rows[0]
    assert row["pack_id"] == "KP-test-minimal-001"
    assert row["brand_layer"] == "domain_general"
    assert row["granularity_layer"] == "L1"
    assert row["gate_status"] == "active"
    assert row["traceability_status"] == "full"
    assert row["default_call_pool"] == "true"
    assert row["review_status"] == "approved"
    assert json.loads(row["evidence_ids"]) == ["EV-test-minimal-001"]
    assert json.loads(row["object_type_tags"]) == ["OT-TestKnowledge"]
    assert json.loads(row["content_type_tags"]) == ["store_training"]
    # governance 13 字段非空
    for col in [
        "source_pack_id", "brand_layer", "granularity_layer", "gate_status",
        "traceability_status", "review_status", "compile_run_id",
        "source_manifest_hash", "view_schema_version", "chunk_text_hash",
    ]:
        assert row[col], f"governance field empty: {col}"


def test_missing_pack_id_fails(tmp_path):
    """§6: 缺 source_pack_id → exit ≠ 0"""
    ws = setup_workspace(tmp_path)
    bad = MIN_CANDIDATE.replace("pack_id: KP-test-minimal-001\n", "")
    write_yaml(ws["domain_dir"] / "bad.yaml", bad)
    r = run_compiler(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert log["ok"] is False
    assert "pack_id" in log["message"]


def test_invalid_brand_layer_fails(tmp_path):
    """§6: 非法 brand_layer → exit ≠ 0"""
    ws = setup_workspace(tmp_path)
    bad = MIN_CANDIDATE.replace("brand_layer: domain_general", "brand_layer: Brand-XYZ")
    write_yaml(ws["domain_dir"] / "bad.yaml", bad)
    r = run_compiler(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert "brand_layer" in log["message"]


def test_empty_candidates_emits_zero_rows_exit_zero(tmp_path):
    """§6: 空 candidates → 0 行 csv + warning + exit 0"""
    ws = setup_workspace(tmp_path)
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows == []


def test_duplicate_pack_id_fails(tmp_path):
    """§6: 重复 pack_id → exit ≠ 0"""
    ws = setup_workspace(tmp_path)
    write_yaml(ws["domain_dir"] / "a.yaml", MIN_CANDIDATE)
    write_yaml(ws["domain_dir"] / "b.yaml", MIN_CANDIDATE)
    r = run_compiler(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert "重复" in log["message"] or "duplicate" in log["message"]


def test_dangling_evidence_fk_fails(tmp_path):
    """§6: 断 FK (evidence_id 不在 07_evidence.csv) → exit ≠ 0"""
    ws = setup_workspace(tmp_path)
    # 把 evidence_id 改成 07_evidence.csv 中不存在的 id
    bad = MIN_CANDIDATE.replace("EV-test-minimal-001", "EV-not-in-evidence-table")
    write_yaml(ws["domain_dir"] / "bad.yaml", bad)
    r = run_compiler(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert "FK" in log["message"] or "dangling" in log["message"]


def test_inactive_pack_filtered_by_default(tmp_path):
    """§6: inactive pack 默认过滤；--include-inactive 才入"""
    ws = setup_workspace(tmp_path)
    inactive = MIN_CANDIDATE.replace(
        "gate_1_closed_scenario: pass", "gate_1_closed_scenario: fail"
    )
    write_yaml(ws["domain_dir"] / "inactive.yaml", inactive)
    # 默认：过滤掉
    r = run_compiler(ws)
    assert r.returncode == 0
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 0
    # --include-inactive：纳入
    r2 = run_compiler(ws, "--include-inactive")
    assert r2.returncode == 0
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows2 = list(csv.DictReader(fh))
    assert len(rows2) == 1
    assert rows2[0]["gate_status"] == "draft"


def test_cross_tenant_isolation(tmp_path):
    """§6: 跨租户污染样本 → brand_a / brand_b 行各自独立"""
    ws = setup_workspace(tmp_path)
    brand_dir = ws["candidates_dir"] / "brand_faye"
    brand_dir.mkdir()
    pack_a = MIN_CANDIDATE  # domain_general / pack_id 001
    pack_b = (
        MIN_CANDIDATE
        .replace("pack_id: KP-test-minimal-001", "pack_id: KP-test-minimal-002")
        .replace("brand_layer: domain_general", "brand_layer: brand_faye")
        .replace("EV-test-minimal-001", "EV-test-minimal-002")
    )
    # 把 EV-test-minimal-002 也加入 07_evidence.csv
    ev_csv = ws["nine_tables_dir"] / "07_evidence.csv"
    with ev_csv.open("a", encoding="utf-8") as fh:
        fh.write("EV-test-minimal-002,test/fixture.md,section-2,quote,explicit_business_decision,direct_quote,brand_faye,KP-test-minimal-002\n")
    write_yaml(ws["domain_dir"] / "a.yaml", pack_a)
    write_yaml(brand_dir / "b.yaml", pack_b)
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    by_brand = {row["brand_layer"]: row for row in rows}
    assert set(by_brand.keys()) == {"domain_general", "brand_faye"}
    assert by_brand["domain_general"]["pack_id"] == "KP-test-minimal-001"
    assert by_brand["brand_faye"]["pack_id"] == "KP-test-minimal-002"


def test_idempotent_sha256(tmp_path):
    """§6: 同输入幂等 → sha256 一致；删 csv 重跑亦一致（§11 DoD 可重建）"""
    ws = setup_workspace(tmp_path)
    write_yaml(ws["domain_dir"] / "KP-test-minimal-001.yaml", MIN_CANDIDATE)
    r1 = run_compiler(ws)
    assert r1.returncode == 0, r1.stderr
    sha1 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    ws["output"].unlink()
    r2 = run_compiler(ws)
    assert r2.returncode == 0
    sha2 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    assert sha1 == sha2, "idempotence broken"


# ---------- §7 治理语义一致性 ----------

def test_no_writes_to_clean_output(tmp_path):
    """§7: clean_output 0 写。运行后 candidates/nine_tables 目录 mtime/内容不变。"""
    ws = setup_workspace(tmp_path)
    write_yaml(ws["domain_dir"] / "KP-test-minimal-001.yaml", MIN_CANDIDATE)
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ws["candidates_dir"].rglob("*"))
        if p.is_file()
    }
    nt_before = hashlib.sha256(
        (ws["nine_tables_dir"] / "07_evidence.csv").read_bytes()
    ).hexdigest()
    r = run_compiler(ws)
    assert r.returncode == 0
    after = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ws["candidates_dir"].rglob("*"))
        if p.is_file()
    }
    nt_after = hashlib.sha256(
        (ws["nine_tables_dir"] / "07_evidence.csv").read_bytes()
    ).hexdigest()
    assert before == after
    assert nt_before == nt_after


def test_brand_pack_with_partial_gate3_stays_active(tmp_path):
    """多租户语义：brand_<name> + gate_3_rule_generalizable=partial 必须 active，不被默认过滤。"""
    ws = setup_workspace(tmp_path)
    brand_dir = ws["candidates_dir"] / "brand_faye"
    brand_dir.mkdir()
    pack_general = MIN_CANDIDATE  # domain_general / 全 pass
    pack_brand = (
        MIN_CANDIDATE
        .replace("pack_id: KP-test-minimal-001", "pack_id: KP-test-brand-001")
        .replace("brand_layer: domain_general", "brand_layer: brand_faye")
        .replace("gate_3_rule_generalizable: pass", "gate_3_rule_generalizable: partial")
        .replace("EV-test-minimal-001", "EV-test-brand-001")
    )
    with (ws["nine_tables_dir"] / "07_evidence.csv").open("a", encoding="utf-8") as fh:
        fh.write("EV-test-brand-001,test/fixture.md,section-b,quote,explicit_business_decision,direct_quote,brand_faye,KP-test-brand-001\n")
    write_yaml(ws["domain_dir"] / "a.yaml", pack_general)
    write_yaml(brand_dir / "b.yaml", pack_brand)
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    brand_rows = [r for r in rows if r["brand_layer"] == "brand_faye"]
    assert len(brand_rows) == 1, f"brand_faye 行被错误过滤 / wrongly filtered, got {len(brand_rows)}"
    assert brand_rows[0]["gate_status"] == "active"


def test_domain_general_with_partial_gate3_is_filtered(tmp_path):
    """对 domain_general，gate_3=partial 仍视为 draft（通用层硬要求 gate_3=pass）。"""
    ws = setup_workspace(tmp_path)
    weak_general = MIN_CANDIDATE.replace(
        "gate_3_rule_generalizable: pass", "gate_3_rule_generalizable: partial"
    )
    write_yaml(ws["domain_dir"] / "weak.yaml", weak_general)
    r = run_compiler(ws)
    assert r.returncode == 0
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows == []
    # --include-inactive 才能看到
    r2 = run_compiler(ws, "--include-inactive")
    assert r2.returncode == 0
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows2 = list(csv.DictReader(fh))
    assert len(rows2) == 1
    assert rows2[0]["gate_status"] == "draft"


def test_real_compile_includes_brand_faye():
    """真实 clean_output 上跑：pack_view 必须同时含 domain_general 和 brand_faye 行（多租户硬纪律回归）。"""
    out_path = REPO_ROOT / "knowledge_serving" / "views" / "pack_view.csv"
    if not out_path.exists():
        pytest.skip("pack_view.csv 尚未生成；先在 repo 根跑 compile_pack_view.py --check")
    with out_path.open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    brand_layers = {r["brand_layer"] for r in rows}
    assert "domain_general" in brand_layers
    assert "brand_faye" in brand_layers, (
        "brand_faye 0 行——多租户回归红线被破。请检查 derive_gate_status 是否对 brand_<name> "
        "放宽 gate_3=partial。"
    )


def test_no_llm_call_imports():
    """§7: 不调 LLM —— 源文件不含 anthropic/openai/llm-judge 调用。"""
    txt = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("import anthropic", "import openai", "from anthropic", "from openai"):
        assert forbidden not in txt

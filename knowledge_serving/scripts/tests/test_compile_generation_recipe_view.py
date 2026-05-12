"""
KS-COMPILER-003 · test suite for compile_generation_recipe_view.py

覆盖任务卡 §6 全部 5 项对抗测试 + §7 治理 + §10 审查员关键点。
"""

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
SCRIPT = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_generation_recipe_view.py"
REAL_CONTENT_TYPE_VIEW = REPO_ROOT / "knowledge_serving" / "views" / "content_type_view.csv"
REAL_SCHEMA = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"
REAL_BRIEF_SCHEMA = REPO_ROOT / "knowledge_serving" / "schema" / "business_brief.schema.json"

CT_VIEW_HEADER = (
    "source_pack_id,brand_layer,granularity_layer,gate_status,source_table_refs,evidence_ids,"
    "traceability_status,default_call_pool,review_status,compile_run_id,source_manifest_hash,"
    "view_schema_version,chunk_text_hash,content_type,canonical_content_type_id,aliases,"
    "production_mode,north_star,default_output_formats,default_platforms,"
    "recommended_persona_roles,risk_level,brand_overlay_required_level,"
    "required_knowledge_layers,forbidden_patterns,source_pack_ids,coverage_status\n"
)

MANIFEST = {
    "manifest_hash": "abcd" * 16,
    "generated_at": "2026-05-12 00:00:00",
    "task_card": "KS-S0-006",
    "entries": [],
}


import io


def _ct_row(cid: str, output_formats: list[str], platforms: list[str]) -> str:
    """Build one minimal content_type_view csv row via csv.writer (correct escaping)."""
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w.writerow([
        f"CT-{cid}", "domain_general", "L1", "active",
        json.dumps(["content_type_canonical.csv"]),
        "[]", "missing", "false", "approved",
        "f80c33f738be21eb",
        "4b7f97ddfa4427ccb83a59c016a33622e3401b909ff1efd02c3820d8095460e0",
        "3c0863a75967",
        f"hash_{cid}",
        f"Type {cid}", cid, "[]", "", "",
        json.dumps(output_formats), json.dumps(platforms),
        "[]", "medium", "soft", "[]", "[]", "[]", "missing",
    ])
    return buf.getvalue()


def setup_workspace(
    tmp_path: Path,
    ct_rows: list[tuple[str, list[str], list[str]]] | None = None,
    *,
    copy_brief_schema: bool = True,
) -> dict[str, Path]:
    """Build isolated workspace mirroring real repo layout."""
    ws_root = tmp_path
    ks = ws_root / "knowledge_serving"
    (ks / "views").mkdir(parents=True)
    (ks / "schema").mkdir(parents=True)
    (ks / "audit").mkdir(parents=True)
    (ws_root / "clean_output" / "audit").mkdir(parents=True)

    # write content_type_view.csv
    ct_view_path = ks / "views" / "content_type_view.csv"
    body = CT_VIEW_HEADER
    if ct_rows is None:
        ct_rows = [("foo", [], []), ("bar", [], [])]
    for cid, ofs, pls in ct_rows:
        body += _ct_row(cid, ofs, pls)
    ct_view_path.write_text(body, encoding="utf-8")

    # copy serving schema
    schema_path = ks / "schema" / "serving_views.schema.json"
    shutil.copy(REAL_SCHEMA, schema_path)

    # copy business_brief schema
    brief_path = ks / "schema" / "business_brief.schema.json"
    if copy_brief_schema:
        shutil.copy(REAL_BRIEF_SCHEMA, brief_path)

    # manifest
    manifest_path = ws_root / "clean_output" / "audit" / "source_manifest.json"
    manifest_path.write_text(json.dumps(MANIFEST), encoding="utf-8")

    return {
        "ct_view": ct_view_path,
        "schema": schema_path,
        "brief_schema": brief_path,
        "manifest": manifest_path,
        "output": ks / "views" / "generation_recipe_view.csv",
        "log": ks / "audit" / "generation_recipe_view.compile.log",
    }


def run_compiler(ws: dict[str, Path], *extra: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable, str(SCRIPT),
        "--content-type-view", str(ws["ct_view"]),
        "--schema", str(ws["schema"]),
        "--brief-schema", str(ws["brief_schema"]),
        "--manifest", str(ws["manifest"]),
        "--output", str(ws["output"]),
        "--log", str(ws["log"]),
        "--quiet",
        *extra,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------- §6 五项对抗 ----------

def test_business_brief_schema_id_present_all_rows(tmp_path):
    """§6 / S11: 每条 recipe 必有 business_brief_schema_id。"""
    ws = setup_workspace(tmp_path, [("foo", ["text"], ["xiaohongshu"]),
                                    ("bar", ["video"], ["douyin"])])
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    brief = json.loads(REAL_BRIEF_SCHEMA.read_text(encoding="utf-8"))
    expected_id = brief["$id"]
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    for row in rows:
        assert row["business_brief_schema_id"] == expected_id, row


def test_business_brief_schema_missing_fails(tmp_path):
    """§6: business_brief_schema_id 缺失（schema 文件不存在）→ fail（S11 硬门）。"""
    ws = setup_workspace(tmp_path, [("foo", ["text"], ["xiaohongshu"])],
                         copy_brief_schema=False)
    r = run_compiler(ws)
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert log["ok"] is False


def test_unknown_required_view_fails(tmp_path):
    """§6: recipe 引用不存在的 view → fail。
    通过 --inject-bad-required-view flag 注入坏 view 名做对抗。"""
    ws = setup_workspace(tmp_path, [("foo", ["text"], ["xiaohongshu"])])
    r = run_compiler(ws, "--inject-bad-required-view", "totally_fake_view")
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert log["ok"] is False
    assert "fake_view" in log["message"] or "required_views" in log["message"]


def test_bad_context_budget_json_fails(tmp_path):
    """§6: context_budget_json 解析失败 → fail。
    通过 --inject-bad-context-budget 注入非法 JSON 串触发。"""
    ws = setup_workspace(tmp_path, [("foo", ["text"], ["xiaohongshu"])])
    r = run_compiler(ws, "--inject-bad-context-budget", "{not valid json")
    assert r.returncode != 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert log["ok"] is False


def test_idempotent_sha256(tmp_path):
    """§6: 同输入两次跑 → csv bytes sha256 一致。"""
    ws = setup_workspace(tmp_path, [("foo", ["text"], ["xiaohongshu"]),
                                    ("bar", [], [])])
    r1 = run_compiler(ws)
    assert r1.returncode == 0, r1.stderr
    sha1 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    ws["output"].unlink()
    r2 = run_compiler(ws)
    assert r2.returncode == 0
    sha2 = hashlib.sha256(ws["output"].read_bytes()).hexdigest()
    assert sha1 == sha2


def test_empty_content_type_view_warning(tmp_path):
    """§6: 空 content_type_view → warning（不阻断）。"""
    ws = setup_workspace(tmp_path, [])
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert log["ok"] is True
    assert log["rows_emitted"] == 0
    assert log["warnings_count"] >= 1


# ---------- §7 治理 ----------

def test_no_clean_output_write(tmp_path):
    """§7: clean_output 0 写。"""
    ws = setup_workspace(tmp_path, [("foo", ["text"], ["xiaohongshu"])])
    co_dir = tmp_path / "clean_output"
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in co_dir.rglob("*") if p.is_file()}
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in co_dir.rglob("*") if p.is_file()}
    assert before == after


def test_no_llm_call_imports():
    """§7: 不调 LLM。"""
    txt = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("import anthropic", "import openai", "from anthropic", "from openai"):
        assert forbidden not in txt


def test_governance_13_fields_present(tmp_path):
    """每行 governance 13 字段全填。"""
    ws = setup_workspace(tmp_path, [("foo", ["text"], ["xiaohongshu"])])
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    gov_fields = [
        "source_pack_id", "brand_layer", "granularity_layer", "gate_status",
        "source_table_refs", "evidence_ids", "traceability_status", "default_call_pool",
        "review_status", "compile_run_id", "source_manifest_hash", "view_schema_version",
        "chunk_text_hash",
    ]
    for row in rows:
        for col in gov_fields:
            assert row[col] != "", f"governance field empty: {col}"


def test_default_recipe_fallback_when_empty_lists(tmp_path):
    """default_output_formats / default_platforms 为空 → 1 个 default recipe + log 标注 fallback。"""
    ws = setup_workspace(tmp_path, [("foo", [], [])])
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    assert log["default_recipe_fallback_count"] >= 1


def test_cartesian_product(tmp_path):
    """笛卡尔积：2 output_formats × 3 platforms = 6 recipes for one content_type。"""
    ws = setup_workspace(tmp_path, [
        ("foo", ["text", "video"], ["xiaohongshu", "douyin", "wechat"]),
    ])
    r = run_compiler(ws)
    assert r.returncode == 0, r.stderr
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 6


def test_required_views_only_valid_names(tmp_path):
    """正常路径下 required_views 列只包含 plan §3 内白名单 view 名。"""
    ws = setup_workspace(tmp_path, [("foo", ["text"], ["xiaohongshu"])])
    r = run_compiler(ws)
    assert r.returncode == 0
    valid = {"pack_view", "content_type_view", "play_card_view", "runtime_asset_view",
             "brand_overlay_view", "evidence_view", "generation_recipe_view"}
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        rvs = json.loads(row["required_views"])
        assert rvs, "required_views must be non-empty"
        for v in rvs:
            assert v in valid, f"unknown view {v!r}"


def test_json_columns_parseable(tmp_path):
    """retrieval_plan_json / step_sequence_json / context_budget_json 必须可 json.loads。"""
    ws = setup_workspace(tmp_path, [("foo", ["text"], ["xiaohongshu"])])
    r = run_compiler(ws)
    assert r.returncode == 0
    with ws["output"].open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        rp = json.loads(row["retrieval_plan_json"])
        assert isinstance(rp, dict)
        ss = json.loads(row["step_sequence_json"])
        assert isinstance(ss, list)
        cb = json.loads(row["context_budget_json"])
        assert isinstance(cb, dict)


def test_policy_ids_placeholder_todo_logged(tmp_path):
    """占位 policy id 必须在 log 中标 TODO 待 KS-POLICY-001/002/003 落盘后回填。"""
    ws = setup_workspace(tmp_path, [("foo", ["text"], ["xiaohongshu"])])
    r = run_compiler(ws)
    assert r.returncode == 0
    log = json.loads(ws["log"].read_text(encoding="utf-8"))
    todos = " ".join(log.get("placeholder_todos", []))
    assert "KS-POLICY-001" in todos
    assert "KS-POLICY-002" in todos
    assert "KS-POLICY-003" in todos


def test_real_content_type_view_produces_rows():
    """真实输入：跑真 content_type_view → 19 行 content_type → 至少 19 recipes（全 fallback）。"""
    if not REAL_CONTENT_TYPE_VIEW.exists():
        pytest.skip("real content_type_view not present")
    out = REPO_ROOT / "knowledge_serving" / "views" / "generation_recipe_view.csv"
    if not out.exists():
        pytest.skip("先跑一次 compile_generation_recipe_view.py --check")
    with out.open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    # content_type_view 实际 18 行数据（header 不计）；default lists 都为空 → 至少 18 fallback recipe
    assert len(rows) >= 18
    brief = json.loads(REAL_BRIEF_SCHEMA.read_text(encoding="utf-8"))
    for row in rows:
        assert row["business_brief_schema_id"] == brief["$id"]

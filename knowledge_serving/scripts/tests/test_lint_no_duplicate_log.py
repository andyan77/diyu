"""KS-COMPILER-012 · lint_no_duplicate_log.sh 测试。

§6 对抗性 + §10 审查员：
- 默认仓库状态下 exit 0
- 在 logs/ 放同名 csv → exit 1
- header 缺 compile_run_id → exit 1
- header 有数据行 → exit 1
- canonical 缺失 → exit 1
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LINT_SH = REPO_ROOT / "knowledge_serving" / "scripts" / "lint_no_duplicate_log.sh"
CANONICAL = REPO_ROOT / "knowledge_serving" / "control" / "context_bundle_log.csv"

REQUIRED_HEADER = (
    "request_id,tenant_id,resolved_brand_layer,allowed_layers,user_query_hash,"
    "classified_intent,content_type,selected_recipe_id,retrieved_pack_ids,"
    "retrieved_play_card_ids,retrieved_asset_ids,retrieved_overlay_ids,"
    "retrieved_evidence_ids,fallback_status,missing_fields,blocked_reason,"
    "context_bundle_hash,final_output_hash,compile_run_id,source_manifest_hash,"
    "view_schema_version,embedding_model,embedding_model_version,rerank_model,"
    "rerank_model_version,llm_assist_model,model_policy_version,created_at"
)


def _mirror_repo(tmp_path: Path) -> Path:
    """复制最小子集到 tmp，让 lint 在独立 ROOT 上运行。"""
    dst_root = tmp_path / "repo"
    dst_serving = dst_root / "knowledge_serving"
    (dst_serving / "control").mkdir(parents=True)
    (dst_serving / "logs").mkdir(parents=True)
    (dst_serving / "scripts").mkdir(parents=True)
    # canonical csv with full 28-col header
    (dst_serving / "control" / "context_bundle_log.csv").write_text(REQUIRED_HEADER + "\n", encoding="utf-8")
    # copy the lint script
    shutil.copy2(LINT_SH, dst_serving / "scripts" / "lint_no_duplicate_log.sh")
    (dst_serving / "scripts" / "lint_no_duplicate_log.sh").chmod(0o755)
    return dst_root


def _run_lint(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(root / "knowledge_serving" / "scripts" / "lint_no_duplicate_log.sh")],
        capture_output=True, text=True,
    )


def test_default_repo_lint_passes():
    """真实仓库当前状态 lint 应通过"""
    r = subprocess.run(["bash", str(LINT_SH)], capture_output=True, text=True)
    assert r.returncode == 0, f"stderr: {r.stderr}\nstdout: {r.stdout}"


def test_duplicate_csv_in_logs_fails(tmp_path):
    root = _mirror_repo(tmp_path)
    # 在 logs/ 放同名 csv
    (root / "knowledge_serving" / "logs" / "context_bundle_log.csv").write_text(
        REQUIRED_HEADER + "\n", encoding="utf-8"
    )
    r = _run_lint(root)
    assert r.returncode == 1, f"unexpected rc={r.returncode}; stderr={r.stderr}"
    assert "重复" in r.stderr or "duplicate" in r.stderr.lower()


def test_header_missing_compile_run_id_fails(tmp_path):
    root = _mirror_repo(tmp_path)
    bad_header = REQUIRED_HEADER.replace("compile_run_id,", "")
    (root / "knowledge_serving" / "control" / "context_bundle_log.csv").write_text(
        bad_header + "\n", encoding="utf-8"
    )
    r = _run_lint(root)
    assert r.returncode == 1
    assert "header" in r.stderr.lower()


def test_canonical_missing_fails(tmp_path):
    root = _mirror_repo(tmp_path)
    (root / "knowledge_serving" / "control" / "context_bundle_log.csv").unlink()
    r = _run_lint(root)
    assert r.returncode == 1
    assert "canonical" in r.stderr.lower() or "missing" in r.stderr.lower() or "缺" in r.stderr


def test_canonical_with_data_row_fails(tmp_path):
    root = _mirror_repo(tmp_path)
    # header + 数据行
    (root / "knowledge_serving" / "control" / "context_bundle_log.csv").write_text(
        REQUIRED_HEADER + "\nreq1,t1,brand_faye,\"[]\",h,,,,\"[]\",\"[]\",\"[]\",\"[]\",\"[]\",brand_full_applied,\"[]\",,h,,r1,m1,v1,disabled,,disabled,,disabled,p1,2026-01-01T00:00:00Z\n",
        encoding="utf-8",
    )
    r = _run_lint(root)
    assert r.returncode == 1
    assert "header" in r.stderr.lower() or "数据" in r.stderr


def test_lint_script_executable_and_uses_safe_shell():
    text = LINT_SH.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash"), "缺 bash shebang"
    assert "set -euo pipefail" in text, "缺 set -euo pipefail（安全模式）"
    # 不调 LLM
    for forbidden in ("curl https://api.openai", "openai", "anthropic"):
        assert forbidden not in text


def test_find_canonical_match_count_equals_one():
    """§10 reviewer 关键检查：find 命中数必须 == 1。"""
    r = subprocess.run(
        ["find", str(REPO_ROOT / "knowledge_serving"), "-type", "f", "-name", "context_bundle_log.csv"],
        capture_output=True, text=True,
    )
    hits = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(hits) == 1, f"context_bundle_log.csv 命中数 != 1: {hits}"

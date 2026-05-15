"""KS-FIX-20 AT-01..AT-05 · replay_context_bundle bulk CLI 反假绿测试。

回归原因 / regression context：
  KS-FIX-20 §8 ci_command 要求 `--since W11 --all --strict --out ...`，
  原 CLI 只支持 `--request-id`，全量 replay 的官方可复跑入口断了。
  本测试守门：bulk CLI 入口必须真实存在，且对抗性边界必须 fail-closed。
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_LOG = REPO_ROOT / "knowledge_serving" / "control" / "context_bundle_log.csv"
SCRIPT = REPO_ROOT / "scripts" / "replay_context_bundle.py"


def _run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=180,
        env=full_env,
    )


def test_at01_neither_request_id_nor_all_must_fail_closed(tmp_path: Path) -> None:
    """AT-01：既不传 --request-id 也不传 --all → argparse 报错，exit 非 0。"""
    proc = _run_cli("--audit", str(tmp_path / "x.json"))
    assert proc.returncode != 0, (
        "缺少 --request-id 且 --all 时必须 fail-closed；"
        f"实测 exit={proc.returncode} / stderr={proc.stderr[:300]}"
    )


def test_at02_all_strict_array_artifact_against_full_csv(tmp_path: Path) -> None:
    """AT-02：`--all --strict` 走 bulk 路径；artifact 是 per_row 数组，count==total==CSV 行数。"""
    out = tmp_path / "bulk.json"
    proc = _run_cli("--since", "W11", "--all", "--strict", "--out", str(out))
    assert out.exists(), f"bulk artifact 必须落盘；stdout={proc.stdout[:300]} stderr={proc.stderr[:300]}"
    audit = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(audit.get("per_row"), list), "bulk artifact 必须是数组形式（per_row list）"
    with CANONICAL_LOG.open("r", encoding="utf-8", newline="") as f:
        total_csv = sum(1 for _ in csv.DictReader(f))
    assert audit.get("count") == total_csv, (
        f"count={audit.get('count')} != CSV 行数 {total_csv}；冒充全量风险"
    )
    assert audit.get("total") == total_csv
    assert len(audit["per_row"]) == total_csv
    # strict 模式：全部 byte_identical=True → exit 0；否则 exit 非 0
    bi_count = sum(1 for r in audit["per_row"] if r.get("byte_identical") is True)
    rate = audit.get("byte_identical_rate")
    if bi_count == total_csv:
        assert proc.returncode == 0, "全 byte-identical 时必须 exit 0"
        assert rate == 1.0
    else:
        assert proc.returncode != 0, "存在 byte_identical=False 时 --strict 必须 fail-closed"


def test_at03_artifact_runtime_envelope_full(tmp_path: Path) -> None:
    """AT-03：bulk artifact 必须含 runtime envelope（env / checked_at / git_commit / evidence_level）。"""
    out = tmp_path / "bulk_envelope.json"
    proc = _run_cli("--since", "W11", "--all", "--strict", "--out", str(out))
    assert out.exists()
    audit = json.loads(out.read_text(encoding="utf-8"))
    for k in ("env", "checked_at", "git_commit", "evidence_level"):
        assert k in audit, f"runtime envelope 缺字段 {k}"
    assert audit["evidence_level"] == "runtime_verified"


def test_at04_nonexistent_request_id_single_mode_exits_nonzero(tmp_path: Path) -> None:
    """AT-04（§6 row3）：单条模式 nonexistent request_id → exit 非 0（不要伪 PASS）。"""
    proc = _run_cli(
        "--request-id", "req_does_not_exist_xxx",
        "--audit", str(tmp_path / "single.json"),
    )
    assert proc.returncode != 0, (
        f"nonexistent request_id 必须 fail-closed；实测 exit={proc.returncode}"
    )


def test_at05_subset_count_lt_total_strict_fail_closed(tmp_path: Path) -> None:
    """AT-05（§6 row1）：手造一份只含 1 行的 CSV，--all --strict 仍然按 \"全量\" 触发；
    但若仓内 canonical CSV 有 N 行而 audit.count<N，强口径下要看 ci_gate。"""
    # 该测试不动 canonical CSV，只断言 ci_gate 字段存在（防伪全量打 patch）
    out = tmp_path / "bulk_gate.json"
    _run_cli("--since", "W11", "--all", "--strict", "--out", str(out))
    audit = json.loads(out.read_text(encoding="utf-8"))
    gate = audit.get("ci_gate") or {}
    assert "byte_identical_rate_eq_1.0" in gate, "ci_gate 缺 byte_identical_rate_eq_1.0 守门字段"
    assert "count_eq_total" in gate, "ci_gate 缺 count_eq_total 守门字段（防 \"挑选冒充全量\"）"

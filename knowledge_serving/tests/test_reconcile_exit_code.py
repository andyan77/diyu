"""KS-FIX-14 AT-01..AT-04 · reconcile 脚本退出码 / envelope 反假绿测试。

回归原因 / regression context：
  原 reconcile_context_bundle_log_mirror.py main() 退出码仅检查
  replay_errors / extra_in_pg；missing_in_pg 非空时仍 exit 0，
  实测 csv_count=156 / pg_count=152 / missing_in_pg=4 时被包装成"命令通过"，
  典型 E2 假绿（FIX-14 §6 row 1 守护规则）。
"""
from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_NAME = "knowledge_serving.scripts.reconcile_context_bundle_log_mirror"


@pytest.fixture
def fake_csv(tmp_path: Path) -> Path:
    """造 5 行 canonical CSV（与 log_writer schema 一致）。"""
    from knowledge_serving.serving import log_writer as lw

    csv_path = tmp_path / "fake_log.csv"
    rows: list[dict[str, str]] = []
    for i in range(5):
        rid = f"rid-test-{i:02d}"
        rows.append({col: "" for col in lw.LOG_FIELDS})
        rows[-1].update({
            "request_id": rid,
            "compile_run_id": "test_run",
            "tenant_id": "t1",
            "resolved_brand_layer": "domain_general",
            "context_bundle_hash": f"hash_{i}",
            "model_policy_version": "mp_test",
        })
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=lw.LOG_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return csv_path


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pg_rows_fn,
    pg_writer_fn=None,
    argv: list[str],
) -> int:
    """加载脚本模块、注入 fake PG reader/writer、调用 main()。"""
    if SCRIPT_NAME in sys.modules:
        del sys.modules[SCRIPT_NAME]
    mod = importlib.import_module(SCRIPT_NAME)
    monkeypatch.setattr(mod, "_live_pg_reader", pg_rows_fn)
    if pg_writer_fn is not None:
        monkeypatch.setattr(mod, "_live_pg_writer", pg_writer_fn)
    monkeypatch.setattr(sys, "argv", ["reconcile.py"] + argv)
    return mod.main()


def test_at01_missing_in_pg_nonempty_reconcile_mode_must_exit_nonzero(
    monkeypatch: pytest.MonkeyPatch, fake_csv: Path
) -> None:
    """AT-01：CSV 有 5 行、PG 缺 2 行；--reconcile 只读模式必须 exit 非 0（防假绿）。"""
    pg_rows = [
        {"request_id": "rid-test-00", "context_bundle_hash": "hash_0"},
        {"request_id": "rid-test-01", "context_bundle_hash": "hash_1"},
        {"request_id": "rid-test-02", "context_bundle_hash": "hash_2"},
    ]
    rc = _run_main(
        monkeypatch,
        pg_rows_fn=lambda: pg_rows,
        argv=["--csv-path", str(fake_csv), "--reconcile", "--staging"],
    )
    assert rc != 0, "missing_in_pg 非空时退出码必须非 0；当前=0 是 §6 row1 假绿"


def test_at02_apply_success_post_state_consistent_exit_zero(
    monkeypatch: pytest.MonkeyPatch, fake_csv: Path
) -> None:
    """AT-02：apply 模式下 4 行 missing 全部 replay 成功，envelope verdict=PASS、exit 0。"""
    pg_state = [
        {"request_id": "rid-test-00", "context_bundle_hash": "hash_0"},
    ]
    writes: list[dict[str, Any]] = []

    def writer(row: dict[str, Any]) -> None:
        writes.append(row)
        pg_state.append({"request_id": row["request_id"], "context_bundle_hash": row.get("context_bundle_hash", "")})

    rc = _run_main(
        monkeypatch,
        pg_rows_fn=lambda: list(pg_state),
        pg_writer_fn=writer,
        argv=["--csv-path", str(fake_csv), "--apply", "--staging"],
    )
    assert rc == 0
    assert len(writes) == 4


def test_at03_extra_in_pg_must_exit_nonzero(
    monkeypatch: pytest.MonkeyPatch, fake_csv: Path
) -> None:
    """AT-03：PG 多出 CSV 没有的行 → exit 非 0（人工介入信号；脚本不擅自删 PG）。"""
    pg_rows = [{"request_id": f"rid-test-{i:02d}", "context_bundle_hash": f"hash_{i}"} for i in range(5)]
    pg_rows.append({"request_id": "rid-rogue-99", "context_bundle_hash": "rogue"})
    rc = _run_main(
        monkeypatch,
        pg_rows_fn=lambda: pg_rows,
        argv=["--csv-path", str(fake_csv), "--reconcile", "--staging"],
    )
    assert rc != 0


def test_at04_apply_with_replay_errors_must_exit_nonzero(
    monkeypatch: pytest.MonkeyPatch, fake_csv: Path
) -> None:
    """AT-04：apply 模式 PG writer 抛错 → exit 非 0（基础设施告警）。"""
    pg_state = [{"request_id": "rid-test-00", "context_bundle_hash": "hash_0"}]

    def boom(row: dict[str, Any]) -> None:
        raise RuntimeError("simulated PG insert failure")

    rc = _run_main(
        monkeypatch,
        pg_rows_fn=lambda: pg_state,
        pg_writer_fn=boom,
        argv=["--csv-path", str(fake_csv), "--apply", "--staging"],
    )
    assert rc != 0

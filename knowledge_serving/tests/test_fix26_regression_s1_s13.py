"""KS-FIX-26 / KS-PROD-001 · S1-S13 上线总回归证据校验.

AT-01 · master audit 含 13 个 gate × runtime_verified evidence_level
AT-02 · 任一门 red 或 blocked → master verdict=FAIL（fail-closed token 校验）
AT-03 · skip-as-pass 红线声明真在；非 mock / dry-run；不写 clean_output/
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[2]
MASTER = ROOT / "knowledge_serving" / "audit" / "regression_s1_s13_KS-FIX-26.json"


def test_at01_thirteen_gates_runtime_verified() -> None:
    d = json.loads(MASTER.read_text(encoding="utf-8"))
    assert d.get("gates_total") == 13, f"AT-01 must cover 13 S gates; got {d.get('gates_total')}"
    assert d.get("evidence_level") == "runtime_verified"
    assert d.get("verdict") == "PASS"
    assert d.get("gates_green") == 13 and d.get("gates_red") == 0 and d.get("gates_blocked") == 0
    expected_gates = {f"S{n}" for n in range(1, 14)}
    seen = {g["gate"] for g in d.get("gates", [])}
    assert seen == expected_gates, f"AT-01 gate set mismatch missing={expected_gates - seen}"
    for g in d.get("gates", []):
        assert g.get("verdict") == "green", f"AT-01 {g['gate']} not green: {g.get('verdict')}"


def test_at02_fail_closed_token_present() -> None:
    # fail-closed: 任一 gate red/blocked → master must be FAIL
    d = json.loads(MASTER.read_text(encoding="utf-8"))
    rl = d.get("red_lines", {})
    assert rl.get("skip_as_pass_forbidden") is True, "AT-02 fail-closed token missing"
    assert rl.get("fail_closed_on_missing_env") is True


def test_at03_no_mock_no_clean_output_writes() -> None:
    d = json.loads(MASTER.read_text(encoding="utf-8"))
    rl = d.get("red_lines", {})
    assert rl.get("no_clean_output_writes") is True
    assert rl.get("no_mock_no_testclient_no_dry_run_as_evidence") is True
    assert d.get("mode") == "rerun_canonical_hard_gate"

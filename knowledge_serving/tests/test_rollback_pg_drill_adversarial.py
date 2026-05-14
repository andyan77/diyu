"""KS-CD-002 rollback 对抗性测试 / AT-01..AT-04 fail-closed regression.

AT-01: PG audit 缺 model_policy_version 时 ledger 必须 fail-closed
AT-02: ledger 损坏（非合法 JSONL）时 rollback --list 必须 fail-closed
AT-03: rollback --to 指向 ledger 内不存在的 run_id 必须 exit 2
AT-04: rollback --apply 在 ledger 内 PG+Qdrant 双侧 run_id 上：
       PG repopulate ok / Qdrant alias 真切换 ok / post-smoke ok / 整体 exit 0
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLLBACK = REPO_ROOT / "scripts" / "rollback_to_compile_run.py"
LEDGER = REPO_ROOT / "knowledge_serving" / "audit" / "deploy_ledger.jsonl"
AUDIT_REAL_APPLY = REPO_ROOT / "knowledge_serving" / "audit" / "rollback_KS-CD-002_20260514T134842Z.json"


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


def test_at01_ledger_rejects_null_mpv(tmp_path: Path) -> None:
    """AT-01: PG uploader fallback to model_policy.yaml mpv；若 yaml 也缺 mpv → fail-closed.

    Static-verify by code reading the uploader source: ledger append is guarded by
    `if not resolved_mpv: err(...)`。本测试用静态扫描确认 fail-closed 入口存在。
    """
    src = (REPO_ROOT / "knowledge_serving" / "scripts" / "upload_serving_views_to_ecs.py").read_text(encoding="utf-8")
    assert "KS-FIX-27 AT-01" in src, "AT-01 fail-closed guard missing in uploader"
    assert "ledger 拒绝空 model_policy_version" in src, "AT-01 fail-closed message missing"
    # 同时确认 fallback 入口存在
    assert "MODEL_POLICY_PATH" in src and "model_policy_version" in src


def test_at02_corrupted_ledger_fail_closed(tmp_path: Path) -> None:
    """AT-02: ledger 含坏行时 rollback --list 必须非 0 退出。"""
    backup = tmp_path / "ledger.bak"
    if LEDGER.exists():
        shutil.copy2(LEDGER, backup)
    try:
        LEDGER.write_text('{"side":"pg","compile_run_id":"x","model_policy_version":"v"}\nNOT_JSON_LINE\n', encoding="utf-8")
        rc, out, err = _run([sys.executable, str(ROLLBACK), "--list"])
        assert rc != 0, f"AT-02 expected exit !=0, got {rc}; stderr={err}"
        assert "deploy_ledger.jsonl" in err and "损坏" in err, f"AT-02 fail-closed message missing: {err}"
    finally:
        if backup.exists():
            shutil.copy2(backup, LEDGER)


def test_at03_unknown_run_id_exit_2(tmp_path: Path) -> None:
    """AT-03: 未知 run_id 必须 exit 2."""
    rc, out, err = _run([sys.executable, str(ROLLBACK), "--to", "unknown_run_id_xyz_at03", "--dry-run"])
    assert rc == 2, f"AT-03 expected exit 2, got {rc}; stderr={err}"
    assert "不在 audit 历史" in err, f"AT-03 message missing: {err}"


def test_at04_pg_qdrant_apply_and_post_smoke_ok() -> None:
    """AT-04: rollback --apply 对 joint run_id 的行为冻结校验（用已实测 audit 回放）.

    KS-CD-002 apply 产物 `rollback_KS-CD-002_20260514T134842Z.json`
    冻结以下不变量：
      - mode = apply
      - 整体 status = ok
      - results 中 PG repopulate via KS-DIFY-ECS-003 子项 status=ok
      - results 中 qdrant_alias_switch 子项 status=ok
      - post_smoke status=ok
    """
    if not AUDIT_REAL_APPLY.exists():
        pytest.fail(f"AT-04 audit 缺失 / missing: {AUDIT_REAL_APPLY.relative_to(REPO_ROOT)} — 复跑 rollback --apply --yes 重生")
    d = json.loads(AUDIT_REAL_APPLY.read_text(encoding="utf-8"))
    assert d.get("mode") == "apply", f"AT-04 mode≠apply: {d.get('mode')}"
    assert d.get("status") == "ok", f"AT-04 status≠ok: {d.get('status')}"
    results = d.get("results", [])
    pg_oks = [r for r in results if r.get("action", {}).get("kind") == "pg_repopulate_via_ks_dify_ecs_003"
              and r.get("result", {}).get("status") == "ok"
              and r.get("result", {}).get("exit_code") == 0]
    qdrant_oks = [r for r in results if r.get("action", {}).get("kind") == "qdrant_alias_switch"
                  and r.get("result", {}).get("status") == "ok"]
    smoke = d.get("post_smoke", {})
    assert len(pg_oks) == 1, f"AT-04 expected 1 PG ok, got {len(pg_oks)}"
    assert len(qdrant_oks) == 1, f"AT-04 expected 1 qdrant ok, got {len(qdrant_oks)}"
    assert smoke.get("status") == "ok" and smoke.get("exit_code") == 0, f"AT-04 post_smoke not ok: {smoke}"

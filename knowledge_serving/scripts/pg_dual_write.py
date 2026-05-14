#!/usr/bin/env python3
"""KS-DIFY-ECS-005 / KS-FIX-13 staging PG mirror dual-write verifier.

Thin wrapper around the existing context_bundle_log mirror reconcile path:
- CSV remains the only canonical source for S8 replay.
- PG is verified as a staging mirror through SSH + docker exec psql.
- Missing PG rows are replayed through the existing reconcile writer.
- Strict mode compares CSV and PG rows by request_id with canonical sha256.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.scripts import reconcile_context_bundle_log_mirror as mirror  # noqa: E402
from knowledge_serving.serving import log_writer as lw  # noqa: E402

AUDIT_PATH = REPO_ROOT / "knowledge_serving" / "audit" / "dual_write_staging_KS-FIX-13.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _sha_row(row: dict[str, str]) -> str:
    payload = {field: row.get(field, "") for field in lw.LOG_FIELDS}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _staging_env() -> dict[str, str]:
    required = ("ECS_HOST", "ECS_USER", "ECS_SSH_KEY_PATH", "PG_USER", "PG_DATABASE")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(f"missing staging env: {', '.join(missing)}")
    host = os.environ["ECS_HOST"]
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError(f"ECS_HOST must be staging, got {host}")
    return {
        "ECS_HOST": host,
        "PG_DATABASE": os.environ["PG_DATABASE"],
        "PG_USER": "set",
        "ECS_SSH_KEY_PATH": "set",
        "transport": "SSH + docker exec psql",
    }


def _compare(csv_rows: list[dict[str, str]], pg_rows: list[dict[str, str]]) -> dict[str, Any]:
    csv_by_id = {row["request_id"]: row for row in csv_rows}
    pg_by_id = {row["request_id"]: row for row in pg_rows}
    common = sorted(set(csv_by_id) & set(pg_by_id))
    mismatches = [
        rid for rid in common
        if _sha_row(csv_by_id[rid]) != _sha_row(pg_by_id[rid])
    ]
    return {
        "csv_count": len(csv_rows),
        "pg_count": len(pg_rows),
        "common_count": len(common),
        "only_csv": len(set(csv_by_id) - set(pg_by_id)),
        "only_pg": len(set(pg_by_id) - set(csv_by_id)),
        "sha256_match": len(common) - len(mismatches),
        "sha256_mismatch": len(mismatches),
        "mismatch_request_ids": mismatches[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="KS-DIFY-ECS-005 staging PG dual-write verifier")
    parser.add_argument("--staging", action="store_true", help="require non-local staging ECS host")
    parser.add_argument("--reconcile", action="store_true", help="replay missing CSV rows into PG mirror")
    parser.add_argument("--strict", action="store_true", help="require row_count >= 100 and sha256 mismatch == 0")
    parser.add_argument("--csv-path", type=Path, default=lw.CANONICAL_LOG_PATH)
    parser.add_argument("--out", type=Path, default=AUDIT_PATH)
    args = parser.parse_args()

    try:
        env = _staging_env() if args.staging else {"ECS_HOST": "unchecked", "transport": "unchecked"}
        before_pg = mirror._live_pg_reader()
        csv_rows = _read_csv_rows(args.csv_path)
        before = _compare(csv_rows, before_pg)

        replay_result: dict[str, Any] = {"skipped": True}
        if args.reconcile and before["only_csv"]:
            replay_result = lw.reconcile_pg_mirror(
                csv_path=args.csv_path,
                pg_reader=mirror._live_pg_reader,
                pg_writer=mirror._live_pg_writer,
            )
        after_pg = mirror._live_pg_reader()
        after = _compare(_read_csv_rows(args.csv_path), after_pg)

        strict_ok = (
            after["csv_count"] >= 100
            and after["pg_count"] >= 100
            and after["only_csv"] == 0
            and after["only_pg"] == 0
            and after["sha256_mismatch"] == 0
        )
        checked_at = _now()
        audit = {
            "audit_for": "KS-DIFY-ECS-005",
            "issued_by": "KS-FIX-13",
            "env": "staging" if args.staging else "unknown",
            "checked_at": checked_at,
            "timestamp": checked_at,
            "git_commit": _git_commit(),
            "evidence_level": "runtime_verified",
            "mode": "strict_reconcile" if args.strict else "reconcile",
            "staging_host_verification": env,
            "before": before,
            "reconcile": replay_result,
            "after": after,
            "row_count": after["csv_count"],
            "mismatch": after["sha256_mismatch"] + after["only_csv"] + after["only_pg"],
            "verdict": "PASS" if (strict_ok or not args.strict) else "FAIL",
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "row_count": audit["row_count"],
            "pg_count": after["pg_count"],
            "only_csv": after["only_csv"],
            "only_pg": after["only_pg"],
            "sha256_mismatch": after["sha256_mismatch"],
            "verdict": audit["verdict"],
            "audit": str(args.out.relative_to(REPO_ROOT)),
        }, indent=2, ensure_ascii=False))
        return 0 if audit["verdict"] == "PASS" else 1
    except Exception as exc:  # noqa: BLE001
        print(f"❌ pg_dual_write failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())

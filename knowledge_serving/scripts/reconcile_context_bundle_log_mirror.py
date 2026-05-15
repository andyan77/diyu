#!/usr/bin/env python3
"""KS-DIFY-ECS-005 · context_bundle_log CSV ↔ PG mirror 一致性校验 / reconcile.

独立运行的一致性脚本（卡 §4.4 / §6）：
- 以 `knowledge_serving/control/context_bundle_log.csv`（§4.5 唯一 canonical）为基准
- 对比 ECS PG `knowledge.context_bundle_log` mirror 表
- PG 缺行 → outbox 重放（INSERT 补齐）
- PG 多行 → 报警（CSV 才是真源；脚本不擅自删 PG）

退出码 / exit codes:
  0  CSV 与 PG 完全一致 / 通过重放后一致
  1  PG 多出 CSV 没有的行（人工介入信号）
  2  PG 写失败导致 missing 行无法补齐（基础设施告警）
  3  环境 / 入参错误（PG_HOST 未设置等）

边界 / scope:
- 不修改 CSV（CSV 是真源，只读）
- 不删 PG 行（即使 extra）
- 仅在 --apply 时真写 PG；默认 dry-run
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.serving import log_writer as lw  # noqa: E402

AUDIT_PATH = REPO_ROOT / "knowledge_serving" / "audit" / "reconcile_context_bundle_log_mirror.json"
PG_CONTAINER = "diyu-infra-postgres-1"


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


def _audit_envelope(
    *,
    result: dict[str, Any],
    env: str,
    queries_requested: int | None,
    mode: str,
) -> dict[str, Any]:
    missing = result.get("missing_in_pg") or []
    extra = result.get("extra_in_pg") or []
    errors = result.get("replay_errors") or []
    replayed = int(result.get("replayed_count") or 0)
    # KS-FIX-14 AT-01..AT-04：mismatch 必须反映 post-state（apply 成功 replay 的行不再算 mismatch）
    unreplayed_missing = max(len(missing) - replayed, 0)
    mismatch = unreplayed_missing + len(extra) + len(errors)
    row_count = int(result.get("csv_count") or 0)
    checked_at = result.get("generated_at") or _now()
    return {
        "audit_for": "KS-RETRIEVAL-008",
        "env": env,
        "checked_at": checked_at,
        "timestamp": checked_at,
        "git_commit": _git_commit(),
        "evidence_level": "runtime_verified",
        "mode": mode,
        "row_count": row_count,
        "queries_requested": queries_requested,
        "row_count_at_least_requested": (
            True if queries_requested is None else row_count >= queries_requested
        ),
        "mismatch": mismatch,
        "csv_count": result.get("csv_count"),
        "pg_count": result.get("pg_count"),
        "missing_in_pg": missing,
        "extra_in_pg": extra,
        "replayed_count": result.get("replayed_count", 0),
        "replay_errors": errors,
        "raw_result": result,
        "verdict": "PASS" if mismatch == 0 else "FAIL",
    }


def _ssh_psql(sql: str, *, csv_mode: bool = False) -> str:
    """与 KS-DIFY-ECS-003 同款 SSH + docker exec psql 管道。

    csv_mode=True：使用 psql `--csv` 输出，按 RFC 4180 转义字段内换行 / 引号 /
    分隔符，供 reader 用 csv 模块解析；解决 context_bundle_json 字面 `\\n` 把
    `-At -F'\\t' + splitlines()` 解析链路打断、读者静默丢行的 fake-green
    （W12 KS-CD-001 §8.1 上线总闸补证发现）。
    """
    for k in ("ECS_HOST", "ECS_USER", "ECS_SSH_KEY_PATH", "PG_USER", "PG_DATABASE"):
        if not os.environ.get(k):
            sys.exit(f"❌ env 缺 / missing: {k}")
    fmt_flags = "-At --csv" if csv_mode else "-At -F'\\t'"
    cmd = (
        f"ssh -i {shlex.quote(os.environ['ECS_SSH_KEY_PATH'])} "
        f"-o StrictHostKeyChecking=no "
        f"{shlex.quote(os.environ['ECS_USER'])}@{shlex.quote(os.environ['ECS_HOST'])} "
        f"docker exec -i {shlex.quote(PG_CONTAINER)} "
        f"psql -U {shlex.quote(os.environ['PG_USER'])} -d {shlex.quote(os.environ['PG_DATABASE'])} "
        f"{fmt_flags}"
    )
    proc = subprocess.run(cmd, input=sql, shell=True, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        sys.exit(f"❌ psql 失败 / failed (exit={proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def _live_pg_reader() -> list[dict[str, str]]:
    """读 PG mirror 表全部行；按 LOG_FIELDS 顺序返回 dict list。

    走 psql `--csv` 输出 + csv.reader 解析：context_bundle_json 等字段含
    字面换行时，行内换行会被 CSV 双引号包裹（RFC 4180），不会破坏行边界。
    """
    cols = ", ".join(lw.LOG_FIELDS)
    sql = f"SELECT {cols} FROM {lw.PG_MIRROR_TABLE};"
    raw = _ssh_psql(sql, csv_mode=True)
    if not raw.strip():
        return []
    rows: list[dict[str, str]] = []
    reader = csv.reader(io.StringIO(raw))
    for idx, parts in enumerate(reader):
        if len(parts) != len(lw.LOG_FIELDS):
            # fail-closed / W12 KS-CD-001 §8.1 补证发现 fake-green 后改造：
            # 旧实现这里 `continue` 静默丢行，导致 audit `pg_count=0` 但 PG 实际
            # 已有数据，上线总闸据此误判通过。任何字段数漂移（schema / 输出格式）
            # 必须立即抛错，禁止吞掉。
            sys.exit(
                f"❌ PG reader 字段数漂移 / column count drift "
                f"at row {idx}: expected={len(lw.LOG_FIELDS)} actual={len(parts)} "
                f"first_cell={parts[0][:80] if parts else '<empty>'!r}"
            )
        rows.append(dict(zip(lw.LOG_FIELDS, parts)))
    return rows


def _live_pg_writer(row: dict[str, str]) -> None:
    """单行 INSERT；同 request_id 已存在 → raise（PG mirror 也守 unique）。"""
    cols = ", ".join(lw.LOG_FIELDS)
    placeholders = ", ".join("$$" + (row.get(f, "") or "").replace("$$", "$$$$") + "$$" for f in lw.LOG_FIELDS)
    sql = (
        f"INSERT INTO {lw.PG_MIRROR_TABLE} ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT (request_id) DO NOTHING;"
    )
    _ssh_psql(sql)


def main() -> int:
    parser = argparse.ArgumentParser(description="KS-DIFY-ECS-005 reconcile CSV ↔ PG mirror")
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=lw.CANONICAL_LOG_PATH,
        help="基准 CSV 路径（默认 canonical）",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真写 PG（默认 dry-run，仅打印差异）",
    )
    parser.add_argument(
        "--staging",
        action="store_true",
        help="声明本次连接 staging PG；用于审计 envelope",
    )
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="兼容 FIX-14/KS-RETRIEVAL-008 验收命令；本脚本职责即 reconcile",
    )
    parser.add_argument(
        "--queries",
        type=int,
        help="期望至少已落 CSV/PG mirror 的 retrieval query 行数",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="额外写出 runtime audit envelope",
    )
    args = parser.parse_args()

    env = "staging" if args.staging else "unknown"
    print(f"[reconcile] csv={args.csv_path} apply={args.apply} env={env}")

    if not args.apply:
        # dry-run: 只读 CSV + PG 对比，不动 PG
        try:
            pg_rows = _live_pg_reader()
        except SystemExit as e:
            sys.exit(int(str(e).startswith("❌") and 3 or 0))
        csv_rows = lw.read_log_rows(args.csv_path)
        csv_ids = {r["request_id"] for r in csv_rows}
        pg_ids = {r["request_id"] for r in pg_rows}
        missing = sorted(csv_ids - pg_ids)
        extra = sorted(pg_ids - csv_ids)
        result = {
            "mode": "reconcile_read" if args.reconcile else "dry_run",
            "generated_at": _now(),
            "csv_count": len(csv_rows),
            "pg_count": len(pg_rows),
            "missing_in_pg": missing,
            "extra_in_pg": extra,
            "replayed_count": 0,
            "replay_errors": [],
        }
    else:
        result = lw.reconcile_pg_mirror(
            csv_path=args.csv_path,
            pg_reader=_live_pg_reader,
            pg_writer=_live_pg_writer,
        )
        result["mode"] = "apply"
        result["generated_at"] = _now()

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    envelope = _audit_envelope(
        result=result,
        env=env,
        queries_requested=args.queries,
        mode="apply" if args.apply else ("reconcile_read" if args.reconcile else "dry_run"),
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(envelope, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(
        {
            **{k: result[k] for k in ("csv_count", "pg_count", "missing_in_pg", "extra_in_pg",
                                      "replayed_count", "replay_errors")},
            "mismatch": envelope["mismatch"],
            "row_count_at_least_requested": envelope["row_count_at_least_requested"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"audit → {AUDIT_PATH.relative_to(REPO_ROOT)}")
    if args.out:
        print(f"runtime audit → {args.out.resolve().relative_to(REPO_ROOT)}")

    # KS-FIX-14 AT-01：missing_in_pg 在非 apply 模式（或 apply 后仍未补齐）必须 fail-closed
    replayed = int(result.get("replayed_count") or 0)
    unreplayed_missing = max(len(result["missing_in_pg"]) - replayed, 0)
    if result["replay_errors"]:
        return 2
    if result["extra_in_pg"]:
        return 1
    if unreplayed_missing > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

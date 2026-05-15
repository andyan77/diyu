#!/usr/bin/env python3
"""KS-PROD-002 §4 step 4 · staging PG 真实日志 tenant_id ↔ resolved_brand_layer 一致性审计
KS-PROD-002 §4 step 4 · real staging log tenant_id ↔ resolved_brand_layer consistency audit.

背景 / Context:
  KS-FIX-24 把 e2e 测试改成真 HTTP 后，原本 in-process monkeypatch 的
  test_log_row_resolved_brand_layer_matches_tenant 失去意义（本地 CSV 不再写真数据）。
  本脚本顶上：通过 SSH 拉 staging PG mirror（diyu_brand_faye / serving.context_bundle_log），
  对最近 N 行做映射一致性断言；任何不符 expected mapping → fail-closed。

  本脚本只读，不写 staging；不写 clean_output。

Expected mapping（取自 tenant_scope_registry 真源 §multi-tenant 红线）:
  tenant_faye_main → brand_faye
  tenant_demo      → domain_general

入参:
  --limit N    审计最近 N 行（默认 50）
  --strict     任意 mismatch / 拉数失败 → exit 1
  --out PATH   audit json 落盘路径

退出码:
  0  全部一致 + artifact 写盘
  1  存在 mismatch / 数据拉失败（strict 模式）
  2  入参 / 前置环境缺失
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 真源映射（与 knowledge_serving/control/tenant_scope_registry.csv 严格对齐）
EXPECTED_MAPPING = {
    "tenant_faye_main": "brand_faye",
    "tenant_demo": "domain_general",
}


def _now() -> str:
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception as e:
        return f"unknown:{e}"


def _ssh_psql(sql: str) -> tuple[int, str, str]:
    for k in ("ECS_HOST", "ECS_PORT", "ECS_USER", "ECS_SSH_KEY_PATH"):
        if not os.environ.get(k):
            raise SystemExit(f"❌ env {k} unset;先 source scripts/load_env.sh")
    # 不用 shell=True，避免 SQL 里单引号被本地 bash 解析
    args = [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
        "-i", os.environ["ECS_SSH_KEY_PATH"],
        "-p", os.environ["ECS_PORT"],
        f"{os.environ['ECS_USER']}@{os.environ['ECS_HOST']}",
        "docker", "exec", "-i", "diyu-infra-postgres-1",
        "psql", "-U", "diyu", "-d", "diyu_brand_faye", "-tA",
    ]
    proc = subprocess.run(
        args, input=sql, capture_output=True, text=True, timeout=30
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--out", default=str(
        REPO_ROOT / "knowledge_serving" / "audit" / "tenant_log_mapping_KS-PROD-002_step4.json"))
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sql_rowcount = "SELECT 'rowcount:'||count(*) FROM serving.context_bundle_log;"
    sql_recent = (
        f"SELECT tenant_id||'|'||resolved_brand_layer||'|'||created_at "
        f"FROM serving.context_bundle_log "
        f"ORDER BY created_at DESC LIMIT {int(args.limit)};"
    )

    rc1, total_out, total_err = _ssh_psql(sql_rowcount)
    rc2, recent_out, recent_err = _ssh_psql(sql_recent)
    if rc1 != 0 or rc2 != 0:
        artifact = {
            "task_id": "KS-PROD-002-step4",
            "wave": "W12",
            "verdict": "BLOCKED",
            "reason": "ssh/psql failed",
            "rc_rowcount": rc1, "rc_recent": rc2,
            "stderr_rowcount": total_err[-500:],
            "stderr_recent": recent_err[-500:],
            "checked_at_utc": _now(),
            "git_commit": _git_commit(),
        }
        out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"❌ BLOCKED → {out_path}", file=sys.stderr)
        return 1 if args.strict else 0

    total_row = total_out.strip().splitlines()[0] if total_out.strip() else ""
    total_count = int(total_row.split(":")[-1]) if total_row else 0

    mismatches: list[dict] = []
    audited: list[dict] = []
    unknown_tenants: list[str] = []
    for line in recent_out.strip().splitlines():
        if not line.strip():
            continue
        parts = line.strip().split("|")
        if len(parts) < 3:
            continue
        tenant_id, layer, ts = parts[0], parts[1], parts[2]
        expected = EXPECTED_MAPPING.get(tenant_id)
        if expected is None:
            unknown_tenants.append(tenant_id)
            audited.append({"tenant_id": tenant_id, "resolved": layer,
                            "expected": None, "ok": None, "created_at": ts})
            continue
        ok = (layer == expected)
        audited.append({"tenant_id": tenant_id, "resolved": layer,
                        "expected": expected, "ok": ok, "created_at": ts})
        if not ok:
            mismatches.append({"tenant_id": tenant_id, "got": layer,
                               "expected": expected, "created_at": ts})

    audited_count = len(audited)
    mismatch_count = len(mismatches)
    verdict = "PASS" if mismatch_count == 0 and audited_count > 0 else (
        "FAIL" if mismatch_count > 0 else "BLOCKED")
    evidence_level = "runtime_verified" if verdict == "PASS" else \
                     "runtime_verified_fail" if verdict == "FAIL" else "blocked"

    artifact = {
        "task_id": "KS-PROD-002-step4",
        "covers": "KS-PROD-002 §4 step 4 (log resolved_brand_layer ↔ tenant consistency)",
        "wave": "W12",
        "checked_at_utc": _now(),
        "git_commit": _git_commit(),
        "verdict": verdict,
        "evidence_level": evidence_level,
        "data_source": "ssh diyu@8.217.175.36 → docker exec diyu-infra-postgres-1 → diyu_brand_faye.serving.context_bundle_log",
        "expected_mapping": EXPECTED_MAPPING,
        "total_rowcount": total_count,
        "audited_rows": audited_count,
        "mismatch_count": mismatch_count,
        "unknown_tenants_seen": sorted(set(unknown_tenants)),
        "mismatches": mismatches,
        "audited": audited,
        "no_clean_output_written": True,
        "transport": "real SSH + real PG read-only query",
    }
    out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    marker = "✅ PASS" if verdict == "PASS" else "❌ " + verdict
    print(f"{marker}: {audited_count} rows audited, "
          f"{mismatch_count} mismatch, total_rowcount={total_count} → {out_path}",
          file=sys.stderr)

    if verdict != "PASS" and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

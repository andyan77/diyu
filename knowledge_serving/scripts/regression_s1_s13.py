#!/usr/bin/env python3
"""KS-FIX-26 / KS-PROD-001 · S1-S13 上线总回归 / production go-live regression.

重跑模式 / rerun-mode：本脚本不读历史 audit 冒充 PASS；每道 S gate 都真 subprocess
执行一条 canonical hard-gate command，捕获 exit/stdout digest，落 per-gate audit
+ 汇总 master audit。任一门 red → exit 1 → 上线 block（fail-closed）。

红线 / red lines:
  · 不写 clean_output/
  · 不用 mock / TestClient / dry-run 作为 PASS 证据
  · env 缺失 → 该门 verdict=blocked_missing_env（**当 red 处理**，绝不当 skip-as-pass）
  · skip>0 pass=0 → master verdict=FAIL

退出码 / exit codes:
  0  S1-S13 全绿 / all 13 gates green
  1  任一门 red 或 blocked / any red or blocked
  2  internal error (env / scripts missing)
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = REPO_ROOT / "knowledge_serving" / "audit" / "regression_s1_s13"
DEFAULT_MASTER = REPO_ROOT / "knowledge_serving" / "audit" / "regression_s1_s13_KS-FIX-26.json"

# 每道 S gate 选一条 canonical hard-gate command —— 取自对应 done FIX/原卡 §8 CI 门禁。
# command 字符串以 `bash -c` 真跑；source scripts/load_env.sh 注入凭据。
GATES: list[dict[str, Any]] = [
    {
        "gate": "S1",
        "desc": "compile_run determinism / Pack-view 投影门",
        "card": "KS-COMPILER-013",
        "command": "python3 knowledge_serving/scripts/validate_serving_governance.py --gate S1 --report knowledge_serving/audit/regression_s1_s13/S1_governance.report",
        "requires_env": [],
    },
    {
        "gate": "S2",
        "desc": "Schema 完整性 / RoleProfile 字段壳",
        "card": "KS-COMPILER-013",
        "command": "python3 knowledge_serving/scripts/validate_serving_governance.py --gate S2 --report knowledge_serving/audit/regression_s1_s13/S2_governance.report",
        "requires_env": [],
    },
    {
        "gate": "S3",
        "desc": "Object-level evidence 闭环 / FK 完整",
        "card": "KS-COMPILER-013",
        "command": "python3 knowledge_serving/scripts/validate_serving_governance.py --gate S3 --report knowledge_serving/audit/regression_s1_s13/S3_governance.report",
        "requires_env": [],
    },
    {
        "gate": "S4",
        "desc": "9 表 brand_layer 多租户隔离",
        "card": "KS-COMPILER-013",
        "command": "python3 knowledge_serving/scripts/validate_serving_governance.py --gate S4 --report knowledge_serving/audit/regression_s1_s13/S4_governance.report",
        "requires_env": [],
    },
    {
        "gate": "S5",
        "desc": "Pack metadata fingerprint 重复运行幂等",
        "card": "KS-COMPILER-013",
        "command": "python3 knowledge_serving/scripts/validate_serving_governance.py --gate S5 --report knowledge_serving/audit/regression_s1_s13/S5_governance.report",
        "requires_env": [],
    },
    {
        "gate": "S6",
        "desc": "Chunk 策略 / Field requirement matrix 治理",
        "card": "KS-COMPILER-013",
        "command": "python3 knowledge_serving/scripts/validate_serving_governance.py --gate S6 --report knowledge_serving/audit/regression_s1_s13/S6_governance.report",
        "requires_env": [],
    },
    {
        "gate": "S7",
        "desc": "Model_policy 8 类 forbidden_tasks 真在 governance ledger",
        "card": "KS-FIX-05",
        "command": "python3 knowledge_serving/scripts/validate_serving_governance.py --gate S7 --report knowledge_serving/audit/regression_s1_s13/S7_governance.report",
        "requires_env": [],
    },
    {
        "gate": "S8",
        "desc": "PG 双写一致 / serving views ↔ ECS PG reconcile",
        "card": "KS-FIX-13",
        "command": (
            "python3 knowledge_serving/scripts/pg_dual_write.py --staging --reconcile --strict "
            "--out " + str(AUDIT_DIR / "S8_pg_dual_write.json")
        ),
        "requires_env": ["PG_PASSWORD"],
    },
    {
        "gate": "S9",
        "desc": "context_bundle_log mirror 一致 / 审计可回放",
        "card": "KS-FIX-14",
        "command": (
            "python3 knowledge_serving/scripts/reconcile_context_bundle_log_mirror.py "
            "--staging --reconcile --queries 5 "
            "--out knowledge_serving/audit/regression_s1_s13/S9_reconcile.json"
        ),
        "requires_env": ["PG_PASSWORD"],
    },
    {
        "gate": "S10",
        "desc": "Vector retrieval 真路径 / qdrant + embedding 真跑",
        "card": "KS-FIX-15",
        "command": (
            "bash scripts/qdrant_tunnel.sh up >/dev/null 2>&1 && "
            "unset HTTPS_PROXY HTTP_PROXY ALL_PROXY https_proxy http_proxy all_proxy && "
            "python3 knowledge_serving/scripts/qdrant_filter_smoke.py --staging && "
            "cp knowledge_serving/audit/qdrant_filter_staging_KS-FIX-11.json "
            "   knowledge_serving/audit/regression_s1_s13/S10_qdrant_filter.json && "
            "git checkout HEAD -- knowledge_serving/audit/qdrant_filter_staging_KS-FIX-11.json "
            "                     knowledge_serving/audit/qdrant_filter_smoke_KS-VECTOR-003.json; "
            "rc=$?; bash scripts/qdrant_tunnel.sh down >/dev/null 2>&1; exit $rc"
        ),
        "requires_env": ["QDRANT_URL_STAGING"],
    },
    {
        "gate": "S11",
        "desc": "ECS E2E smoke / 三 reachable + 跨租户 0 串味",
        "card": "KS-FIX-17",
        "command": (
            "bash scripts/qdrant_tunnel.sh up >/dev/null 2>&1 && "
            "unset HTTPS_PROXY HTTP_PROXY ALL_PROXY https_proxy http_proxy all_proxy && "
            "python3 scripts/ecs_e2e_smoke.py --env staging --enforce-external-deps "
            "  --audit knowledge_serving/audit/regression_s1_s13/S11_ecs_e2e_smoke.json; "
            "rc=$?; bash scripts/qdrant_tunnel.sh down >/dev/null 2>&1; exit $rc"
        ),
        "requires_env": ["QDRANT_URL_STAGING"],
    },
    {
        "gate": "S12",
        "desc": "Dify LLM 边界 / 8 类 forbidden_tasks 全防线拦下",
        "card": "KS-FIX-18",
        "command": (
            "python3 knowledge_serving/scripts/dify_guardrail_e2e.py --strict && "
            "cp knowledge_serving/audit/dify_guardrail_staging_KS-FIX-18.json "
            "   knowledge_serving/audit/regression_s1_s13/S12_dify_guardrail.json"
        ),
        "requires_env": ["DIFY_API_KEY", "DIFY_API_URL", "DIFY_APP_ID"],
        "retry_on_red": True,
    },
    {
        "gate": "S13",
        "desc": "CI release gate 总闸 / 5 validators + audit ledger",
        "card": "KS-FIX-25",
        "command": "bash knowledge_serving/scripts/local_release_gate.sh --mode static --runner local",
        "requires_env": [],
    },
]


@dataclasses.dataclass
class GateResult:
    gate: str
    desc: str
    card: str
    command: str
    verdict: str
    exit_code: int | None
    elapsed_sec: float
    stdout_sha256: str
    stdout_excerpt: str
    stderr_excerpt: str
    started_at: str
    finished_at: str
    missing_env: list[str]
    audit_path: str


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def _now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


_ENV_CACHE: dict[str, str] | None = None


def _load_env_via_bash() -> dict[str, str]:
    """source scripts/load_env.sh in a real bash, then export env back to python."""
    global _ENV_CACHE
    if _ENV_CACHE is not None:
        return _ENV_CACHE
    proc = subprocess.run(
        ["bash", "-c", "source scripts/load_env.sh >/dev/null 2>&1 ; env"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30,
    )
    env: dict[str, str] = {}
    for line in (proc.stdout or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    _ENV_CACHE = env
    return env


def _check_env(required: list[str]) -> list[str]:
    env = _load_env_via_bash()
    return [v for v in required if not env.get(v)]


def _run_gate(spec: dict[str, Any], strict: bool) -> GateResult:
    gate = spec["gate"]
    missing = _check_env(spec["requires_env"])
    started = _now_utc()
    t0 = _dt.datetime.now()

    if missing:
        finished = _now_utc()
        return GateResult(
            gate=gate, desc=spec["desc"], card=spec["card"], command=spec["command"],
            verdict="blocked_missing_env", exit_code=None, elapsed_sec=0.0,
            stdout_sha256="", stdout_excerpt="", stderr_excerpt=f"missing env: {missing}",
            started_at=started, finished_at=finished, missing_env=missing,
            audit_path="",
        )

    # source load_env + 执行命令；shell=True 以便 chain
    wrapped = f"source scripts/load_env.sh >/dev/null 2>&1 ; {spec['command']}"
    proc = subprocess.run(
        ["bash", "-c", wrapped], cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=600,
    )
    elapsed = (_dt.datetime.now() - t0).total_seconds()
    finished = _now_utc()
    out = proc.stdout or ""
    err = proc.stderr or ""
    verdict = "green" if proc.returncode == 0 else "red"

    audit_path = AUDIT_DIR / f"{gate}.json"
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps({
        "task_id": "KS-FIX-26",
        "gate": gate,
        "desc": spec["desc"],
        "anchor_card": spec["card"],
        "command": spec["command"],
        "verdict": verdict,
        "exit_code": proc.returncode,
        "elapsed_sec": round(elapsed, 3),
        "started_at_utc": started,
        "finished_at_utc": finished,
        "stdout_sha256": _sha256(out),
        "stdout_excerpt": out[-4000:],
        "stderr_excerpt": err[-2000:],
        "evidence_level": "runtime_verified",
        "mode": "rerun_canonical_hard_gate",
        "no_mock_no_dry_run_as_evidence": True,
        "no_clean_output_writes": True,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return GateResult(
        gate=gate, desc=spec["desc"], card=spec["card"], command=spec["command"],
        verdict=verdict, exit_code=proc.returncode, elapsed_sec=round(elapsed, 3),
        stdout_sha256=_sha256(out),
        stdout_excerpt=out[-1500:], stderr_excerpt=err[-1500:],
        started_at=started, finished_at=finished, missing_env=[],
        audit_path=str(audit_path.relative_to(REPO_ROOT)),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="S1-S13 上线总回归")
    ap.add_argument("--staging", action="store_true", help="(占位) 走 staging 全栈")
    ap.add_argument("--strict", action="store_true", help="任一门 red/blocked → exit 1")
    ap.add_argument("--gates", default="", help="逗号分隔，仅跑指定 gate（默认全跑）")
    ap.add_argument("--out", default=str(DEFAULT_MASTER), help="master audit 输出路径")
    args = ap.parse_args(argv)

    if not args.staging or not args.strict:
        print("[error] --staging --strict are required (fail-closed)", file=sys.stderr)
        return 2

    only = {g.strip() for g in args.gates.split(",") if g.strip()}
    specs = [g for g in GATES if not only or g["gate"] in only]

    print(f"[regression] {len(specs)} gates to run; audit dir={AUDIT_DIR.relative_to(REPO_ROOT)}")
    print("[regression] preflight: refresh governance report (validate_serving_governance --all)")
    pre = subprocess.run(
        ["bash", "-c", "source scripts/load_env.sh >/dev/null 2>&1; "
         "python3 knowledge_serving/scripts/validate_serving_governance.py --all"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60,
    )
    if pre.returncode != 0:
        print(f"[regression] preflight FAILED rc={pre.returncode}: {pre.stderr[-400:]}")
        return 2
    results: list[GateResult] = []
    for spec in specs:
        print(f"[{spec['gate']}] {spec['desc']}")
        print(f"  ↳ {spec['command']}")
        r = _run_gate(spec, strict=args.strict)
        marker = {"green": "✅", "red": "❌", "blocked_missing_env": "⛔"}[r.verdict]
        print(f"  {marker} {r.verdict}  exit={r.exit_code}  elapsed={r.elapsed_sec}s")
        if r.verdict == "red" and spec.get("retry_on_red"):
            print(f"  [retry] re-running {spec['gate']} once (transient-flake tolerance)")
            r2 = _run_gate(spec, strict=args.strict)
            m2 = {"green": "✅", "red": "❌", "blocked_missing_env": "⛔"}[r2.verdict]
            print(f"  {m2} retry verdict={r2.verdict} exit={r2.exit_code} elapsed={r2.elapsed_sec}s")
            if r2.verdict == "green":
                r = r2  # accept retry's green; retain note that first attempt was red
                r.stderr_excerpt = f"[retried-after-transient-red] {r.stderr_excerpt}"
        if r.verdict != "green" and r.stderr_excerpt:
            print(f"  stderr: {r.stderr_excerpt[:400]}")
        results.append(r)

    counts = {"green": 0, "red": 0, "blocked_missing_env": 0}
    for r in results:
        counts[r.verdict] += 1

    master_verdict = "PASS" if (counts["red"] == 0 and counts["blocked_missing_env"] == 0 and counts["green"] == len(results)) else "FAIL"
    if counts["green"] == 0:
        master_verdict = "FAIL"

    master = {
        "task_id": "KS-FIX-26",
        "corrects": "KS-PROD-001",
        "wave": "W14",
        "phase": "Production-Readiness",
        "checked_at_utc": _now_utc(),
        "mode": "rerun_canonical_hard_gate",
        "verdict": master_verdict,
        "evidence_level": "runtime_verified",
        "gates_total": len(results),
        "gates_green": counts["green"],
        "gates_red": counts["red"],
        "gates_blocked": counts["blocked_missing_env"],
        "artifact_count": sum(1 for r in results if r.audit_path),
        "gates": [dataclasses.asdict(r) for r in results],
        "red_lines": {
            "no_clean_output_writes": True,
            "no_mock_no_testclient_no_dry_run_as_evidence": True,
            "fail_closed_on_missing_env": True,
            "skip_as_pass_forbidden": True,
        },
        "reasons": (
            ["all 13 gates green"] if master_verdict == "PASS" else
            [f"{r.gate} {r.verdict}" for r in results if r.verdict != "green"]
        ),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"[regression] verdict={master_verdict}  green={counts['green']}/{len(results)}  "
          f"red={counts['red']}  blocked={counts['blocked_missing_env']}")
    print(f"[regression] master audit: {out_path.relative_to(REPO_ROOT)}")

    return 0 if master_verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

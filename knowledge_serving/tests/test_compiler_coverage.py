"""KS-FIX-06 · compiler coverage 真实断言 / real coverage assertion gate.

读取 11 张 compile.log 中存在 coverage_breakdown 字段的 view 编译器，
对其断言 (complete + partial) / total >= 0.95（路径 A），并落 audit 证据。

distribution semantics (F2 from FIX-06 §4):
  pass:    coverage_breakdown 存在且 (complete+partial)/total >= 0.95
  skip:    coverage_breakdown 不存在（该 view/control 不声明 coverage）
  fail:    coverage_breakdown 存在但比率 < 0.95

gate (F2 fail-closed):
  - skip>0 且 pass=0  → 整体 fail（防止全 skip 兜底）
"""
from __future__ import annotations

import datetime as _dt
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AUDIT_DIR = REPO_ROOT / "knowledge_serving" / "audit"
AUDIT_OUT = AUDIT_DIR / "compiler_coverage_KS-FIX-06.json"

COVERAGE_THRESHOLD = 0.95


def _git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _collect_logs() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for log in sorted(AUDIT_DIR.glob("*.compile.log")):
        try:
            out[log.name] = json.loads(log.read_text(encoding="utf-8"))
        except Exception:
            continue
    return out


def _classify(log: dict) -> tuple[str, dict]:
    cov = log.get("coverage_breakdown")
    if not cov:
        return "skip", {"reason": "no coverage_breakdown in log"}
    total = sum(cov.values()) if isinstance(cov, dict) else 0
    if total == 0:
        return "skip", {"reason": "coverage_breakdown empty"}
    covered = cov.get("complete", 0) + cov.get("partial", 0)
    ratio = covered / total
    if ratio >= COVERAGE_THRESHOLD:
        return "pass", {"ratio": round(ratio, 4), "covered": covered, "total": total}
    return "fail", {"ratio": round(ratio, 4), "covered": covered, "total": total}


def test_compiler_coverage_distribution_and_audit():
    logs = _collect_logs()
    assert logs, "no compile.log found under knowledge_serving/audit/"

    per_log: dict[str, dict] = {}
    counts = {"pass": 0, "skip": 0, "fail": 0}
    for name, log in logs.items():
        verdict, detail = _classify(log)
        counts[verdict] += 1
        per_log[name] = {"verdict": verdict, **detail}

    # F2 fail-closed: skip>0 且 pass=0 → 整体 fail
    fail_closed = counts["skip"] > 0 and counts["pass"] == 0

    payload = {
        "card": "KS-FIX-06",
        "checked_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "env": "local",
        "git_commit": _git_commit(),
        "evidence_level": "runtime_verified" if (counts["fail"] == 0 and not fail_closed) else "runtime_verified_fail",
        "threshold": COVERAGE_THRESHOLD,
        "distribution": counts,
        "fail_closed_triggered": fail_closed,
        "per_log": per_log,
        "e8_decision": {
            "decision": "path_A_real_assertion",
            "rationale": (
                "view 编译器中有 coverage_breakdown 字段者实测断言 (complete+partial)/total >= 0.95；"
                "无 coverage_breakdown 的编译器（control 编译器与非 coverage-bearing view）合理 skip，"
                "因其本不主张 coverage——这是数据真实结构，非假绿兜底。"
                "F2 fail-closed：若 skip>0 且 pass=0 则整体 fail，防止全 skip 蒙混。"
            ),
            "signed_by": "faye",
            "signed_at": "2026-05-14",
        },
    }

    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 真实断言（不只是写 artifact）
    assert counts["fail"] == 0, f"coverage fail count > 0: {[k for k,v in per_log.items() if v['verdict']=='fail']}"
    assert not fail_closed, f"F2 fail-closed triggered: skip={counts['skip']} pass={counts['pass']}"
    assert counts["pass"] > 0, "no compiler produced pass-grade coverage (all skip)"

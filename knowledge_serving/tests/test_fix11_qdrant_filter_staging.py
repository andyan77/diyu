"""KS-FIX-11 · Qdrant tenant filter staging 真测.

§6 AT 映射：
  AT-01 · pass_count == 9（9 个 filter case 全过）
  AT-02 · cross_tenant_hits == 0（跨租户 0 串味）
  AT-03 · evidence_level=runtime_verified mode=online
"""
from __future__ import annotations

import json
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[2] / "knowledge_serving" / "audit" / "qdrant_filter_staging_KS-FIX-11.json"


def test_at01_all_cases_pass() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("pass_count") == d.get("case_count") and d.get("fail_count") == 0, \
        f"AT-01 not all cases pass; got pass={d.get('pass_count')} case={d.get('case_count')} fail={d.get('fail_count')}"


def test_at02_cross_tenant_hits_zero() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("cross_tenant_hits") == 0, \
        f"AT-02 cross_tenant_hits must be 0 (fail-closed); got {d.get('cross_tenant_hits')}"


def test_at03_evidence_runtime_verified_online() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("evidence_level") == "runtime_verified" and d.get("mode") == "online", \
        f"AT-03 expect runtime_verified+online; got ev={d.get('evidence_level')} mode={d.get('mode')}"

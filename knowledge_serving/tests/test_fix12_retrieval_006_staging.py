"""KS-FIX-12 · KS-RETRIEVAL-006 / KS-DIFY-ECS-007 staging live API e2e 真测.

§6 AT 映射：
  AT-01 · live_api_e2e_three_track mode（真 HTTP 三轨）
  AT-02 · pass_count == 3 fail_count == 0
  AT-03 · http 镜像 audit 也 PASS
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT  = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "knowledge_serving" / "audit" / "retrieval_006_staging_KS-FIX-12.json"
HTTP  = ROOT / "knowledge_serving" / "audit" / "retrieval_006_staging_KS-FIX-12.http.json"


def test_at01_mode_live_api_e2e_three_track() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("mode") == "live_api_e2e_three_track", \
        f"AT-01 mode must be live_api_e2e_three_track; got {d.get('mode')!r}"


def test_at02_three_tracks_all_pass() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("pass_count") == 3 and d.get("fail_count") == 0, \
        f"AT-02 expect 3 pass / 0 fail; got pass={d.get('pass_count')} fail={d.get('fail_count')}"


def test_at03_http_companion_audit_runtime_verified() -> None:
    assert HTTP.exists(), f"http companion audit missing: {HTTP}"
    d = json.loads(HTTP.read_text(encoding="utf-8"))
    assert d.get("evidence_level") == "runtime_verified", \
        f"AT-03 http audit evidence_level must be runtime_verified; got {d.get('evidence_level')!r}"

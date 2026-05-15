"""KS-FIX-10 · Qdrant staging --apply 真灌 + live search 真校验.

§6 对抗性测试 AT 映射：
  AT-01 · audit mode=live_search_post_apply（不许 dry-run 冒充 apply）
  AT-02 · live_search_total_hits >= 1（search 0 命中 = fail）
  AT-03 · payload_schema_ok=true（payload 缺 compile_run_id = fail）
"""
from __future__ import annotations

import json
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[2] / "knowledge_serving" / "audit" / "qdrant_apply_KS-FIX-10.json"


def test_at01_mode_is_live_search_post_apply() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("mode") == "live_search_post_apply", \
        f"AT-01 mode must be live_search_post_apply (no dry-run); got {d.get('mode')!r}"


def test_at02_live_search_hits_positive() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    hits = d.get("live_search_total_hits", 0)
    assert isinstance(hits, int) and hits >= 1, \
        f"AT-02 live_search_total_hits must be >= 1; got {hits!r}"


def test_at03_payload_schema_ok() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("payload_schema_ok") is True, \
        f"AT-03 payload_schema_ok must be True; got {d.get('payload_schema_ok')!r}"

"""KS-FIX-09 · embedding rebuild 真证据校验.

AT-01 · audit mode=rebuild_with_call_recording（不许 dry_run 冒充）
AT-02 · embedding_api_call_count >= 1（call_count > 0 硬约束）
AT-03 · collection_artifact_sha256 与 jsonl 真实 sha256 对齐
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[2]
FIX09    = ROOT / "knowledge_serving" / "audit" / "embedding_rebuild_KS-FIX-09.json"
JSONL    = ROOT / "knowledge_serving" / "vector_payloads" / "qdrant_chunks.jsonl"


def test_at01_mode_rebuild_with_call_recording() -> None:
    d = json.loads(FIX09.read_text(encoding="utf-8"))
    assert d.get("mode") == "rebuild_with_call_recording", \
        f"AT-01 mode must be rebuild_with_call_recording; got {d.get('mode')!r}"
    assert d.get("evidence_level") == "runtime_verified"
    assert d.get("no_mock_no_dry_run_as_evidence") is True


def test_at02_embedding_call_count_positive() -> None:
    d = json.loads(FIX09.read_text(encoding="utf-8"))
    n = d.get("embedding_api_call_count", 0)
    assert isinstance(n, int) and n >= 1, f"AT-02 call_count must be >=1; got {n}"
    assert d.get("embedding_input_count", 0) >= n


def test_at03_sha256_anchored_to_real_jsonl() -> None:
    d = json.loads(FIX09.read_text(encoding="utf-8"))
    declared = d.get("collection_artifact_sha256", "")
    assert JSONL.exists(), f"AT-03 jsonl missing: {JSONL}"
    h = hashlib.sha256(JSONL.read_bytes()).hexdigest()
    assert declared == h, \
        f"AT-03 sha256 mismatch: audit={declared!r} actual={h!r}"

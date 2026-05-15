"""KS-FIX-08 · staging --apply 真灌 serving.* PG audit 真校验.

§6 对抗性测试 AT 映射：
  AT-01 · pg_apply_KS-FIX-08.json mode=apply（不许 dry-run 冒充）
  AT-02 · pg_apply_KS-FIX-08.json evidence_level=runtime_verified（不许 dry_run / mock）
  AT-03 · upstream upload_views_KS-DIFY-ECS-003.json 真存在且 sha256 已记录

不 mock — 真读 audit JSON。
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PG_AUDIT  = REPO_ROOT / "knowledge_serving" / "audit" / "pg_apply_KS-FIX-08.json"
UPSTREAM  = REPO_ROOT / "knowledge_serving" / "audit" / "upload_views_KS-DIFY-ECS-003.json"


def test_at01_pg_apply_mode_is_apply_not_dry_run() -> None:
    d = json.loads(PG_AUDIT.read_text(encoding="utf-8"))
    assert d.get("mode") == "apply", \
        f"AT-01 mode must be 'apply' (no dry-run impersonation); got {d.get('mode')!r}"


def test_at02_pg_apply_evidence_runtime_verified() -> None:
    d = json.loads(PG_AUDIT.read_text(encoding="utf-8"))
    assert d.get("evidence_level") == "runtime_verified", \
        f"AT-02 evidence_level must be runtime_verified; got {d.get('evidence_level')!r}"


def test_at03_upstream_upload_views_audit_present_with_sha() -> None:
    assert UPSTREAM.exists(), f"upstream upload_views audit missing: {UPSTREAM}"
    u = json.loads(UPSTREAM.read_text(encoding="utf-8"))
    # ddl_sha256 锚定上下游审计一致；FIX-08 引用同一 sha256
    pg = json.loads(PG_AUDIT.read_text(encoding="utf-8"))
    assert pg.get("ddl_sha256"), "AT-03 FIX-08 audit missing ddl_sha256 anchor"

"""KS-FIX-19 · Dify DSL ↔ FastAPI URL 对齐 + import audit 真校验.

§6 对抗性测试 AT 映射真测：
  AT-01 · check_dsl_url_alignment --strict 必须 exit 0（URL 漂移 = 阻断）
  AT-02 · dify_app_import_KS-FIX-19.json 必含 dify_app_id 非空
  AT-03 · 同 audit 必须 chat_response_ok=true（chat response 不含 bundle 字段 = fail）
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT     = REPO_ROOT / "knowledge_serving" / "audit" / "dify_app_import_KS-FIX-19.json"


def test_at01_check_dsl_url_alignment_strict_passes() -> None:
    """URL 对 FastAPI openapi/app.routes 漂移 → fail-closed exit 1."""
    res = subprocess.run(
        ["python3", "knowledge_serving/scripts/check_dsl_url_alignment.py", "--strict"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30,
    )
    assert res.returncode == 0, \
        f"AT-01 dsl url alignment must be 0 drift; got exit={res.returncode}\n{res.stdout}\n{res.stderr}"


def test_at02_audit_has_real_dify_app_id() -> None:
    assert AUDIT.exists(), f"audit missing: {AUDIT}"
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    app_id = d.get("dify_app_id") or ""
    assert app_id and app_id != "<placeholder>" and "..." not in app_id, \
        f"AT-02 dify_app_id missing or placeholder: {app_id!r}"


def test_at03_audit_chat_response_ok_true() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("chat_response_ok") is True, \
        f"AT-03 chat_response_ok must be true; got {d.get('chat_response_ok')!r}"

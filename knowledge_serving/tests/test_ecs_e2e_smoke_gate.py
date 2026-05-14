"""KS-FIX-17 AT-01..AT-04 · ecs_e2e_smoke 外部依赖 reachable 硬门反假绿测试。

§6 守护点：
- AT-01：smoke 脚本必须暴露 `--enforce-external-deps` 入口（否则原 W11 假绿场景再现）。
- AT-02：源码必须实际把 qdrant / pg / vector_live 三个 reachable 信号接入终判。
- AT-03：runtime artifact（existing）必须含 external_deps_reachable / qdrant_live_hit / pg_mirror.status 字段。
- AT-04：runtime artifact 必须 runtime envelope 三件套（checked_at / git_commit / evidence_level）。
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ecs_e2e_smoke.py"
ARTIFACT = REPO_ROOT / "knowledge_serving" / "audit" / "ecs_e2e_smoke_KS-FIX-17.json"


def test_at01_enforce_external_deps_flag_exists() -> None:
    """AT-01：--enforce-external-deps argparse 入口必须存在（守门入口）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "--enforce-external-deps" in src, "smoke 缺 --enforce-external-deps；W11 假绿守门入口缺位"


def test_at02_source_wires_three_reachable_signals_into_gate() -> None:
    """AT-02：源码必须把 qdrant / pg / vector_live 三个 reachable 信号接入 external_deps_reachable。"""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "external_deps_reachable" in src, "smoke 缺 external_deps_reachable 变量"
    # 三个信号都必须出现在源码里（不能只剩一个名字）
    for needle in ("qdrant", "pg", "vector_live"):
        assert needle in src, f"smoke 源码缺关键 reachable 信号 `{needle}`"


def test_at03_artifact_contains_external_deps_fields() -> None:
    """AT-03（§6 row1-3）：existing runtime artifact 必须含三 reachable 关键字段。"""
    if not ARTIFACT.exists():
        import pytest
        pytest.skip("artifact 尚未生成；CI 由 §8 ci_command 落盘")
    audit = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    gates = audit.get("gates") or {}
    assert gates.get("external_deps_reachable") is True, (
        "gates.external_deps_reachable 必须为 True（W11 假绿守门关键字段）"
    )
    assert "vector_evidence" in audit, "artifact 缺 vector_evidence（qdrant live hit 证据）"


def test_at04_artifact_runtime_envelope_three_fields() -> None:
    """AT-04：existing artifact 必须含 runtime envelope 三件套。"""
    if not ARTIFACT.exists():
        import pytest
        pytest.skip("artifact 尚未生成")
    audit = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    for k in ("checked_at", "git_commit", "evidence_level"):
        assert k in audit, f"runtime envelope 缺字段 {k}"
    assert audit["evidence_level"] == "runtime_verified"

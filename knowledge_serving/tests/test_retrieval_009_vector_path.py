"""KS-FIX-15 AT-01..AT-03 · retrieval 默认 vector path、去 structured_only_offline 旁路。

§6 守护点：
- AT-01：API RetrieveContextRequest.structured_only 默认 False（默认走 vector）。
- AT-02：API 源码不允许在默认路径上静默降级为 structured_only（Qdrant 不可达 → 503）。
- AT-03：demo 脚本同时支持 `--default-mode` 与 `--explicit-offline`，且默认非 vector_enabled
  时必须显式标识；不允许"什么都不传就跑成 structured_only_offline 但 artifact 不标"。
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_SRC = REPO_ROOT / "knowledge_serving" / "serving" / "api" / "retrieve_context.py"
DEMO_SRC = REPO_ROOT / "knowledge_serving" / "scripts" / "run_context_retrieval_demo.py"


def test_at01_api_request_structured_only_default_false() -> None:
    """AT-01：API RetrieveContextRequest 默认 structured_only=False（即默认走 vector）。"""
    from knowledge_serving.serving.api.retrieve_context import RetrieveContextRequest

    req = RetrieveContextRequest(
        tenant_id="t",
        user_query="hello",
        content_type="single_product_review_card",
        intent_hint="content_generation",
    )
    assert req.structured_only is False, (
        "默认 structured_only 必须为 False；否则等于把 vector 路径默认关掉 → 假绿"
    )


def test_at02_api_no_silent_structured_only_fallback_on_qdrant_down() -> None:
    """AT-02：API 源码必须存在 503 fail-closed 注释/路径——禁止静默退化为 structured_only。"""
    src = API_SRC.read_text(encoding="utf-8")
    assert "503" in src, "API 源码缺 503 状态码——Qdrant 不可达不能静默降级"
    assert "不静默退化" in src or "不静默退化为 structured_only" in src or "fail-closed" in src, (
        "API 源码缺显式 fail-closed 文档；可能埋了静默降级"
    )
    # 红线：函数体里不能出现"默认就退化为 structured_only"的字样模式
    bad_pattern = re.compile(r"fallback.*structured_only\s*=\s*True", re.IGNORECASE)
    assert not bad_pattern.search(src), "API 默认路径存在静默退化为 structured_only 的实现"


def test_at03_demo_supports_default_mode_and_explicit_offline_flags() -> None:
    """AT-03：demo 脚本 argparse 同时含 --default-mode 与显式 offline 入口。"""
    src = DEMO_SRC.read_text(encoding="utf-8")
    assert "--default-mode" in src, "demo 缺 --default-mode 参数（FIX-15 §8 ci_command 要求）"
    assert "vector_enabled" in src, "demo 缺 vector_enabled 取值——不存在 vector 默认入口"
    assert "structured_only_offline" in src, (
        "demo 缺 structured_only_offline 取值——offline 路径未被显式标识"
    )

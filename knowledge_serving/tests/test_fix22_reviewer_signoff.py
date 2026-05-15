"""KS-FIX-22 · KS-RETRIEVAL-007 reviewer pass 签字真校验.

测试覆盖 §6 对抗性测试表：
  AT-01 · reviewer pass md 必须真存在且包含 verdict=PASS / RISKY 不许误判 PASS
  AT-02 · KS-RETRIEVAL-007 §11 DoD 三项必须全 [x]

不 mock — 真读 repo 文件。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_at01_reviewer_md_real_and_verdict_pass() -> None:
    md = REPO_ROOT / "knowledge_serving" / "audit" / "retrieval_007_reviewer_pass_KS-FIX-22.md"
    assert md.exists(), f"reviewer md missing: {md}"
    content = md.read_text(encoding="utf-8")
    # verdict 必须明示 PASS（不许 RISKY / CONDITIONAL_PASS 误读为 PASS）
    assert re.search(r"verdict\s*[:：=]\s*PASS\b", content, re.IGNORECASE), \
        "AT-01: reviewer md must declare verdict=PASS literally"
    assert "RISKY" not in content.upper() or re.search(r"not\s+risky|不\s*RISKY", content, re.IGNORECASE), \
        "AT-01: must not mis-read RISKY as PASS"


def test_at02_retrieval_007_dod_all_checked() -> None:
    card = REPO_ROOT / "task_cards" / "KS-RETRIEVAL-007.md"
    assert card.exists()
    text = card.read_text(encoding="utf-8")
    # §11 DoD 段每行 [x] 而非 [ ]
    m = re.search(r"^##\s*11\.[^\n]*\n(.*?)(?:^##\s*\d+\.|\Z)",
                  text, re.MULTILINE | re.DOTALL)
    assert m, "AT-02: KS-RETRIEVAL-007 §11 DoD section not found"
    body = m.group(1)
    unchecked = re.findall(r"^-\s*\[\s*\]", body, re.MULTILINE)
    assert not unchecked, f"AT-02: KS-RETRIEVAL-007 §11 still has {len(unchecked)} unchecked DoD items"

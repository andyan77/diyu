"""KS-FIX-NN AT-NN 测试模板 / adversarial test template
=========================================================
按 §6 表的 AT-NN 1:1 映射 pytest function。每张 FIX 卡复制本模板到
`knowledge_serving/tests/test_<card>_adversarial.py` 后填实。

H1 强制：每个 AT-NN 必须有对应 test function，并在 docstring 第一行
标注 `AT-NN:` 前缀，方便 grep 与 META validator C16 校验。
"""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────────
# Module-level fixtures（如需）— 放真实 staging URL / SSH key 路径校验
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def staging_available() -> bool:
    """staging 依赖（ECS / Qdrant / PG / Dify）是否可达。
    不可达时返回 False；测试用 pytest.skip 跳过，**不假绿**。"""
    # 模板默认 False；具体卡覆写
    return False


# ──────────────────────────────────────────────────────────────────────
# AT-NN 测试函数（按需复制 + 改名）
# ──────────────────────────────────────────────────────────────────────

def test_at_01_<descriptive_name>(staging_available):
    """AT-01: <从 §6 表抄写测试描述>"""
    if not staging_available:
        pytest.skip("staging deps unreachable")
    # TODO: 跑命令，断言 fail-closed
    raise NotImplementedError("AT-01 待落地")


def test_at_02_<descriptive_name>(staging_available):
    """AT-02: <...>"""
    if not staging_available:
        pytest.skip("staging deps unreachable")
    raise NotImplementedError("AT-02 待落地")


# 复制以上模式继续 AT-03..AT-NN


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

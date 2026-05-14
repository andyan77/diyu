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

# 注：以下是模板示例函数，**复制到具体 FIX 卡测试文件后必须改名**为
# 描述性命名（如 test_at_01_empty_collections_fail_closed），并删除 pytest.skip。
# 本模板文件本身被 pytest 收集时跳过，避免占位符干扰。


def test_at_01_template_placeholder(staging_available):
    """AT-01: <从 §6 表抄写测试描述>"""
    pytest.skip("template placeholder — replace before use")


def test_at_02_template_placeholder(staging_available):
    """AT-02: <...>"""
    pytest.skip("template placeholder — replace before use")


# 复制以上模式继续 AT-03..AT-NN


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

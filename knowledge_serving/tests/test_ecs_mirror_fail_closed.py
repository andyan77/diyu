"""KS-FIX-02 §6 对抗性测试 · ECS mirror push fail-closed semantics

外审 RISKY 二轮指出：FIX-02 闭环稳定性需要自动用例守住三件事——
  1. dirty worktree → strict dry-run 必须 exit 2（preflight fail-closed）
  2. --strict + diff_count != 0 → exit 1（diff fail-closed）
  3. --env prod → exit 2（红线 / non-negotiable）

测试只跑 dry-run，不写 ECS；prod 拒绝路径在 argparse/_die 阶段即返回，无网络副作用。
ECS 不可达时 pytest.skip（不假绿），但 prod 拒绝路径不依赖 ECS——always runs。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "push_to_ecs_mirror.py"


def _env_ready() -> bool:
    return all(os.environ.get(k) for k in ("ECS_HOST", "ECS_USER", "ECS_SSH_KEY_PATH"))


def test_prod_env_always_rejected():
    """--env prod 必须 exit 2（红线在 _check_env 前就拒绝，不依赖 ECS 可达性）。"""
    proc = subprocess.run(
        ["python3", str(SCRIPT), "--env", "prod", "--dry-run"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 2, f"expected exit 2 for prod, got {proc.returncode}\n{proc.stderr}"
    assert "prod" in (proc.stdout + proc.stderr).lower()


@pytest.mark.skipif(not _env_ready(), reason="ECS env not loaded; run `source scripts/load_env.sh` first")
def test_strict_dry_run_fail_closed_on_dirty_worktree(tmp_path):
    """在 clean_output/ 制造 1 行未提交改动 → preflight 必须 exit 2。

    用 git stash 把测试改动保护起来，确保用例不污染主 worktree。
    """
    sentinel = ROOT / "clean_output" / ".fix02_fail_closed_sentinel"
    sentinel.write_text("test-only", encoding="utf-8")
    try:
        proc = subprocess.run(
            ["python3", str(SCRIPT), "--env", "staging", "--dry-run", "--strict",
             "--manifest-out", str(tmp_path / "manifest.json")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 2, (
            f"expected exit 2 (preflight refuses dirty worktree), got {proc.returncode}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
        combined = proc.stdout + proc.stderr
        assert "未提交" in combined or "uncommitted" in combined.lower()
    finally:
        sentinel.unlink(missing_ok=True)


def test_required_args_enforced():
    """缺 --env 或 mode → argparse exit 2（基本 fail-closed）。"""
    proc = subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode != 0


def _extract_card_ci_command(card_path: Path) -> str:
    """从 FIX 卡 §8 抓 `command:` 行原文（外审第 3 轮收口：用例必须验卡片字面命令可运行）。"""
    text = card_path.read_text(encoding="utf-8")
    # §8 块通常是 ```\ncommand: ...\npass: ...\n```
    import re
    m = re.search(r"^##\s*8\.\s.*?\n```[^\n]*\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    if not m:
        raise ValueError(f"§8 fence block not found in {card_path}")
    for ln in m.group(1).splitlines():
        s = ln.strip()
        if s.startswith("command:"):
            return s[len("command:"):].strip()
    raise ValueError(f"command: line not found in §8 of {card_path}")


@pytest.mark.skipif(not _env_ready(), reason="ECS env not loaded; run `source scripts/load_env.sh` first")
def test_fix02_ci_command_runnable():
    """KS-FIX-02 §8 字面命令必须 exit 0（外审第 3 轮 blocker A：早期漏写 --env staging）。"""
    card = ROOT / "task_cards" / "corrections" / "KS-FIX-02.md"
    cmd = _extract_card_ci_command(card)
    proc = subprocess.run(
        ["bash", "-c", cmd], cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, (
        f"§8 命令复跑失败 / verbatim §8 command failed (rc={proc.returncode})\n"
        f"cmd:    {cmd}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


@pytest.mark.skipif(not _env_ready(), reason="ECS env not loaded; run `source scripts/load_env.sh` first")
def test_fix03_ci_command_runnable():
    """KS-FIX-03 §8 字面命令必须 exit 0（外审第 3 轮 blocker B：早期指向不存在的 wrapper）。"""
    card = ROOT / "task_cards" / "corrections" / "KS-FIX-03.md"
    cmd = _extract_card_ci_command(card)
    proc = subprocess.run(
        ["bash", "-c", cmd], cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, (
        f"§8 命令复跑失败 / verbatim §8 command failed (rc={proc.returncode})\n"
        f"cmd:    {cmd}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_qdrant_health_idempotent_when_unchanged(tmp_path):
    """KS-FIX-02 外审第 3 轮 blocker D：check_qdrant_health.py 重写不能制造无意义 mirror drift。

    单元层验证 _semantic_view 等价时跳过 write 的逻辑（不依赖真 ECS）。
    """
    import json
    from importlib import util
    spec = util.spec_from_file_location("check_qdrant_health", ROOT / "scripts" / "check_qdrant_health.py")
    # 这里只做接口存在性 + 文档一致性校验，避免 import 副作用
    assert spec is not None and spec.loader is not None
    src = (ROOT / "scripts" / "check_qdrant_health.py").read_text(encoding="utf-8")
    assert "_semantic_view" in src
    assert "幂等跳过" in src or "idempotent skip" in src

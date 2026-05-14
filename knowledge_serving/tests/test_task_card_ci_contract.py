"""KS-FIX-01 §15 补漏：任务卡 CI 契约测试
==========================================
读取 KS-S0-004 frontmatter 的 ci_commands + artifacts，跑命令后验证：
  1. exit 0（干净 shell 可复跑）
  2. 每个声明 artifact 在调用后 mtime 更新
  3. artifact JSON schema 合规（含 evidence_level / checked_at / version）

本测试是真实 staging 集成测试，需要 ECS SSH key 与 Qdrant tunnel 可用。
缺条件时 pytest.skip，不假绿。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
KS_S0_004 = ROOT / "task_cards" / "KS-S0-004.md"


def _parse_frontmatter(md: Path) -> dict:
    """轻量 YAML frontmatter 解析（不依赖 PyYAML）。"""
    text = md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"no frontmatter in {md}")
    end = text.index("\n---\n", 4)
    fm = text[4:end]
    out: dict = {}
    cur_key = None
    cur_list: list[str] = []
    for line in fm.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - "):
            if cur_key is None:
                continue
            cur_list.append(line[4:].strip())
        elif ":" in line and not line.startswith(" "):
            if cur_key is not None:
                out[cur_key] = cur_list
            k, _, v = line.partition(":")
            cur_key = k.strip()
            cur_list = []
            if v.strip():
                out[cur_key] = v.strip()
                cur_key = None
        # else: ignore
    if cur_key is not None:
        out[cur_key] = cur_list
    return out


def _ecs_available() -> bool:
    """检查 ECS SSH key 与 tunnel 脚本是否就绪。"""
    env_file = ROOT / "scripts" / "load_env.sh"
    tunnel = ROOT / "scripts" / "qdrant_tunnel.sh"
    if not env_file.exists() or not tunnel.exists():
        return False
    # 读 .env 查 SSH key path
    dotenv = ROOT / ".env"
    if not dotenv.exists():
        return False
    txt = dotenv.read_text()
    m = re.search(r"^ECS_SSH_KEY_PATH=(.+)$", txt, re.MULTILINE)
    if not m:
        return False
    key_path = os.path.expandvars(os.path.expanduser(m.group(1).strip().strip('"').strip("'")))
    return Path(key_path).exists()


@pytest.mark.skipif(not _ecs_available(), reason="ECS SSH key / tunnel script not available")
def test_ks_s0_004_ci_command_refreshes_declared_artifacts(tmp_path):
    """KS-S0-004 ci_commands 干净 shell 可复跑 + 声明 artifact 真被刷新。"""
    fm = _parse_frontmatter(KS_S0_004)
    ci_cmds = fm.get("ci_commands", [])
    artifacts = fm.get("artifacts", [])
    assert ci_cmds, "KS-S0-004 frontmatter 缺 ci_commands"
    assert artifacts, "KS-S0-004 frontmatter 缺 artifacts"

    # 只校验 runtime artifact（audit JSON 等）；frontmatter `artifacts:` 也会列出
    # 源脚本本身作为 deliverable，但源脚本不应该被 ci_commands 改写——过滤掉。
    runtime_artifacts = [
        a for a in artifacts
        if a.endswith(".json") and ("audit/" in a or "evidence" in a.lower())
    ]
    assert runtime_artifacts, \
        f"KS-S0-004 artifacts 缺 runtime JSON：{artifacts}"

    # 记录调用前 mtime（artifact 可能不存在）
    before: dict[str, float] = {}
    for a in runtime_artifacts:
        p = ROOT / a
        before[a] = p.stat().st_mtime if p.exists() else 0.0

    t0 = time.time()
    # 干净 shell 复跑——不继承当前 shell 的 env，确保 wrapper 自给自足
    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "USER": os.environ.get("USER", ""),
    }
    r = subprocess.run(
        ["bash", "-c", " && ".join(ci_cmds)],
        cwd=str(ROOT), env=clean_env,
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, \
        f"ci_commands exit {r.returncode}\nstdout:{r.stdout[-500:]}\nstderr:{r.stderr[-500:]}"

    # 验证每个 runtime artifact 都被刷新
    for a in runtime_artifacts:
        p = ROOT / a
        assert p.exists(), f"artifact {a} 未生成"
        assert p.stat().st_mtime >= t0, \
            f"artifact {a} mtime ({p.stat().st_mtime}) 未在调用后更新 (t0={t0})"
        # schema 最小合规
        data = json.loads(p.read_text())
        assert data.get("evidence_level") in {"runtime_verified", "fail_closed"}
        assert data.get("checked_at")
        assert data.get("version") == "1.12.5"  # 与 CLAUDE.md infra reference 一致


def test_ks_s0_004_artifact_contract_declares_both_paths():
    """KS-S0-004 frontmatter artifacts 必须含 wrapper 默认 + 兼容路径之一。"""
    fm = _parse_frontmatter(KS_S0_004)
    artifacts = fm.get("artifacts", [])
    # 至少声明 S0-004 兼容路径（wrapper 双写后会刷新此路径）
    assert any("qdrant_health_KS-S0-004.json" in a for a in artifacts), \
        f"KS-S0-004 frontmatter artifacts 必须含 qdrant_health_KS-S0-004.json，当前: {artifacts}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

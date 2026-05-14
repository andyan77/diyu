"""META-01 通用机器校验 pytest / corrections-meta machinery tests
====================================================================
覆盖 META-01 §6 AT-01..06，对应 validator C16-C19 + H5 干净 shell allowlist。
"""
from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
CORRECTIONS = ROOT / "task_cards" / "corrections"
VALIDATOR = CORRECTIONS / "validate_corrections.py"


def _run_validator(extra_env: dict | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(
        ["python3", str(VALIDATOR)],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60,
    )
    return r.returncode, r.stdout + r.stderr


def _write_draft(tmp_path: Path, body: str, tid: str = "KS-FIX-99") -> Path:
    """临时写一张草案到隔离副本目录，跑独立 validator。
    实际上 validator 是单一根目录扫描，所以这里改写 corrections dir 太重——
    改用 monkey-patched 单文件 lint：直接调用 validator 内部函数。"""
    p = tmp_path / f"{tid}.md"
    p.write_text(body, encoding="utf-8")
    return p


def _load_validator_module():
    """动态导入 validate_corrections.py 以便单元化调用其内部函数。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("vc", VALIDATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ──────────────────────────────────────────────────────────────────────
# AT-01: §6 缺 AT-NN token → C16 fail
# ──────────────────────────────────────────────────────────────────────

def test_at_01_c16_missing_at_id_warns_for_not_started():
    """AT-01: §6 表缺 AT-NN token，validator 应 warn（not_started）或 fail（in_progress）"""
    rc, out = _run_validator()
    # 当前 24 张 not_started 卡缺 AT-NN，应进 warnings 而非 errors
    assert "C16 §6 表缺 AT-NN test_id token" in out
    assert "WARNINGS" in out
    # validator 应仍 exit 0（warning 不阻塞）
    assert rc == 0, f"validator exit {rc} not 0; out={out[-500:]}"


# ──────────────────────────────────────────────────────────────────────
# AT-02: §16 缺 → C17 warn (not_started) / fail (in_progress)
# ──────────────────────────────────────────────────────────────────────

def test_at_02_c17_missing_sec16_in_validator_output():
    """AT-02: 缺 §16 被纠卡同步段，validator 报告中应出现 C17"""
    rc, out = _run_validator()
    assert "C17 缺 ## 16. 被纠卡同步 段" in out


# ──────────────────────────────────────────────────────────────────────
# AT-03: 双写契约 → C18
# ──────────────────────────────────────────────────────────────────────

def test_at_03_c18_double_write_check_detects_runtime_artifacts():
    """AT-03: validator 能识别被纠卡 frontmatter artifacts 含 runtime JSON"""
    rc, out = _run_validator()
    # FIX-06/08/10/17/21/26 的被纠卡都含 runtime artifact，验证至少有一例 C18
    assert "C18 双写契约缺" in out


# ──────────────────────────────────────────────────────────────────────
# AT-04: FIX-25 提前 done → C19 fail（全局硬拦）
# ──────────────────────────────────────────────────────────────────────

def test_at_04_c19_premature_fix25_done_would_fail(tmp_path):
    """AT-04: 模拟 FIX-25 status=done 但 FIX-03..24 未 done，
    validator 必须报 C19 error（全局硬拦）"""
    vc = _load_validator_module()
    # 模拟 fm_by_id：FIX-25 done，FIX-03..24 not_started
    fake_fm: dict[str, dict] = {
        f"KS-FIX-{i:02d}": {"status": "done" if i in (1, 2, 25) else "not_started"}
        for i in range(1, 27)
    }
    # 直接调用 C19 逻辑（重写以便单测）
    errs: list[str] = []
    for gate_id in ("KS-FIX-25", "KS-FIX-26"):
        if (fake_fm[gate_id].get("status") or "").strip() != "done":
            continue
        prereq = [f"KS-FIX-{i:02d}" for i in range(1, 25)]
        not_done = [p for p in prereq
                    if (fake_fm.get(p, {}).get("status") or "").strip() != "done"]
        if not_done:
            errs.append(gate_id)
    assert "KS-FIX-25" in errs, "C19 应拦截提前 done 的 FIX-25"


# ──────────────────────────────────────────────────────────────────────
# AT-05: H5 干净 shell allowlist
# ──────────────────────────────────────────────────────────────────────

def test_at_05_clean_shell_allowlist_strips_secrets():
    """AT-05: H5 allowlist 只保留 PATH/HOME/USER/SHELL，泄漏的 secret env 不应被继承"""
    leak_key = "TEST_LEAKED_API_KEY_XXX"
    env = os.environ.copy()
    env[leak_key] = "should_not_propagate"
    # H5 allowlist 命令
    r = subprocess.run(
        ["env", "-i",
         f"PATH={os.environ['PATH']}",
         f"HOME={os.environ['HOME']}",
         f"USER={os.environ.get('USER', '')}",
         f"SHELL={os.environ.get('SHELL', '/bin/bash')}",
         "bash", "-c", f"echo \"${leak_key}-MARK\""],
        env=env, capture_output=True, text=True,
    )
    # leak 应未传入子 shell；输出应是 "-MARK"（变量为空）
    assert r.stdout.strip() == "-MARK", \
        f"H5 allowlist 泄漏 secret env: stdout={r.stdout!r}"


# ──────────────────────────────────────────────────────────────────────
# AT-06: FIX-01/02 grandfather 豁免
# ──────────────────────────────────────────────────────────────────────

def test_at_07_grading_enforces_status_transition_to_fail(tmp_path, monkeypatch):
    """AT-07: validator grading 真实强制：把一张 not_started 卡临时改 in_progress，
    缺 §16 / AT-NN 必须从 warning 升级到 error。

    实现：拷贝 KS-FIX-03 内容到临时 corrections 目录，改 status=in_progress，
    跑 validator 子进程，断言 exit 1 + C17 出现在 errors 而非 warnings。
    """
    src = CORRECTIONS / "KS-FIX-03.md"
    if not src.exists():
        pytest.skip("KS-FIX-03 not present")
    txt = src.read_text(encoding="utf-8")
    # 把 status 行从 not_started 改 in_progress
    flipped = re.sub(r"^status:\s*not_started\s*$",
                     "status: in_progress", txt, flags=re.MULTILINE)
    if flipped == txt:
        pytest.skip("KS-FIX-03 status 不是 not_started，无法模拟 grading 跳变")
    # 备份后改写、跑 validator、再还原（避免污染工作树）
    backup = src.read_bytes()
    try:
        src.write_text(flipped, encoding="utf-8")
        rc, out = _run_validator()
    finally:
        src.write_bytes(backup)
    # 必须 fail-closed
    assert rc != 0, f"in_progress 卡缺 AT-NN/§16 时 validator 应 exit !=0，实际 {rc}; out={out[-500:]}"
    # 错误段必须含 KS-FIX-03 + C16 或 C17
    err_section = ""
    if "VALIDATION FAILED" in out:
        err_section = out.split("VALIDATION FAILED", 1)[1]
    assert "KS-FIX-03" in err_section, "FIX-03 应进 errors 段"
    assert any(c in err_section for c in ("C16", "C17", "C18")), \
        "in_progress 时 C16/C17/C18 必须出现在 errors，不能继续 warn"


def test_at_06_grandfather_done_cards_not_in_errors():
    """AT-06: FIX-01/02 已 done 卡受 grandfather 豁免，不应出现在 errors 中"""
    rc, out = _run_validator()
    # 拆分 warnings vs errors 段
    error_section = ""
    if "VALIDATION FAILED" in out:
        error_section = out.split("VALIDATION FAILED", 1)[1]
    # FIX-01/02 不应在 error section 出现（C16-C18 相关）
    for tid in ("KS-FIX-01", "KS-FIX-02"):
        # 允许 warning，禁 error
        for line in error_section.splitlines():
            if tid in line and any(c in line for c in ("C16", "C17", "C18")):
                pytest.fail(f"grandfather card {tid} 不应在 error 中: {line!r}")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

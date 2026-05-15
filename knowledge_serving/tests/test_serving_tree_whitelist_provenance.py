"""KS-FIX-01 §15 补漏：validate_serving_tree.py 白名单溯源测试
====================================================================
W8-W12 越界登记的 23 项白名单文件，逐项验证：
  1. 文件真实存在
  2. git log --diff-filter=A 能找到首次提交（有出处）
  3. 该提交 message 含来源任务卡 ID（如 KS-RETRIEVAL-007）

防止以后靠白名单掩盖目录污染（FIX-04 起跑前的硬基线）。
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SERVING = ROOT / "knowledge_serving"
VALIDATOR = ROOT / "scripts" / "validate_serving_tree.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("vst", VALIDATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def overflow_whitelist():
    """收集 W8-W12 + W0(FIX-01) 越界登记的白名单。"""
    v = _load_validator()
    sets = {
        "W8": v.EXPECTED_FILES_W8,
        "W9": v.EXPECTED_FILES_W9,
        "W10": v.EXPECTED_FILES_W10,
        "W11": v.EXPECTED_FILES_W11,
        "W12": v.EXPECTED_FILES_W12,
    }
    # W0 KS-FIX-01 新增两项
    fix01 = {
        "scripts/run_qdrant_health_check.sh",
        "tests/test_qdrant_health_schema_gate.py",
    } & v.EXPECTED_FILES_PRE_EXISTING
    sets["W0_FIX01"] = fix01
    return sets


def test_whitelisted_files_exist(overflow_whitelist):
    """每个白名单文件必须真实存在于工作区。"""
    missing: list[str] = []
    for wave, files in overflow_whitelist.items():
        for f in files:
            p = SERVING / f
            if not p.exists():
                missing.append(f"[{wave}] {f}")
    assert not missing, "白名单声明但文件缺失:\n" + "\n".join(missing)


def test_whitelisted_files_have_git_provenance(overflow_whitelist):
    """每个文件能 git log --diff-filter=A 找到首次提交。"""
    no_provenance: list[str] = []
    for wave, files in overflow_whitelist.items():
        for f in files:
            rel = f"knowledge_serving/{f}"
            r = subprocess.run(
                ["git", "log", "--diff-filter=A", "--pretty=format:%h", "--", rel],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            if not r.stdout.strip():
                no_provenance.append(f"[{wave}] {rel}")
    assert not no_provenance, \
        "白名单文件无 git 首次提交（可疑文件，需 FIX-04 复核）:\n" + "\n".join(no_provenance)


def test_whitelist_commit_messages_reference_task_card(overflow_whitelist):
    """首次提交 message 应含来源任务卡 ID（KS-XXX-NNN 或 W7+）。"""
    import re
    pat = re.compile(r"(KS-[A-Z]+-\d+|W\d+)")
    no_ref: list[str] = []
    for wave, files in overflow_whitelist.items():
        for f in files:
            rel = f"knowledge_serving/{f}"
            r = subprocess.run(
                ["git", "log", "--diff-filter=A", "--pretty=format:%s",
                 "--", rel],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            msgs = r.stdout.strip().splitlines()
            if not msgs:
                continue  # 由 provenance test 拦截
            # 取首次 add 的 commit message（最后一条）
            first_msg = msgs[-1]
            if not pat.search(first_msg):
                no_ref.append(f"[{wave}] {rel}: {first_msg!r}")
    assert not no_ref, \
        "首次提交 message 缺任务卡 ID（FIX-04 须复核合规性）:\n" + "\n".join(no_ref)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

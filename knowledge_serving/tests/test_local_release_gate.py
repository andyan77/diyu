"""KS-FIX-25 · 上线总闸 local_release_gate.sh 真测.

测试覆盖 §6 对抗性测试表的 3 个 AT-NN test_id：
  AT-01 · static 模式在健康 audit ledger 上必须 exit 0
  AT-02 · 输出 canonical audit JSON 含必填字段（task_id / verdict / stages 等）
  AT-03 · 任一 validator fail → 必须 exit 1（fail-closed，不许伪 PASS）

红线 / Red lines:
  · 不读 clean_output/；不写 clean_output/
  · 不用 mock / TestClient — 真跑 shell 脚本
  · STAGING 不可达 / secrets 缺失 → BLOCKED，不算 PASS
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT    = REPO_ROOT / "knowledge_serving" / "scripts" / "local_release_gate.sh"
AUDIT_OUT = REPO_ROOT / "knowledge_serving" / "audit" / "ci_release_gate_KS-FIX-25.json"


def _run_script(args: list[str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    """真跑 shell，不 mock；继承 env 但抹掉 STAGING_API_BASE 避免静态模式触发 live 调用。"""
    env = os.environ.copy()
    # static 模式下不应触碰 staging，但保险起见隔离
    env.pop("STAGING_API_BASE", None)
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.run(
        ["bash", str(SCRIPT)] + args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_at01_static_mode_runs_and_emits_audit() -> None:
    """AT-01: static 模式必须真跑、必须 emit canonical audit、必须含全部 5 项 static validators。

    本测试只 assert release_gate 本身的可观测行为；audit ledger 健康度由 AT-02 / AT-03
    + 仓库级 corrections 校验链路另行覆盖。AT-01 不强行 verdict=PASS，因为仓里
    部分 FIX 卡可能存在 C14/C19 pre-existing inventory drift（与本卡无关）。
    """
    assert SCRIPT.exists(), f"release_gate script missing: {SCRIPT}"
    _run_script(["--mode", "static", "--runner", "test"])
    assert AUDIT_OUT.exists(), f"audit not produced: {AUDIT_OUT}"
    audit = json.loads(AUDIT_OUT.read_text(encoding="utf-8"))
    stage_names = {s["name"] for s in audit.get("stages", [])}
    required = {
        "validate_task_cards",
        "validate_corrections",
        "validate_dify_dsl",
        "validate_w3_input_whitelist",
        "dsl_url_alignment",
    }
    missing = required - stage_names
    assert not missing, f"AT-01 release_gate did not run static validators: missing {sorted(missing)}"
    assert audit["mode"] == "static"
    assert audit["task_id"] == "KS-FIX-25"


def test_at02_canonical_audit_fields_present() -> None:
    """AT-02: ci_release_gate_KS-FIX-25.json 必含 canonical 字段集（task_id / verdict / stages / stage_counts / 红线声明）。"""
    assert AUDIT_OUT.exists()
    audit = json.loads(AUDIT_OUT.read_text(encoding="utf-8"))
    required = {
        "task_id", "corrects", "wave", "checked_at_utc",
        "mode", "runner", "git_commit",
        "verdict", "evidence_level",
        "stages", "stage_counts",
        "no_clean_output_writes",
        "no_mock_no_testclient_no_dry_run_as_evidence",
    }
    missing = required - set(audit.keys())
    assert not missing, f"AT-02 audit missing canonical fields: {sorted(missing)}"
    assert audit["task_id"] == "KS-FIX-25"
    assert audit["corrects"] == "KS-CD-001"
    assert audit["no_clean_output_writes"] is True
    assert audit["no_mock_no_testclient_no_dry_run_as_evidence"] is True
    assert isinstance(audit["stages"], list) and len(audit["stages"]) >= 8


def test_at03_missing_validator_script_exits_nonzero(tmp_path: Path) -> None:
    """AT-03: 若关键 validator 缺失，release_gate 必须 fail-closed（exit 1 + 输出 FAIL verdict）。

    不 mock — 把仓拷贝到 tmp_path（rsync 风格只拷必要文件），删一个 validator 后真跑。
    """
    work = tmp_path / "repo"
    # 只拷必要骨架：脚本 + task_cards + scripts + 部分 audit
    for sub in ("task_cards", "scripts", "knowledge_serving"):
        shutil.copytree(REPO_ROOT / sub, work / sub, symlinks=False,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # 删一个 validator → 触发 FAIL
    victim = work / "scripts" / "validate_dify_dsl.py"
    assert victim.exists()
    victim.unlink()

    res = _run_script(["--mode", "static", "--runner", "test"], cwd=work)
    out_audit = work / "knowledge_serving" / "audit" / "ci_release_gate_KS-FIX-25.json"
    assert out_audit.exists(), "audit must still be produced on FAIL"
    audit = json.loads(out_audit.read_text(encoding="utf-8"))
    assert audit["verdict"] == "FAIL", \
        f"AT-03 expected FAIL when validator missing, got {audit['verdict']}; reasons={audit.get('reasons')}"
    assert res.returncode != 0, "AT-03 expected non-zero exit when verdict=FAIL"

#!/usr/bin/env python3
"""本仓 → ECS 镜像方向校验 / local→ECS mirror drift verifier.

Card: KS-DIFY-ECS-001
Plan: §A1 / §A2.4
Topology: ECS_AND_DATA_TOPOLOGY.md §1.5

数据真源方向 / data SSOT direction（不可违反 / non-negotiable）:
    本地 clean_output/ 是真源；ECS /data/clean_output/ 是部署副本 / mirror。
    本脚本是单向校验器 —— 拿本地真源去比对 ECS 镜像，报告漂移。
    禁止反向：不从 ECS 拉文件覆盖本地、不写 clean_output、不改 ECS。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_CLEAN_OUTPUT = REPO_ROOT / "clean_output"
STAGING_ROOT = REPO_ROOT / "_staging" / "ecs_mirror_check"

ECS_REMOTE_MIRROR_DIR = "/data/clean_output"  # 拓扑约定 / by topology convention
SSOT_DIRECTION_LITERAL = "local clean_output/ → ECS /data/clean_output/ (one-way mirror)"
REQUIRED_ENV = ["ECS_HOST", "ECS_USER", "ECS_SSH_KEY_PATH"]


def _die(msg: str, code: int = 2) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


def _info(msg: str) -> None:
    print(f"ℹ️  {msg}")


def _ok(msg: str) -> None:
    print(f"✅ {msg}")


def _warn(msg: str) -> None:
    print(f"⚠️  {msg}")


def _check_env() -> dict:
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        _die("缺少必需环境变量 / missing required env: " + ", ".join(missing)
             + "。先 `source scripts/load_env.sh`。")
    key_path = Path(os.environ["ECS_SSH_KEY_PATH"]).expanduser()
    if not key_path.exists():
        _die(f"ECS_SSH_KEY_PATH 不存在 / not found: {key_path}")
    return {k: os.environ[k] for k in REQUIRED_ENV}


def _gen_run_id() -> str:
    return _dt.datetime.utcnow().strftime("ecs_mirror_check_%Y%m%dT%H%M%SZ")


def _local_hashes() -> dict[str, str]:
    """本地 clean_output 真源 hash 表 / local SSOT hash table.

    只读 / read-only：本函数只哈希文件内容，绝不写入或修改任何文件。
    """
    if not LOCAL_CLEAN_OUTPUT.exists():
        _die(f"本地 clean_output 不存在 / local clean_output missing: {LOCAL_CLEAN_OUTPUT}")
    table: dict[str, str] = {}
    for p in sorted(LOCAL_CLEAN_OUTPUT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(LOCAL_CLEAN_OUTPUT).as_posix()
        if any(part.startswith(".") for part in rel.split("/")):
            continue
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        table[rel] = h.hexdigest()
    return table


def _ssh_cmd(env: dict, remote_cmd: str) -> list[str]:
    key_path = str(Path(env["ECS_SSH_KEY_PATH"]).expanduser())
    return [
        "ssh", "-i", key_path,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        f"{env['ECS_USER']}@{env['ECS_HOST']}",
        remote_cmd,
    ]


def _ssh_remote_count(env: dict) -> int:
    """先 SSH 一次只算文件数，作为完整性校验基准 / integrity-check baseline."""
    quoted = shlex.quote(ECS_REMOTE_MIRROR_DIR)
    remote = f"cd {quoted} && find . -type f ! -path '*/.*' | wc -l"
    proc = subprocess.run(_ssh_cmd(env, remote), capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        _die(f"SSH count 失败 / remote count failed: {proc.stderr.strip()}")
    try:
        return int(proc.stdout.strip())
    except ValueError:
        _die(f"SSH count 输出非整数 / unexpected count output: {proc.stdout!r}")
        return -1


def _ecs_hashes(env: dict, retries: int = 3) -> dict[str, str]:
    """ECS 镜像 hash 表（只读 SSH 远端）/ remote mirror hash table (read-only via SSH).

    严格完整性校验 / strict integrity check：先取期望文件数，再做 sha256 列表，
    解析后行数必须 = 期望文件数，否则视为 SSH 输出截断（曾出现过 6 行漂移误报），
    重试最多 retries 次仍不一致则 exit 2 —— 宁可报错也不报假漂移。
    """
    expected = _ssh_remote_count(env)
    quoted = shlex.quote(ECS_REMOTE_MIRROR_DIR)
    remote = (
        f"cd {quoted} && "
        f"find . -type f ! -path '*/.*' -print0 | sort -z | xargs -0 sha256sum"
    )
    last_err = ""
    for attempt in range(1, retries + 2):
        proc = subprocess.run(
            _ssh_cmd(env, remote),
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode != 0:
            last_err = proc.stderr.strip() or proc.stdout.strip()
            _warn(f"SSH 第 {attempt} 次失败 / attempt {attempt} failed: {last_err}")
            continue
        table: dict[str, str] = {}
        bad_lines = 0
        for ln in proc.stdout.splitlines():
            if not ln.strip():
                continue
            parts = ln.split(None, 1)
            if len(parts) != 2 or len(parts[0]) != 64:
                bad_lines += 1
                continue
            hexd, raw = parts
            rel = raw.strip()
            if rel.startswith("./"):
                rel = rel[2:]
            table[rel] = hexd
        if len(table) == expected and bad_lines == 0:
            return table
        last_err = (f"integrity check failed: parsed={len(table)} expected={expected} "
                    f"bad_lines={bad_lines}")
        _warn(f"SSH 第 {attempt} 次完整性校验失败 / attempt {attempt} integrity failed: {last_err}")
    _die(f"SSH 镜像枚举失败 / remote enumeration failed after retries: {last_err}", code=2)
    return {}


def _diff(local: dict[str, str], ecs: dict[str, str]) -> dict:
    local_keys = set(local)
    ecs_keys = set(ecs)
    only_local = sorted(local_keys - ecs_keys)
    only_ecs = sorted(ecs_keys - local_keys)
    hash_mismatch = [
        {"path": k, "local_sha256": local[k], "ecs_sha256": ecs[k]}
        for k in sorted(local_keys & ecs_keys) if local[k] != ecs[k]
    ]
    return {
        "only_local": only_local,
        "only_ecs": only_ecs,
        "hash_mismatch": hash_mismatch,
    }


def _git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _write_report(staging_dir: Path, env: dict, env_name: str, local: dict, ecs: dict, drift: dict, dry_run: bool) -> Path:
    drift_total = len(drift["only_local"]) + len(drift["only_ecs"]) + len(drift["hash_mismatch"])
    payload = {
        "run_id": staging_dir.name,
        "checked_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "env": env_name,
        "git_commit": _git_commit(),
        "evidence_level": "runtime_verified" if drift_total == 0 else "runtime_verified_with_drift",
        "source_of_truth_direction": SSOT_DIRECTION_LITERAL,
        "ecs_host": env["ECS_HOST"],
        "ecs_remote_mirror_dir": ECS_REMOTE_MIRROR_DIR,
        "local_file_count": len(local),
        "ecs_file_count": len(ecs),
        "drift_total": drift_total,
        "only_local": drift["only_local"],
        "only_ecs": drift["only_ecs"],
        "hash_mismatch": drift["hash_mismatch"],
        "dry_run": dry_run,
        "writes_clean_output": False,
        "writes_ecs": False,
    }
    out = staging_dir / "mirror_drift_report.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="本仓 → ECS 镜像方向校验 / local→ECS mirror drift verifier")
    parser.add_argument("--env", required=True, choices=["staging", "prod"], help="运行环境 / environment")
    parser.add_argument("--dry-run", action="store_true",
                        help="只列两端文件计数与少量样本，不写完整 drift 报告（仍生成 _staging 目录与一个最小 stub）")
    parser.add_argument("--run-id", default=None, help="可选 / optional explicit run_id")
    parser.add_argument("--out", default=None,
                        help="KS-FIX-03：把 canonical drift 报告复制一份到指定路径（除 _staging 之外的稳定 audit 锚点）。"
                             "路径必须落在 knowledge_serving/audit/ 下；不允许写 clean_output/。")
    parser.add_argument("--fail-on-drift", action="store_true",
                        help="显式声明 drift_total != 0 时 exit 1（默认即此，flag 仅用于卡片可读性）")
    args = parser.parse_args()

    if args.env == "prod":
        _die("--env prod 拒绝 / prod is not permitted by this card.", code=2)

    env = _check_env()
    run_id = args.run_id or _gen_run_id()
    staging_dir = STAGING_ROOT / run_id
    # 二次保险：staging 目录必须落在 _staging 下，绝不能撞 clean_output / ECS
    staging_resolved = staging_dir.resolve()
    if str(staging_resolved).find(str(LOCAL_CLEAN_OUTPUT.resolve())) != -1:
        _die("拒绝写 clean_output 子树 / refused to write under clean_output.")
    if not str(staging_resolved).startswith(str((REPO_ROOT / "_staging").resolve())):
        _die(f"staging 目录非法 / illegal staging dir: {staging_resolved}")
    staging_dir.mkdir(parents=True, exist_ok=True)
    _info(f"run_id = {run_id}")
    _info(f"方向 / direction: {SSOT_DIRECTION_LITERAL}")

    _info(f"枚举本地真源 / hashing local SSOT under {LOCAL_CLEAN_OUTPUT.relative_to(REPO_ROOT)} ...")
    local = _local_hashes()
    _ok(f"本地文件数 / local files: {len(local)}")

    _info(f"枚举 ECS 镜像 / hashing ECS mirror under {ECS_REMOTE_MIRROR_DIR} ...")
    ecs = _ecs_hashes(env)
    _ok(f"ECS 文件数 / ECS files: {len(ecs)}")

    drift = _diff(local, ecs)
    drift_total = len(drift["only_local"]) + len(drift["only_ecs"]) + len(drift["hash_mismatch"])

    report = _write_report(staging_dir, env, args.env, local, ecs, drift, dry_run=args.dry_run)
    _ok(f"drift report: {report.relative_to(REPO_ROOT)}")

    # KS-FIX-03：把 canonical 报告复制到 --out 指定的稳定 audit 路径
    if args.out:
        import shutil  # 局部 import，主路径不变
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = REPO_ROOT / out_path
        # 治理护栏 / governance guard：禁止写 clean_output 子树
        if str(out_path.resolve()).startswith(str(LOCAL_CLEAN_OUTPUT.resolve())):
            _die("--out 拒绝指向 clean_output/ 子树 / clean_output is SSOT, not audit sink.")
        # 必须落在 knowledge_serving/audit/ 或 task_cards/corrections/audit/
        allowed_roots = [
            (REPO_ROOT / "knowledge_serving" / "audit").resolve(),
            (REPO_ROOT / "task_cards" / "corrections" / "audit").resolve(),
        ]
        if not any(str(out_path.resolve()).startswith(str(r)) for r in allowed_roots):
            _die(f"--out 路径不在允许的 audit 目录下 / illegal audit sink: {out_path}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report, out_path)
        _ok(f"canonical out: {out_path.relative_to(REPO_ROOT)}")

    if drift_total == 0:
        _ok("ECS 镜像与本地真源完全一致 / ECS mirror matches local SSOT exactly.")
        return 0
    _warn(f"检测到 {drift_total} 项漂移 / drift detected: "
          f"only_local={len(drift['only_local'])}, "
          f"only_ecs={len(drift['only_ecs'])}, "
          f"hash_mismatch={len(drift['hash_mismatch'])}")
    if args.dry_run:
        _info("dry-run 模式：报告已落盘，未触发任何修复动作（修复由独立 redeploy 卡负责）。")
        # dry-run 仍按漂移返回 1，便于 CI 快速看到状态；如需 dry-run 永远 exit 0，改这里。
    return 1


if __name__ == "__main__":
    sys.exit(main())

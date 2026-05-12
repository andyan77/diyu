#!/usr/bin/env python3
"""
push_to_ecs_mirror.py · KS-DIFY-ECS-011 · 本地 → ECS 镜像 push
==============================================================
数据真源方向 / SSOT direction：
  本地 clean_output/ 是真源 / source of truth；
  ECS /data/clean_output/ 是部署副本 / mirror。
  本脚本是**单向 push 器**：覆盖 ECS + 删除 ECS 孤儿文件，实现严格 mirror（drift=0）。
  禁止反向：脚本无 ECS→local 代码路径。

用法 / usage:
  python3 scripts/push_to_ecs_mirror.py --dry-run --env staging   # 预览，不动 ECS
  python3 scripts/push_to_ecs_mirror.py --apply  --env staging    # 真推送 + 备份 + 校验

退出码 / exit:
  0  dry-run 完成 / apply 完成且 drift=0
  1  drift detection or post-verify failed
  2  环境错 / 拒绝 prod / preflight 失败 / 备份失败 / SSH 错
"""
from __future__ import annotations
import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

# 路径常量 · 硬编码 / hardcoded path constants（KS-DIFY-ECS-011 §7 安全要求）
REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_CLEAN_OUTPUT = REPO_ROOT / "clean_output"
ECS_REMOTE_MIRROR_DIR = "/data/clean_output"  # 含尾斜杠在拼装 rsync target 时单独加
STAGING_ROOT = REPO_ROOT / "_staging" / "ecs_mirror_push"
SSOT_DIRECTION_LITERAL = "local clean_output/ → ECS /data/clean_output/ (one-way mirror)"

REQUIRED_ENV = ["ECS_HOST", "ECS_USER", "ECS_SSH_KEY_PATH"]


def _die(msg: str, code: int = 2) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


def _info(msg: str) -> None:
    print(f"ℹ️  {msg}")


def _ok(msg: str) -> None:
    print(f"✅ {msg}")


def _run_id() -> str:
    return _dt.datetime.utcnow().strftime("ecs_mirror_push_%Y%m%dT%H%M%SZ")


def _check_env() -> dict:
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        _die("缺少必需环境变量 / missing env: " + ", ".join(missing)
             + "。先 `source scripts/load_env.sh`。")
    key_path = Path(os.environ["ECS_SSH_KEY_PATH"]).expanduser()
    if not key_path.exists():
        _die(f"SSH key 不存在 / missing: {key_path}")
    return {k: os.environ[k] for k in REQUIRED_ENV}


def _ssh_base(env: dict) -> list[str]:
    return [
        "ssh", "-i", str(Path(env["ECS_SSH_KEY_PATH"]).expanduser()),
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=yes",
        f"{env['ECS_USER']}@{env['ECS_HOST']}",
    ]


def _preflight() -> None:
    """preflight：本地状态健康才允许推"""
    # 1. clean_output 必须存在
    if not LOCAL_CLEAN_OUTPUT.exists():
        _die(f"本地 clean_output 不存在 / missing: {LOCAL_CLEAN_OUTPUT}")
    # 2. clean_output/ 子树 git status 干净（不许把未提交脏数据推上去）
    proc = subprocess.run(
        ["git", "status", "--porcelain", "clean_output/"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    if proc.stdout.strip():
        _die("clean_output/ 有未提交改动 / uncommitted changes detected:\n" + proc.stdout
             + "\n请先 commit 或 stash，再推送。")
    # 3. manifest 自洽（KS-S0-006 verify）
    proc = subprocess.run(
        ["python3", "scripts/generate_manifest.py", "--verify"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        _die("manifest --verify 失败 / failed:\n" + proc.stdout + proc.stderr)
    _ok("preflight 通过 / passed: git clean + manifest verified")


def _rsync_preview(env: dict) -> tuple[str, dict]:
    """dry-run rsync 输出变更清单"""
    target = f"{env['ECS_USER']}@{env['ECS_HOST']}:{ECS_REMOTE_MIRROR_DIR}/"
    # -c (--checksum)：用 sha 内容判定差异，避免被 mtime 漂移误报
    # 与 verify_ecs_mirror.py 的 sha256 语义对齐，preview 计数 = 真实内容漂移
    cmd = [
        "rsync", "-avzcn", "--delete", "--itemize-changes",
        "-e", f"ssh -i {Path(env['ECS_SSH_KEY_PATH']).expanduser()} -o BatchMode=yes -o ConnectTimeout=10",
        f"{LOCAL_CLEAN_OUTPUT}/",
        target,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        _die(f"rsync dry-run 失败 / failed (rc={proc.returncode}):\n{proc.stderr}")
    text = proc.stdout
    # 计数 itemize 标记 / rsync push 方向用 `<` 前缀（pull 才是 `>`）
    # 参考 rsync(1) --itemize-changes：
    #   <f+++++++++  全新文件 / new file
    #   <f<其它修饰>  已存在但属性差异（size/mtime/checksum 任一）
    #   *deleting    --delete 触发的删除
    adds = sum(1 for ln in text.splitlines() if ln.startswith("<f+++++++++"))
    mods = sum(1 for ln in text.splitlines() if ln.startswith("<f") and not ln.startswith("<f+++++++++"))
    dels = sum(1 for ln in text.splitlines() if ln.startswith("*deleting"))
    return text, {"add": adds, "modify": mods, "delete": dels}


def _ecs_backup(env: dict, run_id: str) -> str:
    """ECS 端备份当前镜像为带时间戳目录"""
    bak = f"{ECS_REMOTE_MIRROR_DIR}.bak_{run_id}"
    remote_cmd = f"cp -a {ECS_REMOTE_MIRROR_DIR} {bak}"
    proc = subprocess.run(_ssh_base(env) + [remote_cmd], capture_output=True, text=True)
    if proc.returncode != 0:
        _die(f"ECS 备份失败 / backup failed (rc={proc.returncode}):\n{proc.stderr}")
    _ok(f"ECS 备份完成 / backup: {bak}")
    return bak


def _rsync_apply(env: dict) -> None:
    target = f"{env['ECS_USER']}@{env['ECS_HOST']}:{ECS_REMOTE_MIRROR_DIR}/"
    # apply 也用 -c：内容一致即跳过传输，避免无意义的 mtime-only update
    cmd = [
        "rsync", "-avzc", "--delete",
        "-e", f"ssh -i {Path(env['ECS_SSH_KEY_PATH']).expanduser()} -o BatchMode=yes -o ConnectTimeout=10",
        f"{LOCAL_CLEAN_OUTPUT}/",
        target,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        _die(f"rsync apply 失败 / failed (rc={proc.returncode}):\n{proc.stderr}", code=1)
    _ok("rsync 完成 / synced")


def _post_verify() -> int:
    """调用 verify_ecs_mirror.py 校验 drift=0"""
    proc = subprocess.run(
        ["python3", "scripts/verify_ecs_mirror.py", "--dry-run", "--env", "staging"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
    return proc.returncode


def _build_partitions(backup_path: str | None, verify_rc: int | None) -> list[dict]:
    """ECS 数据 4 分区状态 / partition status snapshot.

    本卡只直接影响前 2 个分区（current_trusted_mirror + backup_only）；
    后 2 个（legacy_runtime_db / clean_vector_store）由 002/003/004/VECTOR-* 各自卡负责，
    本卡 audit 仅做 informational 标注，consumable=null 表示"非本卡裁决范围"。
    所有 consumable 字段下游 reviewer 脚本可断言用，详见 KS-DIFY-ECS-011 §0.1。
    """
    drift_after = 0 if verify_rc == 0 else (None if verify_rc is None else "unknown_or_nonzero")
    return [
        {
            "partition": "current_trusted_mirror",
            "path": ECS_REMOTE_MIRROR_DIR,
            "consumable": True if verify_rc == 0 else (None if verify_rc is None else False),
            "drift_after": drift_after,
            "owned_by_card": "KS-DIFY-ECS-011",
            "downstream_consumers": "all serving / 编译 / 向量入库",
            "note": "the only ECS path authorized as serving SSOT mirror",
        },
        {
            "partition": "backup_only",
            "path": backup_path if backup_path else f"{ECS_REMOTE_MIRROR_DIR}.bak_<run_id> (not created in this run)",
            "consumable": False,
            "created_at": _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC") if backup_path else None,
            "owned_by_card": "KS-DIFY-ECS-011",
            "downstream_consumers": "NONE — rollback-only; forbidden as compile/ETL/retrieval input",
            "retention_note": "manual cleanup via dedicated ops card; do not auto-delete",
        },
        {
            "partition": "legacy_runtime_db",
            "path": "ECS PG knowledge.*",
            "consumable": None,
            "owned_by_card": "KS-DIFY-ECS-002",
            "downstream_consumers": "NONE until KS-DIFY-ECS-002 reconcile + human adjudication",
            "note": "legacy runtime data; not yet aligned with current 9-table SSOT",
        },
        {
            "partition": "clean_vector_store",
            "path": "Qdrant collections (TBD)",
            "consumable": None,
            "owned_by_card": "KS-VECTOR-* / KS-DIFY-ECS-004",
            "downstream_consumers": "KS-RETRIEVAL-* (must filter by compile_run_id + source_manifest_hash)",
            "note": "future collections must carry batch-anchoring payload fields",
        },
    ]


def _write_audit(staging_dir: Path, env: dict, run_id: str, preview_text: str,
                 counts: dict, mode: str, backup_path: str | None,
                 verify_rc: int | None, status: str) -> Path:
    audit = {
        "task_card": "KS-DIFY-ECS-011",
        "run_id": run_id,
        "mode": mode,
        "env": "staging",
        "ecs_host": env["ECS_HOST"],
        "local_clean_output": str(LOCAL_CLEAN_OUTPUT.relative_to(REPO_ROOT)),
        "ecs_remote_mirror_dir": ECS_REMOTE_MIRROR_DIR,
        "source_of_truth_direction": SSOT_DIRECTION_LITERAL,
        "counts": counts,
        "backup_path": backup_path,
        "post_verify_rc": verify_rc,
        "status": status,
        "rollback_command": (
            f"ssh {env['ECS_USER']}@{env['ECS_HOST']} 'rm -rf {ECS_REMOTE_MIRROR_DIR} && "
            f"mv {backup_path} {ECS_REMOTE_MIRROR_DIR}'"
        ) if backup_path else None,
        "writes_clean_output": False,
        "partitions": _build_partitions(backup_path, verify_rc),
        "checked_at": _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    out = staging_dir / "push_audit.json"
    out.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="local→ECS one-way mirror push (KS-DIFY-ECS-011)")
    parser.add_argument("--env", required=True, choices=["staging", "prod"],
                        help="运行环境 / environment")
    mode_grp = parser.add_mutually_exclusive_group(required=True)
    mode_grp.add_argument("--dry-run", action="store_true", help="预览 / preview only")
    mode_grp.add_argument("--apply", action="store_true", help="真推送 + 备份 + 校验")
    args = parser.parse_args()

    if args.env == "prod":
        _die("--env prod 拒绝 / prod is not permitted by this card.", code=2)

    env = _check_env()
    run_id = _run_id()
    staging_dir = STAGING_ROOT / run_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    # 二次保险：staging 目录必须在 _staging 下
    if not str(staging_dir.resolve()).startswith(str((REPO_ROOT / "_staging").resolve())):
        _die("拒绝写非 _staging 路径 / refused non-staging path")

    _info(f"run_id = {run_id}")
    _info(f"方向 / direction: {SSOT_DIRECTION_LITERAL}")

    _preflight()

    # Phase 2: dry-run preview（不论 mode 都先跑）
    _info("dry-run 预览 / preview rsync changes ...")
    preview_text, counts = _rsync_preview(env)
    preview_path = staging_dir / "preview.txt"
    preview_path.write_text(preview_text, encoding="utf-8")
    _ok(f"preview: add={counts['add']}, modify={counts['modify']}, delete={counts['delete']}")
    _ok(f"preview file: {preview_path.relative_to(REPO_ROOT)}")

    if args.dry_run:
        _write_audit(staging_dir, env, run_id, preview_text, counts,
                     mode="dry_run", backup_path=None, verify_rc=None,
                     status="dry_run_only")
        _info("dry-run 模式：未对 ECS 产生任何写入。下一步：检查 preview.txt 后跑 --apply。")
        return 0

    # Phase 3: apply（备份 + rsync + post-verify）
    _info("apply 模式：先在 ECS 端备份当前镜像 ...")
    backup_path = _ecs_backup(env, run_id)

    _info("执行 rsync（含 --delete） ...")
    _rsync_apply(env)

    _info("post-verify：调 verify_ecs_mirror.py 检查 drift=0 ...")
    verify_rc = _post_verify()

    if verify_rc != 0:
        _write_audit(staging_dir, env, run_id, preview_text, counts,
                     mode="apply", backup_path=backup_path, verify_rc=verify_rc,
                     status="post_verify_failed")
        rollback = (f"ssh {env['ECS_USER']}@{env['ECS_HOST']} "
                    f"'rm -rf {ECS_REMOTE_MIRROR_DIR} && mv {backup_path} {ECS_REMOTE_MIRROR_DIR}'")
        _die(f"post-verify 失败 / failed (rc={verify_rc})。回滚命令:\n  {rollback}", code=1)

    _write_audit(staging_dir, env, run_id, preview_text, counts,
                 mode="apply", backup_path=backup_path, verify_rc=verify_rc,
                 status="success")
    _ok(f"push 完成 + drift=0 / done. backup retained: {backup_path}")
    _info(f"audit: {(staging_dir / 'push_audit.json').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

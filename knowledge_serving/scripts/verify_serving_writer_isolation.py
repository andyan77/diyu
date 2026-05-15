#!/usr/bin/env python3
"""KS-CD-003 §11 DoD · serving_writer PG 隔离远程只读验证.

红线 / Red lines:
  - 只读 / read-only：通过 ssh + docker exec psql 在 ECS 上 SELECT 元数据，不改 ECS
  - 不绕 SSOT：本地 → ECS 单向；不把 ECS 状态当真源回灌
  - fail-closed：任一断言不通过 → exit 1 + audit verdict=FAIL

期望边界（必须全部成立才 PASS）:
  R1. serving_writer 是 login-only 非 super 角色
  R2. 仅 serving / public 两个 schema 可 USAGE；
       knowledge / knowledge_industrial / gateway 全 USAGE=false
  R3. 仅 serving schema 下有表权限，且仅 INSERT + SELECT
  R4. 没有任何 forbidden 组合（其他 schema / UPDATE / DELETE / TRUNCATE / REFERENCES / TRIGGER）

artifact: knowledge_serving/audit/serving_writer_isolation_KS-CD-003.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = REPO_ROOT / "knowledge_serving" / "scripts" / "sql" / "verify_serving_writer_isolation.sql"
AUDIT_PATH = REPO_ROOT / "knowledge_serving" / "audit" / "serving_writer_isolation_KS-CD-003.json"


def _now() -> str:
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception as e:  # pragma: no cover
        return f"unknown:{e}"


def _ssh_exec_sql(ssh_user: str, ssh_host: str, ssh_key: str,
                  container: str, pg_user: str, db: str, sql_text: str) -> tuple[int, str, str]:
    """把 SQL 推到 ECS，docker exec psql 执行，回收 stdout/stderr。"""
    # 通过 stdin 传 SQL；psql -f - 读 stdin
    cmd = [
        "ssh", "-i", ssh_key, "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        f"{ssh_user}@{ssh_host}",
        # docker exec -i 接受 stdin
        f"docker exec -i {shlex.quote(container)} "
        f"psql -U {shlex.quote(pg_user)} -d {shlex.quote(db)} -X -A -F '|' -P pager=off",
    ]
    proc = subprocess.run(cmd, input=sql_text, capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


# ============================================================
# 解析 psql -A -F '|' 输出，按 \echo === SECTION_N name === 切片
# ============================================================
SECTION_RE = re.compile(r"^=== SECTION_(\d+) ([\w_]+) ===\s*$")


def _split_sections(stdout: str) -> dict[str, list[list[str]]]:
    sections: dict[str, list[list[str]]] = {}
    current_name: str | None = None
    current_rows: list[list[str]] = []
    for line in stdout.splitlines():
        m = SECTION_RE.match(line.strip())
        if m:
            if current_name is not None:
                sections[current_name] = current_rows
            current_name = m.group(2)
            current_rows = []
            continue
        if current_name is None:
            continue
        if not line.strip():
            continue
        if re.match(r"^\(\d+ rows?\)$", line.strip()):
            continue
        cols = line.split("|")
        current_rows.append(cols)
    if current_name is not None:
        sections[current_name] = current_rows
    return sections


def _assert_isolation(sections: dict[str, list[list[str]]]) -> list[str]:
    """返回失败原因列表；空列表 = 全部 PASS。"""
    failures: list[str] = []

    # R1 · role attributes（第一行 = 表头，第二行 = 数据；-A 模式头也在）
    rows = sections.get("role_attributes", [])
    if len(rows) < 2:
        failures.append("R1: role_attributes section empty — serving_writer not found")
    else:
        header, data = rows[0], rows[1]
        idx = {h: i for i, h in enumerate(header)}
        if data[idx["rolsuper"]] != "f":
            failures.append(f"R1: serving_writer.rolsuper expected 'f', got {data[idx['rolsuper']]!r}")
        if data[idx["rolcanlogin"]] != "t":
            failures.append(f"R1: serving_writer.rolcanlogin expected 't', got {data[idx['rolcanlogin']]!r}")
        if data[idx["rolcreaterole"]] != "f" or data[idx["rolcreatedb"]] != "f":
            failures.append("R1: serving_writer must not have createrole/createdb")

    # R2 · schema USAGE
    rows = sections.get("schema_usage", [])
    usage = {r[0]: r[1] for r in rows[1:]}  # skip header
    allowed_usage = {"serving": "t", "public": "t"}
    forbidden_usage = {"knowledge": "f", "knowledge_industrial": "f", "gateway": "f"}
    for k, v in allowed_usage.items():
        if usage.get(k) != v:
            failures.append(f"R2: schema {k} USAGE expected {v}, got {usage.get(k)!r}")
    for k, v in forbidden_usage.items():
        if usage.get(k) != v:
            failures.append(f"R2: schema {k} USAGE leak — expected {v}, got {usage.get(k)!r}")

    # R3 · table grants（只能 serving / INSERT+SELECT）
    rows = sections.get("table_grants", [])
    grants = {r[0]: r for r in rows[1:]}
    if set(grants.keys()) != {"serving"}:
        failures.append(f"R3: grants leaked outside serving schema → {list(grants.keys())!r}")
    if "serving" in grants:
        privs = grants["serving"][2]  # privs col
        if privs != "INSERT,SELECT":
            failures.append(f"R3: serving privs expected 'INSERT,SELECT', got {privs!r}")

    # R4 · forbidden privs probe（应当空）
    rows = sections.get("forbidden_privs_probe", [])
    if len(rows) > 1:  # 头之外还有数据 → 隔离破裂
        failures.append(f"R4: forbidden privs found: {rows[1:]!r}")

    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ssh-host", default=os.environ.get("ECS_HOST", "8.217.175.36"))
    ap.add_argument("--ssh-user", default=os.environ.get("ECS_USER", "root"))
    ap.add_argument("--ssh-key", default=os.path.expanduser(
        os.environ.get("ECS_SSH_KEY_PATH", "~/.ssh/diyu-hk.pem")))
    ap.add_argument("--pg-container", default="diyu-infra-postgres-1")
    ap.add_argument("--pg-superuser", default="diyu")
    ap.add_argument("--pg-database", default="diyu_brand_faye")
    args = ap.parse_args()

    if not SQL_PATH.is_file():
        print(f"❌ SQL not found: {SQL_PATH}", file=sys.stderr)
        return 2
    sql_text = SQL_PATH.read_text(encoding="utf-8")

    rc, stdout, stderr = _ssh_exec_sql(
        args.ssh_user, args.ssh_host, args.ssh_key,
        args.pg_container, args.pg_superuser, args.pg_database, sql_text,
    )

    sections = _split_sections(stdout)
    failures = _assert_isolation(sections) if rc == 0 else [f"ssh/psql exit {rc}: {stderr[:300]}"]
    verdict = "PASS" if not failures else "FAIL"

    artifact = {
        "task_id": "KS-CD-003",
        "subgate": "§11_DoD_serving_writer_isolation",
        "checked_at_utc": _now(),
        "git_commit": _git_commit(),
        "ecs_host": args.ssh_host,
        "pg_container": args.pg_container,
        "pg_database": args.pg_database,
        "pg_role_under_test": "serving_writer",
        "command": (
            f"ssh {args.ssh_user}@{args.ssh_host} 'docker exec -i {args.pg_container} "
            f"psql -U {args.pg_superuser} -d {args.pg_database}' < "
            "knowledge_serving/scripts/sql/verify_serving_writer_isolation.sql"
        ),
        "ssh_exit_code": rc,
        "verdict": verdict,
        "evidence_level": "runtime_verified" if verdict == "PASS" else "blocked",
        "failures": failures,
        "rules_checked": {
            "R1": "serving_writer is login-only non-super role",
            "R2": "USAGE granted only on serving + public; knowledge/knowledge_industrial/gateway = false",
            "R3": "table grants confined to serving schema with INSERT,SELECT only",
            "R4": "no forbidden privilege (UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER) anywhere",
        },
        "sections": sections,
        "stderr_tail": stderr[-400:] if stderr else "",
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{'✅ PASS' if verdict == 'PASS' else '❌ FAIL'}: serving_writer isolation → {AUDIT_PATH}")
    if failures:
        for f in failures:
            print(f"   - {f}", file=sys.stderr)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KS-DIFY-ECS-003 · serving views/control 表回灌 ECS PG `serving.*` schema。

【边界 / Boundary（KS-DIFY-ECS-011 §0.1）】
   ECS PG 上有 4 个分区，本卡只写**新建** `serving.*` schema。
   - 不许写 `knowledge.*`（legacy_runtime_db，归 KS-DIFY-ECS-002 对账分区）
   - 不许读 `knowledge.*` 当真源
   - 本地 `clean_output/` + `knowledge_serving/views|control/*.csv` 是唯一真源

【KS-COMPILER-013 前置门禁 / prerequisite gate】
   apply 前必须读取 `knowledge_serving/audit/validate_serving_governance.report`，
   S1-S7 全 pass，且其 `compile_run_id` 与 CSV 行内的 `compile_run_id` 一致。
   任一缺失或 fail → 拒绝执行，exit 2。

【模式 / Modes】
   --env staging --dry-run  ：默认 CI 路径；不连 ECS；产 SQL preview + audit json
   --env staging --apply    ：连 ECS；BEGIN/TRUNCATE/INSERT/COMMIT；落 audit
   --env prod  --apply      ：必须再带 --signoff <name> --model-policy-version <ver>

【幂等 / Idempotence】
   同 compile_run_id + source_manifest_hash 重灌 → 行内容字节级一致，不增不减。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
VIEWS_DIR = REPO_ROOT / "knowledge_serving" / "views"
CONTROL_DIR = REPO_ROOT / "knowledge_serving" / "control"
SCHEMA_PATH = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"
MANIFEST_PATH = REPO_ROOT / "clean_output" / "audit" / "source_manifest.json"
GOVERNANCE_REPORT = REPO_ROOT / "knowledge_serving" / "audit" / "validate_serving_governance.report"
AUDIT_DIR = REPO_ROOT / "knowledge_serving" / "audit"
# 双路径隔离 / dual-path isolation：dry-run 与 apply 永不互相覆盖，
# 防止 CI dry-run 静默抹掉 prod apply 的可回放证据（governor finding 修复）。
AUDIT_PATH_APPLY = AUDIT_DIR / "upload_views_KS-DIFY-ECS-003.json"          # 仅 --apply 写
AUDIT_PATH_DRY_RUN = AUDIT_DIR / "upload_views_KS-DIFY-ECS-003.dry_run.json"  # 仅 --dry-run 写

TARGET_SCHEMA = "serving"  # 新建；与 legacy knowledge.* 物理隔离
PG_CONTAINER = "diyu-infra-postgres-1"

# 7 view + 5 control（plan §3 + §4）。content_type_canonical 是 S0 辅助表，不在 5 control 内。
VIEW_TABLES = [
    "pack_view",
    "content_type_view",
    "generation_recipe_view",
    "play_card_view",
    "runtime_asset_view",
    "brand_overlay_view",
    "evidence_view",
]
CONTROL_TABLES = [
    "tenant_scope_registry",
    "field_requirement_matrix",
    "retrieval_policy_view",
    "merge_precedence_policy",
    "context_bundle_log",
]

S_GATES = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]

# 必需治理列 / required governance columns per spec（plan §2 + §4）。
# 7 views 与 context_bundle_log 必须带治理三联；
# 4 policy control 表（tenant_scope_registry / field_requirement_matrix /
# retrieval_policy_view / merge_precedence_policy）按 plan §4.1-§4.4 是静态配置，
# 不强制治理三联（policy 静态表跨批次复用，不绑 compile_run_id）。
GOVERNANCE_TRIPLET = ("compile_run_id", "source_manifest_hash", "view_schema_version")
TABLES_REQUIRING_GOVERNANCE: Dict[str, Tuple[str, ...]] = {
    "pack_view": GOVERNANCE_TRIPLET,
    "content_type_view": GOVERNANCE_TRIPLET,
    "generation_recipe_view": GOVERNANCE_TRIPLET,
    "play_card_view": GOVERNANCE_TRIPLET,
    "runtime_asset_view": GOVERNANCE_TRIPLET,
    "brand_overlay_view": GOVERNANCE_TRIPLET,
    "evidence_view": GOVERNANCE_TRIPLET,
    "context_bundle_log": GOVERNANCE_TRIPLET,
}

REQUIRED_ENV_APPLY = [
    "PG_HOST", "PG_USER", "PG_PASSWORD", "PG_DATABASE",
    "ECS_SSH_KEY_PATH", "ECS_HOST", "ECS_USER",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def err(msg: str, code: int = 2):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="KS-DIFY-ECS-003 serving 回灌 ECS PG serving.*")
    p.add_argument("--env", required=True, choices=["staging", "prod"])
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="仅生成 SQL preview + audit（不连 ECS）")
    mode.add_argument("--apply", action="store_true",
                      help="连 ECS 执行 DDL+DML（staging 默认放行；prod 需 signoff）")
    p.add_argument("--signoff", default=None, help="prod 模式必填：人工签字名")
    p.add_argument("--model-policy-version", default=None,
                   help="prod 模式必填：与本次回灌绑定的 model_policy 版本")
    return p.parse_args()


# ---------- KS-COMPILER-013 前置门禁 ----------

def parse_governance_report(path: Path) -> Dict[str, object]:
    """读 validate_serving_governance.report，抽 compile_run_id + 各 S 门 status。"""
    if not path.exists():
        err(f"前置门禁缺失 / governance report missing: {path}; 先跑 KS-COMPILER-013", code=2)
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^compile_run_id:\s*(\S+)", text, flags=re.M)
    if not m:
        err("governance report 无 compile_run_id", code=2)
    compile_run_id = m.group(1)
    statuses: Dict[str, str] = {}
    for gate in S_GATES:
        # 每个 S 门段第一个 status: 行
        sec = re.search(rf"\[{gate}[^\]]*\][^\[]*?status:\s*(\S+)", text, flags=re.M)
        if not sec:
            err(f"governance report 缺 {gate} 段", code=2)
        statuses[gate] = sec.group(1)
    return {"compile_run_id": compile_run_id, "gates": statuses}


def enforce_prerequisite_gate() -> Dict[str, object]:
    rep = parse_governance_report(GOVERNANCE_REPORT)
    failing = [g for g, s in rep["gates"].items() if s != "pass"]  # type: ignore[union-attr]
    if failing:
        err(f"KS-COMPILER-013 未全绿，阻断回灌：{failing}", code=2)
    return rep


# ---------- manifest / csv 一致性 ----------

def load_manifest_hash() -> str:
    if not MANIFEST_PATH.exists():
        err(f"source_manifest 缺失: {MANIFEST_PATH}", code=2)
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    h = data.get("manifest_hash")
    if not isinstance(h, str) or not h:
        err("source_manifest.manifest_hash 缺失", code=2)
    return h


def read_csv(path: Path) -> Tuple[List[str], List[List[str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return [], []
        rows = [r for r in reader]
    return header, rows


def extract_csv_compile_run_ids(path: Path) -> List[str]:
    header, rows = read_csv(path)
    if "compile_run_id" not in header:
        return []
    idx = header.index("compile_run_id")
    return sorted({r[idx] for r in rows if idx < len(r) and r[idx]})


def extract_csv_manifest_hashes(path: Path) -> List[str]:
    header, rows = read_csv(path)
    if "source_manifest_hash" not in header:
        return []
    idx = header.index("source_manifest_hash")
    return sorted({r[idx] for r in rows if idx < len(r) and r[idx]})


def assert_required_columns() -> None:
    """治理列硬门 / hard gate on governance columns。

    要求 7 views + context_bundle_log 的 CSV header 必须含 GOVERNANCE_TRIPLET。
    缺任一列 → exit 2（防 E2 假绿：上游报告 stale 时本地编辑漏列）。
    4 policy control 表按 spec 是静态配置，不在此校验范围。
    """
    missing: List[str] = []
    for name, required in TABLES_REQUIRING_GOVERNANCE.items():
        path = (VIEWS_DIR / f"{name}.csv") if name in VIEW_TABLES else (CONTROL_DIR / f"{name}.csv")
        if not path.exists():
            err(f"必需 CSV 缺失 / required CSV missing: {path}", code=2)
        header, _ = read_csv(path)
        for col in required:
            if col not in header:
                missing.append(f"{name}.{col}")
    if missing:
        err("CSV 治理列缺失 / governance columns missing:\n  " + "\n  ".join(missing), code=2)


def assert_csv_consistency(expected_compile_run_id: str, expected_manifest_hash: str) -> None:
    """所有 view CSV 的 compile_run_id / source_manifest_hash 必须与 governance 报告 / manifest 一致。

    注意：本函数前置依赖 assert_required_columns() 已保证列存在；
    若列存在但全为空字符串（extract_*_ids 返回 []），视为漂移而非"无可比"。
    """
    drift: List[str] = []
    for name in VIEW_TABLES:
        path = VIEWS_DIR / f"{name}.csv"
        ids = extract_csv_compile_run_ids(path)
        if ids != [expected_compile_run_id]:
            drift.append(f"{name}.compile_run_id={ids} expected=[{expected_compile_run_id}]")
        hashes = extract_csv_manifest_hashes(path)
        if hashes != [expected_manifest_hash]:
            drift.append(f"{name}.source_manifest_hash={hashes} expected=[{expected_manifest_hash}]")
    if drift:
        err("CSV 与 governance/manifest 不一致 / drift detected:\n  " + "\n  ".join(drift), code=2)


# ---------- DDL 生成 ----------

def quote_ident(name: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        err(f"非法标识符 / illegal identifier: {name!r}", code=2)
    return name  # 已正则白名单


def ddl_for_table(table: str, header: List[str],
                  compile_run_id: str, manifest_hash: str,
                  view_schema_version: str) -> str:
    """所有列 TEXT；附 COMMENT ON TABLE 指向 compile_run_id（任务卡 §4.4 要求）。"""
    cols_sql = ",\n  ".join(f"{quote_ident(c)} TEXT" for c in header)
    comment = (
        f"compile_run_id={compile_run_id};"
        f"source_manifest_hash={manifest_hash};"
        f"view_schema_version={view_schema_version};"
        f"task_card=KS-DIFY-ECS-003"
    )
    return (
        f"CREATE TABLE IF NOT EXISTS {TARGET_SCHEMA}.{quote_ident(table)} (\n"
        f"  {cols_sql}\n"
        f");\n"
        f"COMMENT ON TABLE {TARGET_SCHEMA}.{quote_ident(table)} IS "
        f"E'{pg_escape(comment)}';"
    )


def build_ddl(compile_run_id: str, manifest_hash: str,
              view_schema_version: str) -> Tuple[str, Dict[str, int]]:
    """返回完整 DDL 与各表行数（仅 view+control，5 control 已落地）。"""
    parts = [
        f"-- KS-DIFY-ECS-003 DDL · target schema: {TARGET_SCHEMA}",
        f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA};",
    ]
    inventory: Dict[str, int] = {}
    for name in VIEW_TABLES:
        path = VIEWS_DIR / f"{name}.csv"
        header, rows = read_csv(path)
        parts.append(ddl_for_table(name, header, compile_run_id, manifest_hash, view_schema_version))
        inventory[f"{TARGET_SCHEMA}.{name}"] = len(rows)
    for name in CONTROL_TABLES:
        path = CONTROL_DIR / f"{name}.csv"
        if not path.exists():
            err(f"control CSV 缺失: {path}", code=2)
        header, rows = read_csv(path)
        parts.append(ddl_for_table(name, header, compile_run_id, manifest_hash, view_schema_version))
        inventory[f"{TARGET_SCHEMA}.{name}"] = len(rows)
    return "\n\n".join(parts) + "\n", inventory


# ---------- DML 生成（仅 apply 用）----------

def pg_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "''")


def insert_sql_for_table(schema: str, table: str, header: List[str],
                         rows: List[List[str]]) -> str:
    if not rows:
        return f"-- {schema}.{table}: 0 rows"
    cols = ", ".join(quote_ident(c) for c in header)
    values_parts: List[str] = []
    for r in rows:
        vals = []
        for i, c in enumerate(header):
            v = r[i] if i < len(r) else ""
            vals.append(f"E'{pg_escape(v)}'")
        values_parts.append("(" + ", ".join(vals) + ")")
    return (
        f"INSERT INTO {schema}.{table} ({cols}) VALUES\n  "
        + ",\n  ".join(values_parts) + ";"
    )


def build_dml(inventory_paths: Dict[str, Path]) -> str:
    parts = [
        "BEGIN;",
        f"SET search_path TO {TARGET_SCHEMA};",
    ]
    for fq, path in inventory_paths.items():
        schema, table = fq.split(".", 1)
        header, rows = read_csv(path)
        parts.append(f"TRUNCATE {schema}.{table};")
        parts.append(insert_sql_for_table(schema, table, header, rows))
    parts.append("COMMIT;")
    return "\n\n".join(parts) + "\n"


# ---------- ECS apply（SSH + docker exec psql）----------

FORBIDDEN_TARGETS = re.compile(r"\bknowledge\.", re.IGNORECASE)


def assert_no_legacy_writes(sql: str) -> None:
    """硬阻断：任何引用 `knowledge.` 的 SQL 都不许下发——避免污染 legacy_runtime_db 分区。"""
    if FORBIDDEN_TARGETS.search(sql):
        err("SQL 引用了 knowledge.*（legacy 分区），拒绝执行", code=2)


def ssh_psql_exec(sql: str) -> str:
    assert_no_legacy_writes(sql)
    pg_user = os.environ["PG_USER"]
    pg_db = os.environ["PG_DATABASE"]
    ssh_key = os.environ["ECS_SSH_KEY_PATH"]
    ecs_host = os.environ["ECS_HOST"]
    ecs_user = os.environ["ECS_USER"]
    # 把 SQL 通过 stdin 传给远端 psql，避免单引号 escape 噩梦
    remote_cmd = (
        f"docker exec -i {shlex.quote(PG_CONTAINER)} "
        f"psql -U {shlex.quote(pg_user)} -d {shlex.quote(pg_db)} "
        f"-v ON_ERROR_STOP=1 -f -"
    )
    cmd = [
        "ssh",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-i", ssh_key,
        f"{ecs_user}@{ecs_host}",
        remote_cmd,
    ]
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        err(f"psql 失败 / psql failed (exit={proc.returncode}): {proc.stderr.strip()}", code=2)
    return proc.stdout


def check_apply_env(args: argparse.Namespace) -> None:
    missing = [k for k in REQUIRED_ENV_APPLY if not os.environ.get(k)]
    if missing:
        err(f"apply 模式缺 env: {', '.join(missing)}", code=2)
    if args.env == "prod":
        if not args.signoff:
            err("prod 模式必须 --signoff <name>", code=2)
        if not args.model_policy_version:
            err("prod 模式必须 --model-policy-version <ver>", code=2)


# ---------- 主流程 ----------

def collect_inventory_paths() -> Dict[str, Path]:
    paths: Dict[str, Path] = {}
    for name in VIEW_TABLES:
        paths[f"{TARGET_SCHEMA}.{name}"] = VIEWS_DIR / f"{name}.csv"
    for name in CONTROL_TABLES:
        paths[f"{TARGET_SCHEMA}.{name}"] = CONTROL_DIR / f"{name}.csv"
    return paths


def main() -> int:
    args = parse_args()

    # 1. 前置门禁（KS-COMPILER-013）
    gate = enforce_prerequisite_gate()
    compile_run_id = gate["compile_run_id"]  # type: ignore[index]

    # 2a. 必需治理列硬门（先于值比对；列缺失 → 立即 exit 2，防假绿）
    assert_required_columns()

    # 2b. manifest + CSV 值一致性
    manifest_hash = load_manifest_hash()
    assert_csv_consistency(compile_run_id, manifest_hash)  # type: ignore[arg-type]

    # 3. view_schema_version（与 _common.derive 算法保持一致）
    view_schema_version = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()[:12]

    # 4. DDL + DML（DML 只在 dry-run preview 时拼一份摘要；apply 时落实下发）
    ddl_sql, inventory = build_ddl(compile_run_id, manifest_hash, view_schema_version)  # type: ignore[arg-type]
    inventory_paths = collect_inventory_paths()

    run_id = str(uuid.uuid4())
    mode = "dry_run" if args.dry_run else "apply"

    audit: Dict[str, object] = {
        "task_card": "KS-DIFY-ECS-003",
        "run_id": run_id,
        "run_at": now_iso(),
        "env": args.env,
        "mode": mode,
        "target_schema": TARGET_SCHEMA,
        "partition_reference": "KS-DIFY-ECS-011 §0.1 row 3→new serving.* (NOT legacy knowledge.*)",
        "prerequisite_gate": {
            "task_card": "KS-COMPILER-013",
            "report": str(GOVERNANCE_REPORT.relative_to(REPO_ROOT)),
            "compile_run_id": compile_run_id,
            "gates": gate["gates"],
            "status": "pass",
        },
        "source_manifest_hash": manifest_hash,
        "compile_run_id": compile_run_id,
        "view_schema_version": view_schema_version,
        "tables": inventory,
        "ddl_table_count": len(inventory),
        "ddl_byte_size": len(ddl_sql.encode("utf-8")),
        "ddl_sha256": hashlib.sha256(ddl_sql.encode("utf-8")).hexdigest(),
        "human_signoff": None,
        "model_policy_version": args.model_policy_version,
        "read_only_legacy_guarantee": "脚本拒绝任何引用 knowledge.* 的 SQL；只写 serving.*",
    }

    if args.dry_run:
        # 不连 ECS；落 audit 与 SQL preview sidecar
        preview_path = AUDIT_DIR / "upload_views_KS-DIFY-ECS-003.ddl.sql"
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        preview_path.write_text(ddl_sql, encoding="utf-8")
        audit["ddl_preview_path"] = str(preview_path.relative_to(REPO_ROOT))
        # 关键：dry-run 写 sidecar 路径，永不覆盖 apply 的可回放证据
        AUDIT_PATH_DRY_RUN.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[dry-run] env={args.env} tables={len(inventory)} "
              f"compile_run_id={compile_run_id} manifest={manifest_hash[:12]}…")
        print(f"[dry-run] DDL → {preview_path.relative_to(REPO_ROOT)} "
              f"({audit['ddl_byte_size']} bytes, sha256={audit['ddl_sha256'][:12]}…)")
        print(f"[dry-run] audit → {AUDIT_PATH_DRY_RUN.relative_to(REPO_ROOT)} "
              f"(apply 证据 {AUDIT_PATH_APPLY.relative_to(REPO_ROOT)} 不会被覆盖)")
        return 0

    # apply 路径
    check_apply_env(args)
    if args.signoff:
        audit["human_signoff"] = {"signed_by": args.signoff, "signed_at": now_iso()}

    # 4a. DDL
    ssh_psql_exec(ddl_sql)

    # 4b. DML 分表执行（一次性整包 SQL 太大时可分表事务）
    dml_sql = build_dml(inventory_paths)
    ssh_psql_exec(dml_sql)

    # 4c. post-verify：count(*) 回读对账
    verify: Dict[str, Dict[str, int]] = {}
    for fq in inventory_paths.keys():
        schema, table = fq.split(".", 1)
        out = ssh_psql_exec(
            f"SELECT count(*) FROM {schema}.{table};"
        ).strip().splitlines()
        # psql -f - 输出含表头/分隔，取最后一行数字
        nums = [line.strip() for line in out if line.strip().isdigit()]
        actual = int(nums[-1]) if nums else -1
        verify[fq] = {"expected": inventory[fq], "actual": actual}
    audit["post_verify"] = verify
    audit["post_verify_status"] = (
        "pass" if all(v["expected"] == v["actual"] for v in verify.values()) else "fail"
    )

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    # apply 写 canonical 路径，留作可回放证据；dry-run 永不触碰此文件
    AUDIT_PATH_APPLY.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[apply] env={args.env} tables={len(inventory)} "
          f"post_verify={audit['post_verify_status']}")
    print(f"[apply] audit → {AUDIT_PATH_APPLY.relative_to(REPO_ROOT)}")
    return 0 if audit["post_verify_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KS-DIFY-ECS-002 · ECS PG knowledge.* ↔ 本仓 clean_output/nine_tables/*.csv 对账。

【现实事实 / Reality】
   实测发现 ECS PG `knowledge.*` schema（历史 runtime 数据 / legacy runtime data）
   与本仓抽取产物 9 表（abstract object/relation graph）**表名 0 重合**：
     - ECS:   brand_tone, compliance_rule, content_blueprint, content_type,
              enterprise_narrative_example, global_knowledge, narrative_arc,
              persona, role_profile
     - LOCAL: 01_object_type ~ 09_call_mapping
   两者语义完全不同，不能强行 hash 比对（参见 plan §A1 与 KS-DIFY-ECS-011 §0.1）。

【本脚本职责 / Responsibility】
   1. 诚实揭示 schema misalignment（schema 失配），不假装能算 row diff
   2. 三段诊断：schema_alignment / ecs_inventory / local_inventory
   3. 落盘 reconcile_KS-DIFY-ECS-002.json（含 next_step 指向 KS-DIFY-ECS-003）
   4. exit code：misalignment → 1；overlap>0 + row diff → 1；完全一致 → 0
   5. **只读 / read-only**：禁止 INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE

【用法 / Usage】
   bash -c 'source scripts/load_env.sh && \\
            python3 scripts/reconcile_ecs_pg_vs_nine_tables.py --env staging'
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shlex
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
NINE_TABLES_DIR = REPO_ROOT / "clean_output" / "nine_tables"
AUDIT_DIR = REPO_ROOT / "knowledge_serving" / "audit"
RECONCILE_PATH = AUDIT_DIR / "reconcile_KS-DIFY-ECS-002.json"

# 必填环境变量 / required env
REQUIRED_ENV = [
    "PG_HOST", "PG_USER", "PG_PASSWORD", "PG_DATABASE",
    "ECS_SSH_KEY_PATH", "ECS_HOST", "ECS_USER",
]

# ECS 上 PG 容器名（runtime_verified · ECS_AND_DATA_TOPOLOGY.md §1.3）
PG_CONTAINER = "diyu-infra-postgres-1"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ECS PG ↔ 9 表对账（read-only）")
    p.add_argument("--env", required=True, choices=["staging", "prod"],
                   help="目标环境（prod 被禁止）")
    p.add_argument("--allow-diff", action="store_true",
                   help="允许 schema/row 差异不致 exit≠0（仅人工评审用）")
    p.add_argument("--signoff", default=None,
                   help="人工签字名（与 --allow-diff 配合）")
    p.add_argument("--dry-run", action="store_true",
                   help="只校验 env 与参数，不连 ECS / 不读 CSV")
    return p.parse_args()


def err(msg: str, code: int = 2) -> "NoReturn":  # type: ignore[name-defined]
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def check_env() -> None:
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        err(f"缺少必填环境变量 / missing env: {', '.join(missing)}；请先 "
            f"`source scripts/load_env.sh` 并确认 .env 完整。", code=2)


def ssh_psql(sql: str) -> str:
    """通过 SSH + docker exec psql 在 ECS 上跑只读 SQL。返回 stdout 文本。"""
    # 反向写检查：禁止任何 DDL/DML（双保险）
    forbidden = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b",
                           re.IGNORECASE)
    if forbidden.search(sql):
        err(f"SQL 含禁用关键字 / SQL contains forbidden keyword: {sql!r}", code=2)

    pg_user = os.environ["PG_USER"]
    pg_db = os.environ["PG_DATABASE"]
    ssh_key = os.environ["ECS_SSH_KEY_PATH"]
    ecs_host = os.environ["ECS_HOST"]
    ecs_user = os.environ["ECS_USER"]

    # 远端命令：psql -At 取裸值，-c 执行 SQL。SQL 单引号 escape。
    sql_escaped = sql.replace("'", "'\"'\"'")
    remote_cmd = (
        f"docker exec {shlex.quote(PG_CONTAINER)} "
        f"psql -U {shlex.quote(pg_user)} -d {shlex.quote(pg_db)} "
        f"-At -c '{sql_escaped}'"
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
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        err(f"SSH/psql 失败 / SSH or psql failed (exit={proc.returncode}): "
            f"{proc.stderr.strip()}", code=2)
    return proc.stdout


def fetch_ecs_inventory() -> Dict[str, int]:
    """读 ECS PG knowledge.* 各表行数（只读 SELECT count(*)）。"""
    # 先取表名清单
    tables_sql = (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='knowledge' ORDER BY table_name"
    )
    raw = ssh_psql(tables_sql)
    tables = [t.strip() for t in raw.splitlines() if t.strip()]
    if not tables:
        return {}

    inventory: Dict[str, int] = {}
    for t in tables:
        # 表名仅 [a-zA-Z0-9_]，再校验防注入
        if not re.fullmatch(r"[a-zA-Z0-9_]+", t):
            err(f"非法 ECS 表名 / illegal table name: {t!r}", code=2)
        sql = f"SELECT count(*) FROM knowledge.{t}"
        out = ssh_psql(sql).strip()
        try:
            inventory[t] = int(out)
        except ValueError:
            err(f"无法解析 count 输出 / cannot parse count: {out!r}", code=2)
    return inventory


def fetch_local_inventory() -> Dict[str, int]:
    """读本仓 nine_tables/*.csv 各表数据行数（不含 header）。"""
    if not NINE_TABLES_DIR.is_dir():
        err(f"本仓 9 表目录不存在 / nine_tables dir missing: {NINE_TABLES_DIR}", code=2)
    inventory: Dict[str, int] = {}
    for csv_path in sorted(NINE_TABLES_DIR.glob("*.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            try:
                next(reader)  # skip header
            except StopIteration:
                inventory[csv_path.name] = 0
                continue
            inventory[csv_path.name] = sum(1 for _ in reader)
    return inventory


def normalize_local_table(name: str) -> str:
    """`01_object_type.csv` → `object_type`（去前缀数字与 .csv）。"""
    stem = name[:-4] if name.endswith(".csv") else name
    return re.sub(r"^\d+_", "", stem)


def compute_overlap(ecs: Dict[str, int],
                    local: Dict[str, int]) -> Tuple[List[str], List[str], List[str]]:
    ecs_names = sorted(ecs.keys())
    local_norm = sorted({normalize_local_table(n) for n in local.keys()})
    overlap = sorted(set(ecs_names) & set(local_norm))
    return ecs_names, local_norm, overlap


def main() -> int:
    args = parse_args()

    if args.env == "prod":
        err("prod 环境被本卡禁止 / prod is forbidden for this card", code=2)

    check_env()

    if args.dry_run:
        print(f"[DRY-RUN] env={args.env} · all required env present · OK")
        return 0

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 拉数据
    ecs_inventory = fetch_ecs_inventory()
    local_inventory = fetch_local_inventory()

    # 2. schema overlap
    ecs_names, local_names, overlap = compute_overlap(ecs_inventory, local_inventory)
    overlap_count = len(overlap)

    # 3. status 判定
    if overlap_count == 0 and (ecs_names or local_names):
        status = "schema_misalignment"
        diff_count = max(len(ecs_names), len(local_names))
    elif overlap_count > 0:
        # 有交集时才比 row count（当前现实下不应进入此分支）
        diffs = []
        for t in overlap:
            local_rows = next(
                v for k, v in local_inventory.items() if normalize_local_table(k) == t
            )
            if ecs_inventory[t] != local_rows:
                diffs.append(t)
        if diffs:
            status = "row_diff"
            diff_count = len(diffs)
        else:
            status = "aligned"
            diff_count = 0
    else:
        status = "empty"
        diff_count = 0

    # 4. human signoff
    human_signoff = None
    if args.allow_diff and args.signoff:
        human_signoff = {"signed_by": args.signoff, "signed_at": now_iso()}

    # 5. 落盘 reconcile json
    payload = {
        "task_card": "KS-DIFY-ECS-002",
        "run_id": str(uuid.uuid4()),
        "run_at": now_iso(),
        "env": args.env,
        "ecs_host": os.environ["ECS_HOST"],
        "pg_database": os.environ["PG_DATABASE"],
        "status": status,
        "diff_count": diff_count,
        "schema_alignment": {
            "ecs_tables": ecs_names,
            "local_tables": local_names,
            "overlap": overlap,
            "overlap_count": overlap_count,
        },
        "ecs_inventory": ecs_inventory,
        "local_inventory": local_inventory,
        "next_step": (
            "下游 KS-DIFY-ECS-003（W6 回灌）必须先解决 schema 映射；"
            "当前 ECS PG knowledge.* 不能直接作为 serving 输入"
            "（对应 KS-DIFY-ECS-011 §0.1 第 3 行 legacy_runtime_db.consumable=null 的约束）"
        ),
        "partition_reference": "see KS-DIFY-ECS-011 §0.1 row 3 (legacy_runtime_db, consumable=null)",
        "read_only_guarantee": "本脚本只跑 SELECT；任何 INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE 在执行前会被拦截。",
        "human_signoff": human_signoff,
    }

    RECONCILE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"[reconcile] status={status} overlap={overlap_count} "
          f"ecs_tables={len(ecs_names)} local_tables={len(local_names)} "
          f"-> {RECONCILE_PATH.relative_to(REPO_ROOT)}")

    # 6. exit code
    if status == "aligned":
        return 0
    if args.allow_diff and human_signoff:
        print(f"[reconcile] --allow-diff with signoff={human_signoff['signed_by']}; "
              "exit 0 by manual override")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

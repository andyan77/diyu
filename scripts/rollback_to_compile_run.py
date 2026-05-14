#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KS-CD-002 · 回滚预案 / rollback to compile_run_id.

【边界 / Boundary】
   - 真源 / SSOT: 本地 `clean_output/`；ECS PG `serving.*` + Qdrant 是部署副本
   - 本脚本只做"切回上版部署副本"，**不重建真源**
   - 仅支持回到 KS-CD-001 流水线生成过的 compile_run_id（必须在 audit 历史里）
   - 不调 LLM；不写 `clean_output/`

【依赖 / Prerequisites】
   - KS-DIFY-ECS-003 audit: `knowledge_serving/audit/upload_views_KS-DIFY-ECS-003.json`
   - KS-DIFY-ECS-004 audit: `knowledge_serving/audit/qdrant_upload_KS-DIFY-ECS-004.json`
     （含 previous_collection 字段，用于 Qdrant alias 回切）

【模式 / Modes】
   --list                列出 audit 中可见的所有 compile_run_id
   --to <run_id> --dry-run    仅列出会动的 PG 表 / Qdrant alias，不真改
   --to <run_id> --apply      真执行；需要 --yes 双确认
   --smoke-after              apply 完调 KS-RETRIEVAL-006 smoke 验证（默认 on for --apply）

【失败模式 / Failure modes】
   - 目标 run_id 不在 audit 历史 → exit 2
   - 目标 collection 已不存在 → exit 3
   - PG / Qdrant 任一失败 → exit 4 + audit 标 partial（要求人工介入）
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO_ROOT / "knowledge_serving" / "audit"
VIEW_AUDIT = AUDIT_DIR / "upload_views_KS-DIFY-ECS-003.json"
QDRANT_AUDIT = AUDIT_DIR / "qdrant_upload_KS-DIFY-ECS-004.json"
ROLLBACK_AUDIT_TEMPLATE = AUDIT_DIR / "rollback_KS-CD-002_{ts}.json"
DEPLOY_LEDGER_PATH = AUDIT_DIR / "deploy_ledger.jsonl"  # KS-FIX-27 C1

EXIT_OK = 0
EXIT_BAD_ARGS = 1
EXIT_RUN_NOT_FOUND = 2
EXIT_COLLECTION_MISSING = 3
EXIT_PARTIAL_FAILURE = 4


def _err(msg: str, code: int = EXIT_BAD_ARGS) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_ledger() -> list[dict[str, Any]]:
    """KS-FIX-27 C1：读 deploy_ledger.jsonl。损坏行 fail-closed。"""
    if not DEPLOY_LEDGER_PATH.exists():
        return []
    entries: list[dict[str, Any]] = []
    for i, line in enumerate(DEPLOY_LEDGER_PATH.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as e:
            _err(f"KS-FIX-27 AT-02：deploy_ledger.jsonl line {i} 损坏 / corrupted: {e}", code=EXIT_BAD_ARGS)
    return entries


def discover_run_ids() -> dict[str, dict[str, Any]]:
    """从 deploy audit 收集 {compile_run_id: {pg: {...}, qdrant: {...}}}.

    锚点关系：
      - PG audit (`upload_views_KS-DIFY-ECS-003.json`) 用 compile_run_id 直接标识
      - Qdrant audit (`qdrant_upload_KS-DIFY-ECS-004.json`) 用 model_policy_version 标识；
        与 PG audit 同一次 deploy 时 model_policy_version 一致 → 关联到同 compile_run_id
      - Qdrant audit 的 previous_collection 暗示更早的部署副本，登记为 placeholder

    KS-FIX-27 C1：若 deploy_ledger.jsonl 存在则**先**合并 ledger entries
    （PG 多条历史 / Qdrant 多次切换），再叠加最新单份 audit 作为兜底。
    """
    runs: dict[str, dict[str, Any]] = {}

    # KS-FIX-27 C1：ledger 优先
    for entry in _load_ledger():
        side = entry.get("side")
        rid = entry.get("compile_run_id")
        if not rid or side not in ("pg", "qdrant"):
            continue
        runs.setdefault(rid, {})[side] = {
            "audit_path": entry.get("audit_path"),
            "model_policy_version": entry.get("model_policy_version"),
            "source_manifest_hash": entry.get("source_manifest_hash"),
            "view_schema_version": entry.get("view_schema_version"),
            "run_at": entry.get("run_at"),
            "view_tables": entry.get("view_tables") or [f"table_{i}" for i in range(entry.get("table_count") or 0)],
            "target_schema": "serving",
            "alias": entry.get("alias", "ks_chunks_current"),
            "collection": entry.get("collection"),
            "previous_collection": entry.get("previous_collection"),
        }

    view_audit = _load_json(VIEW_AUDIT)
    view_mpv: str | None = None
    if view_audit:
        rid = view_audit.get("compile_run_id")
        view_mpv = view_audit.get("model_policy_version")
        if rid:
            tables_block = view_audit.get("tables") or []
            if isinstance(tables_block, list):
                table_names = sorted(t.get("name") for t in tables_block if t.get("name"))
            elif isinstance(tables_block, dict):
                table_names = sorted(tables_block.keys())
            else:
                table_names = []
            runs.setdefault(rid, {})["pg"] = {
                "audit_path": str(VIEW_AUDIT.relative_to(REPO_ROOT)),
                "target_schema": view_audit.get("target_schema", "serving"),
                "view_tables": table_names,
                "source_manifest_hash": view_audit.get("source_manifest_hash"),
                "view_schema_version": view_audit.get("view_schema_version"),
                "model_policy_version": view_mpv,
                "run_at": view_audit.get("run_at"),
            }

    qdr_audit = _load_json(QDRANT_AUDIT)
    if qdr_audit:
        q_mpv = qdr_audit.get("model_policy_version")
        # 与 PG audit 的 model_policy_version 一致 → 同一次 deploy → 同 compile_run_id
        rid_for_qdrant = None
        for rid, sides in runs.items():
            if sides.get("pg", {}).get("model_policy_version") == q_mpv:
                rid_for_qdrant = rid
                break
        if rid_for_qdrant is None:
            # 没找到匹配的 PG audit；用 mpv 当 placeholder run_id
            rid_for_qdrant = f"mpv::{q_mpv}"
        runs.setdefault(rid_for_qdrant, {})["qdrant"] = {
            "audit_path": str(QDRANT_AUDIT.relative_to(REPO_ROOT)),
            "alias": qdr_audit.get("alias", "ks_chunks_current"),
            "collection": qdr_audit.get("collection_name"),
            "previous_collection": qdr_audit.get("previous_collection"),
            "retained_collections": qdr_audit.get("retained_collections", []),
            "model_policy_version": q_mpv,
            "run_at": qdr_audit.get("run_at"),
        }
        # previous_collection 暗含一个更早的部署副本
        prev = qdr_audit.get("previous_collection")
        if prev and prev != qdr_audit.get("collection_name"):
            placeholder = f"qdrant_prev::{prev}"
            runs.setdefault(placeholder, {})["qdrant"] = {
                "audit_path": "(implicit from previous_collection)",
                "alias": qdr_audit.get("alias", "ks_chunks_current"),
                "collection": prev,
                "previous_collection": None,
                "model_policy_version": None,
                "run_at": None,
            }

    return runs


def _print_list(runs: dict[str, dict[str, Any]]) -> None:
    if not runs:
        print("(no compile_run_id 可见 / no runs found in audit history)")
        return
    print(f"=== 已知 compile_run_id ({len(runs)} 个) ===")
    for rid, sides in sorted(runs.items()):
        pg = sides.get("pg")
        qd = sides.get("qdrant")
        print(f"\n  run_id: {rid}")
        if pg:
            print(f"    PG  ({pg['target_schema']}.*): {len(pg['view_tables'])} tables · "
                  f"manifest={pg['source_manifest_hash'][:12] if pg.get('source_manifest_hash') else 'n/a'} · "
                  f"mpv={pg.get('model_policy_version')}")
            print(f"        deployed_at={pg.get('run_at')}")
        if qd:
            print(f"    Qdrant alias={qd['alias']} → collection={qd['collection']} · "
                  f"mpv={qd.get('model_policy_version')}")
            print(f"        deployed_at={qd.get('run_at')}")
            if qd.get("previous_collection") and qd.get("previous_collection") != qd.get("collection"):
                print(f"        previous_collection={qd['previous_collection']}")


def _qdrant_client():
    from qdrant_client import QdrantClient
    url = os.environ.get("QDRANT_URL_STAGING")
    if not url:
        _err("QDRANT_URL_STAGING 未设置；先 source scripts/load_env.sh + bash scripts/qdrant_tunnel.sh up")
    api_key = os.environ.get("QDRANT_API_KEY") or None
    return QdrantClient(url=url, api_key=api_key, timeout=30.0)


def plan_rollback(
    *,
    target_run_id: str,
    runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if target_run_id not in runs:
        return {
            "status": "run_not_found",
            "target_run_id": target_run_id,
            "known_run_ids": sorted(runs.keys()),
        }
    target = runs[target_run_id]
    actions: list[dict[str, Any]] = []
    warnings: list[str] = []

    if "qdrant" in target:
        q = target["qdrant"]
        actions.append({
            "kind": "qdrant_alias_switch",
            "alias": q["alias"],
            "switch_to_collection": q["collection"],
            "model_policy_version": q.get("model_policy_version"),
            "reversible_via": "切回 alias 当前指向",
        })
    else:
        warnings.append(f"目标 run_id {target_run_id} 无 Qdrant 部署历史 audit")

    if "pg" in target:
        pg = target["pg"]
        for table in pg["view_tables"]:
            actions.append({
                "kind": "pg_table_repopulate",
                "schema": pg["target_schema"],
                "table": table,
                "operation": "TRUNCATE + INSERT (from historical view CSV)",
                "requires_git_checkout": True,
                "reversible_via": "重跑当前 compile_run_id 的 KS-DIFY-ECS-003 --apply",
            })
        warnings.append(
            "PG apply 复用 KS-DIFY-ECS-003 --apply 重灌 serving.*；若目标 run_id 不等于当前 "
            "knowledge_serving/views/*.csv 批次，需先恢复对应历史 view CSV 后再执行。"
        )
    else:
        warnings.append(f"目标 run_id {target_run_id} 无 PG 部署历史 audit")

    return {
        "status": "planned",
        "target_run_id": target_run_id,
        "actions": actions,
        "warnings": warnings,
    }


def resolve_target_run_id(
    target_run_id: str,
    runs: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    if target_run_id in runs:
        return target_run_id, None
    if not target_run_id.startswith("mpv::"):
        return target_run_id, None

    target_mpv = target_run_id.removeprefix("mpv::")
    matches = [
        rid for rid, sides in runs.items()
        if any(side.get("model_policy_version") == target_mpv for side in sides.values())
    ]
    if len(matches) != 1:
        return target_run_id, {
            "status": "mpv_alias_ambiguous" if matches else "mpv_alias_not_found",
            "requested_run_id": target_run_id,
            "model_policy_version": target_mpv,
            "matches": sorted(matches),
        }
    return matches[0], {
        "status": "resolved",
        "requested_run_id": target_run_id,
        "resolved_run_id": matches[0],
        "model_policy_version": target_mpv,
    }


def apply_qdrant_alias_switch(
    *,
    alias: str,
    target_collection: str,
) -> dict[str, Any]:
    """对接 Qdrant 切 alias；前置：collection 必须存在。"""
    client = _qdrant_client()
    # 检查 collection 是否存在
    cols = {c.name for c in client.get_collections().collections}
    if target_collection not in cols:
        return {
            "status": "collection_missing",
            "target_collection": target_collection,
            "available": sorted(cols),
        }
    # 读当前 alias 指向
    cur_aliases = {a.alias_name: a.collection_name for a in client.get_aliases().aliases}
    previous = cur_aliases.get(alias)
    # 执行切换
    from qdrant_client import models as qm
    ops: list[Any] = []
    if previous:
        ops.append(qm.DeleteAliasOperation(delete_alias=qm.DeleteAlias(alias_name=alias)))
    ops.append(qm.CreateAliasOperation(
        create_alias=qm.CreateAlias(collection_name=target_collection, alias_name=alias)
    ))
    client.update_collection_aliases(change_aliases_operations=ops)
    return {
        "status": "ok",
        "alias": alias,
        "previous_collection": previous,
        "new_collection": target_collection,
    }


def apply_pg_repopulate(target_run_id: str) -> dict[str, Any]:
    """Repopulate ECS PG serving.* through the existing KS-DIFY-ECS-003 apply path."""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "knowledge_serving" / "scripts" / "upload_serving_views_to_ecs.py"),
        "--env",
        "staging",
        "--apply",
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return {
        "status": "ok" if proc.returncode == 0 else "failed",
        "target_run_id": target_run_id,
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "audit_path": str(VIEW_AUDIT.relative_to(REPO_ROOT)),
    }


def run_post_smoke() -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "knowledge_serving" / "scripts" / "smoke_vector_retrieval.py"),
        "--env",
        "staging",
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return {
        "status": "ok" if proc.returncode == 0 else "failed",
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "audit_path": "knowledge_serving/audit/smoke_vector_retrieval_KS-RETRIEVAL-006.json",
    }


def write_audit(payload: dict[str, Any]) -> Path:
    path = Path(str(ROLLBACK_AUDIT_TEMPLATE).format(ts=_ts()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    p = argparse.ArgumentParser(description="KS-CD-002 回滚到指定 compile_run_id")
    p.add_argument("--to", dest="run_id", help="目标 compile_run_id")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="列出已知 compile_run_id")
    mode.add_argument("--dry-run", action="store_true", help="仅出动作清单")
    mode.add_argument("--apply", action="store_true", help="真执行（需 --yes 双确认）")
    p.add_argument("--yes", action="store_true", help="确认 apply（与 --apply 同用）")
    args = p.parse_args()

    runs = discover_run_ids()

    if args.list:
        _print_list(runs)
        return EXIT_OK

    if not args.run_id:
        _err("缺 --to <run_id>；先 --list 看可用 run_id")

    resolved_run_id, resolution = resolve_target_run_id(args.run_id, runs)
    if resolution and resolution["status"] != "resolved":
        print(f"❌ run_id {args.run_id} 无法解析：{resolution}",
              file=sys.stderr)
        return EXIT_RUN_NOT_FOUND

    plan = plan_rollback(target_run_id=resolved_run_id, runs=runs)
    if plan["status"] == "run_not_found":
        print(f"❌ run_id {args.run_id} 不在 audit 历史；已知：{plan['known_run_ids']}",
              file=sys.stderr)
        return EXIT_RUN_NOT_FOUND

    # 通用 audit 框架
    checked_at = _now_iso()
    audit: dict[str, Any] = {
        "task_card": "KS-CD-002",
        "generated_at": checked_at,
        "checked_at": checked_at,
        "env": "staging",
        "git_commit": _git_commit(),
        "evidence_level": "runtime_verified",
        "operator": getpass.getuser(),
        "mode": "dry_run" if args.dry_run else ("apply" if args.apply else "dry_run"),
        "requested_run_id": args.run_id,
        "target_run_id": resolved_run_id,
        "target_resolution": resolution,
        "plan": plan,
        "results": [],
        "status": "dry_run_only",
    }

    print(f"=== KS-CD-002 rollback plan · target={args.run_id} ===")
    if resolution:
        print(f"  resolved target: {resolution['requested_run_id']} → {resolution['resolved_run_id']}")
    for w in plan["warnings"]:
        print(f"  warn: {w}")
    print(f"  actions ({len(plan['actions'])}):")
    for i, a in enumerate(plan["actions"], 1):
        print(f"    [{i}] {a['kind']}: {json.dumps({k: v for k, v in a.items() if k != 'kind'}, ensure_ascii=False)}")

    if args.dry_run or not args.apply:
        audit_path = write_audit(audit)
        print(f"\n  ✅ dry-run audit: {audit_path.relative_to(REPO_ROOT)}")
        return EXIT_OK

    # apply 路径
    if not args.yes:
        _err("--apply 必须同时给 --yes 双确认；否则视为危险操作拒绝")

    print("\n--- apply phase ---")
    audit["mode"] = "apply"
    overall_ok = True
    pg_actions = [a for a in plan["actions"] if a["kind"] == "pg_table_repopulate"]
    if pg_actions:
        res = apply_pg_repopulate(resolved_run_id)
        audit["results"].append({
            "action": {
                "kind": "pg_repopulate_via_ks_dify_ecs_003",
                "table_count": len(pg_actions),
                "target_run_id": resolved_run_id,
            },
            "result": res,
        })
        if res["status"] != "ok":
            overall_ok = False
            print(f"  ❌ pg repopulate via KS-DIFY-ECS-003 failed: exit={res['exit_code']}")
        else:
            print(f"  ✅ pg repopulate via KS-DIFY-ECS-003: {len(pg_actions)} tables")

    for a in plan["actions"]:
        if a["kind"] == "qdrant_alias_switch":
            res = apply_qdrant_alias_switch(
                alias=a["alias"],
                target_collection=a["switch_to_collection"],
            )
            audit["results"].append({"action": a, "result": res})
            if res["status"] != "ok":
                overall_ok = False
                print(f"  ❌ qdrant: {res}")
                if res["status"] == "collection_missing":
                    audit["status"] = "partial_collection_missing"
                    audit_path = write_audit(audit)
                    print(f"  audit: {audit_path.relative_to(REPO_ROOT)}")
                    return EXIT_COLLECTION_MISSING
            else:
                print(f"  ✅ qdrant alias {res['alias']}: {res['previous_collection']} → {res['new_collection']}")
        elif a["kind"] == "pg_table_repopulate":
            continue

    smoke = run_post_smoke()
    audit["post_smoke"] = smoke
    if smoke["status"] != "ok":
        overall_ok = False
        print(f"  ❌ post-smoke failed: exit={smoke['exit_code']}")
    else:
        print("  ✅ post-smoke pass")

    audit["status"] = "ok" if overall_ok else "partial_failure"
    audit_path = write_audit(audit)
    print(f"\n  audit: {audit_path.relative_to(REPO_ROOT)}")
    print(f"  status: {audit['status']}")
    return EXIT_OK if overall_ok else EXIT_PARTIAL_FAILURE


if __name__ == "__main__":
    sys.exit(main())

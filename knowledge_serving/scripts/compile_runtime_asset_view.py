#!/usr/bin/env python3
"""
KS-COMPILER-005 · compile_runtime_asset_view.py

把 clean_output/runtime_assets/runtime_asset_index.csv 投影为 runtime_asset_view.csv（plan §3.5）。
S gate：S1 source_traceability — source_pointer + traceability_status 全行非空。
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _common import (
    DEFAULT_AUDIT_DIR,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_NINE_TABLES_DIR,
    DEFAULT_SCHEMA_PATH,
    DEFAULT_VIEWS_DIR,
    REPO_ROOT,
    BRAND_LAYER_RE,
    CompileError,
    GOVERNANCE_FIELDS,
    GRANULARITY_ENUM,
    GovernanceContext,
    build_view_validator,
    derive_compile_run_id,
    derive_view_schema_version,
    load_manifest_hash,
    make_governance,
    safe_relative,
    sha256_bytes,
    sha256_text,
    validate_row,
    write_csv,
    write_log,
)

DEFAULT_REGISTER_CSV = REPO_ROOT / "clean_output" / "runtime_assets" / "runtime_asset_index.csv"
DEFAULT_OUTPUT_CSV = DEFAULT_VIEWS_DIR / "runtime_asset_view.csv"
DEFAULT_LOG_PATH = DEFAULT_AUDIT_DIR / "runtime_asset_view.compile.log"

# asset_type 允许枚举：从真实 register 观察 + 留余地。新增类型时必须在此显式登记。
ASSET_TYPE_ENUM = {"role_split", "action_template", "dialogue_template", "shot_template"}
ASSET_ID_RE = re.compile(r"^RA-[a-z0-9_\-]+$")

CSV_COLUMNS = GOVERNANCE_FIELDS + [
    "runtime_asset_id",
    "pack_id",
    "asset_type",
    "title",
    "summary",
    "content_pointer",
    "asset_payload_json",
    "source_pointer",
]

logger = logging.getLogger("compile_runtime_asset_view")


@dataclass
class CompileContext:
    register_csv: Path
    manifest_path: Path
    schema_path: Path
    output_csv: Path
    log_path: Path


def load_register(register_csv: Path) -> list[dict[str, Any]]:
    if not register_csv.exists():
        raise CompileError(f"runtime_asset_index 不存在 / missing: {register_csv}")
    rows: list[dict[str, Any]] = []
    with register_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            rows.append({k: (v or "").strip() for k, v in raw.items()})
    return rows


def build_row(reg: dict[str, Any], *, gctx: GovernanceContext) -> dict[str, Any]:
    rid = reg.get("runtime_asset_id", "")
    pack_id = reg.get("pack_id", "")
    if not rid:
        raise CompileError("缺 runtime_asset_id / missing")
    if not ASSET_ID_RE.match(rid):
        raise CompileError(f"非法 runtime_asset_id={rid!r}（应符 ^RA-...）")
    if not pack_id:
        raise CompileError(f"缺 pack_id (runtime_asset_id={rid})")

    asset_type = reg.get("asset_type", "")
    if asset_type not in ASSET_TYPE_ENUM:
        raise CompileError(
            f"非法 asset_type={asset_type!r} 不在登记枚举 {sorted(ASSET_TYPE_ENUM)} (runtime_asset_id={rid})"
        )

    title = reg.get("title", "")
    if not title:
        raise CompileError(f"缺 title (runtime_asset_id={rid})")
    summary = reg.get("summary", "")
    if not summary:
        raise CompileError(f"缺 summary (runtime_asset_id={rid})")

    source_pointer = reg.get("source_pointer", "")
    if not source_pointer:
        raise CompileError(f"S1 违例：缺 source_pointer (runtime_asset_id={rid})")

    brand_layer = reg.get("brand_layer", "")
    if not BRAND_LAYER_RE.match(brand_layer):
        raise CompileError(f"非法 brand_layer={brand_layer!r} (runtime_asset_id={rid})")
    granularity_layer = reg.get("granularity_layer", "")
    if granularity_layer not in GRANULARITY_ENUM:
        raise CompileError(f"非法 granularity_layer={granularity_layer!r} (runtime_asset_id={rid})")

    # content_pointer 与 source_pointer 同源（register 没有独立 content_pointer 字段）
    content_pointer = source_pointer
    # asset_payload_json：register 无结构化 payload；输出空 dict 保持 schema 合规
    asset_payload_json: dict[str, Any] = {}

    chunk_text = f"{title}\n{summary}\nasset_type:{asset_type}\nsource:{source_pointer}"
    chunk_text_hash = sha256_text(chunk_text)

    gov = make_governance(
        source_pack_id=pack_id,
        brand_layer=brand_layer,
        granularity_layer=granularity_layer,
        gate_status="active",
        source_table_refs=["runtime_asset_index.csv"],
        evidence_ids=[],
        # S1 硬门：source_pointer 在场（前面已 fail-closed），traceability=partial（有指针无直接 evidence link）
        traceability_status="partial",
        default_call_pool=False,
        review_status="approved",
        ctx=gctx,
        chunk_text_hash=chunk_text_hash,
    )
    row = dict(gov)
    row.update({
        "runtime_asset_id": rid,
        "pack_id": pack_id,
        "asset_type": asset_type,
        "title": title,
        "summary": summary,
        "content_pointer": content_pointer,
        "asset_payload_json": asset_payload_json,
        "source_pointer": source_pointer,
    })
    return row


def compile_runtime_asset_view(ctx: CompileContext) -> dict[str, Any]:
    schema = json.loads(ctx.schema_path.read_text(encoding="utf-8"))
    view_schema_version = derive_view_schema_version(ctx.schema_path)
    source_manifest_hash = load_manifest_hash(ctx.manifest_path)
    compile_run_id = derive_compile_run_id(source_manifest_hash, view_schema_version)
    gctx = GovernanceContext(
        compile_run_id=compile_run_id,
        source_manifest_hash=source_manifest_hash,
        view_schema_version=view_schema_version,
    )

    register = load_register(ctx.register_csv)
    seen: set[str] = set()
    validator = build_view_validator(schema, "runtime_asset_view")
    rows: list[dict[str, Any]] = []
    schema_errors: list[str] = []
    asset_type_breakdown: dict[str, int] = {}

    for reg in register:
        rid = reg.get("runtime_asset_id", "")
        if rid in seen:
            raise CompileError(f"重复 runtime_asset_id / duplicate: {rid}")
        if rid:
            seen.add(rid)
        row = build_row(reg, gctx=gctx)
        errs = validate_row(validator, row)
        if errs:
            schema_errors.append(f"{rid}: {'; '.join(errs)}")
            continue
        rows.append(row)
        asset_type_breakdown[row["asset_type"]] = asset_type_breakdown.get(row["asset_type"], 0) + 1

    if schema_errors:
        raise CompileError(
            "schema 校验失败:\n  " + "\n  ".join(schema_errors[:5])
        )

    rows.sort(key=lambda r: r["runtime_asset_id"])
    write_csv(ctx.output_csv, CSV_COLUMNS, rows)
    csv_sha256 = sha256_bytes(ctx.output_csv.read_bytes())

    return {
        "task_card": "KS-COMPILER-005",
        "register_rows_scanned": len(register),
        "rows_emitted": len(rows),
        "asset_type_breakdown": asset_type_breakdown,
        "source_manifest_hash": source_manifest_hash,
        "view_schema_version": view_schema_version,
        "compile_run_id": compile_run_id,
        "output_csv": safe_relative(ctx.output_csv),
        "output_csv_sha256": csv_sha256,
    }


def build_context(args: argparse.Namespace) -> CompileContext:
    return CompileContext(
        register_csv=Path(args.register).resolve(),
        manifest_path=Path(args.manifest).resolve(),
        schema_path=Path(args.schema).resolve(),
        output_csv=Path(args.output).resolve(),
        log_path=Path(args.log).resolve(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KS-COMPILER-005 · 编译 runtime_asset_view")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--register", default=str(DEFAULT_REGISTER_CSV))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--log", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    ctx = build_context(args)
    try:
        report = compile_runtime_asset_view(ctx)
    except CompileError as e:
        write_log({"task_card": "KS-COMPILER-005"}, ctx.log_path, ok=False, message=str(e))
        logger.error("compile failed: %s", e)
        return 2
    except Exception as e:  # noqa: BLE001
        write_log({"task_card": "KS-COMPILER-005"}, ctx.log_path, ok=False, message=f"unexpected: {e}")
        logger.exception("unexpected error")
        return 3

    write_log(report, ctx.log_path, ok=True)
    if report["rows_emitted"] == 0:
        logger.warning("emitted 0 rows (register=%d)", report["register_rows_scanned"])
    logger.info(
        "runtime_asset_view rows=%d breakdown=%s sha256=%s",
        report["rows_emitted"], report["asset_type_breakdown"],
        report["output_csv_sha256"][:12],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

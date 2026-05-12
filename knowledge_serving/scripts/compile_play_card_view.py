#!/usr/bin/env python3
"""
KS-COMPILER-004 · compile_play_card_view.py

把 clean_output/play_cards/play_card_register.csv 投影为 play_card_view.csv（plan §3.4）。
应用业务字段从对应 candidate pack 反查（FK 经由 pack_id）。

S gate：S6 play_card_completeness（completeness_status 全行非空）。

退出码：
  0  OK
  2  输入异常（重复 play_card_id / 非法 brand_layer / 断 FK / deprecated 包等）
  3  schema 校验失败
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

import yaml

from _common import (
    DEFAULT_AUDIT_DIR,
    DEFAULT_CANDIDATES_DIR,
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

DEFAULT_REGISTER_CSV = REPO_ROOT / "clean_output" / "play_cards" / "play_card_register.csv"
DEFAULT_OUTPUT_CSV = DEFAULT_VIEWS_DIR / "play_card_view.csv"
DEFAULT_LOG_PATH = DEFAULT_AUDIT_DIR / "play_card_view.compile.log"

COMPLETENESS_ENUM = {"complete", "partial", "stub"}

CSV_COLUMNS = GOVERNANCE_FIELDS + [
    "play_card_id",
    "pack_id",
    "content_type",
    "hook",
    "production_tier",
    "production_difficulty",
    "duration",
    "steps_json",
    "anti_pattern",
    "applicable_when",
    "success_scenario",
    "alternative_boundary",
    "completeness_status",
]

logger = logging.getLogger("compile_play_card_view")


@dataclass
class CompileContext:
    candidates_dir: Path
    nine_tables_dir: Path
    register_csv: Path
    manifest_path: Path
    schema_path: Path
    output_csv: Path
    log_path: Path
    include_inactive_pack: bool  # 默认 False：pack 不 active 则过滤对应 play card


# ---- candidate pack index ----

def derive_gate_status_for_pack(candidate: dict) -> str:
    """与 KS-COMPILER-001 一致的多租户 4 闸判定。"""
    gsc = candidate.get("gate_self_check") or {}
    brand_layer = (candidate.get("brand_layer") or "").strip()
    universal_keys = (
        "gate_1_closed_scenario",
        "gate_2_reverse_infer",
        "gate_4_production_feasible",
    )
    universal_pass = all((gsc.get(k) or "").strip() == "pass" for k in universal_keys)
    gate3 = (gsc.get("gate_3_rule_generalizable") or "").strip()
    if not universal_pass:
        return "draft"
    if brand_layer == "domain_general":
        return "active" if gate3 == "pass" else "draft"
    if gate3 in ("pass", "partial"):
        return "active"
    return "draft"


def load_candidate_index(candidates_dir: Path) -> dict[str, dict[str, Any]]:
    """pack_id -> {brand_layer, gate_status, applicable_when, success_scenario, alternative_boundary, evidence_ids, source_table_refs}"""
    index: dict[str, dict[str, Any]] = {}
    if not candidates_dir.exists():
        return index
    for fp in sorted(candidates_dir.rglob("*.yaml")):
        try:
            data = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise CompileError(f"YAML 解析失败: {fp}: {e}")
        if not isinstance(data, dict):
            continue
        pack_id = (data.get("pack_id") or "").strip()
        if not pack_id:
            continue
        scenario = data.get("scenario") or {}
        boundary = scenario.get("boundary") or {}
        result = scenario.get("result") or {}
        alt_path = scenario.get("alternative_path") or []
        applicable_when = (boundary.get("applicable_when") or "").strip()
        success = (result.get("success_pattern") or "").strip()
        not_applicable = (boundary.get("not_applicable_when") or "").strip()
        alt_path_str = "; ".join(str(p).strip() for p in alt_path if str(p).strip())
        alt_boundary_parts: list[str] = []
        if not_applicable:
            alt_boundary_parts.append(f"not_applicable_when: {not_applicable}")
        if alt_path_str:
            alt_boundary_parts.append(f"alternative_path: {alt_path_str}")
        alt_boundary = " | ".join(alt_boundary_parts)

        proj = data.get("nine_table_projection") or {}
        # evidence_ids
        evidence_ids = []
        for e in proj.get("evidence") or []:
            if isinstance(e, dict):
                eid = (e.get("evidence_id") or "").strip()
            elif isinstance(e, str):
                eid = e.strip()
            else:
                eid = ""
            if eid:
                evidence_ids.append(eid)
        # source_table_refs
        name_map = {
            "object_type": "01_object_type.csv",
            "field": "02_field.csv",
            "semantic": "03_semantic.csv",
            "value_set": "04_value_set.csv",
            "relation": "05_relation.csv",
            "rule": "06_rule.csv",
            "evidence": "07_evidence.csv",
            "lifecycle": "08_lifecycle.csv",
            "call_mapping": "09_call_mapping.csv",
        }
        source_table_refs = [
            fname for key, fname in name_map.items() if proj.get(key)
        ]

        index[pack_id] = {
            "brand_layer": (data.get("brand_layer") or "").strip(),
            "gate_status": derive_gate_status_for_pack(data),
            "applicable_when": applicable_when,
            "success_scenario": success,
            "alternative_boundary": alt_boundary,
            "evidence_ids": evidence_ids,
            "source_table_refs": source_table_refs,
        }
    return index


# ---- register loading ----

def load_register(register_csv: Path) -> list[dict[str, Any]]:
    if not register_csv.exists():
        raise CompileError(f"play_card_register 不存在 / missing: {register_csv}")
    rows: list[dict[str, Any]] = []
    with register_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            rows.append({k: (v or "").strip() for k, v in raw.items()})
    return rows


# ---- field derivation ----

CONTENT_TYPE_RE = re.compile(r"^PC-(?:[a-z_]+)-([a-z][a-z0-9_-]*?)(?:-[a-z][a-z0-9_-]*)*$")


def derive_content_type(play_card_id: str) -> str:
    """PC-<pack_type>-<slug>... → 取 slug 第一段当 content_type 暗示；不强校验。"""
    m = re.match(r"^PC-([a-z_]+)-(.+)$", play_card_id)
    if not m:
        return ""
    slug = m.group(2)
    # 取第一个 hyphen 分割块作为粗 content_type 提示
    first_seg = slug.split("-", 1)[0]
    return first_seg


def derive_completeness(
    steps_count: int,
    anti_pattern: str,
    applicable_when: str,
    success_scenario: str,
    alternative_boundary: str,
) -> str:
    """五字段齐 → complete；缺 1-2 → partial；缺更多 → stub。

    注：schema enum 为 complete/partial/stub（不是 missing）。
    steps_count > 0 视为 steps_json 字段"在场"（即使我们 emit 的 steps_json 是 []，因为 register
    没有结构化 steps）。
    """
    presence = [
        steps_count > 0,
        bool(anti_pattern),
        bool(applicable_when),
        bool(success_scenario),
        bool(alternative_boundary),
    ]
    n = sum(presence)
    if n == 5:
        return "complete"
    if n >= 3:
        return "partial"
    return "stub"


def build_row(
    register_row: dict[str, Any],
    pack_meta: dict[str, Any] | None,
    *,
    gctx: GovernanceContext,
) -> dict[str, Any]:
    play_card_id = register_row.get("play_card_id", "")
    pack_id = register_row.get("pack_id", "")
    if not play_card_id:
        raise CompileError("缺 play_card_id / missing")
    if not pack_id:
        raise CompileError(f"缺 pack_id / missing (play_card_id={play_card_id})")

    brand_layer = register_row.get("brand_layer", "")
    if not BRAND_LAYER_RE.match(brand_layer):
        raise CompileError(
            f"非法 brand_layer / invalid={brand_layer!r} (play_card_id={play_card_id})"
        )
    granularity_layer = register_row.get("granularity_layer", "")
    if granularity_layer not in GRANULARITY_ENUM:
        raise CompileError(
            f"非法 granularity_layer={granularity_layer!r} (play_card_id={play_card_id})"
        )

    if pack_meta is None:
        raise CompileError(
            f"断 FK / dangling pack_id={pack_id} (play_card_id={play_card_id}) — 不在 candidate 索引"
        )

    applicable_when = pack_meta["applicable_when"]
    success = pack_meta["success_scenario"]
    alt_boundary = pack_meta["alternative_boundary"]
    anti_pattern = register_row.get("anti_pattern", "")
    hook = register_row.get("hook", "")
    duration = register_row.get("duration", "")
    production_tier = register_row.get("production_tier", "")
    production_difficulty = register_row.get("production_difficulty", "")
    try:
        steps_count = int(register_row.get("steps_count") or 0)
    except ValueError:
        steps_count = 0

    # steps_json：register 没有结构化 steps，按 steps_count 占位生成稳定占位（不 fake 内容）
    steps_json = [{"step_index": i + 1} for i in range(steps_count)]

    completeness = derive_completeness(
        steps_count, anti_pattern, applicable_when, success, alt_boundary
    )

    content_type = derive_content_type(play_card_id)

    source_table_refs = ["play_card_register.csv"] + pack_meta["source_table_refs"]
    # 去重保序
    seen: set[str] = set()
    source_table_refs = [x for x in source_table_refs if not (x in seen or seen.add(x))]

    evidence_ids = list(pack_meta["evidence_ids"])
    traceability = "partial" if evidence_ids else "weak"

    default_call_pool_raw = (register_row.get("default_call_pool") or "").strip().lower()
    default_call_pool = default_call_pool_raw in ("true", "1", "yes")

    chunk_text = f"hook: {hook}\nanti_pattern: {anti_pattern}\nhook_slug: {play_card_id}"
    chunk_text_hash = sha256_text(chunk_text)

    gov = make_governance(
        source_pack_id=pack_id,
        brand_layer=brand_layer,
        granularity_layer=granularity_layer,
        gate_status="active",
        source_table_refs=source_table_refs,
        evidence_ids=evidence_ids,
        traceability_status=traceability,
        default_call_pool=default_call_pool,
        review_status="approved",
        ctx=gctx,
        chunk_text_hash=chunk_text_hash,
    )

    row = dict(gov)
    row.update({
        "play_card_id": play_card_id,
        "pack_id": pack_id,
        "content_type": content_type,
        "hook": hook,
        "production_tier": production_tier,
        "production_difficulty": production_difficulty,
        "duration": duration,
        "steps_json": steps_json,
        "anti_pattern": anti_pattern,
        "applicable_when": applicable_when,
        "success_scenario": success,
        "alternative_boundary": alt_boundary,
        "completeness_status": completeness,
    })
    return row


def compile_play_card_view(ctx: CompileContext) -> dict[str, Any]:
    schema = json.loads(ctx.schema_path.read_text(encoding="utf-8"))
    view_schema_version = derive_view_schema_version(ctx.schema_path)
    source_manifest_hash = load_manifest_hash(ctx.manifest_path)
    compile_run_id = derive_compile_run_id(source_manifest_hash, view_schema_version)
    gctx = GovernanceContext(
        compile_run_id=compile_run_id,
        source_manifest_hash=source_manifest_hash,
        view_schema_version=view_schema_version,
    )

    pack_index = load_candidate_index(ctx.candidates_dir)
    register = load_register(ctx.register_csv)

    seen_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    filtered_inactive = 0
    warnings: list[str] = []
    validator = build_view_validator(schema, "play_card_view")
    schema_errors: list[str] = []

    for reg in register:
        pc_id = reg.get("play_card_id", "")
        if not pc_id:
            raise CompileError("register 行缺 play_card_id")
        if pc_id in seen_ids:
            raise CompileError(f"重复 play_card_id / duplicate: {pc_id}")
        seen_ids.add(pc_id)

        pack_id = reg.get("pack_id", "")
        pack_meta = pack_index.get(pack_id)
        if pack_meta is None:
            raise CompileError(
                f"断 FK / dangling pack_id={pack_id} (play_card_id={pc_id})"
            )
        if pack_meta["gate_status"] != "active" and not ctx.include_inactive_pack:
            filtered_inactive += 1
            warnings.append(f"过滤 deprecated/inactive pack 的 play card: {pc_id} (pack_gate={pack_meta['gate_status']})")
            continue

        row = build_row(reg, pack_meta, gctx=gctx)
        errs = validate_row(validator, row)
        if errs:
            schema_errors.append(f"{pc_id}: {'; '.join(errs)}")
            continue
        rows.append(row)

    if schema_errors:
        raise CompileError(
            "schema 校验失败 / schema validation failed:\n  " + "\n  ".join(schema_errors[:5])
        )

    rows.sort(key=lambda r: r["play_card_id"])
    write_csv(ctx.output_csv, CSV_COLUMNS, rows)
    csv_sha256 = sha256_bytes(ctx.output_csv.read_bytes())

    breakdown = {"complete": 0, "partial": 0, "stub": 0}
    for r in rows:
        breakdown[r["completeness_status"]] += 1

    return {
        "task_card": "KS-COMPILER-004",
        "register_rows_scanned": len(register),
        "rows_emitted": len(rows),
        "filtered_inactive_pack": filtered_inactive,
        "completeness_breakdown": breakdown,
        "warnings": warnings,
        "warnings_count": len(warnings),
        "source_manifest_hash": source_manifest_hash,
        "view_schema_version": view_schema_version,
        "compile_run_id": compile_run_id,
        "output_csv": safe_relative(ctx.output_csv),
        "output_csv_sha256": csv_sha256,
    }


def build_context(args: argparse.Namespace) -> CompileContext:
    return CompileContext(
        candidates_dir=Path(args.candidates_dir).resolve(),
        nine_tables_dir=Path(args.nine_tables_dir).resolve(),
        register_csv=Path(args.register).resolve(),
        manifest_path=Path(args.manifest).resolve(),
        schema_path=Path(args.schema).resolve(),
        output_csv=Path(args.output).resolve(),
        log_path=Path(args.log).resolve(),
        include_inactive_pack=args.include_inactive_pack,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KS-COMPILER-004 · 编译 play_card_view")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--candidates-dir", default=str(DEFAULT_CANDIDATES_DIR))
    parser.add_argument("--nine-tables-dir", default=str(DEFAULT_NINE_TABLES_DIR))
    parser.add_argument("--register", default=str(DEFAULT_REGISTER_CSV))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--log", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--include-inactive-pack", action="store_true",
                        help="包含 pack gate_status≠active 的 play card（默认过滤）")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    ctx = build_context(args)
    try:
        report = compile_play_card_view(ctx)
    except CompileError as e:
        write_log({"task_card": "KS-COMPILER-004"}, ctx.log_path, ok=False, message=str(e))
        logger.error("compile failed: %s", e)
        return 2
    except Exception as e:  # noqa: BLE001
        write_log({"task_card": "KS-COMPILER-004"}, ctx.log_path, ok=False, message=f"unexpected: {e}")
        logger.exception("unexpected error")
        return 3

    write_log(report, ctx.log_path, ok=True)
    if report["rows_emitted"] == 0:
        logger.warning("emitted 0 rows (register=%d)", report["register_rows_scanned"])
    logger.info(
        "play_card_view rows=%d filtered_inactive_pack=%d breakdown=%s sha256=%s",
        report["rows_emitted"],
        report["filtered_inactive_pack"],
        report["completeness_breakdown"],
        report["output_csv_sha256"][:12],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
KS-COMPILER-002 · compile_content_type_view.py

把 knowledge_serving/control/content_type_canonical.csv（KS-S0-005 落盘的 canonical 注册表）
+ candidates 的 runtime_method 投影，编译成 content_type_view.csv（plan §3.2）。

驱动源 / driving source：content_type_canonical.csv 是 canonical_content_type_id 唯一来源；
candidates 仅作 source_pack_ids 聚合参考，不允许新增 canonical id。

退出码 / exit codes：
  0  正常 / OK（含 warning）
  2  输入异常 / input invalid（canonical id 漂移 / 重复 / 非法 / 18 类不全 + 严格模式）
  3  schema 校验失败 / schema validation failed
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
    DEFAULT_CONTROL_DIR,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_NINE_TABLES_DIR,
    DEFAULT_SCHEMA_PATH,
    DEFAULT_VIEWS_DIR,
    REPO_ROOT,
    CompileError,
    GOVERNANCE_FIELDS,
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

DEFAULT_CANONICAL_CSV = DEFAULT_CONTROL_DIR / "content_type_canonical.csv"
DEFAULT_OUTPUT_CSV = DEFAULT_VIEWS_DIR / "content_type_view.csv"
DEFAULT_LOG_PATH = DEFAULT_AUDIT_DIR / "content_type_view.compile.log"

CANONICAL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
COVERAGE_ENUM = {"complete", "partial", "missing"}
RISK_LEVEL_ENUM = {"low", "medium", "high"}
BRAND_OVERLAY_LEVEL_ENUM = {"none", "soft", "hard"}

EXPECTED_CANONICAL_ROWS = 18  # task card §6 "18 类不全 → warning"

CSV_COLUMNS = GOVERNANCE_FIELDS + [
    "content_type",
    "canonical_content_type_id",
    "aliases",
    "production_mode",
    "north_star",
    "default_output_formats",
    "default_platforms",
    "recommended_persona_roles",
    "risk_level",
    "brand_overlay_required_level",
    "required_knowledge_layers",
    "forbidden_patterns",
    "source_pack_ids",
    "coverage_status",
]

logger = logging.getLogger("compile_content_type_view")


@dataclass
class CompileContext:
    candidates_dir: Path
    nine_tables_dir: Path
    canonical_csv: Path
    manifest_path: Path
    schema_path: Path
    output_csv: Path
    log_path: Path
    strict_completeness: bool  # 若 True，canonical 行数 < 18 直接 fail


def load_canonical_rows(canonical_csv: Path) -> list[dict[str, Any]]:
    if not canonical_csv.exists():
        raise CompileError(f"canonical csv 不存在 / missing: {canonical_csv}")
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with canonical_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            cid = (raw.get("canonical_content_type_id") or "").strip()
            if not cid:
                raise CompileError(f"canonical row 缺 canonical_content_type_id: {raw}")
            if not CANONICAL_ID_RE.match(cid):
                raise CompileError(
                    f"canonical_content_type_id 漂移 / drift: {cid!r} 不符 ^[a-z][a-z0-9_]*$"
                )
            if cid in seen_ids:
                raise CompileError(f"canonical_content_type_id 重复 / duplicate: {cid}")
            seen_ids.add(cid)

            coverage_raw = (raw.get("coverage_status") or "").strip()
            if coverage_raw and coverage_raw not in COVERAGE_ENUM:
                # 不是 fatal，但提示：register 里的 coverage_status 字段无效
                logger.warning(
                    "canonical row %s coverage_status 非枚举: %r — 将在 derive 时覆盖",
                    cid, coverage_raw,
                )

            aliases_str = (raw.get("aliases") or "").strip()
            aliases = [a.strip() for a in aliases_str.split("|") if a.strip()] if aliases_str else []
            rows.append({
                "canonical_content_type_id": cid,
                "name_zh": (raw.get("name_zh") or "").strip(),
                "name_en": (raw.get("name_en") or "").strip(),
                "aliases": aliases,
                "register_coverage_status": coverage_raw or None,
            })
    return rows


def build_alias_index(canonical_rows: list[dict[str, Any]]) -> dict[str, str]:
    """所有 alias（含 canonical_id 自身、name_zh、name_en）→ canonical_id 反查表（小写）。"""
    index: dict[str, str] = {}
    for r in canonical_rows:
        cid = r["canonical_content_type_id"]
        keys = {cid, r["name_zh"], r["name_en"]} | set(r["aliases"])
        for k in keys:
            if k:
                index[k.lower()] = cid
    return index


def scan_candidates(candidates_dir: Path) -> list[tuple[Path, dict]]:
    out: list[tuple[Path, dict]] = []
    if not candidates_dir.exists():
        return out
    for fp in sorted(candidates_dir.rglob("*.yaml")):
        try:
            data = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise CompileError(f"YAML 解析失败: {fp}: {e}")
        if not isinstance(data, dict):
            raise CompileError(f"candidate 顶层非 dict: {fp}")
        out.append((fp, data))
    return out


def derive_coverage(num_packs: int) -> str:
    if num_packs == 0:
        return "missing"
    if num_packs >= 10:
        return "complete"
    return "partial"


def derive_traceability(num_packs: int) -> str:
    return "missing" if num_packs == 0 else "partial"


def aggregate_source_packs(
    canonical_rows: list[dict[str, Any]],
    candidates: list[tuple[Path, dict]],
    alias_index: dict[str, str],
) -> tuple[dict[str, list[str]], list[str]]:
    """
    扫 candidates 的 nine_table_projection.call_mapping[].runtime_method，
    若小写值命中 alias_index，归到对应 canonical_id 的 source_pack_ids。

    返回 (canonical_id -> sorted pack_ids list, 未登记别名 warning 列表)。
    """
    bucket: dict[str, set[str]] = {r["canonical_content_type_id"]: set() for r in canonical_rows}
    canonical_ids = set(bucket)
    unregistered: dict[str, set[str]] = {}  # alias -> set of pack_ids that used it
    for fp, data in candidates:
        pack_id = (data.get("pack_id") or "").strip()
        if not pack_id:
            continue
        for cid in extract_content_type_ids(data, canonical_ids):
            bucket[cid].add(pack_id)

        proj_cm = (data.get("nine_table_projection") or {}).get("call_mapping") or []
        runtime_methods: list[str] = []
        for cm in proj_cm:
            if isinstance(cm, dict):
                rm = (cm.get("runtime_method") or "").strip()
                if rm:
                    runtime_methods.append(rm)
                runtime_methods.extend(extract_content_type_tokens(cm.get("input_types"), canonical_ids))
            # bare-string call_mapping 是 mapping_id（如 CM-xxx），不含独立 runtime_method 字段 → 跳过
        # 兼容 candidate 顶层 content_type / content_type_tag（如有）
        for k in ("content_type", "content_type_tag"):
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                runtime_methods.append(v.strip())
            elif isinstance(v, list):
                runtime_methods.extend([str(x).strip() for x in v if str(x).strip()])

        for rm in runtime_methods:
            key = rm.lower()
            if key in alias_index:
                cid = alias_index[key]
                bucket[cid].add(pack_id)
            else:
                unregistered.setdefault(rm, set()).add(pack_id)
    aggregated = {cid: sorted(pids) for cid, pids in bucket.items()}
    warnings = sorted(
        f"未登记别名 / unregistered alias: {alias!r} (used by {sorted(pids)[:3]})"
        for alias, pids in unregistered.items()
    )
    return aggregated, warnings


def normalize_content_type_token(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def add_if_canonical(out: set[str], value: Any, canonical_ids: set[str]) -> None:
    if isinstance(value, str):
        token = normalize_content_type_token(value)
        if token in canonical_ids:
            out.add(token)


def extract_content_type_tokens(value: Any, canonical_ids: set[str]) -> set[str]:
    out: set[str] = set()
    if isinstance(value, str):
        for match in re.findall(r"ContentType\s*=\s*([A-Za-z0-9_-]+)", value):
            add_if_canonical(out, match, canonical_ids)
    elif isinstance(value, list):
        for item in value:
            out.update(extract_content_type_tokens(item, canonical_ids))
    elif isinstance(value, dict):
        for item in value.values():
            out.update(extract_content_type_tokens(item, canonical_ids))
    return out


def extract_content_type_ids(data: dict[str, Any], canonical_ids: set[str]) -> set[str]:
    """从候选包真实投影中采集 content_type 覆盖 / collect real content-type coverage.

    来源只限当前 candidate 的结构化字段：pack_id 北极星命名、relation.properties_json、
    call_mapping.input_types 中的 ContentType=<id>。不凭自然语言正文猜测。
    """
    out: set[str] = set()
    pack_id = str(data.get("pack_id") or "")
    marker = "content-type-north-star-"
    if marker in pack_id:
        add_if_canonical(out, pack_id.split(marker, 1)[1], canonical_ids)

    relations = (data.get("nine_table_projection") or {}).get("relation") or []
    for rel in relations:
        if not isinstance(rel, dict) or rel.get("relation_kind") != "compatible_with_content_type":
            continue
        raw = rel.get("properties_json")
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            props = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for key in ("content_type_id", "source_ct"):
            add_if_canonical(out, props.get(key), canonical_ids)
        for key in ("applies_to", "cross_ct_applicable", "content_types"):
            vals = props.get(key)
            if isinstance(vals, list):
                for val in vals:
                    add_if_canonical(out, val, canonical_ids)
    return out


def build_row(
    canonical: dict[str, Any],
    source_pack_ids: list[str],
    *,
    gctx: GovernanceContext,
) -> dict[str, Any]:
    cid = canonical["canonical_content_type_id"]
    aliases = list(canonical["aliases"])
    name_en = canonical["name_en"] or cid

    coverage_status = derive_coverage(len(source_pack_ids))
    if coverage_status not in COVERAGE_ENUM:
        raise CompileError(f"derived coverage_status 非枚举: {coverage_status}")

    traceability = derive_traceability(len(source_pack_ids))

    # 派生 chunk_text_hash: 组合 cid + name + aliases，足够稳定可幂等
    chunk_text = "\n".join([
        f"canonical_id: {cid}",
        f"name_zh: {canonical['name_zh']}",
        f"name_en: {name_en}",
        f"aliases: {'|'.join(aliases)}",
    ])
    chunk_text_hash = sha256_text(chunk_text)

    gov = make_governance(
        source_pack_id=f"CT-{cid}",
        brand_layer="domain_general",
        granularity_layer="L1",
        gate_status="active",
        source_table_refs=["content_type_canonical.csv"],
        evidence_ids=[],
        traceability_status=traceability,
        default_call_pool=bool(source_pack_ids),
        review_status="approved",
        ctx=gctx,
        chunk_text_hash=chunk_text_hash,
    )

    row = dict(gov)
    row.update({
        "content_type": name_en,
        "canonical_content_type_id": cid,
        "aliases": aliases,
        # 以下 8 字段当前没有结构化来源 / no structured source yet → 显式默认（诚实揭示，非 fake fill）
        # 后续可由独立的 content_type metadata 卡补齐
        "production_mode": "",
        "north_star": "",
        "default_output_formats": [],
        "default_platforms": [],
        "recommended_persona_roles": [],
        "risk_level": "medium",
        "brand_overlay_required_level": "soft",
        "required_knowledge_layers": [],
        "forbidden_patterns": [],
        "source_pack_ids": source_pack_ids,
        "coverage_status": coverage_status,
    })
    return row


def compile_content_type_view(ctx: CompileContext) -> dict[str, Any]:
    schema = json.loads(ctx.schema_path.read_text(encoding="utf-8"))
    view_schema_version = derive_view_schema_version(ctx.schema_path)
    source_manifest_hash = load_manifest_hash(ctx.manifest_path)
    compile_run_id = derive_compile_run_id(source_manifest_hash, view_schema_version)
    gctx = GovernanceContext(
        compile_run_id=compile_run_id,
        source_manifest_hash=source_manifest_hash,
        view_schema_version=view_schema_version,
    )

    canonical_rows = load_canonical_rows(ctx.canonical_csv)
    canonical_count = len(canonical_rows)
    warnings: list[str] = []
    if canonical_count != EXPECTED_CANONICAL_ROWS:
        msg = f"canonical 行数 {canonical_count} ≠ 期望 {EXPECTED_CANONICAL_ROWS}（18 类不全）"
        warnings.append(msg)
        if ctx.strict_completeness:
            raise CompileError(msg)
        logger.warning(msg)

    candidates = scan_candidates(ctx.candidates_dir)
    alias_index = build_alias_index(canonical_rows)
    aggregated, alias_warnings = aggregate_source_packs(canonical_rows, candidates, alias_index)
    warnings.extend(alias_warnings)
    for w in alias_warnings:
        logger.warning(w)

    validator = build_view_validator(schema, "content_type_view")
    rows: list[dict[str, Any]] = []
    schema_errors: list[str] = []
    for canonical in canonical_rows:
        cid = canonical["canonical_content_type_id"]
        spids = aggregated.get(cid, [])
        row = build_row(canonical, spids, gctx=gctx)
        errs = validate_row(validator, row)
        if errs:
            schema_errors.append(f"{cid}: {'; '.join(errs)}")
            continue
        rows.append(row)

    if schema_errors:
        raise CompileError(
            "schema 校验失败 / schema validation failed:\n  " + "\n  ".join(schema_errors[:5])
        )

    rows.sort(key=lambda r: r["canonical_content_type_id"])
    write_csv(ctx.output_csv, CSV_COLUMNS, rows)
    csv_sha256 = sha256_bytes(ctx.output_csv.read_bytes())

    coverage_breakdown = {"complete": 0, "partial": 0, "missing": 0}
    for r in rows:
        coverage_breakdown[r["coverage_status"]] += 1

    return {
        "task_card": "KS-COMPILER-002",
        "canonical_rows_scanned": canonical_count,
        "rows_emitted": len(rows),
        "coverage_breakdown": coverage_breakdown,
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
        canonical_csv=Path(args.canonical).resolve(),
        manifest_path=Path(args.manifest).resolve(),
        schema_path=Path(args.schema).resolve(),
        output_csv=Path(args.output).resolve(),
        log_path=Path(args.log).resolve(),
        strict_completeness=args.strict_completeness,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="KS-COMPILER-002 · 编译 content_type_view 服务读模型 / compile content_type_view"
    )
    parser.add_argument("--check", action="store_true", help="CI 默认入口 / CI entrypoint")
    parser.add_argument("--candidates-dir", default=str(DEFAULT_CANDIDATES_DIR))
    parser.add_argument("--nine-tables-dir", default=str(DEFAULT_NINE_TABLES_DIR))
    parser.add_argument("--canonical", default=str(DEFAULT_CANONICAL_CSV))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--log", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--strict-completeness", action="store_true", help="canonical 行数 ≠ 18 直接 fail")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    ctx = build_context(args)
    try:
        report = compile_content_type_view(ctx)
    except CompileError as e:
        write_log({"task_card": "KS-COMPILER-002"}, ctx.log_path, ok=False, message=str(e))
        logger.error("compile failed: %s", e)
        return 2
    except Exception as e:  # noqa: BLE001
        write_log({"task_card": "KS-COMPILER-002"}, ctx.log_path, ok=False, message=f"unexpected: {e}")
        logger.exception("unexpected error")
        return 3

    write_log(report, ctx.log_path, ok=True)
    logger.info(
        "content_type_view rows=%d coverage=%s warnings=%d sha256=%s",
        report["rows_emitted"],
        report["coverage_breakdown"],
        report["warnings_count"],
        report["output_csv_sha256"][:12],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

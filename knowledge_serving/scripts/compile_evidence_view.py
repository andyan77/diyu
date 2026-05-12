#!/usr/bin/env python3
"""
KS-COMPILER-007 · compile_evidence_view.py

把 clean_output/nine_tables/07_evidence.csv 投影为 evidence_view.csv（plan §3.7）。
S gate：S5 evidence_linkage — evidence_id 唯一 + inference_level / trace_quality 全填。
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
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
    BRAND_LAYER_RE,
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

DEFAULT_EVIDENCE_CSV = DEFAULT_NINE_TABLES_DIR / "07_evidence.csv"
DEFAULT_OUTPUT_CSV = DEFAULT_VIEWS_DIR / "evidence_view.csv"
DEFAULT_LOG_PATH = DEFAULT_AUDIT_DIR / "evidence_view.compile.log"

INFERENCE_LEVEL_ENUM = {
    "direct_quote",
    "paraphrase_high",
    "paraphrase_mid",
    "paraphrase_low",
    "inferred",
}
TRACE_QUALITY_ENUM = {"high", "mid", "low"}

# 候选写到 9 表时使用的 inference_level 取值历史上有非 schema 枚举（'low'），
# 这里做显式语义映射，避免假绿；新增映射必须在此显式登记。
INFERENCE_LEVEL_NORMALIZE = {
    "low": "paraphrase_low",
}

CSV_COLUMNS = GOVERNANCE_FIELDS + [
    "evidence_id",
    "source_md",
    "source_anchor",
    "evidence_quote",
    "source_type",
    "inference_level",
    "trace_quality",
    "line_no",
    "adjudication_status",
]

logger = logging.getLogger("compile_evidence_view")


@dataclass
class CompileContext:
    evidence_csv: Path
    manifest_path: Path
    schema_path: Path
    output_csv: Path
    log_path: Path


def load_evidence_rows(evidence_csv: Path) -> list[dict[str, str]]:
    if not evidence_csv.exists():
        raise CompileError(f"07_evidence.csv 不存在 / missing: {evidence_csv}")
    with evidence_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{k: (v or "").strip() for k, v in r.items()} for r in reader]


def normalize_inference_level(raw: str, evidence_id: str) -> str:
    raw = (raw or "").strip()
    if raw in INFERENCE_LEVEL_ENUM:
        return raw
    if raw in INFERENCE_LEVEL_NORMALIZE:
        return INFERENCE_LEVEL_NORMALIZE[raw]
    raise CompileError(
        f"inference_level={raw!r} 非枚举且无登记映射 (evidence_id={evidence_id}) "
        f"— 期望 {sorted(INFERENCE_LEVEL_ENUM)} 之一"
    )


def derive_trace_quality(inference_level: str) -> str:
    if inference_level in ("direct_quote", "paraphrase_high"):
        return "high"
    if inference_level == "paraphrase_mid":
        return "mid"
    # paraphrase_low / inferred → low
    return "low"


def derive_traceability_status(inference_level: str) -> str:
    if inference_level == "direct_quote":
        return "full"
    if inference_level in ("paraphrase_high", "paraphrase_mid"):
        return "partial"
    return "weak"


def build_row(raw: dict[str, str], *, gctx: GovernanceContext) -> dict[str, Any]:
    eid = raw.get("evidence_id", "")
    if not eid:
        raise CompileError("缺 evidence_id / missing")
    source_md = raw.get("source_md", "")
    if not source_md:
        raise CompileError(f"S5 违例：缺 source_md (evidence_id={eid})")
    quote = raw.get("evidence_quote", "")
    if not quote:
        raise CompileError(f"缺 evidence_quote (evidence_id={eid})")
    pack_id = raw.get("source_pack_id", "")
    if not pack_id:
        raise CompileError(f"缺 source_pack_id (evidence_id={eid})")
    brand_layer = raw.get("brand_layer", "")
    if not BRAND_LAYER_RE.match(brand_layer):
        raise CompileError(f"非法 brand_layer={brand_layer!r} (evidence_id={eid})")

    inference_level = normalize_inference_level(raw.get("inference_level", ""), eid)
    trace_quality = derive_trace_quality(inference_level)
    if trace_quality not in TRACE_QUALITY_ENUM:
        raise CompileError(f"derived trace_quality 非枚举: {trace_quality} (evidence_id={eid})")

    line_no_raw = raw.get("line_no", "")
    try:
        line_no = int(line_no_raw) if line_no_raw else 0
    except ValueError:
        line_no = 0
    if line_no < 0:
        line_no = 0  # schema 要求 minimum 0；源中 -1 占位标记按 0 入

    chunk_text = f"{source_md}#{raw.get('source_anchor','')}\n{quote}"
    chunk_text_hash = sha256_text(chunk_text)

    gov = make_governance(
        source_pack_id=pack_id,
        brand_layer=brand_layer,
        granularity_layer="L1",  # evidence 是最细粒度支撑层
        gate_status="active",
        source_table_refs=["07_evidence.csv"],
        evidence_ids=[eid],  # self-ref
        traceability_status=derive_traceability_status(inference_level),
        default_call_pool=False,
        review_status="approved",
        ctx=gctx,
        chunk_text_hash=chunk_text_hash,
    )
    row = dict(gov)
    row.update({
        "evidence_id": eid,
        "source_md": source_md,
        "source_anchor": raw.get("source_anchor", ""),
        "evidence_quote": quote,
        "source_type": raw.get("source_type", ""),
        "inference_level": inference_level,
        "trace_quality": trace_quality,
        "line_no": line_no,
        "adjudication_status": "approved",
    })
    return row


def compile_evidence_view(ctx: CompileContext) -> dict[str, Any]:
    schema = json.loads(ctx.schema_path.read_text(encoding="utf-8"))
    view_schema_version = derive_view_schema_version(ctx.schema_path)
    source_manifest_hash = load_manifest_hash(ctx.manifest_path)
    compile_run_id = derive_compile_run_id(source_manifest_hash, view_schema_version)
    gctx = GovernanceContext(
        compile_run_id=compile_run_id,
        source_manifest_hash=source_manifest_hash,
        view_schema_version=view_schema_version,
    )

    evidences = load_evidence_rows(ctx.evidence_csv)
    if not evidences:
        # §6 + S5：空源表直接 fail
        raise CompileError("S5 违例：07_evidence.csv 空表 — evidence_linkage 无法建立")

    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    validator = build_view_validator(schema, "evidence_view")
    schema_errors: list[str] = []
    inf_level_breakdown: dict[str, int] = {}

    for ev in evidences:
        eid = ev.get("evidence_id", "")
        if eid in seen:
            raise CompileError(f"重复 evidence_id / duplicate: {eid}")
        if eid:
            seen.add(eid)
        row = build_row(ev, gctx=gctx)
        errs = validate_row(validator, row)
        if errs:
            schema_errors.append(f"{eid}: {'; '.join(errs)}")
            continue
        rows.append(row)
        inf_level_breakdown[row["inference_level"]] = inf_level_breakdown.get(row["inference_level"], 0) + 1

    if schema_errors:
        raise CompileError(
            "schema 校验失败:\n  " + "\n  ".join(schema_errors[:5])
        )

    rows.sort(key=lambda r: r["evidence_id"])
    write_csv(ctx.output_csv, CSV_COLUMNS, rows)
    csv_sha256 = sha256_bytes(ctx.output_csv.read_bytes())

    return {
        "task_card": "KS-COMPILER-007",
        "evidence_rows_scanned": len(evidences),
        "rows_emitted": len(rows),
        "inference_level_breakdown": inf_level_breakdown,
        "source_manifest_hash": source_manifest_hash,
        "view_schema_version": view_schema_version,
        "compile_run_id": compile_run_id,
        "output_csv": safe_relative(ctx.output_csv),
        "output_csv_sha256": csv_sha256,
    }


def build_context(args: argparse.Namespace) -> CompileContext:
    return CompileContext(
        evidence_csv=Path(args.evidence).resolve(),
        manifest_path=Path(args.manifest).resolve(),
        schema_path=Path(args.schema).resolve(),
        output_csv=Path(args.output).resolve(),
        log_path=Path(args.log).resolve(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KS-COMPILER-007 · 编译 evidence_view")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--evidence", default=str(DEFAULT_EVIDENCE_CSV))
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
        report = compile_evidence_view(ctx)
    except CompileError as e:
        write_log({"task_card": "KS-COMPILER-007"}, ctx.log_path, ok=False, message=str(e))
        logger.error("compile failed: %s", e)
        return 2
    except Exception as e:  # noqa: BLE001
        write_log({"task_card": "KS-COMPILER-007"}, ctx.log_path, ok=False, message=f"unexpected: {e}")
        logger.exception("unexpected error")
        return 3

    write_log(report, ctx.log_path, ok=True)
    logger.info(
        "evidence_view rows=%d inf_levels=%s sha256=%s",
        report["rows_emitted"], report["inference_level_breakdown"],
        report["output_csv_sha256"][:12],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

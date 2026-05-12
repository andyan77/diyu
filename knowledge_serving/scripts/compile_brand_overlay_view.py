#!/usr/bin/env python3
"""
KS-COMPILER-006 · compile_brand_overlay_view.py

把 clean_output/candidates/brand_*/ 与 needs_review/ 下的 brand_<name> 候选投影为
brand_overlay_view.csv（plan §3.6）。

S gate：S3 brand_layer_scope。
红线（CLAUDE.md 多租户）：
  - brand_layer 不得为 domain_general
  - overlay 只承载 brand_voice / founder_persona / team_persona_overlay / content_type_overlay 4 类
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from _common import (
    DEFAULT_AUDIT_DIR,
    DEFAULT_CANDIDATES_DIR,
    DEFAULT_MANIFEST_PATH,
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

DEFAULT_OUTPUT_CSV = DEFAULT_VIEWS_DIR / "brand_overlay_view.csv"
DEFAULT_LOG_PATH = DEFAULT_AUDIT_DIR / "brand_overlay_view.compile.log"

BRAND_OVERLAY_KIND_ENUM = {
    "brand_voice",
    "founder_persona",
    "team_persona_overlay",
    "content_type_overlay",
}

# precedence 默认顺序：founder_persona 最优先（1），content_type_overlay 最低（4）
PRECEDENCE_MAP = {
    "founder_persona": 1,
    "brand_voice": 2,
    "team_persona_overlay": 3,
    "content_type_overlay": 4,
}

# 软告警关键词：若候选文案出现这些词，可能是门店纪律 / 商品事实误入 overlay；emit warning，不阻断
SOFT_REDLINE_KEYWORDS = ("门店纪律", "面料工艺品质判断", "陈列规则", "商品属性硬性",)

CSV_COLUMNS = GOVERNANCE_FIELDS + [
    "overlay_id",
    "brand_overlay_kind",
    "target_content_type",
    "target_pack_id",
    "tone_constraints_json",
    "output_structure_json",
    "required_knowledge_json",
    "forbidden_words",
    "signature_phrases",
    "precedence",
    "fallback_behavior",
]

logger = logging.getLogger("compile_brand_overlay_view")


@dataclass
class CompileContext:
    candidates_dir: Path
    manifest_path: Path
    schema_path: Path
    output_csv: Path
    log_path: Path


def discover_brand_candidates(candidates_dir: Path) -> list[Path]:
    """只扫 brand_* 与 needs_review 子目录（不扫 domain_general）。"""
    if not candidates_dir.exists():
        return []
    paths: list[Path] = []
    for sub in sorted(candidates_dir.iterdir()):
        if not sub.is_dir():
            continue
        if sub.name == "domain_general":
            continue  # 红线：不读 domain_general
        if sub.name.startswith("brand_") or sub.name == "needs_review":
            paths.extend(sorted(sub.rglob("*.yaml")))
    return paths


def load_candidate(fp: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise CompileError(f"YAML 解析失败: {fp}: {e}")
    if not isinstance(data, dict):
        raise CompileError(f"candidate 顶层非 dict: {fp}")
    return data


def derive_target_content_type(candidate: dict[str, Any]) -> str:
    """content_type_overlay 类型时尝试从 pack_id 派生 content_type 暗示；其它类返回空。"""
    kind = (candidate.get("brand_overlay_kind") or "").strip()
    if kind != "content_type_overlay":
        return ""
    pid = (candidate.get("pack_id") or "").strip()
    # 形如 KP-training_unit-faye-ctype-founder-ip → 取 founder-ip 段
    if "-ctype-" in pid:
        return pid.split("-ctype-", 1)[1]
    return ""


def scan_soft_redlines(candidate: dict[str, Any]) -> list[str]:
    """关键词软扫描：若命中返回提示词列表，仅 warning。"""
    text_chunks = [
        candidate.get("knowledge_assertion") or "",
        str((candidate.get("evidence") or {}).get("evidence_quote") or ""),
        str(((candidate.get("scenario") or {}).get("boundary") or {}).get("applicable_when") or ""),
    ]
    text = "\n".join(text_chunks)
    return [k for k in SOFT_REDLINE_KEYWORDS if k in text]


def build_row(
    candidate: dict[str, Any],
    fp: Path,
    *,
    gctx: GovernanceContext,
) -> dict[str, Any]:
    pack_id = (candidate.get("pack_id") or "").strip()
    if not pack_id:
        raise CompileError(f"缺 pack_id: {fp}")
    brand_layer = (candidate.get("brand_layer") or "").strip()
    if not BRAND_LAYER_RE.match(brand_layer):
        raise CompileError(f"非法 brand_layer={brand_layer!r} (pack_id={pack_id})")
    # S3 硬门：overlay 不能是 domain_general
    if brand_layer == "domain_general":
        raise CompileError(
            f"S3 违例 / brand_layer_scope: pack_id={pack_id} brand_layer=domain_general 不得进入 overlay"
        )
    granularity_layer = (candidate.get("granularity_layer") or "").strip()
    if granularity_layer not in GRANULARITY_ENUM:
        raise CompileError(f"非法 granularity_layer={granularity_layer!r} (pack={pack_id})")

    kind = (candidate.get("brand_overlay_kind") or "").strip()
    if not kind:
        raise CompileError(
            f"缺 brand_overlay_kind: pack_id={pack_id} — 该 brand 候选未显式声明 overlay 类型"
        )
    if kind not in BRAND_OVERLAY_KIND_ENUM:
        raise CompileError(
            f"非法 brand_overlay_kind={kind!r} (pack_id={pack_id}) 不在 4 枚举 {sorted(BRAND_OVERLAY_KIND_ENUM)}"
        )

    precedence = PRECEDENCE_MAP[kind]
    target_content_type = derive_target_content_type(candidate)

    overlay_id = f"BO-{pack_id[3:]}" if pack_id.startswith("KP-") else f"BO-{pack_id}"

    chunk_text = f"{kind}\n{candidate.get('knowledge_assertion','')}\n{target_content_type}"
    chunk_text_hash = sha256_text(chunk_text)

    gov = make_governance(
        source_pack_id=pack_id,
        brand_layer=brand_layer,
        granularity_layer=granularity_layer,
        gate_status="active",
        source_table_refs=["candidates/" + brand_layer + "/"],
        evidence_ids=[],
        traceability_status="partial",
        default_call_pool=False,
        review_status="approved",
        ctx=gctx,
        chunk_text_hash=chunk_text_hash,
    )
    row = dict(gov)
    row.update({
        "overlay_id": overlay_id,
        "brand_overlay_kind": kind,
        "target_content_type": target_content_type,
        "target_pack_id": pack_id,
        "tone_constraints_json": {},
        "output_structure_json": {},
        "required_knowledge_json": {},
        "forbidden_words": [],
        "signature_phrases": [],
        "precedence": precedence,
        "fallback_behavior": "use_domain_general",
    })
    return row


def compile_brand_overlay_view(ctx: CompileContext) -> dict[str, Any]:
    schema = json.loads(ctx.schema_path.read_text(encoding="utf-8"))
    view_schema_version = derive_view_schema_version(ctx.schema_path)
    source_manifest_hash = load_manifest_hash(ctx.manifest_path)
    compile_run_id = derive_compile_run_id(source_manifest_hash, view_schema_version)
    gctx = GovernanceContext(
        compile_run_id=compile_run_id,
        source_manifest_hash=source_manifest_hash,
        view_schema_version=view_schema_version,
    )

    files = discover_brand_candidates(ctx.candidates_dir)
    validator = build_view_validator(schema, "brand_overlay_view")
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    warnings: list[str] = []
    skipped_no_kind: list[str] = []
    schema_errors: list[str] = []
    kind_breakdown: dict[str, int] = {k: 0 for k in BRAND_OVERLAY_KIND_ENUM}

    for fp in files:
        data = load_candidate(fp)
        pack_id = (data.get("pack_id") or "").strip()
        kind = (data.get("brand_overlay_kind") or "").strip()
        if not kind:
            # 跳过：候选无显式 overlay_kind（如 needs_review 中的过渡 pack）
            skipped_no_kind.append(pack_id or fp.name)
            warnings.append(f"跳过：候选未声明 brand_overlay_kind → {pack_id or fp.name}")
            continue

        # 软关键词扫描（不阻断）
        hits = scan_soft_redlines(data)
        if hits:
            warnings.append(f"软告警 / soft redline: pack_id={pack_id} 关键词命中 {hits}")

        row = build_row(data, fp, gctx=gctx)
        if row["overlay_id"] in seen_ids:
            raise CompileError(f"重复 overlay_id: {row['overlay_id']}")
        seen_ids.add(row["overlay_id"])

        errs = validate_row(validator, row)
        if errs:
            schema_errors.append(f"{row['overlay_id']}: {'; '.join(errs)}")
            continue
        rows.append(row)
        kind_breakdown[row["brand_overlay_kind"]] += 1

    if schema_errors:
        raise CompileError("schema 校验失败:\n  " + "\n  ".join(schema_errors[:5]))

    rows.sort(key=lambda r: r["overlay_id"])
    write_csv(ctx.output_csv, CSV_COLUMNS, rows)
    csv_sha256 = sha256_bytes(ctx.output_csv.read_bytes())

    for w in warnings:
        logger.warning(w)

    return {
        "task_card": "KS-COMPILER-006",
        "candidates_scanned": len(files),
        "rows_emitted": len(rows),
        "kind_breakdown": kind_breakdown,
        "skipped_no_kind_count": len(skipped_no_kind),
        "skipped_no_kind": skipped_no_kind,
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
        manifest_path=Path(args.manifest).resolve(),
        schema_path=Path(args.schema).resolve(),
        output_csv=Path(args.output).resolve(),
        log_path=Path(args.log).resolve(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KS-COMPILER-006 · 编译 brand_overlay_view")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--candidates-dir", default=str(DEFAULT_CANDIDATES_DIR))
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
        report = compile_brand_overlay_view(ctx)
    except CompileError as e:
        write_log({"task_card": "KS-COMPILER-006"}, ctx.log_path, ok=False, message=str(e))
        logger.error("compile failed: %s", e)
        return 2
    except Exception as e:  # noqa: BLE001
        write_log({"task_card": "KS-COMPILER-006"}, ctx.log_path, ok=False, message=f"unexpected: {e}")
        logger.exception("unexpected error")
        return 3

    write_log(report, ctx.log_path, ok=True)
    logger.info(
        "brand_overlay_view rows=%d kinds=%s skipped=%d warnings=%d sha256=%s",
        report["rows_emitted"], report["kind_breakdown"],
        report["skipped_no_kind_count"], report["warnings_count"],
        report["output_csv_sha256"][:12],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

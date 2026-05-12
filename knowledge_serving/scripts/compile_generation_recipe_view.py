#!/usr/bin/env python3
"""
KS-COMPILER-003 · compile_generation_recipe_view.py

把 knowledge_serving/views/content_type_view.csv 投影成
generation_recipe_view.csv（plan §3.3）。

为每个 content_type × default_output_formats × default_platforms 的笛卡尔积
生成 recipe 行；空列表 fallback 为 1 个默认 recipe。

S gate: S11 — business_brief_schema_id 必填，运行时实读 business_brief.schema.json
的 $id，禁止硬编码字面量。

退出码 / exit codes：
  0  正常 / OK（含 warning）
  2  输入异常 / input invalid（schema 缺失、required_views 引用不存在、
                                  context_budget_json 不可 parse 等）
  3  schema 校验失败 / jsonschema validation failed
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

DEFAULT_CT_VIEW = DEFAULT_VIEWS_DIR / "content_type_view.csv"
DEFAULT_OUTPUT_CSV = DEFAULT_VIEWS_DIR / "generation_recipe_view.csv"
DEFAULT_LOG_PATH = DEFAULT_AUDIT_DIR / "generation_recipe_view.compile.log"
DEFAULT_BRIEF_SCHEMA = REPO_ROOT / "knowledge_serving" / "schema" / "business_brief.schema.json"

# plan §3 view 名白名单 / valid view names referenced from recipe.required_views
VALID_VIEW_NAMES = {
    "pack_view",
    "content_type_view",
    "play_card_view",
    "runtime_asset_view",
    "brand_overlay_view",
    "evidence_view",
    "generation_recipe_view",
}

# 占位 policy id —— 待 KS-POLICY-001/002/003 落盘后回填
FALLBACK_POLICY_ID = "fp_default_v1"
GUARDRAIL_POLICY_ID = "gp_default_v1"
MERGE_POLICY_ID = "mp_brand_over_domain_v1"

PLACEHOLDER_TODOS = [
    f"TODO: fallback_policy_id={FALLBACK_POLICY_ID} 待 KS-POLICY-001 落盘后回填",
    f"TODO: guardrail_policy_id={GUARDRAIL_POLICY_ID} 待 KS-POLICY-002 落盘后回填",
    f"TODO: merge_policy_id={MERGE_POLICY_ID} 待 KS-POLICY-003 落盘后回填",
]

CSV_COLUMNS = GOVERNANCE_FIELDS + [
    "recipe_id",
    "content_type",
    "output_format",
    "platform",
    "intent_scope",
    "required_views",
    "retrieval_plan_json",
    "step_sequence_json",
    "context_budget_json",
    "fallback_policy_id",
    "guardrail_policy_id",
    "merge_policy_id",
    "business_brief_schema_id",
]

logger = logging.getLogger("compile_generation_recipe_view")


@dataclass
class CompileContext:
    content_type_view: Path
    schema_path: Path
    brief_schema_path: Path
    manifest_path: Path
    output_csv: Path
    log_path: Path
    inject_bad_required_view: str | None  # test-only 注入项
    inject_bad_context_budget: str | None  # test-only 注入项


# ---------- parsing ----------

def _parse_json_list(val: str) -> list[str]:
    val = (val or "").strip()
    if not val:
        return []
    try:
        data = json.loads(val)
    except json.JSONDecodeError as e:
        raise CompileError(f"content_type_view 列非合法 JSON: {val!r}: {e}")
    if not isinstance(data, list):
        raise CompileError(f"content_type_view 列非 list: {val!r}")
    return [str(x) for x in data if str(x).strip()]


def load_content_type_view(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise CompileError(f"content_type_view 不存在 / missing: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            ct_id = (raw.get("canonical_content_type_id") or "").strip()
            if not ct_id:
                raise CompileError(f"content_type_view 行缺 canonical_content_type_id: {raw}")
            rows.append({
                "canonical_content_type_id": ct_id,
                "content_type": (raw.get("content_type") or "").strip(),
                "production_mode": (raw.get("production_mode") or "").strip(),
                "north_star": (raw.get("north_star") or "").strip(),
                "default_output_formats": _parse_json_list(raw.get("default_output_formats") or ""),
                "default_platforms": _parse_json_list(raw.get("default_platforms") or ""),
                "risk_level": (raw.get("risk_level") or "medium").strip() or "medium",
            })
    return rows


def load_brief_schema_id(path: Path) -> str:
    """S11 硬门：实读 business_brief.schema.json 的 $id。"""
    if not path.exists():
        raise CompileError(
            f"business_brief.schema.json 不存在 / missing: {path}（S11 business_brief_no_fabrication）"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CompileError(f"business_brief.schema.json 解析失败: {e}")
    sid = data.get("$id")
    if not isinstance(sid, str) or not sid:
        raise CompileError("business_brief.schema.json 缺 $id（S11）")
    return sid


# ---------- recipe row builder ----------

def _enumerate_recipes(
    ct: dict[str, Any],
) -> tuple[list[tuple[str, str, bool]], bool]:
    """
    返回 [(output_format, platform, is_fallback)...]，以及是否触发 fallback。
    """
    ofs = ct["default_output_formats"]
    pls = ct["default_platforms"]
    if not ofs or not pls:
        # 1 个 default fallback
        return [(_default_output_format(ct), _default_platform(ct), True)], True
    out = []
    for of in ofs:
        for pl in pls:
            out.append((of, pl, False))
    return out, False


def _default_output_format(ct: dict[str, Any]) -> str:
    """空 fallback 默认 output_format —— 基于 production_mode 推断；不可读时回 'text'。"""
    pm = (ct.get("production_mode") or "").lower()
    if "video" in pm:
        return "video"
    if "image" in pm or "graphic" in pm:
        return "image"
    return "text"


def _default_platform(ct: dict[str, Any]) -> str:
    """空 fallback 默认 platform —— 服装零售主力渠道：xiaohongshu。"""
    return "xiaohongshu"


def _build_required_views(ct: dict[str, Any], inject_bad: str | None) -> list[str]:
    """生成 recipe 的 required_views；如有注入项则添加（用于对抗测试）。"""
    base = ["content_type_view", "pack_view", "play_card_view",
            "runtime_asset_view", "evidence_view"]
    if inject_bad:
        base.append(inject_bad)
    return base


def _build_retrieval_plan(ct: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_views": ["pack_view", "play_card_view"],
        "secondary_views": ["runtime_asset_view", "evidence_view"],
        "filter": {"content_type": ct["canonical_content_type_id"]},
        "top_k": 5,
    }


def _build_step_sequence(ct: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"step": "resolve_brand_layer"},
        {"step": "retrieve_packs"},
        {"step": "retrieve_play_cards"},
        {"step": "retrieve_assets"},
        {"step": "compose_context"},
        {"step": "validate_business_brief"},
    ]


def _build_context_budget(ct: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_tokens": 4000,
        "max_chunks": 8,
        "reserved_for_brand_overlay": 400,
    }


def _build_recipe_id(ct_id: str, output_format: str, platform: str) -> str:
    """确定性 recipe_id —— 仅依赖三元组，幂等。"""
    base = f"{ct_id}-{output_format}-{platform}"
    # 用 hash 缩短并避免特殊字符；前缀保留语义
    digest = sha256_text(base)[:10]
    return f"RECIPE-{ct_id}-{output_format}-{platform}-{digest}"


def build_row(
    ct: dict[str, Any],
    output_format: str,
    platform: str,
    is_fallback: bool,
    *,
    brief_schema_id: str,
    gctx: GovernanceContext,
    inject_bad_required_view: str | None,
    inject_bad_context_budget: str | None,
) -> dict[str, Any]:
    ct_id = ct["canonical_content_type_id"]
    recipe_id = _build_recipe_id(ct_id, output_format, platform)

    required_views = _build_required_views(ct, inject_bad_required_view)
    retrieval_plan = _build_retrieval_plan(ct)
    step_sequence = _build_step_sequence(ct)
    if inject_bad_context_budget is not None:
        # 故意注入非法 JSON 串 —— 编译器必须 fail
        # 我们把它放到 _validate_json_columns 检查链
        context_budget: Any = inject_bad_context_budget
    else:
        context_budget = _build_context_budget(ct)

    chunk_text = "\n".join([
        f"recipe_id: {recipe_id}",
        f"content_type: {ct_id}",
        f"output_format: {output_format}",
        f"platform: {platform}",
        f"business_brief_schema_id: {brief_schema_id}",
    ])
    chunk_text_hash = sha256_text(chunk_text)

    intent_scope = "fallback_default" if is_fallback else "explicit_default"

    gov = make_governance(
        source_pack_id=f"RECIPE-{ct_id}-{output_format}-{platform}",
        brand_layer="domain_general",
        granularity_layer="L2",
        gate_status="active",
        source_table_refs=["content_type_view.csv", "business_brief.schema.json"],
        evidence_ids=[],
        traceability_status="full",
        default_call_pool=True,
        review_status="approved",
        ctx=gctx,
        chunk_text_hash=chunk_text_hash,
    )

    row = dict(gov)
    row.update({
        "recipe_id": recipe_id,
        "content_type": ct_id,
        "output_format": output_format,
        "platform": platform,
        "intent_scope": intent_scope,
        "required_views": required_views,
        "retrieval_plan_json": retrieval_plan,
        "step_sequence_json": step_sequence,
        "context_budget_json": context_budget,
        "fallback_policy_id": FALLBACK_POLICY_ID,
        "guardrail_policy_id": GUARDRAIL_POLICY_ID,
        "merge_policy_id": MERGE_POLICY_ID,
        "business_brief_schema_id": brief_schema_id,
    })
    return row


# ---------- validations ----------

def _validate_required_views(row: dict[str, Any]) -> None:
    rvs = row["required_views"]
    if not isinstance(rvs, list) or not rvs:
        raise CompileError(
            f"recipe {row['recipe_id']} required_views 必须非空 list"
        )
    bad = [v for v in rvs if v not in VALID_VIEW_NAMES]
    if bad:
        raise CompileError(
            f"recipe {row['recipe_id']} required_views 引用未知 view: {bad!r}"
            f"（白名单 = {sorted(VALID_VIEW_NAMES)}）"
        )


def _validate_json_columns(row: dict[str, Any]) -> None:
    """retrieval_plan_json / step_sequence_json / context_budget_json 必须可被 json.loads
    重新解析（防止 dict 嵌入了不可序列化对象）。"""
    for col, expected_type in [
        ("retrieval_plan_json", dict),
        ("step_sequence_json", list),
        ("context_budget_json", dict),
    ]:
        val = row[col]
        # 若注入的是字符串（test 路径），直接 json.loads 验证
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
            except json.JSONDecodeError as e:
                raise CompileError(
                    f"recipe {row['recipe_id']} {col} 非合法 JSON 字符串: {e}"
                )
            if not isinstance(parsed, expected_type):
                raise CompileError(
                    f"recipe {row['recipe_id']} {col} 解析后类型不符 {expected_type.__name__}"
                )
            row[col] = parsed  # 落盘前规整
            continue
        if not isinstance(val, expected_type):
            raise CompileError(
                f"recipe {row['recipe_id']} {col} 类型不符 {expected_type.__name__}: got {type(val).__name__}"
            )
        # 再走一遍 round-trip 确认可序列化
        try:
            json.dumps(val, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raise CompileError(
                f"recipe {row['recipe_id']} {col} 不可 JSON 序列化: {e}"
            )


# ---------- main pipeline ----------

def compile_generation_recipe_view(ctx: CompileContext) -> dict[str, Any]:
    schema = json.loads(ctx.schema_path.read_text(encoding="utf-8"))
    view_schema_version = derive_view_schema_version(ctx.schema_path)
    source_manifest_hash = load_manifest_hash(ctx.manifest_path)
    compile_run_id = derive_compile_run_id(source_manifest_hash, view_schema_version)
    gctx = GovernanceContext(
        compile_run_id=compile_run_id,
        source_manifest_hash=source_manifest_hash,
        view_schema_version=view_schema_version,
    )

    brief_schema_id = load_brief_schema_id(ctx.brief_schema_path)

    ct_rows = load_content_type_view(ctx.content_type_view)
    warnings: list[str] = []
    if not ct_rows:
        warnings.append("content_type_view 为空 / empty input — 输出 0 行 recipe")
        logger.warning(warnings[-1])

    validator = build_view_validator(schema, "generation_recipe_view")
    rows: list[dict[str, Any]] = []
    schema_errors: list[str] = []
    fallback_count = 0

    for ct in ct_rows:
        recipes, used_fallback = _enumerate_recipes(ct)
        if used_fallback:
            fallback_count += 1
            warnings.append(
                f"content_type={ct['canonical_content_type_id']} "
                f"default_output_formats/platforms 为空 → default_recipe_fallback"
            )
        for output_format, platform, is_fallback in recipes:
            row = build_row(
                ct, output_format, platform, is_fallback,
                brief_schema_id=brief_schema_id,
                gctx=gctx,
                inject_bad_required_view=ctx.inject_bad_required_view,
                inject_bad_context_budget=ctx.inject_bad_context_budget,
            )
            # 校验：required_views 白名单
            _validate_required_views(row)
            # 校验：json 三列可解析
            _validate_json_columns(row)
            # S11 硬门：business_brief_schema_id 非空且 == 实读 $id
            if not row["business_brief_schema_id"]:
                raise CompileError(
                    f"recipe {row['recipe_id']} business_brief_schema_id 为空（S11）"
                )
            if row["business_brief_schema_id"] != brief_schema_id:
                raise CompileError(
                    f"recipe {row['recipe_id']} business_brief_schema_id 漂移（S11）"
                )
            errs = validate_row(validator, row)
            if errs:
                schema_errors.append(f"{row['recipe_id']}: {'; '.join(errs)}")
                continue
            rows.append(row)

    if schema_errors:
        raise CompileError(
            "schema 校验失败 / schema validation failed:\n  "
            + "\n  ".join(schema_errors[:5])
        )

    # 排序保证幂等
    rows.sort(key=lambda r: (r["content_type"], r["output_format"], r["platform"]))

    write_csv(ctx.output_csv, CSV_COLUMNS, rows)
    csv_sha256 = sha256_bytes(ctx.output_csv.read_bytes())

    return {
        "task_card": "KS-COMPILER-003",
        "content_type_rows_scanned": len(ct_rows),
        "rows_emitted": len(rows),
        "default_recipe_fallback_count": fallback_count,
        "warnings": warnings,
        "warnings_count": len(warnings),
        "source_manifest_hash": source_manifest_hash,
        "view_schema_version": view_schema_version,
        "compile_run_id": compile_run_id,
        "brief_schema_id": brief_schema_id,
        "placeholder_todos": PLACEHOLDER_TODOS,
        "output_csv": safe_relative(ctx.output_csv),
        "output_csv_sha256": csv_sha256,
    }


def build_context(args: argparse.Namespace) -> CompileContext:
    return CompileContext(
        content_type_view=Path(args.content_type_view).resolve(),
        schema_path=Path(args.schema).resolve(),
        brief_schema_path=Path(args.brief_schema).resolve(),
        manifest_path=Path(args.manifest).resolve(),
        output_csv=Path(args.output).resolve(),
        log_path=Path(args.log).resolve(),
        inject_bad_required_view=args.inject_bad_required_view,
        inject_bad_context_budget=args.inject_bad_context_budget,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="KS-COMPILER-003 · 编译 generation_recipe_view 服务读模型 / compile generation_recipe_view"
    )
    parser.add_argument("--check", action="store_true", help="CI 默认入口 / CI entrypoint")
    parser.add_argument("--content-type-view", default=str(DEFAULT_CT_VIEW))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH))
    parser.add_argument("--brief-schema", default=str(DEFAULT_BRIEF_SCHEMA))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--log", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--quiet", action="store_true")
    # test-only 注入项
    parser.add_argument("--inject-bad-required-view", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--inject-bad-context-budget", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    ctx = build_context(args)
    try:
        report = compile_generation_recipe_view(ctx)
    except CompileError as e:
        write_log({"task_card": "KS-COMPILER-003"}, ctx.log_path, ok=False, message=str(e))
        logger.error("compile failed: %s", e)
        return 2
    except Exception as e:  # noqa: BLE001
        write_log({"task_card": "KS-COMPILER-003"}, ctx.log_path, ok=False, message=f"unexpected: {e}")
        logger.exception("unexpected error")
        return 3

    write_log(report, ctx.log_path, ok=True)
    logger.info(
        "generation_recipe_view rows=%d fallback=%d warnings=%d sha256=%s",
        report["rows_emitted"],
        report["default_recipe_fallback_count"],
        report["warnings_count"],
        report["output_csv_sha256"][:12],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

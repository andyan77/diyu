#!/usr/bin/env python3
"""KS-COMPILER-010 · compile_retrieval_policy_view.py

落 §4.3 retrieval_policy_view（每 (intent, content_type) 一行）。
红线：vector_filters 必含 gate_status='active' + brand_layer 约束（多租户硬隔离）。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from _common import (
    CompileError,
    DEFAULT_AUDIT_DIR,
    DEFAULT_CONTROL_DIR,
    REPO_ROOT,
    row_to_csv_dict,
    safe_relative,
    write_log,
)

DEFAULT_OUTPUT_CSV = DEFAULT_CONTROL_DIR / "retrieval_policy_view.csv"
DEFAULT_LOG_PATH = DEFAULT_AUDIT_DIR / "retrieval_policy_view.compile.log"
CANONICAL_CSV = DEFAULT_CONTROL_DIR / "content_type_canonical.csv"

CSV_COLUMNS = [
    "intent", "content_type", "required_views", "optional_views",
    "structured_filters_json", "vector_filters_json", "max_items_per_view",
    "rerank_strategy", "merge_precedence_policy", "timeout_ms",
]

# 7 个 serving views（plan §3）
VALID_VIEW_NAMES = {
    "pack_view", "content_type_view", "generation_recipe_view",
    "play_card_view", "runtime_asset_view", "brand_overlay_view",
    "evidence_view",
}

RERANK_ENUM = {"none", "vector_score", "lex_boost", "policy_weighted"}


def _load_canonical_types() -> list[str]:
    if not CANONICAL_CSV.exists():
        return []
    with CANONICAL_CSV.open(encoding="utf-8") as fh:
        return [r["canonical_content_type_id"] for r in csv.DictReader(fh)]


def _default_policy_for(ct: str) -> dict[str, Any]:
    """每个 canonical content_type 默认 generate intent 一条策略。"""
    return {
        "intent": "generate",
        "content_type": ct,
        "required_views": ["pack_view", "content_type_view"],
        "optional_views": ["play_card_view", "runtime_asset_view", "brand_overlay_view", "evidence_view"],
        "structured_filters_json": {"coverage_status": ["complete", "partial"]},
        "vector_filters_json": {
            "gate_status": "active",
            "brand_layer": "$allowed_layers",  # 运行时由 tenant_scope_resolver 注入
        },
        "max_items_per_view": 5,
        "rerank_strategy": "vector_score",
        "merge_precedence_policy": "brand_over_domain",
        "timeout_ms": 1500,
    }


def _build_default_policies() -> list[dict[str, Any]]:
    return [_default_policy_for(ct) for ct in _load_canonical_types()]


def _validate_policy(r: dict[str, Any]) -> None:
    for k in CSV_COLUMNS:
        if k not in r:
            raise CompileError(f"policy 行缺字段 / missing: {k!r}")
    if not (r["intent"] or "").strip() or not (r["content_type"] or "").strip():
        raise CompileError(f"intent / content_type 不得为空: {r!r}")
    rv = r["required_views"]
    if not isinstance(rv, list) or not rv:
        raise CompileError(f"required_views 必须非空数组 / non-empty list: {r['intent']}/{r['content_type']}")
    for v in rv:
        if v not in VALID_VIEW_NAMES:
            raise CompileError(f"required_views 含未知 view / unknown: {v!r} ({r['intent']}/{r['content_type']})")
    ov = r["optional_views"]
    if not isinstance(ov, list):
        raise CompileError(f"optional_views 必须 list: {r['intent']}/{r['content_type']}")
    for v in ov:
        if v not in VALID_VIEW_NAMES:
            raise CompileError(f"optional_views 含未知 view / unknown: {v!r}")
    sf = r["structured_filters_json"]
    vf = r["vector_filters_json"]
    if not isinstance(sf, dict):
        raise CompileError(f"structured_filters_json 必须 object / must be dict: {r['intent']}/{r['content_type']}")
    if not isinstance(vf, dict):
        raise CompileError(f"vector_filters_json 必须 object / must be dict: {r['intent']}/{r['content_type']}")
    # 红线：gate_status=active + brand_layer 约束
    if vf.get("gate_status") != "active":
        raise CompileError(
            f"vector_filters 缺 gate_status='active' / missing: {r['intent']}/{r['content_type']}"
        )
    if "brand_layer" not in vf:
        raise CompileError(
            f"vector_filters 缺 brand_layer 约束 / missing: {r['intent']}/{r['content_type']}"
        )
    if not isinstance(r["max_items_per_view"], int) or r["max_items_per_view"] <= 0:
        raise CompileError(f"max_items_per_view 必须 > 0: {r['intent']}/{r['content_type']}")
    if r["rerank_strategy"] not in RERANK_ENUM:
        raise CompileError(f"rerank_strategy 非枚举 / not in enum: {r['rerank_strategy']!r}")
    if not isinstance(r["timeout_ms"], int) or r["timeout_ms"] <= 0:
        raise CompileError(f"timeout_ms 必须 > 0: {r['intent']}/{r['content_type']}")


def _serialize_row(r: dict[str, Any]) -> dict[str, str]:
    """JSON object 字段统一序列化为字符串列存盘。"""
    out = {}
    for col in CSV_COLUMNS:
        v = r[col]
        if col in ("structured_filters_json", "vector_filters_json"):
            out[col] = json.dumps(v, ensure_ascii=False, sort_keys=True)
        elif col in ("required_views", "optional_views"):
            out[col] = json.dumps(v, ensure_ascii=False)
        else:
            out[col] = str(v)
    return out


def compile_retrieval_policy_view(
    *,
    policies: list[dict[str, Any]] | None,
    output_csv: Path | None,
    log_path: Path | None,
    check_only: bool = False,
) -> int:
    rows = policies if policies is not None else _build_default_policies()
    if not rows:
        raise CompileError("policies 至少 1 行 / non-empty required")
    seen: set[tuple[str, str]] = set()
    for r in rows:
        _validate_policy(r)
        key = (r["intent"], r["content_type"])
        if key in seen:
            raise CompileError(f"重复 (intent, content_type) / duplicate: {key!r}")
        seen.add(key)
    sorted_rows = sorted(rows, key=lambda r: (r["intent"], r["content_type"]))

    # 18 类覆盖告警
    uncovered: list[str] = []
    if policies is None:
        canonical = set(_load_canonical_types())
        covered = {r["content_type"] for r in sorted_rows}
        uncovered = sorted(canonical - covered)
        if uncovered:
            print(f"[WARN] canonical 未覆盖 / uncovered: {uncovered}", file=sys.stderr)

    if check_only:
        return 0

    assert output_csv is not None
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writeheader()
        for r in sorted_rows:
            writer.writerow(_serialize_row(r))

    if log_path is not None:
        write_log(
            {
                "task_id": "KS-COMPILER-010",
                "output_csv": safe_relative(output_csv),
                "row_count": len(sorted_rows),
                "canonical_uncovered": uncovered,
            },
            log_path,
            ok=True,
            message=f"retrieval_policy_view compiled: {len(sorted_rows)} rows",
        )
    return 0


# DEFAULT_POLICIES alias for tests (eager build with canonical types snapshot at module load)
DEFAULT_POLICIES = _build_default_policies()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CSV)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    try:
        return compile_retrieval_policy_view(
            policies=None,
            output_csv=None if args.check else args.output,
            log_path=None if args.check else args.log,
            check_only=args.check,
        )
    except CompileError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"[FATAL] {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())

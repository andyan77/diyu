#!/usr/bin/env python3
"""KS-COMPILER-011 · compile_merge_precedence_policy.py

落 §4.4 merge_precedence_policy（每 (target_type, conflict_key) 一行）。
红线：domain_general 不得在 brand_<name> 之前；conflict_action=block 时 allow_override 必须 False。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

from _common import (
    BRAND_LAYER_RE,
    CompileError,
    DEFAULT_AUDIT_DIR,
    DEFAULT_CONTROL_DIR,
    row_to_csv_dict,
    safe_relative,
    write_log,
)

DEFAULT_OUTPUT_CSV = DEFAULT_CONTROL_DIR / "merge_precedence_policy.csv"
DEFAULT_LOG_PATH = DEFAULT_AUDIT_DIR / "merge_precedence_policy.compile.log"
TENANT_REGISTRY_CSV = DEFAULT_CONTROL_DIR / "tenant_scope_registry.csv"

CSV_COLUMNS = ["target_type", "conflict_key", "precedence_order", "conflict_action", "allow_override"]
CONFLICT_ACTION_ENUM = {"override", "append", "block", "needs_review"}

# precedence_order 形如 "brand_faye > domain_general"
_PRECEDENCE_RE = re.compile(r"^\s*(brand_[a-z][a-z0-9_]*)\s*>\s*domain_general\s*$")


def _load_registered_brands() -> set[str]:
    brands: set[str] = set()
    if not TENANT_REGISTRY_CSV.exists():
        return brands
    with TENANT_REGISTRY_CSV.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            bl = (row.get("brand_layer") or "").strip()
            if bl.startswith("brand_"):
                brands.add(bl)
    return brands


# §4.4 默认策略：4 类常见 conflict_key × brand_faye
def _default_policies(brand: str = "brand_faye") -> list[dict[str, Any]]:
    po = f"{brand} > domain_general"
    return [
        # tone：品牌覆盖通用
        {"target_type": "brand_overlay", "conflict_key": "tone", "precedence_order": po,
         "conflict_action": "override", "allow_override": True},
        # forbidden_words：品牌追加（非覆盖）—— 通用禁词 + 品牌禁词都生效
        {"target_type": "brand_overlay", "conflict_key": "forbidden_words", "precedence_order": po,
         "conflict_action": "append", "allow_override": False},
        # signature_phrases：品牌覆盖
        {"target_type": "brand_overlay", "conflict_key": "signature_phrases", "precedence_order": po,
         "conflict_action": "override", "allow_override": True},
        # persona_role：品牌覆盖
        {"target_type": "persona", "conflict_key": "persona_role", "precedence_order": po,
         "conflict_action": "override", "allow_override": True},
        # persona_voice：品牌覆盖
        {"target_type": "persona", "conflict_key": "persona_voice", "precedence_order": po,
         "conflict_action": "override", "allow_override": True},
        # founder_profile：品牌硬块，不允许通用层覆盖
        {"target_type": "brand_overlay", "conflict_key": "founder_profile", "precedence_order": po,
         "conflict_action": "block", "allow_override": False},
        # brand_values：品牌硬块
        {"target_type": "brand_overlay", "conflict_key": "brand_values", "precedence_order": po,
         "conflict_action": "block", "allow_override": False},
        # tagline 冲突需人评审
        {"target_type": "brand_overlay", "conflict_key": "tagline", "precedence_order": po,
         "conflict_action": "needs_review", "allow_override": False},
    ]


def _build_default_policies() -> list[dict[str, Any]]:
    brands = _load_registered_brands() or {"brand_faye"}
    out: list[dict[str, Any]] = []
    for b in sorted(brands):
        out.extend(_default_policies(b))
    return out


def _validate_policy(r: dict[str, Any], registered_brands: set[str]) -> None:
    for k in CSV_COLUMNS:
        if k not in r:
            raise CompileError(f"policy 行缺字段 / missing: {k!r}")
    tt = (r["target_type"] or "").strip()
    ck = (r["conflict_key"] or "").strip()
    if not tt or not ck:
        raise CompileError(f"target_type / conflict_key 不得为空: {r!r}")
    po = (r["precedence_order"] or "").strip()
    m = _PRECEDENCE_RE.match(po)
    if not m:
        raise CompileError(
            f"precedence_order 格式必须为 'brand_<name> > domain_general' / required pattern: {po!r}"
        )
    brand = m.group(1)
    if registered_brands and brand not in registered_brands:
        raise CompileError(
            f"precedence_order 含未登记 brand / unregistered: {brand!r} (registered: {sorted(registered_brands)})"
        )
    if r["conflict_action"] not in CONFLICT_ACTION_ENUM:
        raise CompileError(f"非法 conflict_action / invalid: {r['conflict_action']!r}")
    if not isinstance(r["allow_override"], bool):
        raise CompileError(f"allow_override 必须 bool: {r!r}")
    # 红线：conflict_action=block 时 allow_override 必须 False
    if r["conflict_action"] == "block" and r["allow_override"]:
        raise CompileError(
            f"allow_override 与 conflict_action=block 冲突 / contradiction: ({tt}, {ck})"
        )


def compile_merge_precedence_policy(
    *,
    policies: list[dict[str, Any]] | None,
    output_csv: Path | None,
    log_path: Path | None,
    check_only: bool = False,
) -> int:
    rows = policies if policies is not None else _build_default_policies()
    if not rows:
        raise CompileError("policies 至少 1 行 / non-empty required")
    registered_brands = _load_registered_brands()
    seen: set[tuple[str, str]] = set()
    for r in rows:
        _validate_policy(r, registered_brands)
        key = (r["target_type"], r["conflict_key"])
        if key in seen:
            raise CompileError(f"重复 (target_type, conflict_key) / duplicate: {key!r}")
        seen.add(key)
    sorted_rows = sorted(rows, key=lambda r: (r["target_type"], r["conflict_key"]))

    if check_only:
        return 0

    assert output_csv is not None
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writeheader()
        for r in sorted_rows:
            writer.writerow(row_to_csv_dict(r, CSV_COLUMNS))

    if log_path is not None:
        write_log(
            {
                "task_id": "KS-COMPILER-011",
                "output_csv": safe_relative(output_csv),
                "row_count": len(sorted_rows),
                "registered_brands": sorted(registered_brands),
            },
            log_path,
            ok=True,
            message=f"merge_precedence_policy compiled: {len(sorted_rows)} rows",
        )
    return 0


DEFAULT_POLICIES = _build_default_policies()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CSV)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    try:
        return compile_merge_precedence_policy(
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

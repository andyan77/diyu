#!/usr/bin/env python3
"""KS-COMPILER-008 · compile_tenant_scope_registry.py

落 §4.1 tenant_scope_registry 真源表（多租户隔离 / tenant isolation）。
brand_layer 只能从此表派生；运行时禁止从自然语言推断。
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
    REPO_ROOT,
    row_to_csv_dict,
    safe_relative,
    write_log,
)

DEFAULT_OUTPUT_CSV = DEFAULT_CONTROL_DIR / "tenant_scope_registry.csv"
DEFAULT_LOG_PATH = DEFAULT_AUDIT_DIR / "tenant_scope_registry.compile.log"

CSV_COLUMNS = [
    "tenant_id", "api_key_id", "brand_layer", "allowed_layers",
    "default_platforms", "policy_level", "enabled", "environment",
]

ENVIRONMENT_ENUM = {"dev", "staging", "prod"}

# 默认登记：必须至少包含 tenant_faye_main（卡 §4）
DEFAULT_TENANTS: list[dict[str, Any]] = [
    {
        "tenant_id": "tenant_faye_main",
        "api_key_id": "key_ref:tenant_faye_main",
        "brand_layer": "brand_faye",
        "allowed_layers": ["domain_general", "brand_faye"],
        "default_platforms": ["xiaohongshu", "wechat"],
        "policy_level": "standard",
        "enabled": True,
        "environment": "dev",
    },
    {
        "tenant_id": "tenant_demo",
        "api_key_id": "key_ref:tenant_demo",
        "brand_layer": "domain_general",
        "allowed_layers": ["domain_general"],
        "default_platforms": ["xiaohongshu"],
        "policy_level": "demo",
        "enabled": True,
        "environment": "dev",
    },
]

# 明文 key 启发式：sk-... / xoxb-... / hex/base64 长串
_PLAINTEXT_KEY_RE = re.compile(r"^(sk-|xoxb-|xoxp-|ghp_|github_pat_)|^[A-Za-z0-9+/=]{32,}$")


def _validate_tenant(t: dict[str, Any], registered_brands: set[str]) -> None:
    for k in CSV_COLUMNS:
        if k not in t:
            raise CompileError(f"tenant 行缺字段 / missing field {k!r}: {t!r}")
    tid = (t["tenant_id"] or "").strip()
    if not tid:
        raise CompileError("tenant_id 空 / empty tenant_id")
    if not BRAND_LAYER_RE.match(t["brand_layer"]):
        raise CompileError(f"非法 brand_layer / invalid: {t['brand_layer']!r} (tenant={tid})")
    if t["environment"] not in ENVIRONMENT_ENUM:
        raise CompileError(f"非法 environment / invalid (tenant={tid}): {t['environment']!r}")
    allowed = t["allowed_layers"]
    if not isinstance(allowed, list) or not allowed:
        raise CompileError(f"allowed_layers 必须为非空数组 / non-empty list (tenant={tid})")
    for layer in allowed:
        if not BRAND_LAYER_RE.match(layer):
            raise CompileError(f"allowed_layers 非法 layer / invalid: {layer!r} (tenant={tid})")
        if layer.startswith("brand_") and layer not in registered_brands:
            raise CompileError(
                f"allowed_layers 含未登记 brand / unregistered: {layer!r} (tenant={tid})"
            )
    if not isinstance(t["enabled"], bool):
        raise CompileError(f"enabled 必须 bool / must be bool (tenant={tid})")
    api_key_id = (t["api_key_id"] or "").strip()
    if not api_key_id:
        raise CompileError(f"api_key_id 空 / empty (tenant={tid})")
    if _PLAINTEXT_KEY_RE.match(api_key_id):
        raise CompileError(
            f"api_key_id 疑似明文 key / plaintext key suspected (tenant={tid}); "
            f"请改用引用形如 'key_ref:<tenant>'"
        )


def compile_tenant_scope_registry(
    *,
    tenants: list[dict[str, Any]] | None,
    output_csv: Path | None,
    log_path: Path | None,
    check_only: bool = False,
) -> int:
    rows = tenants if tenants is not None else [dict(t) for t in DEFAULT_TENANTS]
    if not rows:
        raise CompileError("registry 至少 1 行 / non-empty required")
    # 第一遍：收集已登记 brand
    registered_brands = {r["brand_layer"] for r in rows if r.get("brand_layer", "").startswith("brand_")}
    # 第二遍：逐行校验
    seen_ids: set[str] = set()
    for t in rows:
        _validate_tenant(t, registered_brands)
        tid = t["tenant_id"]
        if tid in seen_ids:
            raise CompileError(f"重复 tenant_id / duplicate: {tid!r}")
        seen_ids.add(tid)

    # 排序：确定性
    sorted_rows = sorted(rows, key=lambda r: r["tenant_id"])

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
                "task_id": "KS-COMPILER-008",
                "output_csv": safe_relative(output_csv),
                "row_count": len(sorted_rows),
                "registered_brands": sorted(registered_brands),
            },
            log_path,
            ok=True,
            message=f"tenant_scope_registry compiled: {len(sorted_rows)} rows",
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="compile tenant_scope_registry.csv")
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CSV)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    p.add_argument("--check", action="store_true", help="只校验默认登记，不写文件")
    args = p.parse_args(argv)
    try:
        return compile_tenant_scope_registry(
            tenants=None,
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

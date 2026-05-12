#!/usr/bin/env python3
"""KS-COMPILER-009 · compile_field_requirement_matrix.py

落 §4.2 field_requirement_matrix 真源表（S7 fallback 覆盖度真源）。
每个 (content_type, field_key) 一行；required_level / fallback_action / ask_user_question / block_reason 全填。
"""
from __future__ import annotations

import argparse
import csv
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

DEFAULT_OUTPUT_CSV = DEFAULT_CONTROL_DIR / "field_requirement_matrix.csv"
DEFAULT_LOG_PATH = DEFAULT_AUDIT_DIR / "field_requirement_matrix.compile.log"
CANONICAL_CSV = DEFAULT_CONTROL_DIR / "content_type_canonical.csv"

CSV_COLUMNS = [
    "content_type", "field_key", "required_level",
    "fallback_action", "ask_user_question", "block_reason",
]

REQUIRED_LEVEL_ENUM = {"none", "soft", "hard"}
FALLBACK_ACTION_ENUM = {"use_domain_general", "neutral_tone", "ask_user", "block_brand_output"}
# soft 允许的 fallback_action（不许直接 block）
SOFT_ALLOWED_FALLBACK = {"use_domain_general", "neutral_tone", "ask_user"}
# hard 必须 block_brand_output
HARD_REQUIRED_FALLBACK = {"block_brand_output"}

# §4.2 4 条样例 + 扩展覆盖 18 类 canonical content types
DEFAULT_RULES: list[dict[str, Any]] = [
    # § 4.2 四条样例 / four canonical samples
    {
        "content_type": "product_review", "field_key": "brand_tone",
        "required_level": "soft", "fallback_action": "neutral_tone",
        "ask_user_question": "是否使用品牌专属语气？",
        "block_reason": "",
    },
    {
        "content_type": "store_daily", "field_key": "team_persona",
        "required_level": "soft", "fallback_action": "use_domain_general",
        "ask_user_question": "缺门店团队人设，是否用通用门店人设？",
        "block_reason": "",
    },
    {
        "content_type": "founder_ip", "field_key": "founder_profile",
        "required_level": "hard", "fallback_action": "block_brand_output",
        "ask_user_question": "",
        "block_reason": "founder_ip 必须基于具体创始人画像，缺失则阻断成稿",
    },
    {
        "content_type": "founder_ip", "field_key": "brand_values",
        "required_level": "hard", "fallback_action": "block_brand_output",
        "ask_user_question": "",
        "block_reason": "founder_ip 缺品牌价值观时阻断创始人化成稿",
    },
    # 其余 17 类 canonical content_type 至少 1 行（S7 全覆盖）
    {
        "content_type": "behind_the_scenes", "field_key": "process_detail",
        "required_level": "soft", "fallback_action": "use_domain_general",
        "ask_user_question": "缺幕后细节，是否用通用工艺说明？", "block_reason": "",
    },
    {
        "content_type": "daily_fragment", "field_key": "scene_anchor",
        "required_level": "none", "fallback_action": "neutral_tone",
        "ask_user_question": "", "block_reason": "",
    },
    {
        "content_type": "emotion_expression", "field_key": "tone_constraint",
        "required_level": "soft", "fallback_action": "neutral_tone",
        "ask_user_question": "", "block_reason": "",
    },
    {
        "content_type": "event_documentary", "field_key": "event_anchor",
        "required_level": "hard", "fallback_action": "block_brand_output",
        "ask_user_question": "", "block_reason": "事件纪实必须基于具体事件，缺失则阻断",
    },
    {
        "content_type": "humor_content", "field_key": "tone_constraint",
        "required_level": "soft", "fallback_action": "neutral_tone",
        "ask_user_question": "", "block_reason": "",
    },
    {
        "content_type": "knowledge_sharing", "field_key": "knowledge_pack",
        "required_level": "hard", "fallback_action": "block_brand_output",
        "ask_user_question": "", "block_reason": "知识分享必须有可追溯知识包，缺失则阻断",
    },
    {
        "content_type": "lifestyle_expression", "field_key": "brand_tone",
        "required_level": "soft", "fallback_action": "neutral_tone",
        "ask_user_question": "", "block_reason": "",
    },
    {
        "content_type": "outfit_of_the_day", "field_key": "outfit_pack",
        "required_level": "hard", "fallback_action": "block_brand_output",
        "ask_user_question": "", "block_reason": "OOTD 必须基于具体单品/搭配，缺失则阻断",
    },
    {
        "content_type": "personal_vlog", "field_key": "persona",
        "required_level": "soft", "fallback_action": "use_domain_general",
        "ask_user_question": "", "block_reason": "",
    },
    {
        "content_type": "process_trace", "field_key": "process_anchor",
        "required_level": "hard", "fallback_action": "block_brand_output",
        "ask_user_question": "", "block_reason": "过程记录必须基于具体过程节点，缺失则阻断",
    },
    {
        "content_type": "product_copy_general", "field_key": "product_pack",
        "required_level": "hard", "fallback_action": "block_brand_output",
        "ask_user_question": "", "block_reason": "商品文案必须基于具体 SKU/品类，缺失则阻断",
    },
    {
        "content_type": "product_journey", "field_key": "product_origin",
        "required_level": "hard", "fallback_action": "block_brand_output",
        "ask_user_question": "", "block_reason": "商品溯源必须基于真实来源/工艺，缺失则阻断",
    },
    {
        "content_type": "role_work_vlog", "field_key": "role_profile",
        "required_level": "soft", "fallback_action": "use_domain_general",
        "ask_user_question": "缺角色画像，是否用通用岗位画像?", "block_reason": "",
    },
    {
        "content_type": "talent_showcase", "field_key": "talent_anchor",
        "required_level": "soft", "fallback_action": "neutral_tone",
        "ask_user_question": "", "block_reason": "",
    },
    {
        "content_type": "training_material", "field_key": "training_anchor",
        "required_level": "hard", "fallback_action": "block_brand_output",
        "ask_user_question": "", "block_reason": "培训素材必须基于具体岗位/制度条目，缺失则阻断",
    },
]


def _validate_rule(r: dict[str, Any]) -> None:
    for k in CSV_COLUMNS:
        if k not in r:
            raise CompileError(f"规则缺字段 / missing field: {k!r} in {r!r}")
    ct = (r["content_type"] or "").strip()
    fk = (r["field_key"] or "").strip()
    if not ct or not fk:
        raise CompileError(f"content_type / field_key 不得为空: {r!r}")
    if r["required_level"] not in REQUIRED_LEVEL_ENUM:
        raise CompileError(f"非法 required_level / invalid: {r['required_level']!r} ({ct}.{fk})")
    if r["fallback_action"] not in FALLBACK_ACTION_ENUM:
        raise CompileError(f"非法 fallback_action / invalid: {r['fallback_action']!r} ({ct}.{fk})")
    if r["required_level"] == "hard":
        if not (r["block_reason"] or "").strip():
            raise CompileError(f"hard 行未填 block_reason / hard row missing block_reason: ({ct}.{fk})")
        if r["fallback_action"] not in HARD_REQUIRED_FALLBACK:
            raise CompileError(
                f"hard 行 fallback_action 必须 block_brand_output / hard rule must block: "
                f"({ct}.{fk}) got {r['fallback_action']!r}"
            )
    if r["required_level"] == "soft":
        if r["fallback_action"] not in SOFT_ALLOWED_FALLBACK:
            raise CompileError(
                f"soft 行 fallback_action 不得为 block_brand_output / soft cannot block: "
                f"({ct}.{fk}) got {r['fallback_action']!r}"
            )


def compile_field_requirement_matrix(
    *,
    rules: list[dict[str, Any]] | None,
    output_csv: Path | None,
    log_path: Path | None,
    check_only: bool = False,
) -> int:
    rows = rules if rules is not None else [dict(r) for r in DEFAULT_RULES]
    if not rows:
        raise CompileError("规则集至少 1 行 / non-empty required")
    seen: set[tuple[str, str]] = set()
    for r in rows:
        _validate_rule(r)
        key = (r["content_type"], r["field_key"])
        if key in seen:
            raise CompileError(f"重复 (content_type, field_key) / duplicate: {key!r}")
        seen.add(key)

    sorted_rows = sorted(rows, key=lambda r: (r["content_type"], r["field_key"]))

    # S7 全覆盖 warning（仅在 default-rules 路径检查 canonical 18 类）
    canonical_uncovered: list[str] = []
    if rules is None and CANONICAL_CSV.exists():
        covered = {r["content_type"] for r in sorted_rows}
        with CANONICAL_CSV.open(encoding="utf-8") as fh:
            canonical = {row["canonical_content_type_id"] for row in csv.DictReader(fh)}
        canonical_uncovered = sorted(canonical - covered)
        if canonical_uncovered:
            print(f"[WARN] canonical 未覆盖 / uncovered: {canonical_uncovered}", file=sys.stderr)

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
                "task_id": "KS-COMPILER-009",
                "output_csv": safe_relative(output_csv),
                "row_count": len(sorted_rows),
                "canonical_uncovered": canonical_uncovered,
                "hard_rows": sum(1 for r in sorted_rows if r["required_level"] == "hard"),
                "soft_rows": sum(1 for r in sorted_rows if r["required_level"] == "soft"),
            },
            log_path,
            ok=True,
            message=f"field_requirement_matrix compiled: {len(sorted_rows)} rows",
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CSV)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    try:
        return compile_field_requirement_matrix(
            rules=None,
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

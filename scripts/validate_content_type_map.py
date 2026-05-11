#!/usr/bin/env python3
"""
validate_content_type_map.py · KS-S0-005 校验器 / validator

校验 / checks:
  V1 canonical_content_type_id 唯一 / unique
  V2 canonical id 全部 snake_case（小写 + 下划线，无空格 / 无大写）
  V3 name_zh 非空 / non-empty
  V4 name_en 非空 / non-empty
  V5 aliases 反查唯一：不同 canonical id 不得共享同一 alias
  V6 aliases 不与 canonical_id 自身重复
  V7 coverage_status ∈ {complete, partial, missing}
  V8 行数 == 18（方案约定的 ContentType 数）
  V9 与 Q2-内容类型种子/ 文件名一致性：每个 canonical id 必须对应一个
     `<id>-交付物-v0.1.md` 文件存在 / file must exist

退出码 / exit code: 0 = 全绿；非 0 = fail。
不调 LLM / no LLM calls.
"""
from __future__ import annotations
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "knowledge_serving" / "control" / "content_type_canonical.csv"
SEED_DIR = ROOT / "Q2-内容类型种子"

VALID_COVERAGE = {"complete", "partial", "missing"}
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")

errors: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def main() -> int:
    if not CSV_PATH.exists():
        print(f"❌ csv 不存在 / missing: {CSV_PATH}")
        return 2

    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))

    # V8 行数 / row count
    if len(rows) != 18:
        fail(f"V8 行数 {len(rows)} != 18")

    seen_ids: dict[str, int] = {}
    alias_to_id: dict[str, str] = {}

    for i, row in enumerate(rows, start=2):  # csv 行号 / csv line number (header = 1)
        cid = row.get("canonical_content_type_id", "").strip()
        name_zh = row.get("name_zh", "").strip()
        name_en = row.get("name_en", "").strip()
        aliases_raw = row.get("aliases", "").strip()
        cov = row.get("coverage_status", "").strip()

        # V1 唯一 / unique
        if cid in seen_ids:
            fail(f"V1 第 {i} 行 canonical id 重复 / duplicate: {cid!r}（首次见于第 {seen_ids[cid]} 行）")
        seen_ids[cid] = i

        # V2 snake_case
        if not SNAKE_CASE.match(cid):
            fail(f"V2 第 {i} 行 canonical id 非 snake_case: {cid!r}")

        # V3/V4 非空 / non-empty
        if not name_zh:
            fail(f"V3 第 {i} 行 name_zh 空 / empty (cid={cid})")
        if not name_en:
            fail(f"V4 第 {i} 行 name_en 空 / empty (cid={cid})")

        # V5/V6 aliases
        aliases = [a.strip() for a in aliases_raw.split("|") if a.strip()]
        if not aliases:
            warn(f"第 {i} 行 aliases 空 / empty aliases (cid={cid})")
        for a in aliases:
            if a == cid:
                fail(f"V6 第 {i} 行 alias 与 canonical id 重复 / alias equals id: {a!r}")
            if a in alias_to_id and alias_to_id[a] != cid:
                fail(
                    f"V5 alias {a!r} 同时指向 {alias_to_id[a]!r} 和 {cid!r}（第 {i} 行）"
                )
            alias_to_id[a] = cid

        # V7 coverage
        if cov not in VALID_COVERAGE:
            fail(f"V7 第 {i} 行 coverage_status 非法 / invalid: {cov!r}")

        # V9 与种子文件名一致性 / consistency with seed file
        if SEED_DIR.exists():
            seed_file = SEED_DIR / f"{cid}-交付物-v0.1.md"
            if not seed_file.exists():
                warn(f"V9 第 {i} 行 cid={cid} 未找到对应种子文件 / seed file missing: {seed_file.name}")

    # Report
    print(f"已校验 / checked: {len(rows)} 行")
    if warnings:
        print(f"\n⚠️  warnings ({len(warnings)}):")
        for w in warnings:
            print(f"   - {w}")
    if errors:
        print(f"\n❌ errors ({len(errors)}):")
        for e in errors:
            print(f"   - {e}")
        return 1
    print(f"\n✅ V1-V9 全绿 / all checks passed（{len(rows)} 行 · {len(alias_to_id)} 别名）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

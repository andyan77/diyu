#!/usr/bin/env python3
"""硬门 G16d · 章节级裁决账本完整性

reviewer 决议：
- 仅硬门"全章节有合法 adjudication_status"（无 _pending_review_ / 空状态）
- 不硬门自动签发率（pending_decision 合法存在）
- pending_decision 必须带 priority + rationale + batch_target（"具名 + 理由 + 优先级"）
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADJ = ROOT / "audit" / "source_unit_adjudication.csv"
INV = ROOT / "audit" / "source_unit_inventory.csv"

VALID = {"covered_by_pack", "unprocessable", "duplicate_or_redundant", "pending_decision"}


def main():
    if not ADJ.exists():
        print("❌ 缺 audit/source_unit_adjudication.csv（先跑 build_source_unit_adjudication.py）")
        return 1

    inv_total = sum(1 for _ in csv.DictReader(INV.open(encoding="utf-8")))
    rows = list(csv.DictReader(ADJ.open(encoding="utf-8")))

    issues = []
    if len(rows) != inv_total:
        issues.append(f"adjudication 行数 {len(rows)} != inventory {inv_total}")

    bad_status = [r for r in rows if r["adjudication_status"] not in VALID]
    if bad_status:
        issues.append(f"非法 adjudication_status: {len(bad_status)} 条")

    empty_adj = [r for r in rows if not r.get("adjudicator", "").strip()]
    if empty_adj:
        issues.append(f"adjudicator 字段为空: {len(empty_adj)} 条")

    pendings = [r for r in rows if r["adjudication_status"] == "pending_decision"]
    bad_pending = [
        r for r in pendings
        if not (r.get("priority") and r.get("rationale") and r.get("batch_target") and r.get("heading_path"))
    ]
    if bad_pending:
        issues.append(
            f"{len(bad_pending)} 条 pending_decision 缺 priority/rationale/batch_target/heading_path"
        )

    from collections import Counter
    cnt = Counter(r["adjudication_status"] for r in rows)
    pri_cnt = Counter(r["priority"] for r in pendings)
    print("=== G16d · 章节级裁决账本完整性 ===\n")
    print(f"  覆盖: {len(rows)}/{inv_total} source_unit")
    for k in ("covered_by_pack", "unprocessable", "duplicate_or_redundant", "pending_decision"):
        print(f"    {k:25s} {cnt.get(k, 0)}")
    print(f"  pending priority 分布: {dict(pri_cnt)}")

    if issues:
        print(f"\n  ❌ {len(issues)} 项问题:")
        for x in issues:
            print(f"    - {x}")
        return 1
    print(f"\n  ✅ 全部 source_unit 有合法 adjudication_status；pending 全部具名+优先级+理由")
    return 0


if __name__ == "__main__":
    sys.exit(main())

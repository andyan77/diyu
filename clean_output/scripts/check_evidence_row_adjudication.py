#!/usr/bin/env python3
"""硬门 G17 · evidence row 级裁决账本完整性

规则：
1. audit/evidence_row_adjudication.csv 存在
2. 与 07_evidence.csv 一一对应（行数 + evidence_id 集合相等）
3. adjudication_status ∈ {direct_quote_verified, paraphrase_located, needs_human_review}
4. needs_human_review 行的 adjudicator 必须 != 'auto'（要求人工裁决签字）
   - auto + needs_human_review → 触红
5. inference_level_current vs recommended 不一致 仅 warning（不阻断；reviewer 决议）
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADJ = ROOT / "audit" / "evidence_row_adjudication.csv"
EV = ROOT / "nine_tables" / "07_evidence.csv"

VALID_STATUS = {"direct_quote_verified", "paraphrase_located", "needs_human_review"}


def main():
    if not ADJ.exists():
        print(f"❌ 缺 {ADJ.relative_to(ROOT)}（先跑 build_evidence_row_adjudication.py）")
        return 1

    ev_ids = {r["evidence_id"] for r in csv.DictReader(EV.open(encoding="utf-8"))}
    adj_rows = list(csv.DictReader(ADJ.open(encoding="utf-8")))
    adj_ids = {r["evidence_id"] for r in adj_rows}

    issues = []
    if adj_ids != ev_ids:
        miss = ev_ids - adj_ids
        extra = adj_ids - ev_ids
        if miss:
            issues.append(f"adjudication 缺失 {len(miss)} 条 evidence_id（如 {list(miss)[:3]}）")
        if extra:
            issues.append(f"adjudication 多出 {len(extra)} 条不存在的 evidence_id")

    bad_status = [r for r in adj_rows if r["adjudication_status"] not in VALID_STATUS]
    if bad_status:
        issues.append(f"非法 adjudication_status: {len(bad_status)} 条")

    auto_needs_review = [
        r for r in adj_rows
        if r["adjudication_status"] == "needs_human_review"
        and r.get("adjudicator", "auto") == "auto"
    ]
    if auto_needs_review:
        issues.append(
            f"{len(auto_needs_review)} 条 needs_human_review 仍为 adjudicator=auto，"
            f"需人工裁决并把 adjudicator 改为 human"
        )

    warnings = sum(1 for r in adj_rows if r.get("recommendation_warning", ""))
    counts = {}
    for r in adj_rows:
        counts[r["adjudication_status"]] = counts.get(r["adjudication_status"], 0) + 1

    print("=== G17 · evidence row 级裁决账本完整性 ===\n")
    print(f"  覆盖: {len(adj_rows)}/{len(ev_ids)} evidence")
    for k, n in sorted(counts.items()):
        print(f"    {k:25s} {n}")
    print(f"  inference_level current vs recommended 不一致 (warning only): {warnings}")

    if issues:
        print(f"\n  ❌ {len(issues)} 项问题:")
        for x in issues:
            print(f"    - {x}")
        return 1
    print(f"\n  ✅ row 级裁决账本完整、覆盖率 100%、无未签字 needs_human_review")
    return 0


if __name__ == "__main__":
    sys.exit(main())

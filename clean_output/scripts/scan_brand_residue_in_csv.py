#!/usr/bin/env python3
"""硬门 10 · 9 表中 brand_layer=domain_general 行品牌残留扫描

复用 W1 reviewer 提的根因：审计声称已删，9 表仍有笛语句。
扫描所有 CSV 中 brand_layer=domain_general 行的所有文本字段，
检查是否含品牌专属关键词。命中即写违反清单 + 退 1。
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NINE = ROOT / "nine_tables"
OUT = ROOT / "audit" / "_process" / "brand_residue_in_csv.csv"

# 品牌专属关键词（笛语 = brand_faye 唯一识别符）
BRAND_KEYWORDS = ["笛语"]

# 每张表的 brand_layer 列名
BRAND_LAYER_COL = "brand_layer"


def scan_row(row, line, table):
    hits = []
    layer = row.get(BRAND_LAYER_COL, "")
    if layer != "domain_general":
        return hits
    for col, val in row.items():
        if not val:
            continue
        for kw in BRAND_KEYWORDS:
            if kw in str(val):
                hits.append({
                    "table": table, "line": line,
                    "source_pack_id": row.get("source_pack_id", ""),
                    "field": col, "keyword": kw,
                    "snippet": str(val)[:150].replace("\n", " "),
                })
    return hits


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    all_hits = []
    print("=== 硬门 10 · 9 表 domain_general 行品牌残留扫描 ===\n")
    for csvf in sorted(NINE.glob("*.csv")):
        with open(csvf, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        hits = []
        for i, r in enumerate(rows, start=2):
            hits.extend(scan_row(r, i, csvf.stem))
        mark = "✅" if not hits else "❌"
        print(f"  {mark} {csvf.stem:20s} 命中 {len(hits)}")
        all_hits.extend(hits)

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "line", "source_pack_id", "field", "keyword", "snippet"])
        for h in all_hits:
            w.writerow([h["table"], h["line"], h["source_pack_id"],
                        h["field"], h["keyword"], h["snippet"]])

    print(f"\n违反总数: {len(all_hits)}")
    print(f"清单    : {OUT}")
    return 0 if not all_hits else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""硬门 9 · manifest 一致性

校验 manifest.json summary 与磁盘真相对齐：
  candidate_count_total / candidate_<layer> / nine_tables_data_rows_total
任一不等即退出 1。
"""
import json
import sys
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.json"


def csv_count(p):
    with p.open(encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def main():
    if not MANIFEST.exists():
        print("ERROR: manifest.json 不存在，先跑 build_manifest.py", file=sys.stderr)
        return 2

    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = m.get("summary", {})

    cand = ROOT / "candidates"
    actual = {
        "domain_general": len(list((cand / "domain_general").glob("*.yaml"))) if (cand / "domain_general").exists() else 0,
        "brand_faye":     len(list((cand / "brand_faye").glob("*.yaml")))     if (cand / "brand_faye").exists()     else 0,
        "needs_review":   len(list((cand / "needs_review").glob("*.yaml")))   if (cand / "needs_review").exists()   else 0,
    }
    actual_total = sum(actual.values())
    actual_rows = sum(csv_count(p) for p in (ROOT / "nine_tables").glob("*.csv"))

    diffs = []
    if summary.get("candidate_count_total") != actual_total:
        diffs.append(f"candidate_count_total: manifest={summary.get('candidate_count_total')} vs disk={actual_total}")
    for layer in ("domain_general", "brand_faye", "needs_review"):
        key = f"candidate_{layer}"
        if summary.get(key) != actual[layer]:
            diffs.append(f"{key}: manifest={summary.get(key)} vs disk={actual[layer]}")
    if summary.get("nine_tables_data_rows_total") != actual_rows:
        diffs.append(f"nine_tables_data_rows_total: manifest={summary.get('nine_tables_data_rows_total')} vs disk={actual_rows}")

    print(f"  candidate total     : manifest={summary.get('candidate_count_total')}  disk={actual_total}")
    print(f"  domain_general      : manifest={summary.get('candidate_domain_general')}  disk={actual['domain_general']}")
    print(f"  brand_faye          : manifest={summary.get('candidate_brand_faye')}  disk={actual['brand_faye']}")
    print(f"  needs_review        : manifest={summary.get('candidate_needs_review')}  disk={actual['needs_review']}")
    print(f"  9 tables row total  : manifest={summary.get('nine_tables_data_rows_total')}  disk={actual_rows}")

    if diffs:
        print("\n❌ manifest 漂移：")
        for d in diffs:
            print(f"  {d}")
        return 1
    print("\n✅ manifest 与磁盘真相一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())

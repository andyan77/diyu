#!/usr/bin/env python3
"""W11.1b · 抽样规则落盘

按"分层抽样"从高置信项里选样本，避免只在某些 md 集中抽：
- source_unit: extract_l2 + high (171 条) → 每 source_md 至少 2 条 + 总 ≥30 条
- pack: L2 + high (26 条) → 全审

输出:
  audit/review_must.csv     必审清单（needs_human_review=true 全集 + L2 抽样）
  audit/review_sample.csv   抽样清单（高置信 L2 的子集，便于交叉核对）
"""
import csv
from collections import defaultdict
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parent.parent
SU = ROOT / "audit" / "source_unit_adjudication_v2.csv"
PK = ROOT / "audit" / "pack_layer_register.csv"
OUT_MUST = ROOT / "audit" / "review_must.csv"
OUT_SAMPLE = ROOT / "audit" / "review_sample.csv"

random.seed(42)  # 可重复抽样


def main():
    su = list(csv.DictReader(SU.open(encoding="utf-8")))
    pk = list(csv.DictReader(PK.open(encoding="utf-8")))

    # --- source_unit 必审：needs_human_review=true ---
    su_must = [r for r in su if r["needs_human_review"] == "true"]
    # --- source_unit 抽样：extract_l2 + high，按 source_md 分层 ---
    su_l2_high = [r for r in su
                  if r["suggested_status"] == "extract_l2"
                  and r["confidence"] == "high"]
    by_md = defaultdict(list)
    for r in su_l2_high:
        by_md[r["source_md"]].append(r)
    sampled = []
    for md, rows in by_md.items():
        # 每 md 至少 2 条；如果该 md ≤ 2 条则全取
        n = min(len(rows), max(2, len(rows) // 6))  # 约 16-17%
        sampled.extend(random.sample(rows, n))

    # 必审 = needs_human_review + sampled L2
    su_review = list({id(r): r for r in (su_must + sampled)}.values())

    cols = list(su[0].keys())
    OUT_MUST.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MUST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(su_review)

    # 抽样表（仅 sampled，便于 cross-check）
    with OUT_SAMPLE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sampled)

    # --- pack 必审：L2 + high (全审) + needs_human_review=true ---
    pk_must = [r for r in pk
               if r["needs_human_review"] == "true"
               or (r["suggested_layer"] == "L2" and r["confidence"] == "high")]

    OUT_PK_MUST = ROOT / "audit" / "pack_review_must.csv"
    pcols = list(pk[0].keys())
    with OUT_PK_MUST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pcols, extrasaction="ignore")
        w.writeheader()
        w.writerows(pk_must)

    print("=== W11.1b · 审样规则落盘 ===\n")
    print(f"source_unit_adjudication_v2.csv:")
    print(f"  needs_human_review=true       : {len(su_must)}")
    print(f"  extract_l2 + high (按 md 分层抽): {len(sampled)} (覆盖 {len(by_md)} md, 总池 {len(su_l2_high)})")
    print(f"  → 必审合并: {len(su_review)} 条 → {OUT_MUST}")
    print(f"  → 抽样独立表: {len(sampled)} 条 → {OUT_SAMPLE}\n")

    print(f"pack_layer_register.csv:")
    print(f"  needs_human_review=true (low) : {sum(1 for r in pk if r['needs_human_review']=='true')}")
    print(f"  L2 + high                     : {sum(1 for r in pk if r['suggested_layer']=='L2' and r['confidence']=='high')}")
    print(f"  → 必审合并 (去重): {len(pk_must)} 条 → {OUT_PK_MUST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

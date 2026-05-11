#!/usr/bin/env python3
"""W11.2.1 · 34 条 dispute pack 补审表

筛 pack_layer_register 中：final_layer=L2 且缺 production 字段的行。
导出到 audit/pack_dispute_review.csv，含每个 pack 的 yaml 文件 knowledge_assertion 摘要
（前 200 字）便于人工判 L1/L2。

人工填列:
  reviewer_decision: accept | override
  final_layer: L1 | L2  (override 时改 L1，accept 时保 L2)
  production_tier: instant | long_term | brand_tier  (仅 L2 必填)
  default_call_pool: true | false  (仅 L2 必填)
  review_notes: ≥10 字（override 必填，accept 可选）
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PK_REG = ROOT / "audit" / "pack_layer_register.csv"
CAND = ROOT / "candidates"
OUT = ROOT / "audit" / "pack_dispute_review.csv"


def extract_assertion(yaml_text):
    """提取 knowledge_assertion 第一段（≤200 字）"""
    m = re.search(r"^knowledge_assertion:\s*>?\-?\s*\n((?:  .+\n)+)", yaml_text, re.MULTILINE)
    if m:
        body = " ".join(line.strip() for line in m.group(1).splitlines() if line.strip())
        return body[:200].replace("\n", " ")
    return ""


def find_yaml(pack_id):
    for sub in ("domain_general", "brand_faye", "needs_review"):
        p = CAND / sub / f"{pack_id}.yaml"
        if p.exists():
            return p
    return None


def main():
    pk = list(csv.DictReader(PK_REG.open(encoding="utf-8")))
    dispute = [
        r for r in pk
        if r.get("final_layer", "").strip() == "L2"
        and (not r.get("production_tier", "").strip() or not r.get("default_call_pool", "").strip())
    ]
    print(f"=== W11.2.1 · pack dispute 审表 ===\n")
    print(f"  共 {len(dispute)} 条 final_layer=L2 但缺 production 字段")

    rows = []
    for r in dispute:
        ypath = find_yaml(r["pack_id"])
        excerpt = extract_assertion(ypath.read_text(encoding="utf-8")) if ypath else ""
        rows.append({
            "pack_id": r["pack_id"],
            "current_final_layer": "L2",
            "current_confidence": r.get("confidence", ""),
            "suggestion_rationale": r.get("suggestion_rationale", ""),
            "yaml_path": str(ypath.relative_to(ROOT)) if ypath else "",
            "knowledge_assertion_excerpt": excerpt,
            # 人工填列
            "reviewer_decision": "",       # accept | override
            "final_layer": "",             # L1 | L2
            "production_tier": "",         # 若 L2 必填
            "default_call_pool": "",       # 若 L2 必填
            "review_notes": "",            # override 必填 ≥10 字
        })

    cols = list(rows[0].keys())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"  → {OUT.relative_to(ROOT)}")
    print(f"\n填法：")
    print(f"  - 看 knowledge_assertion_excerpt，判该 pack 是 L1（判断/反推）还是 L2（生成/玩法）")
    print(f"  - L1: reviewer_decision=override, final_layer=L1, review_notes ≥10 字")
    print(f"  - L2: reviewer_decision=accept,   final_layer=L2, 必填 production_tier + default_call_pool")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""W12.A.3 + W12.A.4 · 给 29 L2 + 24 L3 pack 建增量审表

输出:
  audit/l2_play_card_review.csv  (29 行) — 你填 hook/steps/anti_pattern/duration/audience/production_difficulty
  audit/l3_runtime_asset_review.csv (24 行) — 你填 asset_type/source_pointer

资源基线 resource_baseline 自动派生 (production_tier 已知):
  instant     → 1人+手机+200元+4h
  long_term   → 2-3人+轻设备+1000元+1-2天
  brand_tier  → 专业团队+品牌资源+不限

L2 摘要 / L3 摘要从 yaml knowledge_assertion + scenario 提取，便于人工判断填什么。
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PK_REG = ROOT / "audit" / "pack_layer_register.csv"
CAND = ROOT / "candidates"
OUT_L2 = ROOT / "audit" / "l2_play_card_review.csv"
OUT_L3 = ROOT / "audit" / "l3_runtime_asset_review.csv"

TIER_TO_BASELINE = {
    "instant": "1人+手机+200元+4h",
    "long_term": "2-3人+轻设备+1000元+1-2天",
    "brand_tier": "专业团队+品牌资源+不限",
}


def find_yaml(pack_id):
    for sub in ("domain_general", "brand_faye", "needs_review"):
        p = CAND / sub / f"{pack_id}.yaml"
        if p.exists():
            return p, sub
    return None, None


def extract_meta(yaml_text):
    """提取 knowledge_assertion 前 200 字 + scenario 简介"""
    m = re.search(r"^knowledge_assertion:\s*>?\-?\s*\n((?:  .+\n)+)", yaml_text, re.MULTILINE)
    assertion = ""
    if m:
        body = " ".join(line.strip() for line in m.group(1).splitlines() if line.strip())
        assertion = body[:300].replace("\n", " ")
    # source_md
    sm = re.search(r"^\s*source_md:\s*(.+?)\s*$", yaml_text, re.MULTILINE)
    source_md = sm.group(1).strip().strip("'\"") if sm else ""
    # production_tier (W11 已注入)
    pt = re.search(r"^production_tier:\s*(\S+)", yaml_text, re.MULTILINE)
    tier = pt.group(1).strip() if pt else ""
    pool = re.search(r"^default_call_pool:\s*(\S+)", yaml_text, re.MULTILINE)
    call_pool = pool.group(1).strip() if pool else ""
    return assertion, source_md, tier, call_pool


def main():
    pk = list(csv.DictReader(PK_REG.open(encoding="utf-8")))
    l2_packs = [r for r in pk if r["final_layer"] == "L2"]
    l3_packs = [r for r in pk if r["final_layer"] == "L3"]

    # ===== L2 审表 =====
    l2_rows = []
    for r in l2_packs:
        ypath, sub = find_yaml(r["pack_id"])
        if not ypath:
            continue
        text = ypath.read_text(encoding="utf-8")
        assertion, source_md, tier, pool = extract_meta(text)
        baseline = TIER_TO_BASELINE.get(tier, "")
        l2_rows.append({
            "pack_id": r["pack_id"],
            "yaml_path": str(ypath.relative_to(ROOT)),
            "source_md": source_md,
            "production_tier_w11": tier,
            "default_call_pool_w11": pool,
            "resource_baseline_auto": baseline,  # 已派生，可直接用
            "knowledge_assertion_excerpt": assertion,
            # 人工填列
            "production_difficulty": "",   # low | medium | high
            "hook": "",                    # ≥10 字
            "steps_json": "",              # JSON 列表 ≥2 项: ["开场...","中段...","结尾..."]
            "anti_pattern": "",            # ≥10 字
            "duration": "",                # short | medium | long
            "audience": "",                # ≥6 字
            "review_notes": "",
        })

    OUT_L2.parent.mkdir(parents=True, exist_ok=True)
    with OUT_L2.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(l2_rows[0].keys()))
        w.writeheader()
        w.writerows(l2_rows)

    # ===== L3 审表 =====
    l3_rows = []
    for r in l3_packs:
        ypath, sub = find_yaml(r["pack_id"])
        if not ypath:
            continue
        text = ypath.read_text(encoding="utf-8")
        assertion, source_md, _, _ = extract_meta(text)
        # 试图找 source_anchor 行号（从 evidence_quote 上面）
        ln_match = re.search(r"^\s*source_anchor:\s*(.+?)\s*$", text, re.MULTILINE)
        anchor = ln_match.group(1).strip().strip("'\"") if ln_match else ""
        l3_rows.append({
            "pack_id": r["pack_id"],
            "yaml_path": str(ypath.relative_to(ROOT)),
            "source_md": source_md,
            "source_anchor": anchor,
            "knowledge_assertion_excerpt": assertion,
            "suggested_runtime_asset_id": "RA-" + r["pack_id"][3:] if r["pack_id"].startswith("KP-") else "RA-" + r["pack_id"],
            # 人工填列
            "asset_type": "",          # shot_template | dialogue_template | action_template | prop_list | role_split
            "source_pointer": "",      # <source_md>:<line_no>，如 Q4-人设种子/xxx.md:42
            "review_notes": "",
        })

    with OUT_L3.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(l3_rows[0].keys()))
        w.writeheader()
        w.writerows(l3_rows)

    print(f"=== W12.A.3 + W12.A.4 · L2/L3 审表 ===\n")
    print(f"L2 审表 → {OUT_L2.relative_to(ROOT)}  ({len(l2_rows)} 行)")
    print(f"  字段: production_difficulty / hook / steps_json / anti_pattern / duration / audience")
    print(f"  resource_baseline 已自动派生（基于 W11 production_tier）")
    print()
    print(f"L3 审表 → {OUT_L3.relative_to(ROOT)}  ({len(l3_rows)} 行)")
    print(f"  字段: asset_type (5 类受控) / source_pointer (md:line)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

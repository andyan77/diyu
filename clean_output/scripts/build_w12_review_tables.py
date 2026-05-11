#!/usr/bin/env python3
"""W12.A.3 + W12.A.4 · 建 L2 / L3 审表

输入:
  audit/pack_layer_register.csv  (W11 真源 · 含 final_layer L1/L2/L3)
  candidates/**/*.yaml           (194 个 pack · 提取 knowledge_assertion 摘要)

输出:
  audit/l2_play_card_review.csv      (29 行)
    每行：pack_id + W11 基线字段（已填）+ W12 业务字段（人工填）
  audit/l3_runtime_asset_review.csv  (24 行)
    每行：pack_id + asset_type 候选 + title / summary（人工填）

人工填写规则见 templates/play_card_schema.md / runtime_asset_schema.md
"""
import csv
import re
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
PK_REG = ROOT / "audit" / "pack_layer_register.csv"
CAND = ROOT / "candidates"
OUT_L2 = ROOT / "audit" / "l2_play_card_review.csv"
OUT_L3 = ROOT / "audit" / "l3_runtime_asset_review.csv"


def find_yaml(pack_id):
    for sub in ("domain_general", "brand_faye", "needs_review"):
        p = CAND / sub / f"{pack_id}.yaml"
        if p.exists():
            return p, sub
    return None, None


def extract_assertion(text):
    m = re.search(r"^knowledge_assertion:\s*>?\-?\s*\n((?:  .+\n?)+)", text, re.MULTILINE)
    if m:
        body = " ".join(line.strip() for line in m.group(1).splitlines() if line.strip())
        return body[:200].replace("\n", " ")
    return ""


def yaml_field(text, key):
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)$", text, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else ""


def derive_resource_baseline(tier):
    return {
        "instant": "1人+手机+200元+4h",
        "long_term": "2-3人+轻设备+1000元+1-2天",
        "brand_tier": "专业团队+品牌资源+不限",
    }.get(tier, "")


# 启发式 asset_type 推断（仅作初猜，需人工确认）
ASSET_TYPE_HINTS = [
    ("shot_template",     ["镜头", "分镜", "运镜", "构图", "走位", "机位"]),
    ("dialogue_template", ["台词", "口播", "解说", "禁忌词", "禁区", "三问", "话术"]),
    ("action_template",   ["动作", "手势", "拍摄动作", "执行步骤", "操作步骤", "拍摄步骤"]),
    ("prop_list",         ["道具", "物料", "清单", "搭配清单"]),
    ("role_split",        ["分工", "员工", "店员", "店长", "角色"]),
]


def guess_asset_type(text):
    score = {}
    for at, kws in ASSET_TYPE_HINTS:
        n = sum(text.count(k) for k in kws)
        if n:
            score[at] = n
    if not score:
        return ""
    return max(score, key=score.get)


def main():
    pk = list(csv.DictReader(PK_REG.open(encoding="utf-8")))

    # ===== L2 审表 =====
    l2_rows = [r for r in pk if r["final_layer"] == "L2"]
    l2_out = []
    for r in l2_rows:
        ypath, sub = find_yaml(r["pack_id"])
        if not ypath:
            continue
        text = ypath.read_text(encoding="utf-8")
        tier = r.get("production_tier", "").strip()
        l2_out.append({
            "pack_id": r["pack_id"],
            "yaml_path": str(ypath.relative_to(ROOT)),
            "brand_layer_dir": sub,
            "knowledge_assertion_excerpt": extract_assertion(text),
            # W11 基线字段（已填，不让人改）
            "granularity_layer": "L2",
            "consumption_purpose": "generation",
            "production_tier": tier,
            "default_call_pool": r.get("default_call_pool", "").strip(),
            # 派生默认 resource_baseline，人工可改
            "resource_baseline_default": derive_resource_baseline(tier),
            # 人工填列
            "production_difficulty": "",   # low | medium | high  (必填)
            "resource_baseline": "",       # 留空则采用 default
            "hook": "",                    # ≥10 字
            "steps": "",                   # JSON list 或 ; 分隔
            "anti_pattern": "",            # ≥10 字
            "duration": "",                # short | medium | long
            "audience": "",                # ≥6 字
            "review_notes": "",
        })
    cols_l2 = list(l2_out[0].keys())
    OUT_L2.parent.mkdir(parents=True, exist_ok=True)
    with OUT_L2.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols_l2)
        w.writeheader()
        w.writerows(l2_out)

    # ===== L3 审表 =====
    l3_rows = [r for r in pk if r["final_layer"] == "L3"]
    l3_out = []
    for r in l3_rows:
        ypath, sub = find_yaml(r["pack_id"])
        if not ypath:
            continue
        text = ypath.read_text(encoding="utf-8")
        guess = guess_asset_type(text + r["pack_id"])
        # 用 pack_id 后缀生成 runtime_asset_id 候选
        ra_id = "RA-" + r["pack_id"].replace("KP-", "", 1)
        l3_out.append({
            "pack_id": r["pack_id"],
            "yaml_path": str(ypath.relative_to(ROOT)),
            "brand_layer_dir": sub,
            "knowledge_assertion_excerpt": extract_assertion(text),
            "granularity_layer": "L3",
            "runtime_asset_id_default": ra_id,
            "asset_type_guess": guess,
            # 人工填列
            "asset_type": "",              # 5 类受控枚举（必填）
            "runtime_asset_id": "",        # 留空采用 default
            "title": "",                   # ≥6 字
            "summary": "",                 # ≥10 字
            "review_notes": "",
        })
    cols_l3 = list(l3_out[0].keys())
    with OUT_L3.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols_l3)
        w.writeheader()
        w.writerows(l3_out)

    print(f"=== W12.A.3 审表 ===\n")
    print(f"  L2 玩法卡审表: {len(l2_out)} 行 → {OUT_L2.relative_to(ROOT)}")
    print(f"  L3 资产审表  : {len(l3_out)} 行 → {OUT_L3.relative_to(ROOT)}")
    from collections import Counter
    print(f"\n  L2 production_tier 分布: {dict(Counter(r['production_tier'] for r in l2_out))}")
    print(f"  L3 asset_type_guess 分布: {dict(Counter(r['asset_type_guess'] for r in l3_out))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

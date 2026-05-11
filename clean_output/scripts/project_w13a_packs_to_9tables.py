#!/usr/bin/env python3
"""W13.A.5b · 把 W13.A 7 个 brand pack 的 nine_table_projection 投影到 csv

读 candidates/needs_review/KP-*-faye-*.yaml 中 nine_table_projection 的 rule + evidence 行，
追加到 06_rule.csv 和 07_evidence.csv。

幂等：若 rule_id / evidence_id 已存在则跳过。
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEEDS = ROOT / "candidates" / "needs_review"
RULE_CSV = ROOT / "nine_tables" / "06_rule.csv"
EV_CSV = ROOT / "nine_tables" / "07_evidence.csv"

W13A_PATTERN = "*-faye-*.yaml"


def parse_inline_dict(s):
    """{rule_id: X, key: Y, ...} 简单 inline yaml dict 解析"""
    s = s.strip().lstrip("{").rstrip("}").strip()
    out = {}
    # 简单切分（不处理引号嵌套深层逻辑，因本批 yaml 都是规则化生成）
    parts = re.split(r",\s*(?=\w+:)", s)
    for p in parts:
        if ":" not in p:
            continue
        k, v = p.split(":", 1)
        out[k.strip()] = v.strip().strip('"')
    return out


def extract_block_lines(text, key):
    """提取顶层 key: 下的列表项（缩进式 yaml）"""
    # 先找 nine_table_projection: 块，再找其下 key:
    in_proj = False
    in_key = False
    items = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if line.startswith("nine_table_projection:"):
            in_proj = True
            continue
        if in_proj and not line.startswith(" ") and stripped:
            in_proj = False
            in_key = False
        if not in_proj:
            continue
        if line.startswith(f"  {key}:"):
            in_key = True
            continue
        if in_key:
            if line.startswith("  ") and not line.startswith("    "):
                in_key = False
                continue
            if stripped.startswith("- {") and stripped.endswith("}"):
                items.append(stripped[2:])  # 去掉 "- "
    return items


def extract_top_evidence(text):
    """读 yaml 顶层 evidence: 块的 source_md / anchor / source_type / inference_level / quote"""
    out = {}
    in_block = False
    quote_lines = []
    in_quote = False
    for line in text.splitlines():
        if line.startswith("evidence:"):
            in_block = True; continue
        if in_block:
            if line and not line.startswith(" ") and not line.startswith("\t"):
                in_block = False; continue
            stripped = line.strip()
            if stripped.startswith("source_md:"):
                out["source_md"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("source_anchor:"):
                out["source_anchor"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("source_type:"):
                out["source_type"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("inference_level:"):
                out["inference_level"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("evidence_quote:"):
                in_quote = True
                # 处理 evidence_quote: | 多行
                continue
            elif in_quote:
                if line.startswith("    ") or line.startswith("  - "):
                    quote_lines.append(line.strip())
                else:
                    in_quote = False
    out["evidence_quote"] = "\n".join(quote_lines).strip() if quote_lines else ""
    return out


def main():
    yamls = sorted(NEEDS.glob(W13A_PATTERN))
    if not yamls:
        print("无匹配 yaml")
        return 0

    # 读现有 csv
    existing_rules = set()
    rule_rows = list(csv.DictReader(RULE_CSV.open(encoding="utf-8")))
    rule_cols = list(rule_rows[0].keys())
    existing_rules = {r["rule_id"] for r in rule_rows}

    existing_evs = set()
    ev_rows = list(csv.DictReader(EV_CSV.open(encoding="utf-8")))
    ev_cols = list(ev_rows[0].keys())
    existing_evs = {r["evidence_id"] for r in ev_rows}

    new_rules = []
    new_evs = []
    for ypath in yamls:
        text = ypath.read_text(encoding="utf-8")
        pack_id = ypath.stem
        # rule
        for item in extract_block_lines(text, "rule"):
            d = parse_inline_dict(item)
            rid = d.get("rule_id")
            if not rid or rid in existing_rules:
                continue
            row = {
                "rule_id": rid,
                "rule_type": d.get("rule_type", ""),
                "applicable_when": d.get("applicable_when", ""),
                "success_scenario": d.get("success_scenario", ""),
                "flip_scenario": d.get("flip_scenario", ""),
                "alternative_boundary": d.get("alternative_boundary", ""),
                "brand_layer": "needs_review",
                "source_pack_id": pack_id,
            }
            new_rules.append(row)
            existing_rules.add(rid)
        # evidence — quote 取 yaml 顶层 evidence 块（完整文本），保证 G11 quote 一致
        top_ev = extract_top_evidence(text)
        for item in extract_block_lines(text, "evidence"):
            d = parse_inline_dict(item)
            eid = d.get("evidence_id")
            if not eid or eid in existing_evs:
                continue
            row = {
                "evidence_id": eid,
                "source_md": top_ev.get("source_md", d.get("source_md", "")),
                "source_anchor": top_ev.get("source_anchor", d.get("source_anchor", "")),
                "evidence_quote": top_ev.get("evidence_quote", d.get("evidence_quote", "")),
                "source_type": top_ev.get("source_type", d.get("source_type", "")),
                "inference_level": top_ev.get("inference_level", d.get("inference_level", "")),
                "brand_layer": "needs_review",
                "source_pack_id": pack_id,
            }
            new_evs.append(row)
            existing_evs.add(eid)

    # 追加写入
    if new_rules:
        with RULE_CSV.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rule_cols, extrasaction="ignore")
            w.writerows(new_rules)
        print(f"  ✅ 06_rule.csv +{len(new_rules)} 行")
    if new_evs:
        with EV_CSV.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=ev_cols, extrasaction="ignore")
            w.writerows(new_evs)
        print(f"  ✅ 07_evidence.csv +{len(new_evs)} 行")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

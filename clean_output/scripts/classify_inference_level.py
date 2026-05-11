#!/usr/bin/env python3
"""inference_level 名实对齐分类器

对 07_evidence.csv 每条 evidence 做三层分类：
  T1 strict_direct_quote: evidence_quote 严格 substring of MD（loose 空白归一）
  T2 paraphrase_authentic: phrase ≥30% 命中（合理 paraphrase / 多段拼接 / 压缩）
  T3 suspect: phrase <30% 命中（疑似编造，需人工 review）

输出 audit/inference_level_audit.csv 三列分类结果，供 repair_inference_level 消费。
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent
EVIDENCE = ROOT / "nine_tables" / "07_evidence.csv"
OUT = ROOT / "audit" / "_process" / "inference_level_audit.csv"

PUNCT_MAP = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "、": ",", "。": ".", "，": ",", "：": ":",
    "；": ";", "？": "?", "！": "!",
    "—": "-", "–": "-", "−": "-",
    " ": " ", " ": " ", "​": "",
    "（": "(", "）": ")", "【": "[", "】": "]",
})


def loose_norm(s):
    """空白 + 标点归一化"""
    s = (s or "").translate(PUNCT_MAP)
    return re.sub(r"\s+", " ", s).strip()


def loose_strip_punct(s):
    """归一 + 删所有 ASCII 标点和空白（用于 phrase 比对的'紧实'形式）"""
    s = loose_norm(s)
    return re.sub(r"[,.;:()\[\]\"'!?\-/|→<>=*\s]+", "", s)


def phrase_hit_rate(quote, md):
    q_n = loose_norm(quote)
    md_stripped = loose_strip_punct(md)
    md_n = loose_norm(md)
    phrases = [p.strip() for p in re.split(r"[,.;:()\[\]\"'!?\-/|→<>=*\s]+", q_n)
               if len(p.strip()) >= 6]
    if not phrases:
        return 1.0 if q_n in md_n else 0.0
    hit = sum(1 for p in phrases if p in md_stripped or p in md_n)
    return hit / len(phrases)


md_cache = {}
def load_md(rel):
    if rel in md_cache: return md_cache[rel]
    p = WORKSPACE / rel
    md_cache[rel] = p.read_text(encoding="utf-8") if p.exists() else None
    return md_cache[rel]


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(EVIDENCE, encoding="utf-8")))
    out_rows = []
    counts = {"T1_strict_direct_quote": 0, "T2_paraphrase_authentic": 0, "T3_suspect": 0}

    print("=== inference_level 名实分类（T1 / T2 / T3）===\n")

    for r in rows:
        ev_id = r["evidence_id"]
        cur_level = r["inference_level"]
        srcs = [s.strip() for s in r["source_md"].split("&") if s.strip()]
        if "/" not in srcs[0] and len(srcs) > 1:
            base = srcs[0].rsplit("/", 1)[0] if "/" in srcs[0] else ""
            srcs = [s if "/" in s else f"{base}/{s}" for s in srcs]
        anchor, quote = r["source_anchor"], r["evidence_quote"]

        best_strict_q = False
        best_strict_a = False
        best_phrase = 0.0
        for s in srcs:
            md = load_md(s)
            if md is None: continue
            md_n = loose_norm(md)
            if quote and loose_norm(quote) in md_n:
                best_strict_q = True
            if anchor and loose_norm(anchor) in md_n:
                best_strict_a = True
            best_phrase = max(best_phrase, phrase_hit_rate(quote, md))

        # 分类
        if best_strict_q:
            tier = "T1_strict_direct_quote"
            recommend = "direct_quote"
        elif best_phrase >= 0.3:
            tier = "T2_paraphrase_authentic"
            recommend = "low"
        else:
            tier = "T3_suspect"
            recommend = "low"  # 仍归 low，但标 suspect 需人工 review

        counts[tier] += 1
        change = "no_change" if cur_level == recommend else f"{cur_level}→{recommend}"
        out_rows.append({
            "evidence_id": ev_id,
            "current_inference_level": cur_level,
            "recommended_inference_level": recommend,
            "tier": tier,
            "strict_quote_match": best_strict_q,
            "strict_anchor_match": best_strict_a,
            "phrase_hit_rate": f"{best_phrase:.2f}",
            "change": change,
        })

    # 写清单
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    for k, n in counts.items():
        print(f"  {k}: {n}")
    changes = sum(1 for r in out_rows if r["change"] != "no_change")
    print(f"\n建议改动: {changes} 行 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Plan B · 生成 audit/evidence_row_adjudication.csv

每条 evidence 一行，列出：strict 严格命中 / 浅层 phrase 命中率 /
最长连续命中片段 / 裁决状态 / 推荐 inference_level / 警告。

裁决状态（reviewer 命名 paraphrase_located 而非 paraphrase_authentic）：
  - direct_quote_verified  : 字面（仅空白+标点归一后）出现在原 MD
  - paraphrase_located     : 严格不命中，但 phrase ≥30% 命中（有来源痕迹）
  - needs_human_review     : 严格不命中且 phrase < 30%（疑似编造）

inference_level_recommended 仅作 warning（不强制改写 07_evidence.csv）。
"""
import csv
import sys
from difflib import SequenceMatcher
from pathlib import Path

import os
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from verify_anchor_quote_authenticity import (  # noqa: E402
    normalize_ws, check_quote_strict, split_compound, load_md, SPLIT_CHARS,
)

EVIDENCE = ROOT / "nine_tables" / "07_evidence.csv"
OUT = ROOT / "audit" / "evidence_row_adjudication.csv"


def phrase_hit_stats(quote: str, md_text: str):
    q_norm = normalize_ws(quote)
    md_norm = normalize_ws(md_text)
    md_stripped = SPLIT_CHARS.sub("", md_norm)
    phrases = [p.strip() for p in SPLIT_CHARS.split(q_norm) if len(p.strip()) >= 6]
    if not phrases:
        return 0, 0, 0.0
    hits = sum(1 for p in phrases if p in md_stripped or p in md_norm)
    return len(phrases), hits, round(hits / len(phrases), 4)


def longest_span_in_md(quote: str, md_text: str, max_len: int = 80):
    """返回 (excerpt, span_start_in_md, span_end_in_md, line_no)
    span 偏移以 normalize_ws 后的 md 字符串为基准（与命中字符串一一对应）。
    line_no 以 1-based 原 md 行号粗定位（用未 normalize 的字符流做 quote 子串近似定位）。
    """
    q = normalize_ws(quote)
    m_norm = normalize_ws(md_text)
    if not q or not m_norm:
        return "", -1, -1, -1
    sm = SequenceMatcher(None, q, m_norm, autojunk=False)
    match = sm.find_longest_match(0, len(q), 0, len(m_norm))
    if match.size <= 0:
        return "", -1, -1, -1
    span = q[match.a : match.a + match.size]
    span_start = match.b
    span_end = match.b + match.size
    excerpt = span[:max_len].replace("\n", " ")

    # 粗定位 line_no：找 span 在原 md_text 中的近似位置（按归一化前的字符流找 8-char 锚）
    line_no = -1
    if match.size >= 6:
        anchor = span[: min(20, match.size)]
        # 用同样的 normalize 方法切原 md 行
        cum = 0
        for i, line in enumerate(md_text.splitlines(), start=1):
            line_norm = normalize_ws(line)
            if anchor[:8] in line_norm:
                line_no = i
                break
    return excerpt, span_start, span_end, line_no


def section_heading_for(md_text: str, line_no: int) -> str:
    """向上找最近的 markdown heading 行作为 original_section_heading"""
    if line_no <= 0:
        return ""
    lines = md_text.splitlines()
    for i in range(min(line_no, len(lines)) - 1, -1, -1):
        s = lines[i].lstrip()
        if s.startswith("#"):
            return s.lstrip("# ").strip()
    return ""


def adjudicate(strict_hit: bool, phrase_rate: float, current_level: str):
    if strict_hit:
        status = "direct_quote_verified"
        recommended = "direct_quote"
    elif phrase_rate >= 0.30:
        status = "paraphrase_located"
        recommended = "low"
    else:
        status = "needs_human_review"
        recommended = "low"
    warning = ""
    if current_level and current_level != recommended:
        warning = f"current={current_level} vs recommended={recommended} (warning only)"
    return status, recommended, warning


def main():
    rows = list(csv.DictReader(EVIDENCE.open(encoding="utf-8")))
    md_cache = {}
    out_rows = []
    counts = {"direct_quote_verified": 0, "paraphrase_located": 0, "needs_human_review": 0}
    warnings = 0

    for r in rows:
        ev_id = r["evidence_id"]
        srcs = split_compound(r.get("source_md", ""))
        anchor = r.get("source_anchor", "")
        quote = r.get("evidence_quote", "")
        current_level = r.get("inference_level", "")

        strict_hit = False
        best_total, best_hits, best_rate = 0, 0, 0.0
        best_excerpt = ""
        best_span_start = -1
        best_span_end = -1
        best_line_no = -1
        best_heading = ""
        used_md = ""

        for s in srcs:
            if s not in md_cache:
                md_cache[s] = load_md(s)
            md = md_cache[s]
            if md is None:
                continue
            if check_quote_strict(quote, md):
                strict_hit = True
            tot, hits, rate = phrase_hit_stats(quote, md)
            if rate > best_rate or (rate == best_rate and hits > best_hits):
                best_total, best_hits, best_rate = tot, hits, rate
                best_excerpt, best_span_start, best_span_end, best_line_no = longest_span_in_md(quote, md)
                best_heading = section_heading_for(md, best_line_no) if best_line_no > 0 else ""
                used_md = s

        status, recommended, warning = adjudicate(strict_hit, best_rate, current_level)
        counts[status] += 1
        if warning:
            warnings += 1

        out_rows.append({
            "evidence_id": ev_id,
            "source_md": used_md or (srcs[0] if srcs else ""),
            "source_anchor": anchor,
            "inference_level_current": current_level,
            "strict_substring_hit": "true" if strict_hit else "false",
            "phrase_total": best_total,
            "phrase_hits": best_hits,
            "phrase_hit_rate": best_rate,
            "best_span_excerpt": best_excerpt,
            "source_md_span_start": best_span_start,
            "source_md_span_end": best_span_end,
            "line_no": best_line_no,
            "original_section_heading": best_heading,
            "adjudication_status": status,
            "inference_level_recommended": recommended,
            "recommendation_warning": warning,
            "adjudicator": "auto",
            "rationale": {
                "direct_quote_verified": "字面在原 MD（空白+标点归一）",
                "paraphrase_located":    f"phrase 命中率 {best_rate:.0%} ≥ 30%（有原文痕迹）",
                "needs_human_review":    "严格不命中且 phrase < 30%，需人工裁决",
            }[status],
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    print(f"=== Plan B · evidence row adjudication ===\n")
    print(f"  总计 {len(out_rows)} 行 evidence 已裁决：")
    for k, n in counts.items():
        print(f"    {k:30s} {n}")
    print(f"  inference_level current vs recommended 不一致（warning，不阻断）: {warnings}")
    print(f"\n输出: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

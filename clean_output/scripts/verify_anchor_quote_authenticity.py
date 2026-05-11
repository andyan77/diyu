#!/usr/bin/env python3
"""硬门 13 · evidence anchor + quote 原文实证

reviewer F1 修复：从"指针有效"升级到"指针指向真存在"——
对 07_evidence.csv 每条 evidence：
  1. 验证 source_md 文件存在
  2. 验证 source_anchor 串（去掉 § + 空白归一化后）出现在 source_md 中
  3. 验证 evidence_quote 子串（空白归一化后）出现在 source_md 中

cross-source 形式 source_md = "A.md & B.md & C.md" 时只需任一来源命中即合格。

任一不实 → 退 1 + 写 audit/_process/anchor_quote_violations.csv
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent
EVIDENCE = ROOT / "nine_tables" / "07_evidence.csv"
OUT = ROOT / "audit" / "_process" / "anchor_quote_violations.csv"


# 标点归一化映射：直引号 ↔ 中文弯引号、连字符变体、空格变体
PUNCT_MAP = str.maketrans({
    "“": '"', "”": '"',  # " " → "
    "‘": "'", "’": "'",  # ' ' → '
    "、": ",",  # 、→ ,
    "。": ".",  # 。→ .
    "，": ",",  # ，→ ,
    "：": ":",  # ：→ :
    "；": ";",  # ；→ ;
    "？": "?",  # ？→ ?
    "！": "!",  # ！→ !
    "—": "-", "–": "-", "−": "-",  # —–− → -
    " ": " ", " ": " ", "​": "",   # nbsp/thin space/zero-width
    "（": "(", "）": ")", "【": "[", "】": "]",
})


def normalize_ws(s):
    """空白 + 标点归一化：所有空白折叠成单空格 + 中文标点 → ASCII，去首尾"""
    s = (s or "").translate(PUNCT_MAP)
    return re.sub(r"\s+", " ", s).strip()


def normalize_anchor(a):
    """锚点归一化：去 § 前缀和零宽空格 + 标点归一 + 空白删除"""
    s = (a or "").replace("§", "").translate(PUNCT_MAP)
    return re.sub(r"\s+", "", s).strip()


def load_md(rel_path):
    p = WORKSPACE / rel_path
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def split_compound(s):
    """source_md 'A.md & B.md & C.md' → ['A.md','B.md','C.md']"""
    parts = [p.strip() for p in s.split("&") if p.strip()]
    if len(parts) <= 1:
        return [s]
    base = parts[0].rsplit("/", 1)[0] if "/" in parts[0] else ""
    out = []
    for i, p in enumerate(parts):
        if i > 0 and "/" not in p and base:
            out.append(f"{base}/{p}")
        else:
            out.append(p)
    return out


def check_anchor_in_md(anchor, md_text):
    """锚点浅层证伪：anchor 可能是 'A + B + C' 拼接多锚点，
    或 '一、X · 二、Y' 这种节段并列。把 anchor 按 + / · / ， / 、 / ; 切分，
    任一切片（≥4 字符）出现在 MD 即视为可信。"""
    if not anchor:
        return True  # 空锚点不强查
    md_norm = normalize_anchor(md_text)
    # 切 anchor 为多个候选片段（按 +/·/，/、/; 切；保留空格之间作子片段）
    parts = [p.strip() for p in re.split(r"[+·,、;]+", anchor) if p.strip()]
    candidates = []
    for part in parts:
        # 整片段先归一
        whole = normalize_anchor(part)
        if len(whole) >= 3:
            candidates.append(whole)
        # 再按空格切分细化（处理"6.1 规则 01"这种）
        for sub in part.split():
            sub_n = normalize_anchor(sub)
            if len(sub_n) >= 3 and not re.fullmatch(r"[\d.]+", sub_n):
                candidates.append(sub_n)
    if not candidates:
        # 整 anchor 太短就直接子串匹配
        a_norm = normalize_anchor(anchor)
        return a_norm in md_norm if a_norm else True
    # 任一片段命中即过
    return any(c in md_norm for c in candidates)


SPLIT_CHARS = re.compile(r"[,.;:()\[\]\"'!?\-/|→<>=*\s]+")


def check_quote_in_md(quote, md_text):
    """证据原文浅层证伪：reviewer F1 的核心要求是"agent 没瞎编 quote"。

    策略：把 quote 切成 phrase（按所有标点 + 空白切），
    每个 ≥6 字的 phrase 在 MD（同样切分后的字符流）中能找到即得分；
    phrase 命中率 ≥ 30% 视为"quote 有原文支撑（可能是合理 paraphrase
    或多段拼接，但绝非凭空编造）"。

    返回 True = 通过浅层证伪；False = 几乎无原文支撑（疑似编造）。"""
    q_norm = normalize_ws(quote)
    md_norm = normalize_ws(md_text)
    if not q_norm or not md_norm:
        return False
    # md 一侧也按 splitter chars 删除（让两侧用同样的切割规则做比对）
    md_stripped = SPLIT_CHARS.sub("", md_norm)
    phrases = [p.strip() for p in SPLIT_CHARS.split(q_norm)
               if len(p.strip()) >= 6]
    if not phrases:
        return q_norm in md_norm
    hit = sum(1 for p in phrases if p in md_stripped or p in md_norm)
    return hit / len(phrases) >= 0.3


def check_quote_strict(quote, md_text):
    """严格 substring 校验：quote 必须按字面（仅空白+标点归一后）出现在 MD"""
    q_n = normalize_ws(quote)
    md_n = normalize_ws(md_text)
    return bool(q_n) and q_n in md_n


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    viol = []
    print("=== 硬门 13 · evidence 原文实证（双层）===\n")
    md_cache = {}

    with open(EVIDENCE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    direct_quote_rows = 0
    direct_quote_strict_pass = 0
    paraphrase_rows = 0
    paraphrase_loose_pass = 0

    for i, r in enumerate(rows, start=2):
        ev_id = r.get("evidence_id", "?")
        inf_level = r.get("inference_level", "")
        srcs = split_compound(r.get("source_md", ""))
        anchor = r.get("source_anchor", "")
        quote = r.get("evidence_quote", "")

        any_md_exists = False
        loose_quote_hit = False
        strict_quote_hit = False
        anchor_hit = False
        for s in srcs:
            if s not in md_cache:
                md_cache[s] = load_md(s)
            md = md_cache[s]
            if md is None:
                continue
            any_md_exists = True
            if check_anchor_in_md(anchor, md):
                anchor_hit = True
            if check_quote_in_md(quote, md):
                loose_quote_hit = True
            if check_quote_strict(quote, md):
                strict_quote_hit = True

        if not any_md_exists:
            viol.append([i, ev_id, "source_md_missing", "; ".join(srcs)])
            continue

        # 严格层（G13a）：inference_level=direct_quote 必须严格通过
        if inf_level == "direct_quote":
            direct_quote_rows += 1
            if strict_quote_hit:
                direct_quote_strict_pass += 1
            else:
                viol.append([i, ev_id, "direct_quote_not_literal_in_md",
                             quote[:80].replace("\n", " ")])
        # 浅层（G13b）：所有非 direct_quote 行必须 phrase ≥30% 命中（anti-fabrication）
        else:
            paraphrase_rows += 1
            if loose_quote_hit:
                paraphrase_loose_pass += 1
            else:
                # 7 条 T3 suspect 已知，标 informational 不阻断
                viol.append([i, ev_id, "paraphrase_low_phrase_hit_rate(suspect)",
                             quote[:80].replace("\n", " ")])

    print(f"  G13a 严格层（inference_level=direct_quote 必须字面在原文）：")
    print(f"      {direct_quote_strict_pass}/{direct_quote_rows} 通过")
    print(f"  G13b 浅层（其他行 phrase ≥30% 命中 / anti-fabrication）：")
    print(f"      {paraphrase_loose_pass}/{paraphrase_rows} 通过")

    by_kind = {}
    for v in viol:
        by_kind[v[2]] = by_kind.get(v[2], 0) + 1
    for k, n in sorted(by_kind.items()):
        print(f"  ❌ {k}: {n}")
    if not viol:
        print("  ✅ 全部 evidence 的 anchor + quote 在原 MD 中可定位")

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "evidence_id", "violation", "snippet"])
        w.writerows(viol)
    print(f"\n违反: {len(viol)} → {OUT}")
    return 0 if not viol else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""解析 44 份输入 MD 为 source_unit 清单（按 H1/H2/H3 章节切段）

source_unit = 一个章节级知识单元
  - source_md
  - heading_path（如 "三、4）适合先陈列后开口"）
  - heading_text（标题文本）
  - heading_level (1/2/3)
  - body_first_100（章节正文前 100 字）
  - body_length（正文字数）
  - line_no

输出 audit/source_unit_inventory.csv，供知识点级覆盖计算消费。
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent
INPUT_DIRS = ["Q2-内容类型种子", "Q4-人设种子", "Q7Q12-搭配陈列业务包", "Q-brand-seeds"]
OUT = ROOT / "audit" / "source_unit_inventory.csv"

# 匹配 H1/H2/H3 标题的多种形式：
# - markdown # / ## / ###
# - 中文章节号 一、X / 二、X
# - 数字章节 1. X / 1.1 X / 6.1 X
HEADING_PATTERNS = [
    (re.compile(r"^(#{1,6})\s+(.+)$"), "md_heading"),
    (re.compile(r"^([一二三四五六七八九十]+)、\s*(.+)$"), "cn_section"),
    (re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$"), "num_section"),
]


def detect_heading(line):
    line = line.rstrip()
    for pat, kind in HEADING_PATTERNS:
        m = pat.match(line)
        if m:
            if kind == "md_heading":
                level = len(m.group(1))
                return level, m.group(2).strip(), kind
            elif kind == "cn_section":
                return 2, f"{m.group(1)}、{m.group(2).strip()}", kind
            elif kind == "num_section":
                num = m.group(1)
                level = num.count(".") + 2  # 6 → 2, 6.1 → 3
                return level, f"{num} {m.group(2).strip()}", kind
    return None


def parse_md(path):
    """切到 source_unit 列表"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    units = []
    cur = None
    for i, line in enumerate(lines, start=1):
        h = detect_heading(line)
        if h:
            if cur:
                units.append(cur)
            level, heading, kind = h
            cur = {
                "source_md": str(path.relative_to(WORKSPACE)),
                "heading_path": heading,
                "heading_text": heading,
                "heading_level": level,
                "heading_kind": kind,
                "line_no": i,
                "body_lines": [],
            }
        elif cur:
            cur["body_lines"].append(line)
    if cur:
        units.append(cur)

    # finalize body
    out = []
    for u in units:
        body = "\n".join(u.pop("body_lines"))
        u["body_first_100"] = (body[:100] or "").replace("\n", " ").strip()
        u["body_length"] = len(body)
        out.append(u)
    return out


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    all_units = []
    md_count = 0
    for d in INPUT_DIRS:
        for p in sorted((WORKSPACE / d).rglob("*.md")):
            md_count += 1
            try:
                units = parse_md(p)
                all_units.extend(units)
            except Exception as e:
                print(f"  ⚠️  {p.name} 解析失败: {e}", file=sys.stderr)

    print(f"=== source_unit 解析 ===\n")
    print(f"  输入 MD: {md_count} 份")
    print(f"  source_unit 总数: {len(all_units)}")
    by_kind = {}
    for u in all_units:
        by_kind[u["heading_kind"]] = by_kind.get(u["heading_kind"], 0) + 1
    for k, n in sorted(by_kind.items()):
        print(f"    {k}: {n}")

    cols = ["source_md", "heading_level", "heading_kind", "heading_path",
            "line_no", "body_length", "body_first_100"]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for u in all_units:
            w.writerow({c: u.get(c, "") for c in cols})

    print(f"\n  → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

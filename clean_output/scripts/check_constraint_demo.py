#!/usr/bin/env python3
"""硬门 8 · brand_layer CHECK 约束反例验证

对一张内存表 SQLite 应用同一段 CHECK 表达式：
  4 反例 INSERT 必须全部触发 IntegrityError
  1 正例 INSERT (brand_xyz) 必须成功

反例覆盖：
  brand_         空尾巴
  brand_X        含大写
  brand_with-dash 含横线
  brand_中文     非 ASCII
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "storage" / "sqlite3_demo_log.txt"

DDL = """
CREATE TABLE t (
    brand_layer TEXT NOT NULL,
    CHECK (brand_layer = 'domain_general'
           OR brand_layer = 'needs_review'
           OR (brand_layer GLOB 'brand_[a-z]*'
               AND brand_layer NOT GLOB '*[^a-z_]*'
               AND length(brand_layer) > 6))
);
"""

NEG_CASES = [
    ("brand_",          "空尾巴：长度 6，不满足 length>6"),
    ("brand_X",         "大写字母 X，不满足 GLOB 'brand_[a-z]*'"),
    ("brand_with-dash", "横线 -，被 NOT GLOB '*[^a-z_]*' 排除"),
    ("brand_中文",      "非 ASCII，被 NOT GLOB '*[^a-z_]*' 排除"),
]

POS_CASES = [
    ("domain_general", "通用层"),
    ("needs_review",   "待审"),
    ("brand_xyz",      "品牌 xyz"),
    ("brand_a_b",      "下划线连缀"),
]


def main():
    lines = []
    def out(s=""):
        print(s)
        lines.append(s)

    out("=== 硬门 8 · brand_layer CHECK 约束反例 demo ===")
    out("")
    conn = sqlite3.connect(":memory:")
    conn.executescript(DDL)
    out("DDL applied:")
    out(DDL.strip())
    out("")

    out("--- 反例（应全部 fail）---")
    neg_ok = 0
    for v, why in NEG_CASES:
        try:
            conn.execute("INSERT INTO t(brand_layer) VALUES (?)", (v,))
            out(f"  ❌ '{v}' 不应通过却通过了")
        except sqlite3.IntegrityError as e:
            out(f"  ✅ '{v}' 拒绝 ({why})")
            neg_ok += 1

    out("")
    out("--- 正例（应全部 ok）---")
    pos_ok = 0
    for v, why in POS_CASES:
        try:
            conn.execute("INSERT INTO t(brand_layer) VALUES (?)", (v,))
            out(f"  ✅ '{v}' 接受 ({why})")
            pos_ok += 1
        except sqlite3.IntegrityError as e:
            out(f"  ❌ '{v}' 不应拒绝却拒绝: {e}")

    conn.rollback()
    conn.close()

    out("")
    out(f"反例 {neg_ok}/{len(NEG_CASES)} · 正例 {pos_ok}/{len(POS_CASES)}")
    rc = 0 if (neg_ok == len(NEG_CASES) and pos_ok == len(POS_CASES)) else 1
    out(f"exit={rc}")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n日志: {LOG}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

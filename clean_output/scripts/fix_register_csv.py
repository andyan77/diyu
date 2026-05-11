#!/usr/bin/env python3
"""硬门 5 · unprocessable_register 列漂移修复 + 备份

实测 5 行 (line 38/39/41/45/46) 列数 8，缺 source_anchor (col2)。
最小干预修复：在 col2 位置插入空字符串占位（source_anchor 留空待补），
原 col1 的 source_md 中已混入 §X 章节信息，保持原样。

修复后跑 csv 模块严格校验：每行 9 列对齐。
"""
import csv
import datetime as dt
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTER = ROOT / "clean_output" / "unprocessable_register" / "register.csv"

def main():
    # backup
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = REGISTER.with_suffix(f".csv.bak.{ts}")
    shutil.copy(REGISTER, bak)
    print(f"备份: {bak}")

    with open(REGISTER, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    ncols = len(header)
    print(f"header 列数: {ncols} | {header}")

    fixed = []
    fixed.append(header)
    fix_count = 0
    for i, row in enumerate(rows[1:], start=2):
        if len(row) == ncols:
            fixed.append(row)
        elif len(row) == ncols - 1:
            # 缺 source_anchor (col2)：在 col1 后插入空字符串
            new_row = row[:2] + [""] + row[2:]
            fixed.append(new_row)
            print(f"  fix line {i}: 插入空 source_anchor (col2)")
            fix_count += 1
        else:
            # 其他列差，留原样并报告
            fixed.append(row)
            print(f"  WARN line {i}: cols={len(row)} 与 header({ncols}) 差 != 1，未自动修")

    with REGISTER.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerows(fixed)

    # 严格回读校验
    with open(REGISTER, encoding="utf-8") as f:
        check = list(csv.reader(f))
    bad = [i for i, r in enumerate(check[1:], start=2) if len(r) != ncols]
    print(f"修复 {fix_count} 行 / 修复后 BAD = {len(bad)}")
    return 0 if not bad else 1

if __name__ == "__main__":
    sys.exit(main())

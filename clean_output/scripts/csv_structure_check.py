#!/usr/bin/env python3
"""硬门 0 · CSV 结构验收（只读诊断 / 不写）

用 csv 模块严格读 9 nine_tables csv + register csv，校验：
- 每行列数 = header 列数
- 07_evidence 的 source_type / inference_level 取值落在受控枚举

任一不过 → 退出 1 + 落 audit/_process/csv_struct_violations.csv
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
NINE = ROOT / "clean_output" / "nine_tables"
REGISTER = ROOT / "clean_output" / "unprocessable_register" / "register.csv"
OUT = ROOT / "clean_output" / "audit" / "_process" / "csv_struct_violations.csv"

# 受控枚举（v2-rev3 §1.1 实测真值）
EVIDENCE_SOURCE_TYPE = {
    "cross_source_consensus", "explicit_business_decision", "explicit_business_rule",
    "explicit_play_card", "explicit_role_skill_lock", "structural_pattern",
    # legacy 早期 W1 的样本
    "explicit_business_decision", "direct_quote",
}
EVIDENCE_INFERENCE_LEVEL = {"direct_quote", "low", "structural_induction"}

def check_csv(path):
    """返回 (rows_total, bad_rows, distinct_cols dict)"""
    bad = []
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return 0, [], {}
        ncols = len(header)
        rows = []
        for i, row in enumerate(reader, start=2):
            if len(row) != ncols:
                bad.append((i, len(row), ncols))
            else:
                rows.append(row)
    distinct = {}
    if rows:
        for col_idx, col_name in enumerate(header):
            distinct[col_name] = sorted({row[col_idx] for row in rows})
    return len(rows), bad, distinct

def main():
    violations = []
    print("=== nine_tables 9 张 csv ===")
    for csvf in sorted(NINE.glob("*.csv")):
        n, bad, distinct = check_csv(csvf)
        status = "OK" if not bad else f"BAD x{len(bad)}"
        print(f"  {csvf.name:25s} rows={n:4d}  {status}")
        for line, got, want in bad:
            violations.append([csvf.name, line, "col_count", f"got={got} want={want}", ""])

        # 07_evidence 枚举校验
        if csvf.name == "07_evidence.csv":
            st = set(distinct.get("source_type", []))
            il = set(distinct.get("inference_level", []))
            bad_st = st - EVIDENCE_SOURCE_TYPE
            bad_il = il - EVIDENCE_INFERENCE_LEVEL
            if bad_st:
                print(f"    source_type 越界: {bad_st}")
                for v in bad_st:
                    violations.append([csvf.name, "-", "source_type", v, "not in canonical 6 values"])
            if bad_il:
                print(f"    inference_level 越界: {bad_il}")
                for v in bad_il:
                    violations.append([csvf.name, "-", "inference_level", v, "not in canonical 3 values"])

    print(f"\n=== unprocessable_register csv ===")
    if REGISTER.exists():
        n, bad, _ = check_csv(REGISTER)
        status = "OK" if not bad else f"BAD x{len(bad)}"
        print(f"  {REGISTER.name:25s} rows={n:4d}  {status}")
        for line, got, want in bad:
            violations.append([REGISTER.name, line, "col_count", f"got={got} want={want}",
                               "由硬门 5 修复"])

    # 落违反清单
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "line", "violation", "value", "note"])
        w.writerows(violations)

    print(f"\n违反总数: {len(violations)}")
    print(f"清单写入: {OUT}")
    return 0 if not violations else 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""硬门 6 · CSV ↔ SQLite 一致性（PK 唯一 + 内容 hash 比对）

⚠️  已废弃 / DEPRECATED · 2026-05-12 ⚠️
本脚本 Phase 2 起不再被消费 / no longer consumed by Phase 2。
处置依据 / disposition: clean_output/audit/db_state_evidence_KS-S0-002.md（path B）
Phase 2 serving 工程唯一真源 = 9 张 CSV / 9 tables (clean_output/nine_tables/*.csv)
保留本文件仅作 Phase 1 历史档案 / kept as Phase 1 archive only.

流程（历史 / historical）：
  1. 应用 DDL 到一张干净 sqlite db（默认 storage/knowledge.db，可 --memory）
  2. 装载 9 张 CSV（用 INSERT，不 OR IGNORE——重复 PK 立即报错）
  3. 对每张表分别：
       - CSV 端：行数、PK 唯一性、内容 sha256
       - SQLite 端：COUNT(*)、内容 sha256（同序）
       - 比对
  4. 任一环节失败 → 退出 1，写明 mismatch 行
  5. 通过 → 写 audit/_process/csv_sqlite_consistency.csv（9 行各表证书）
"""
import argparse
import csv
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

# Deprecation gate / 废弃拦截
if not os.environ.get("ALLOW_DEPRECATED_LOAD_TO_SQLITE"):
    sys.stderr.write(
        "❌ load_to_sqlite.py 已废弃 / deprecated 2026-05-12\n"
        "   见 clean_output/audit/db_state_evidence_KS-S0-002.md\n"
        "   如确需运行（仅历史复盘）：\n"
        "     ALLOW_DEPRECATED_LOAD_TO_SQLITE=1 python3 clean_output/scripts/load_to_sqlite.py\n"
    )
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
DDL = ROOT / "storage" / "single_db_logical_isolation.sql"
NINE = ROOT / "nine_tables"
DB = ROOT / "storage" / "knowledge.db"
REPORT = ROOT / "audit" / "_process" / "csv_sqlite_consistency.csv"

TBL = {
    "object_type":  ("01_object_type",  ["type_id"]),
    "field":        ("02_field",        ["field_id"]),
    "semantic":     ("03_semantic",     ["semantic_id"]),
    "value_set":    ("04_value_set",    ["value_set_id", "value"]),
    "relation":     ("05_relation",     ["relation_id"]),
    "rule":         ("06_rule",         ["rule_id"]),
    "evidence":     ("07_evidence",     ["evidence_id"]),
    "lifecycle":    ("08_lifecycle",    ["lifecycle_id"]),
    "call_mapping": ("09_call_mapping", ["mapping_id"]),
}


def row_hash(rows, cols):
    """对一组 dict 行求 sha256（按 cols 顺序、按 PK 排序，确保确定性）。"""
    h = hashlib.sha256()
    for r in rows:
        line = "".join((r.get(c) or "") for c in cols)
        h.update(line.encode("utf-8"))
        h.update(b"")
    return h.hexdigest()


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f)), csv.DictReader(open(path, encoding="utf-8")).fieldnames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--memory", action="store_true", help="使用 :memory: 而非物理 db")
    args = ap.parse_args()

    if not args.memory and DB.exists():
        DB.unlink()
    conn = sqlite3.connect(":memory:" if args.memory else str(DB))
    conn.execute("PRAGMA foreign_keys = ON")  # F2 启用 FK 约束
    conn.executescript(DDL.read_text(encoding="utf-8"))

    report_rows = []
    fail = 0

    print("=== 硬门 6 · CSV↔SQLite 一致性 ===\n")
    for table, (stem, pk_cols) in TBL.items():
        path = NINE / f"{stem}.csv"
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames
            rows = list(reader)

        # PK 唯一性
        seen = {}
        for i, r in enumerate(rows, start=2):
            key = tuple(r[c] for c in pk_cols)
            if key in seen:
                print(f"  ❌ {stem}: PK 重复 {key} (line {i} & {seen[key]})")
                fail += 1
            seen[key] = i

        # 排序：按 PK 求 hash
        sorted_rows = sorted(rows, key=lambda r: tuple(r[c] for c in pk_cols))
        csv_hash = row_hash(sorted_rows, cols)

        # INSERT (不 OR IGNORE)
        placeholders = ",".join("?" * len(cols))
        try:
            conn.executemany(
                f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                [tuple(r[c] for c in cols) for r in rows],
            )
        except sqlite3.IntegrityError as e:
            print(f"  ❌ {stem}: INSERT 失败 — {e}")
            fail += 1
            continue

        # SQLite 端 hash
        cur = conn.execute(f"SELECT {','.join(cols)} FROM {table} ORDER BY {','.join(pk_cols)}")
        db_rows = []
        for tup in cur.fetchall():
            db_rows.append({c: ("" if v is None else str(v)) for c, v in zip(cols, tup)})
        db_hash = row_hash(db_rows, cols)

        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
        db_count = cur.fetchone()[0]

        ok = (csv_hash == db_hash and db_count == len(rows))
        mark = "✅" if ok else "❌"
        if not ok:
            fail += 1
        print(f"  {mark} {stem:20s} csv_rows={len(rows):4d}  db_rows={db_count:4d}  "
              f"csv_hash={csv_hash[:12]}  db_hash={db_hash[:12]}")

        report_rows.append([table, stem, len(rows), db_count, csv_hash, db_hash, "ok" if ok else "MISMATCH"])

    conn.commit()
    conn.close()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "csv_stem", "csv_rows", "db_rows", "csv_sha256", "db_sha256", "status"])
        w.writerows(report_rows)

    print(f"\n报告: {REPORT}")
    if fail:
        print(f"\n❌ 失败 {fail} 项")
        return 1
    print(f"\n✅ 9 表 PK 唯一 + 内容 hash 全部对齐  db: {'memory' if args.memory else DB}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

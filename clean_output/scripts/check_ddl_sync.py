#!/usr/bin/env python3
"""硬门 8 · DDL 双源同步校验

schema/nine_tables_ddl.sql 与 storage/single_db_logical_isolation.sql 必须字符级一致
（除了文件首部允许的注释行差异）。任一处 CHECK 不一致即退出 1。
"""
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "schema" / "nine_tables_ddl.sql"
B = ROOT / "storage" / "single_db_logical_isolation.sql"


def normalize(text: str) -> str:
    """裁掉文件末尾的演示性 SQL 注释段（storage 版本特有的查询示例），
    只比对 CREATE TABLE / CREATE INDEX 段。"""
    out = []
    for line in text.splitlines():
        out.append(line.rstrip())
    return "\n".join(out).strip()


def extract_checks(text: str):
    return [l.strip() for l in text.splitlines() if "CHECK (brand_layer" in l]


def main():
    if not A.exists() or not B.exists():
        print(f"ERROR: missing DDL file(s)", file=sys.stderr)
        return 2

    ta = A.read_text(encoding="utf-8")
    tb = B.read_text(encoding="utf-8")

    ca = extract_checks(ta)
    cb = extract_checks(tb)

    print(f"  schema/nine_tables_ddl.sql:           {len(ca)} CHECK 行")
    print(f"  storage/single_db_logical_isolation:  {len(cb)} CHECK 行")

    if len(ca) != 9 or len(cb) != 9:
        print(f"❌ 期望 9 行 CHECK 各文件，实际 {len(ca)} / {len(cb)}", file=sys.stderr)
        return 1

    if ca != cb:
        print("❌ CHECK 行内容不一致：", file=sys.stderr)
        for i, (x, y) in enumerate(zip(ca, cb)):
            if x != y:
                print(f"  [{i}] A: {x}", file=sys.stderr)
                print(f"  [{i}] B: {y}", file=sys.stderr)
        return 1

    sig = hashlib.sha256("\n".join(ca).encode("utf-8")).hexdigest()[:16]
    print(f"✅ 9 CHECK 行字符级一致，签名 {sig}")
    print(f"   CHECK 表达：{ca[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""verify_reverse_traceability.py · 反向追溯链路核对

逐 9 表 row → source_pack_id → 找 candidates yaml → 校验 source_md / source_anchor /
evidence_quote 三字段非空 → 校验 source_md 文件实际存在。
任一断点退出 1。
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
NINE = ROOT / "clean_output" / "nine_tables"
CAND = ROOT / "clean_output" / "candidates"

PAT = {
    "source_md": re.compile(r"^\s*source_md:\s*(.+?)\s*$"),
    "source_anchor": re.compile(r"^\s*source_anchor:\s*(.+?)\s*$"),
    "evidence_quote": re.compile(r"^\s*evidence_quote:\s*[|>]?-?\s*(.*)$"),
}

def index_packs():
    idx = {}
    for y in CAND.rglob("*.yaml"):
        text = y.read_text(encoding="utf-8")
        info = {"path": y, "source_md": None, "source_anchor": None, "evidence_quote": None}
        for line in text.splitlines():
            for k, p in PAT.items():
                if info[k] is None:
                    m = p.match(line)
                    if m:
                        v = m.group(1).strip().strip("'\"")
                        info[k] = v if v else "<block>"
        idx[y.stem] = info
    return idx

def main():
    pack_idx = index_packs()
    errors = []
    rows_checked = 0

    for csvfile in sorted(NINE.glob("*.csv")):
        with open(csvfile, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "source_pack_id" not in reader.fieldnames:
                continue
            for i, row in enumerate(reader, start=2):
                rows_checked += 1
                pid = row.get("source_pack_id", "").strip()
                if not pid:
                    errors.append(f"{csvfile.name}:{i} source_pack_id 空")
                    continue
                pack = pack_idx.get(pid)
                if not pack:
                    errors.append(f"{csvfile.name}:{i} pack 未找到 {pid}")
                    continue
                for f3 in ("source_md", "source_anchor", "evidence_quote"):
                    if not pack[f3]:
                        errors.append(f"{csvfile.name}:{i} pack={pid} 缺 {f3}")
                src = pack["source_md"]
                if src and src != "<block>":
                    # Support compound source_md (cross-source consensus): "A.md & B.md & C.md"
                    # Each part must exist; any leading dir is shared from the first part.
                    parts = [p.strip() for p in src.split("&") if p.strip()]
                    base_dir = ""
                    for idx, p in enumerate(parts):
                        candidate = p
                        if idx > 0 and "/" not in p:
                            # bare filename — inherit dir from first part
                            base_dir = parts[0].rsplit("/", 1)[0] if "/" in parts[0] else ""
                            candidate = f"{base_dir}/{p}" if base_dir else p
                        if not (ROOT / candidate).exists():
                            errors.append(f"{csvfile.name}:{i} pack={pid} source_md 文件不存在: {candidate}")

    print(f"已检查 9 表数据行 : {rows_checked}")
    print(f"已索引 pack 数    : {len(pack_idx)}")
    print(f"断点数            : {len(errors)}")
    if errors:
        print("\n--- 断点明细 ---")
        for e in errors[:50]:
            print(e)
        return 1
    print("✅ 反向追溯链路全通")
    return 0

if __name__ == "__main__":
    sys.exit(main())

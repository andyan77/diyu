#!/usr/bin/env python3
"""scan_unprocessed_md.py · 正向覆盖率检测

扫描 3 个素材目录的全部 .md，对照 candidates/*/*.yaml 中 source_md 字段，
列出"已抽 / 未抽"两份清单 + 覆盖率，写入 audit/coverage_report.md 末尾节并打印。
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_DIRS = ["Q2-内容类型种子", "Q4-人设种子", "Q7Q12-搭配陈列业务包", "Q-brand-seeds"]
CAND_DIR = ROOT / "clean_output" / "candidates"

def list_input_md():
    out = []
    for d in INPUT_DIRS:
        p = ROOT / d
        if not p.exists():
            continue
        for f in sorted(p.rglob("*.md")):
            out.append(str(f.relative_to(ROOT)))
    return out

def list_processed_source_md():
    pat = re.compile(r"^\s*source_md:\s*(.+?)\s*$")
    seen = set()
    for y in CAND_DIR.rglob("*.yaml"):
        for line in y.read_text(encoding="utf-8").splitlines():
            m = pat.match(line)
            if m:
                v = m.group(1).strip().strip("'\"")
                # Support compound source_md "A.md & B.md & C.md" (cross-source consensus)
                if "&" in v:
                    parts = [p.strip() for p in v.split("&") if p.strip()]
                    base_dir = parts[0].rsplit("/", 1)[0] if "/" in parts[0] else ""
                    for idx, p in enumerate(parts):
                        if idx > 0 and "/" not in p and base_dir:
                            seen.add(f"{base_dir}/{p}")
                        else:
                            seen.add(p)
                else:
                    seen.add(v)
                break
    return seen

REGISTER_MD = ROOT / "clean_output" / "audit" / "uncovered_md_register.md"

def load_registered_5class():
    """读 uncovered_md_register.md 表格，返回 {source_md: (classification, resolved_by)}"""
    if not REGISTER_MD.exists():
        return {}
    out = {}
    pat = re.compile(r"^\|\s*([^|]+?\.md)\s*\|\s*([a-z_]+)\s*\|\s*([^|]+?)\s*\|")
    for line in REGISTER_MD.read_text(encoding="utf-8").splitlines():
        m = pat.match(line)
        if m:
            src, cls, by = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            if by and by != "_pending_review_":
                out[src] = (cls, by)
    return out

def main():
    inputs = list_input_md()
    processed = list_processed_source_md()
    registered = load_registered_5class()
    processed_in_scope = {p for p in processed if p in inputs}
    resolved_via_register = {p for p in inputs if p in registered}
    closed = processed_in_scope | resolved_via_register
    unprocessed = [p for p in inputs if p not in closed]

    cov_raw = len(processed_in_scope) / len(inputs) if inputs else 0
    cov_total = len(closed) / len(inputs) if inputs else 0
    print(f"输入 MD 总数      : {len(inputs)}")
    print(f"已抽 pack         : {len(processed_in_scope)}")
    print(f"5-class 闭环签字  : {len(resolved_via_register)}")
    print(f"覆盖率(直抽)      : {cov_raw*100:.1f}%")
    print(f"闭环率(直抽+签字) : {cov_total*100:.1f}%")
    print(f"未闭环 MD 数      : {len(unprocessed)}")
    if unprocessed:
        print("\n--- 未闭环 MD 清单 ---")
        for u in unprocessed:
            print(u)
    print("\n--- 5-class 签字分布 ---")
    by_cls = {}
    for src, (cls, by) in registered.items():
        by_cls.setdefault(cls, []).append(src)
    for cls in sorted(by_cls):
        print(f"  {cls}: {len(by_cls[cls])}")
    return 0 if not unprocessed else 1

if __name__ == "__main__":
    sys.exit(main())

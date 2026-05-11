#!/usr/bin/env python3
"""消费 coverage_status.json 渲染 audit/coverage_report.md"""
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "audit" / "coverage_status.json"
OUT = ROOT / "audit" / "coverage_report.md"


def main():
    if not STATUS.exists():
        print("先跑 compute_coverage_status.py", file=sys.stderr)
        return 2
    s = json.loads(STATUS.read_text(encoding="utf-8"))

    md = []
    md.append(f"# coverage_report · 输入 MD 闭环状态\n")
    md.append(f"> 自动渲染于 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 数据源：audit/coverage_status.json（SSOT）\n")
    md.append("## 总览\n")
    md.append(f"- 输入 MD 总数：**{s['total_input_md']}**")
    md.append(f"- 直接抽出 pack：**{s['directly_processed']}** ({s['raw_coverage_pct']}%)")
    md.append(f"- 5-class 签字闭环：**{s['resolved_via_5class_register']}**")
    md.append(f"- 闭环率：**{s['closure_rate_pct']}%**")
    md.append(f"- 未闭环：**{s['unprocessed']}**\n")

    md.append("## 5-class 签字分布\n")
    md.append("| classification | 数量 |")
    md.append("| --- | ---: |")
    for k, n in s["five_class_distribution"].items():
        md.append(f"| {k} | {n} |")
    md.append("")

    md.append("## 5-class 签字明细\n")
    md.append("| source_md | classification | resolved_by |")
    md.append("| --- | --- | --- |")
    for src, meta in s["register_detail"].items():
        rb = meta["resolved_by"]
        if len(rb) > 80:
            rb = rb[:80] + "…"
        md.append(f"| {src} | {meta['classification']} | {rb} |")
    md.append("")

    if s["unprocessed_md"]:
        md.append("## ❌ 仍未闭环\n")
        for u in s["unprocessed_md"]:
            md.append(f"- {u}")
        md.append("")
    else:
        md.append("## ✅ 全集闭环\n")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"coverage_report → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

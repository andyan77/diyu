#!/usr/bin/env python3
"""coverage SSOT · 计算覆盖状态写入 audit/coverage_status.json

reviewer 修正方向：先有机器可读 JSON，再让两份 markdown（final_report /
coverage_report）从 JSON 消费，避免双 markdown 漂移。

数据：
  - 输入 markdown 全集（Q2/Q4/Q7Q12 *.md）
  - 已抽 packs 的 source_md（含 cross-source 多源）
  - uncovered_md_register.md 的 5-class 签名
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent
INPUT_DIRS = ["Q2-内容类型种子", "Q4-人设种子", "Q7Q12-搭配陈列业务包", "Q-brand-seeds"]
CAND = ROOT / "candidates"
REGISTER_MD = ROOT / "audit" / "uncovered_md_register.md"
OUT = ROOT / "audit" / "coverage_status.json"


def list_input_md():
    out = []
    for d in INPUT_DIRS:
        p = WORKSPACE / d
        if p.exists():
            for f in sorted(p.rglob("*.md")):
                out.append(str(f.relative_to(WORKSPACE)))
    return out


def list_processed_source_md():
    pat = re.compile(r"^\s*source_md:\s*(.+?)\s*$")
    seen = set()
    for y in CAND.rglob("*.yaml"):
        for line in y.read_text(encoding="utf-8").splitlines():
            m = pat.match(line)
            if m:
                v = m.group(1).strip().strip("'\"")
                if "&" in v:
                    parts = [p.strip() for p in v.split("&") if p.strip()]
                    base = parts[0].rsplit("/", 1)[0] if "/" in parts[0] else ""
                    for idx, p in enumerate(parts):
                        if idx > 0 and "/" not in p and base:
                            seen.add(f"{base}/{p}")
                        else:
                            seen.add(p)
                else:
                    seen.add(v)
                break
    return seen


def load_5class_register():
    if not REGISTER_MD.exists():
        return {}
    out = {}
    pat = re.compile(r"^\|\s*([^|]+?\.md)\s*\|\s*([a-z_]+)\s*\|\s*([^|]+?)\s*\|")
    for line in REGISTER_MD.read_text(encoding="utf-8").splitlines():
        m = pat.match(line)
        if m:
            src, cls, by = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            if by and by != "_pending_review_":
                out[src] = {"classification": cls, "resolved_by": by}
    return out


def main():
    inputs = list_input_md()
    processed = list_processed_source_md()
    registered = load_5class_register()
    processed_in_scope = sorted(p for p in processed if p in inputs)
    resolved_via_register = sorted(p for p in inputs if p in registered)
    closed = set(processed_in_scope) | set(resolved_via_register)
    unprocessed = [p for p in inputs if p not in closed]

    by_class = {}
    for src, meta in registered.items():
        by_class.setdefault(meta["classification"], []).append(src)

    status = {
        "total_input_md": len(inputs),
        "directly_processed": len(processed_in_scope),
        "resolved_via_5class_register": len(resolved_via_register),
        "closed_total": len(closed),
        "unprocessed": len(unprocessed),
        "raw_coverage_pct": round(len(processed_in_scope) / len(inputs) * 100, 1) if inputs else 0,
        "closure_rate_pct": round(len(closed) / len(inputs) * 100, 1) if inputs else 0,
        "five_class_distribution": {k: len(v) for k, v in sorted(by_class.items())},
        "directly_processed_md": processed_in_scope,
        "resolved_via_register_md": resolved_via_register,
        "unprocessed_md": unprocessed,
        "register_detail": registered,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"=== coverage SSOT ===")
    print(f"  total_input_md       : {status['total_input_md']}")
    print(f"  directly_processed   : {status['directly_processed']}")
    print(f"  resolved_via_register: {status['resolved_via_5class_register']}")
    print(f"  closure_rate_pct     : {status['closure_rate_pct']}%")
    print(f"  unprocessed          : {status['unprocessed']}")
    print(f"  json -> {OUT}")
    return 0 if status["unprocessed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

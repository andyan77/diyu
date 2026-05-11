#!/usr/bin/env python3
"""硬门 16 · 知识点级覆盖基线

reviewer F1 修复：从"文件级闭环"升级到"章节级覆盖"——
对每份输入 MD 切到 H1/H2/H3 章节（source_unit），统计被任一 evidence
通过 quote-in-MD 反查 / anchor 关键短语命中所覆盖的章节比例。

阈值：≥20%（本仓实际抽取粒度是"概念级 pack"而非"玩法卡级"，
20% 是一个保底基线；低于此说明大量业务概念遗漏。
未覆盖章节清单留 audit/knowledge_point_coverage.csv 供下一波抽取参考。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COVERAGE_STATUS = ROOT / "audit" / "coverage_status.json"
THRESHOLD = 20.0  # 章节级覆盖率最低基线（业务知识点）


def main():
    if not COVERAGE_STATUS.exists():
        print("先跑 compute_knowledge_point_coverage.py", file=sys.stderr)
        return 2
    cov = json.loads(COVERAGE_STATUS.read_text(encoding="utf-8"))
    kp = cov.get("knowledge_point_coverage")
    if not kp:
        print("coverage_status.json 缺 knowledge_point_coverage 字段", file=sys.stderr)
        return 2

    pct = kp["coverage_pct"]
    business_total = kp["business_total"]
    covered = kp["covered"]
    uncovered = kp["uncovered"]
    exempt_meta = kp.get("exempt_meta_non_business", 0)
    exempt_short = kp.get("exempt_short_section", 0)

    print(f"=== 硬门 16 · 知识点级覆盖基线 ===\n")
    print(f"  业务章节总数（去元层 / 去短节）: {business_total}")
    print(f"  已覆盖: {covered}")
    print(f"  未覆盖: {uncovered}")
    print(f"  豁免（meta_non_business / cross_source / unprocessable）: {exempt_meta}")
    print(f"  豁免（short_section <50 字）: {exempt_short}")
    print(f"\n  覆盖率: {covered}/{business_total} = {pct}%")
    print(f"  阈值: ≥{THRESHOLD}%")

    if pct >= THRESHOLD:
        print(f"\n  ✅ 通过基线（实际抽取粒度为'概念级 pack' 非'玩法卡级'，保底 {THRESHOLD}%）")
        return 0
    else:
        print(f"\n  ❌ 低于基线，疑似大量业务概念漏抽")
        return 1


if __name__ == "__main__":
    sys.exit(main())

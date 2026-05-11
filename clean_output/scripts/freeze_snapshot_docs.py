#!/usr/bin/env python3
"""一次性脚本 · 给历史派生文档批量加 frozen_at frontmatter

为 audit/_process/ 下的历史快照 markdown 添加 YAML frontmatter：
  ---
  snapshot_type: historical_review
  frozen_at: <utc_iso>
  source_state: <git_describe_or_NA>
  rationale: 历史复核报告/方案，反映当时状态，不再随仓库演进
  ---

幂等：已带 frontmatter 的跳过。
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESS = ROOT / "audit" / "_process"

SNAPSHOTS = [
    "w1_wave_review.md",
    "w2_wave_review.md",
    "tc_b01_review.md",
    "tc_b04_review.md",
    "tc_b09_review.md",
    "self_audit.md",
    "remediation_plan.md",
    "remediation_plan_v2.md",
    "remediation_plan_v2_rev2.md",
    "multi_tenant_correction.md",
]


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    added = 0
    for name in SNAPSHOTS:
        p = PROCESS / name
        if not p.exists():
            print(f"  缺失: {name}")
            continue
        text = p.read_text(encoding="utf-8")
        if text.startswith("---\n") and "frozen_at:" in text.split("\n---", 1)[0]:
            print(f"  已冻: {name}")
            continue
        fm = (
            "---\n"
            f"snapshot_type: historical_review\n"
            f"frozen_at: {now}\n"
            f"source_state: pre-W10\n"
            f"rationale: 历史复核/方案文档，反映当时状态，不再随仓库演进；不参与 G18 漂移检测\n"
            "---\n\n"
        )
        p.write_text(fm + text, encoding="utf-8")
        added += 1
        print(f"  已加: {name}")
    print(f"\n总计加冻结标记: {added}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

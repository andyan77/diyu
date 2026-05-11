#!/usr/bin/env python3
"""按 audit/inference_level_audit.csv 批量名实对齐 inference_level

只改 change 非 no_change 的行（163 行 direct_quote → low 名实修正）。
双向写：07_evidence.csv + 对应 yaml（candidates/*/*.yaml）双源同步。
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "nine_tables" / "07_evidence.csv"
AUDIT = ROOT / "audit" / "_process" / "inference_level_audit.csv"
CAND = ROOT / "candidates"


def main():
    if not AUDIT.exists():
        print("先跑 classify_inference_level.py", file=sys.stderr)
        return 2

    # 读分类结果，构造 (evidence_id → recommended_level) for 改动行
    audit_rows = list(csv.DictReader(open(AUDIT, encoding="utf-8")))
    to_change = {r["evidence_id"]: r["recommended_inference_level"]
                 for r in audit_rows if r["change"] != "no_change"}
    print(f"待修改 {len(to_change)} 行")

    # 1) 改 07_evidence.csv
    rows = list(csv.reader(open(EVIDENCE, encoding="utf-8")))
    header = rows[0]
    eid_idx = header.index("evidence_id")
    inf_idx = header.index("inference_level")
    fixed_csv = 0
    for r in rows[1:]:
        if r[eid_idx] in to_change:
            old = r[inf_idx]
            new = to_change[r[eid_idx]]
            if old != new:
                r[inf_idx] = new
                fixed_csv += 1
    with EVIDENCE.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    print(f"07_evidence.csv: {fixed_csv} 行 inference_level 已改")

    # 2) 改对应 yaml — yaml 中 evidence.inference_level 字段
    # evidence_id = EV-<pack_id>，反推 pack_id 即文件名
    fixed_yaml = 0
    for ev_id, new_level in to_change.items():
        pack_id = ev_id[3:] if ev_id.startswith("EV-") else ev_id
        for sub in ("domain_general", "brand_faye", "needs_review"):
            yp = CAND / sub / f"{pack_id}.yaml"
            if yp.exists():
                text = yp.read_text(encoding="utf-8")
                # 改 evidence: inference_level: direct_quote → low
                # 用安全的精确替换：仅在已知值 direct_quote 替换为 low
                replaced = text.replace(
                    "inference_level: direct_quote",
                    f"inference_level: {new_level}"
                )
                if replaced != text:
                    yp.write_text(replaced, encoding="utf-8")
                    fixed_yaml += 1
                break
    print(f"yaml: {fixed_yaml} 个文件 inference_level 已改")
    return 0


if __name__ == "__main__":
    sys.exit(main())

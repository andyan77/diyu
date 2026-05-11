#!/usr/bin/env python3
"""硬门 11 · yaml↔csv 轻量字段一致性

按 reviewer 修正方向：先做轻量字段比对，不重写完整投影器。
两类检查：
  A. 双向存在性：yaml.nine_table_projection 中声明的 rule_id/evidence_id
     必须存在于对应 CSV；CSV 行的 source_pack_id 必须有 yaml 文件。
  B. 关键字段值相等：相同 (yaml.evidence.evidence_quote) 与 CSV 同 pack_id
     evidence_quote 必须字符级一致（不验整 pack 投影，只验 evidence_quote
     这一个最常漂移字段）。

任一不一致 → 写违反清单 + 退 1。
"""
import csv
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NINE = ROOT / "nine_tables"
CAND = ROOT / "candidates"
OUT = ROOT / "audit" / "_process" / "yaml_csv_sync_violations.csv"


def load_all_packs():
    out = {}
    for sub in CAND.iterdir():
        if not sub.is_dir():
            continue
        for y in sub.glob("*.yaml"):
            try:
                d = yaml.safe_load(y.read_text(encoding="utf-8"))
                if d and isinstance(d, dict):
                    out[d.get("pack_id", y.stem)] = (y, d)
            except Exception as e:
                print(f"  ⚠️  yaml 解析失败 {y.name}: {e}", file=sys.stderr)
    return out


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    packs = load_all_packs()
    print(f"=== 硬门 11 · yaml↔csv 轻量一致性 ({len(packs)} packs) ===\n")

    viol = []

    # 加载 9 表
    csv_data = {}
    for csvf in NINE.glob("*.csv"):
        with open(csvf, encoding="utf-8") as f:
            csv_data[csvf.stem] = list(csv.DictReader(f))

    # A.1 yaml 声明的 rule_id / evidence_id 必须存在于 CSV
    csv_rule_ids = {r["rule_id"] for r in csv_data.get("06_rule", [])}
    csv_evidence_ids = {r["evidence_id"] for r in csv_data.get("07_evidence", [])}

    for pid, (path, d) in packs.items():
        ntp = d.get("nine_table_projection") or {}
        for r in (ntp.get("rule") or []):
            if isinstance(r, dict) and r.get("rule_id") and r["rule_id"] not in csv_rule_ids:
                viol.append({"yaml": path.name, "pack_id": pid,
                             "kind": "yaml_rule_id_missing_in_csv",
                             "detail": r["rule_id"]})
        for r in (ntp.get("evidence") or []):
            if isinstance(r, dict) and r.get("evidence_id") and r["evidence_id"] not in csv_evidence_ids:
                viol.append({"yaml": path.name, "pack_id": pid,
                             "kind": "yaml_evidence_id_missing_in_csv",
                             "detail": r["evidence_id"]})

    # A.2 CSV 的 source_pack_id 必须有 yaml 文件
    yaml_pack_ids = set(packs)
    for stem, rows in csv_data.items():
        for i, row in enumerate(rows, start=2):
            spid = row.get("source_pack_id", "")
            if spid and spid not in yaml_pack_ids:
                viol.append({"yaml": "<missing>", "pack_id": spid,
                             "kind": "csv_source_pack_id_no_yaml",
                             "detail": f"{stem} line {i}"})

    # B. evidence_quote 字符级一致：yaml.evidence.evidence_quote vs csv 07_evidence
    csv_evidence_by_pack = {}
    for r in csv_data.get("07_evidence", []):
        spid = r.get("source_pack_id", "")
        if spid:
            csv_evidence_by_pack.setdefault(spid, []).append(r)

    for pid, (path, d) in packs.items():
        ev = d.get("evidence") or {}
        yaml_quote = (ev.get("evidence_quote") or "").strip()
        if not yaml_quote:
            continue
        csv_rows = csv_evidence_by_pack.get(pid, [])
        if not csv_rows:
            continue
        csv_quote = (csv_rows[0].get("evidence_quote") or "").strip()
        # 标准化空白：把多个空格 / 换行折叠成单空格再比对
        nyaml = " ".join(yaml_quote.split())
        ncsv = " ".join(csv_quote.split())
        if nyaml != ncsv:
            viol.append({"yaml": path.name, "pack_id": pid,
                         "kind": "evidence_quote_drift",
                         "detail": f"yaml({len(nyaml)}) vs csv({len(ncsv)})"})

    # 写违反清单
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["yaml", "pack_id", "kind", "detail"])
        for v in viol:
            w.writerow([v["yaml"], v["pack_id"], v["kind"], v["detail"]])

    by_kind = {}
    for v in viol:
        by_kind[v["kind"]] = by_kind.get(v["kind"], 0) + 1
    for kind, n in sorted(by_kind.items()):
        print(f"  ❌ {kind}: {n}")
    if not viol:
        print("  ✅ yaml↔csv 字段一致")

    print(f"\n违反总数: {len(viol)}")
    print(f"清单    : {OUT}")
    return 0 if not viol else 1


if __name__ == "__main__":
    sys.exit(main())

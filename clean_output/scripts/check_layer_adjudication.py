#!/usr/bin/env python3
"""硬门 G19 · W11 三层裁决完整性

边界（W11.2 立法）:
  - 只读 audit/source_unit_adjudication_w11.csv（不读 W10 兼容主表）
  - 只读 audit/pack_layer_register.csv 用于 pack 校验
  - 失败时只写 audit/_process/g19_violations.csv（一份违规清单）
  - 不修改任何业务产物（不动 9 表 / yaml / 主表 / coverage）
  - 通过时不写文件

依据契约: templates/G19_layer_adjudication_contract.md
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SU_W11 = ROOT / "audit" / "source_unit_adjudication_w11.csv"
PK_REG = ROOT / "audit" / "pack_layer_register.csv"
CAND = ROOT / "candidates"
OUT_VIOL = ROOT / "audit" / "_process" / "g19_violations.csv"

VALID_FINAL_STATUS = {
    "extract_l1", "extract_l2", "defer_l3_to_runtime_asset",
    "merge_to_existing", "unprocessable", "duplicate",
}
VALID_LAYER = {"L1", "L2", "L3", "L_NA"}
VALID_TIER = {"instant", "long_term", "brand_tier"}
VALID_DECISION = {"accept", "override", "defer"}


def collect_existing_pack_ids():
    ids = set()
    for sub in ("domain_general", "brand_faye", "needs_review"):
        d = CAND / sub
        if d.exists():
            ids |= {y.stem for y in d.glob("*.yaml")}
    return ids


def check_su(rows, pack_ids):
    issues = []
    for i, r in enumerate(rows, start=2):
        fs = r.get("final_status", "").strip()
        fl = r.get("final_layer", "").strip()
        rd = r.get("reviewer_decision", "").strip()
        notes = r.get("review_notes", "").strip()
        head = r.get("heading_path", "")[:50]

        if not fs:
            issues.append((i, head, "su:final_status 为空"))
            continue
        if fs not in VALID_FINAL_STATUS:
            issues.append((i, head, f"su:非法 final_status={fs}"))
            continue
        if rd and rd not in VALID_DECISION:
            issues.append((i, head, f"su:非法 reviewer_decision={rd}"))

        if fs == "extract_l1":
            if fl != "L1":
                issues.append((i, head, f"su:extract_l1 但 final_layer={fl}"))
            if rd == "override" and len(notes) < 10:
                issues.append((i, head, "su:override review_notes < 10 字"))
        elif fs == "extract_l2":
            if fl != "L2":
                issues.append((i, head, f"su:extract_l2 但 final_layer={fl}"))
            tier = r.get("production_tier", "").strip()
            pool = r.get("default_call_pool", "").strip().lower()
            if tier not in VALID_TIER:
                issues.append((i, head, f"su:L2 production_tier 非法: {tier!r}"))
            if pool not in {"true", "false"}:
                issues.append((i, head, f"su:L2 default_call_pool 非法: {pool!r}"))
        elif fs == "defer_l3_to_runtime_asset":
            if fl != "L3":
                issues.append((i, head, f"su:defer_l3 但 final_layer={fl}"))
            if len(notes) < 10:
                issues.append((i, head, "su:L3 review_notes < 10 字"))
        elif fs == "merge_to_existing":
            mt = r.get("merge_target", "").strip()
            if not mt:
                issues.append((i, head, "su:merge_to_existing 缺 merge_target"))
            elif mt not in pack_ids:
                issues.append((i, head, f"su:merge_target={mt} 不存在"))
        elif fs in ("unprocessable", "duplicate"):
            if fl != "L_NA":
                issues.append((i, head, f"su:{fs} 但 final_layer={fl} (应 L_NA)"))

        if rd == "accept":
            ss = r.get("suggested_status")
            sl = r.get("suggested_layer")
            if fs != ss or fl != sl:
                issues.append((i, head, f"su:accept 但 final({fs}/{fl}) != suggested({ss}/{sl})"))
    return issues


def check_pack(rows):
    """pack_layer_register: 每行必须有合法 final_layer；L2 必填 production"""
    issues = []
    for i, r in enumerate(rows, start=2):
        pid = r.get("pack_id", "")[:50]
        fl = r.get("final_layer", "").strip()
        if fl not in VALID_LAYER:
            issues.append((i, pid, f"pack:final_layer 非法/为空: {fl!r}"))
            continue
        if fl == "L2":
            tier = r.get("production_tier", "").strip()
            pool = r.get("default_call_pool", "").strip().lower()
            if tier not in VALID_TIER:
                issues.append((i, pid, f"pack:L2 production_tier 非法: {tier!r}"))
            if pool not in {"true", "false"}:
                issues.append((i, pid, f"pack:L2 default_call_pool 非法: {pool!r}"))
    return issues


def main():
    print("=== G19 · W11 三层裁决完整性 ===\n")
    if not SU_W11.exists():
        print(f"❌ 缺 {SU_W11.relative_to(ROOT)} （先跑 apply_layer_adjudication.py --apply --confirmed）")
        return 1
    if not PK_REG.exists():
        print(f"❌ 缺 {PK_REG.relative_to(ROOT)}")
        return 1

    su_rows = list(csv.DictReader(SU_W11.open(encoding="utf-8")))
    pk_rows = list(csv.DictReader(PK_REG.open(encoding="utf-8")))
    pack_ids = collect_existing_pack_ids()

    su_issues = check_su(su_rows, pack_ids)
    pk_issues = check_pack(pk_rows)

    # 状态分布
    su_dist = Counter(r.get("final_status", "(空)") for r in su_rows)
    pk_dist = Counter(r.get("final_layer", "(空)") for r in pk_rows)

    print(f"  source_unit_w11    : {len(su_rows)} 行")
    print(f"    final_status 分布: {dict(su_dist)}")
    print(f"  pack_layer_register: {len(pk_rows)} 行")
    print(f"    final_layer 分布 : {dict(pk_dist)}")

    issues = [("su", *t) for t in su_issues] + [("pk", *t) for t in pk_issues]

    if issues:
        OUT_VIOL.parent.mkdir(parents=True, exist_ok=True)
        with OUT_VIOL.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["scope", "line", "key", "issue"])
            w.writerows(issues)
        print(f"\n  ❌ G19 未通过，违规 {len(issues)} 项 → {OUT_VIOL.relative_to(ROOT)}")
        for sc, ln, k, msg in issues[:5]:
            print(f"    [{sc}] L{ln} {k[:40]:40s} {msg}")
        return 1

    print(f"\n  ✅ G19 通过：W11 三层裁决完整、契约合规、无未签字行")
    return 0


if __name__ == "__main__":
    sys.exit(main())

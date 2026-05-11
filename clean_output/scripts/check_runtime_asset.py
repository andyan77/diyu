#!/usr/bin/env python3
"""硬门 G21 · L3 runtime_asset 注册完整性

依据 templates/runtime_asset_schema.md
边界:
  - 仅读 runtime_assets/runtime_asset_index.csv + L3 yaml
  - 失败仅写 audit/_process/g21_violations.csv

通过条件:
  1. runtime_asset_index.csv 存在且行数 == pack_layer_register 中 L3 数（当前 24）
  2. asset_type ∈ 5 类受控枚举
  3. runtime_asset_id 唯一
  4. pack_id 若非空必须在 candidates/ 找到
  5. title ≥6 字 / summary ≥10 字
  6. 每个 L3 yaml 含 runtime_asset: 块
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PK_REG = ROOT / "audit" / "pack_layer_register.csv"
INDEX = ROOT / "runtime_assets" / "runtime_asset_index.csv"
CAND = ROOT / "candidates"
OUT_VIOL = ROOT / "audit" / "_process" / "g21_violations.csv"

ASSET_TYPES = {"shot_template", "dialogue_template", "action_template", "prop_list", "role_split"}


def collect_pack_ids():
    ids = set()
    for sub in ("domain_general", "brand_faye", "needs_review"):
        d = CAND / sub
        if d.exists():
            ids |= {y.stem for y in d.glob("*.yaml")}
    return ids


def main():
    print("=== G21 · L3 runtime_asset 完整性 ===\n")
    if not PK_REG.exists():
        print("❌ 缺 pack_layer_register.csv"); return 1
    if not INDEX.exists():
        print(f"❌ 缺 {INDEX.relative_to(ROOT)}（先跑 apply_l3_runtime_asset.py --apply --confirmed）")
        return 1

    pk = list(csv.DictReader(PK_REG.open(encoding="utf-8")))
    expected_l3 = sum(1 for r in pk if r["final_layer"] == "L3")
    idx = list(csv.DictReader(INDEX.open(encoding="utf-8")))
    pack_ids = collect_pack_ids()

    issues = []
    if len(idx) != expected_l3:
        issues.append((0, "", f"行数不一致：index={len(idx)} vs L3 pack={expected_l3}"))

    seen = set()
    for i, r in enumerate(idx, start=2):
        rid = r.get("runtime_asset_id", "").strip()
        if not rid:
            issues.append((i, "", "runtime_asset_id 空")); continue
        if rid in seen:
            issues.append((i, rid, "runtime_asset_id 重复"))
        seen.add(rid)
        at = r.get("asset_type", "").strip()
        if at not in ASSET_TYPES:
            issues.append((i, rid, f"asset_type 非法 {at!r}"))
        pid = r.get("pack_id", "").strip()
        if pid and pid not in pack_ids:
            issues.append((i, rid, f"pack_id={pid} 不存在"))
        if len(r.get("title", "").strip()) < 6:
            issues.append((i, rid, "title < 6 字"))
        if len(r.get("summary", "").strip()) < 10:
            issues.append((i, rid, "summary < 10 字"))

    # yaml 含 runtime_asset 块
    for r in idx:
        pid = r.get("pack_id", "").strip()
        if not pid:
            continue
        for sub in ("domain_general", "brand_faye", "needs_review"):
            ypath = CAND / sub / f"{pid}.yaml"
            if ypath.exists():
                if "runtime_asset:" not in ypath.read_text(encoding="utf-8"):
                    issues.append((0, pid, "yaml 缺 runtime_asset: 块"))
                break

    if issues:
        OUT_VIOL.parent.mkdir(parents=True, exist_ok=True)
        with OUT_VIOL.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(["line", "runtime_asset_id", "issue"]); w.writerows(issues)
        print(f"  ❌ G21 违规 {len(issues)} 项 → {OUT_VIOL.relative_to(ROOT)}")
        for ln, k, msg in issues[:5]:
            print(f"    L{ln} {k[:35]:35s} {msg}")
        return 1
    print(f"  ✅ G21 通过：runtime_asset_index {len(idx)} 行完整、契约合规、与 yaml 同步")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""W11.2.2 · 合并 pack_dispute_review.csv 回 pack_layer_register.csv

行为:
  1. 备份 pack_layer_register.csv + 受影响 yaml 到 _process/_backup_w11/<ts>/
  2. 把 dispute 中 final_layer 写回 pack_layer_register.csv
  3. 同步修改 yaml: granularity_layer 改为 final_layer；
     - L1: 移除 production_tier / default_call_pool 行
     - L2: 确保 production_tier / default_call_pool 行存在且取值正确
  4. 不动 9 表 / W10 主表 / coverage_status

边界:
  - 默认 dry-run；--apply --confirmed 才写
  - 跑完不自动跑 full_audit（由调用方决定）
"""
import argparse
import csv
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISPUTE = ROOT / "audit" / "pack_dispute_review.csv"
PK_REG = ROOT / "audit" / "pack_layer_register.csv"
CAND = ROOT / "candidates"
BACKUP = ROOT / "audit" / "_process" / "_backup_w11"


def find_yaml(pack_id):
    for sub in ("domain_general", "brand_faye", "needs_review"):
        p = CAND / sub / f"{pack_id}.yaml"
        if p.exists():
            return p
    return None


def patch_yaml(yaml_path: Path, target_layer: str, tier: str = "", pool: str = ""):
    """改 yaml 顶部的 granularity_layer 行，并按目标层补/删 production 字段。"""
    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    # 改 granularity_layer 行
    for i, l in enumerate(lines):
        if l.startswith("granularity_layer:"):
            lines[i] = f"granularity_layer: {target_layer}"
            break
    # production 行处理（旧值移除）
    lines = [l for l in lines if not l.startswith("production_tier:") and not l.startswith("default_call_pool:")]
    if target_layer == "L2":
        # 在 granularity_layer 后插入
        for i, l in enumerate(lines):
            if l.startswith("granularity_layer:"):
                ins = i + 1
                lines.insert(ins, f"production_tier: {tier}")
                lines.insert(ins + 1, f"default_call_pool: {pool}")
                break
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirmed", action="store_true")
    args = ap.parse_args()

    if not DISPUTE.exists():
        print(f"❌ 缺 {DISPUTE.relative_to(ROOT)}")
        return 2

    dispute = list(csv.DictReader(DISPUTE.open(encoding="utf-8")))
    pk = list(csv.DictReader(PK_REG.open(encoding="utf-8")))
    pk_idx = {r["pack_id"]: r for r in pk}

    print("=== W11.2.2 · pack dispute 写回 ===\n")
    print(f"模式: {'apply' if args.apply else 'dry-run'}")
    print(f"输入: {len(dispute)} dispute 行 / {len(pk)} pack")

    # 校验
    issues = []
    for r in dispute:
        pid = r["pack_id"]
        rd = r.get("reviewer_decision", "").strip()
        fl = r.get("final_layer", "").strip()
        notes = r.get("review_notes", "").strip()
        if rd not in {"accept", "override"}:
            issues.append(f"{pid}: reviewer_decision 非法 ({rd})")
        if fl not in {"L1", "L2"}:
            issues.append(f"{pid}: final_layer 必须是 L1 或 L2 ({fl})")
        if rd == "override" and len(notes) < 10:
            issues.append(f"{pid}: override 但 review_notes < 10 字")
        if fl == "L2":
            if r.get("production_tier", "").strip() not in {"instant", "long_term", "brand_tier"}:
                issues.append(f"{pid}: L2 production_tier 非法")
            if r.get("default_call_pool", "").strip().lower() not in {"true", "false"}:
                issues.append(f"{pid}: L2 default_call_pool 非法")
        if pid not in pk_idx:
            issues.append(f"{pid}: 不在 pack_layer_register")

    if issues:
        print(f"\n❌ 校验失败 {len(issues)} 项:")
        for x in issues[:10]:
            print(f"  - {x}")
        return 1

    # 摘要
    to_l1 = [r for r in dispute if r["final_layer"] == "L1"]
    to_l2 = [r for r in dispute if r["final_layer"] == "L2"]
    print(f"\n变更摘要:")
    print(f"  L2 → L1 (override): {len(to_l1)}")
    print(f"  L2 → L2 保留 (accept): {len(to_l2)}")
    print(f"  L2 production 分布: tier={','.join(sorted(set(r['production_tier'] for r in to_l2)))} pool={','.join(sorted(set(r['default_call_pool'] for r in to_l2)))}")

    if not (args.apply and args.confirmed):
        print(f"\n💡 dry-run；--apply --confirmed 才写")
        return 0

    # 备份
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snap = BACKUP / ts
    snap.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PK_REG, snap / "pack_layer_register.csv")
    yaml_dir = snap / "yamls"
    yaml_dir.mkdir(exist_ok=True)
    for r in dispute:
        ypath = find_yaml(r["pack_id"])
        if ypath:
            shutil.copy2(ypath, yaml_dir / ypath.name)
    print(f"\n✅ 备份: {snap.relative_to(ROOT)}")

    # 写回 pack_layer_register
    for r in dispute:
        pk_row = pk_idx[r["pack_id"]]
        pk_row["reviewer_decision"] = r["reviewer_decision"]
        pk_row["final_layer"] = r["final_layer"]
        pk_row["production_tier"] = r["production_tier"] if r["final_layer"] == "L2" else ""
        pk_row["default_call_pool"] = r["default_call_pool"] if r["final_layer"] == "L2" else ""
        if r.get("review_notes", "").strip():
            existing = pk_row.get("review_notes", "")
            pk_row["review_notes"] = (existing + " | " + r["review_notes"]) if existing else r["review_notes"]

    cols = list(pk[0].keys())
    with PK_REG.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(pk)
    print(f"✅ pack_layer_register.csv 已更新（{len(dispute)} 行 dispute 写回）")

    # 写回 yaml
    patched = 0
    for r in dispute:
        ypath = find_yaml(r["pack_id"])
        if ypath:
            patch_yaml(ypath, r["final_layer"], r.get("production_tier", ""), r.get("default_call_pool", ""))
            patched += 1
    print(f"✅ yaml 已修补: {patched} 个")
    print(f"\n请重跑 full_audit 验证 G19 转绿。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

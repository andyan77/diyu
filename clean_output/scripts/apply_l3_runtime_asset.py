#!/usr/bin/env python3
"""W12.A.6 · L3 资产注册写回（默认 dry-run）

输入: audit/l3_runtime_asset_review.csv（人工已填）
写回:
  1. yaml 注入 runtime_asset: 块
  2. 新建 runtime_assets/runtime_asset_index.csv

边界: 不动 9 表 / 不动 W11 主表 / 备份到 _process/_backup_w12/<ts>/
"""
import argparse
import csv
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / "audit" / "l3_runtime_asset_review.csv"
CAND = ROOT / "candidates"
ASSET_DIR = ROOT / "runtime_assets"
INDEX = ASSET_DIR / "runtime_asset_index.csv"
BACKUP = ROOT / "audit" / "_process" / "_backup_w12"

ASSET_TYPES = {"shot_template", "dialogue_template", "action_template", "prop_list", "role_split"}


def find_yaml(pack_id):
    for sub in ("domain_general", "brand_faye", "needs_review"):
        p = CAND / sub / f"{pack_id}.yaml"
        if p.exists():
            return p, sub
    return None, None


def validate(rows):
    issues = []
    seen = set()
    for r in rows:
        pid = r["pack_id"]
        at = r.get("asset_type", "").strip()
        rid = r.get("runtime_asset_id", "").strip() or r.get("runtime_asset_id_default", "").strip()
        title = r.get("title", "").strip()
        summary = r.get("summary", "").strip()
        if at not in ASSET_TYPES:
            issues.append(f"{pid}: asset_type 非法 {at!r}")
        if not rid:
            issues.append(f"{pid}: runtime_asset_id 空")
        elif rid in seen:
            issues.append(f"{pid}: runtime_asset_id 重复 ({rid})")
        else:
            seen.add(rid)
        if len(title) < 6:
            issues.append(f"{pid}: title < 6 字")
        if len(summary) < 10:
            issues.append(f"{pid}: summary < 10 字")
    return issues


def patch_yaml(yaml_path: Path, asset_type: str, runtime_asset_id: str, title: str, summary: str, pack_id: str):
    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    # 删旧 runtime_asset 块
    new_lines = []
    skip = False
    for l in lines:
        if l.startswith("runtime_asset:"):
            skip = True; continue
        if skip:
            if l and not l.startswith(" "):
                skip = False
            else:
                continue
        new_lines.append(l)
    # 找插入点
    ins = None
    for i, l in enumerate(new_lines):
        if l.startswith("granularity_layer:"):
            ins = i + 1
    if ins is None:
        ins = 1
    block = ["", "runtime_asset:",
             f"  runtime_asset_id: {runtime_asset_id}",
             f"  asset_type: {asset_type}",
             f'  title: "{title}"',
             f'  summary: "{summary}"',
             f'  source_pointer: "candidates/.../{pack_id}.yaml#runtime_asset"',
             ""]
    new_lines[ins:ins] = block
    yaml_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirmed", action="store_true")
    args = ap.parse_args()

    if not REVIEW.exists():
        print(f"❌ 缺 {REVIEW.relative_to(ROOT)}")
        return 2

    rows = list(csv.DictReader(REVIEW.open(encoding="utf-8")))
    print("=== W12.A.6 · L3 资产写回 ===\n")
    print(f"模式: {'apply' if args.apply else 'dry-run'}")
    print(f"输入: {len(rows)} L3 pack 待审表行")

    issues = validate(rows)
    if issues:
        print(f"\n❌ 校验失败 {len(issues)} 项（前 10 条）:")
        for x in issues[:10]:
            print(f"  - {x}")
        return 1
    print("  ✅ 审表校验通过")

    print(f"\n--- 写回预览 ---")
    print(f"  yaml 注入 runtime_asset: 块: {len(rows)} 个")
    print(f"  runtime_asset_index.csv 行数: {len(rows)}")

    if not (args.apply and args.confirmed):
        print("\n💡 dry-run；--apply --confirmed 才写")
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snap = BACKUP / ts
    snap.mkdir(parents=True, exist_ok=True)
    yaml_dir = snap / "yamls"
    yaml_dir.mkdir(exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    if INDEX.exists():
        shutil.copy2(INDEX, snap / "runtime_asset_index.csv")

    index_rows = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for r in rows:
        ypath, sub = find_yaml(r["pack_id"])
        if not ypath:
            continue
        rid = r.get("runtime_asset_id", "").strip() or r.get("runtime_asset_id_default", "").strip()
        at = r["asset_type"].strip()
        shutil.copy2(ypath, yaml_dir / ypath.name)
        patch_yaml(ypath, at, rid, r["title"].strip(), r["summary"].strip(), r["pack_id"])
        index_rows.append({
            "runtime_asset_id": rid,
            "pack_id": r["pack_id"],
            "granularity_layer": "L3",
            "asset_type": at,
            "source_md": "",  # 留 W12.B 补
            "source_anchor": "",
            "line_no": -1,
            "title": r["title"].strip(),
            "summary": r["summary"].strip(),
            "source_pointer": f"candidates/{sub}/{r['pack_id']}.yaml#runtime_asset",
            "brand_layer": sub,
            "registered_at": now,
        })

    cols = list(index_rows[0].keys())
    with INDEX.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(index_rows)

    print(f"\n✅ 写回完成")
    print(f"  备份: audit/_process/_backup_w12/{ts}")
    print(f"  yaml 注入: {len(index_rows)} 个")
    print(f"  runtime_asset_index.csv: {len(index_rows)} 行 → {INDEX.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

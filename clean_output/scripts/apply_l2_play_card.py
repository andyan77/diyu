#!/usr/bin/env python3
"""W12.A.5 · L2 玩法卡写回（默认 dry-run，--apply --confirmed 才落盘）

输入: audit/l2_play_card_review.csv（人工已填）
写回:
  1. yaml 注入 play_card: 块（W12 业务字段 + W11 基线字段）
  2. 新建/重写 play_cards/play_card_register.csv

边界:
  - 不动 9 表 / 不动 W11 主表 / 不动其他 yaml 字段
  - 备份 yaml + register 到 _process/_backup_w12/<utc-ts>/
  - dry-run 模式零写入
"""
import argparse
import csv
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / "audit" / "l2_play_card_review.csv"
CAND = ROOT / "candidates"
PLAY_CARDS_DIR = ROOT / "play_cards"
REGISTER = PLAY_CARDS_DIR / "play_card_register.csv"
BACKUP = ROOT / "audit" / "_process" / "_backup_w12"

REQUIRED = ["production_difficulty", "hook", "steps", "anti_pattern", "duration", "audience"]
DIFFICULTY = {"low", "medium", "high"}
DURATION = {"short", "medium", "long"}
TIER_BASELINE = {
    "instant": "1人+手机+200元+4h",
    "long_term": "2-3人+轻设备+1000元+1-2天",
    "brand_tier": "专业团队+品牌资源+不限",
}


def find_yaml(pack_id):
    for sub in ("domain_general", "brand_faye", "needs_review"):
        p = CAND / sub / f"{pack_id}.yaml"
        if p.exists():
            return p
    return None


def validate(rows):
    issues = []
    for r in rows:
        pid = r["pack_id"]
        diff = r.get("production_difficulty", "").strip()
        dur = r.get("duration", "").strip()
        for f in REQUIRED:
            if not r.get(f, "").strip():
                issues.append(f"{pid}: 缺 {f}")
        if diff and diff not in DIFFICULTY:
            issues.append(f"{pid}: production_difficulty 非法 ({diff})")
        if dur and dur not in DURATION:
            issues.append(f"{pid}: duration 非法 ({dur})")
        if r.get("hook", "").strip() and len(r["hook"].strip()) < 10:
            issues.append(f"{pid}: hook < 10 字")
        if r.get("anti_pattern", "").strip() and len(r["anti_pattern"].strip()) < 10:
            issues.append(f"{pid}: anti_pattern < 10 字")
        if r.get("audience", "").strip() and len(r["audience"].strip()) < 6:
            issues.append(f"{pid}: audience < 6 字")
        # steps: 至少 2 项（按 ; 或 JSON 列表识别）
        steps = r.get("steps", "").strip()
        if steps:
            n = 0
            try:
                lst = json.loads(steps) if steps.startswith("[") else None
                if isinstance(lst, list):
                    n = len(lst)
                else:
                    n = len([s for s in re.split(r"[;；\n]+", steps) if s.strip()])
            except Exception:
                n = len([s for s in re.split(r"[;；\n]+", steps) if s.strip()])
            if n < 2:
                issues.append(f"{pid}: steps < 2 项")
    return issues


def parse_steps(s):
    s = s.strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            v = json.loads(s)
            if isinstance(v, list):
                return [str(x) for x in v]
        except Exception:
            pass
    return [x.strip() for x in re.split(r"[;；\n]+", s) if x.strip()]


def patch_yaml(yaml_path: Path, row: dict):
    """在 granularity_layer/production_tier/default_call_pool 之后插入 play_card: 块。
    幂等：若已含 play_card: 块，先删除再重建。"""
    text = yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    # 删除已有 play_card 块（从 'play_card:' 到下一个非缩进行）
    new_lines = []
    skip = False
    for l in lines:
        if l.startswith("play_card:"):
            skip = True
            continue
        if skip:
            if l and not l.startswith(" ") and not l.startswith("\t"):
                skip = False
            else:
                continue
        new_lines.append(l)
    # 找插入点（default_call_pool 行后；否则 granularity_layer 行后）
    ins = None
    for i, l in enumerate(new_lines):
        if l.startswith("default_call_pool:"):
            ins = i + 1
    if ins is None:
        for i, l in enumerate(new_lines):
            if l.startswith("granularity_layer:"):
                ins = i + 1
                break
    if ins is None:
        ins = 1

    tier = row.get("production_tier", "").strip()
    rb = row.get("resource_baseline", "").strip() or row.get("resource_baseline_default", "").strip() or TIER_BASELINE.get(tier, "")
    steps = parse_steps(row.get("steps", ""))
    block = ["", "play_card:",
             f"  consumption_purpose: generation",
             f"  production_difficulty: {row['production_difficulty'].strip()}",
             f'  resource_baseline: "{rb}"',
             f'  hook: "{row["hook"].strip()}"',
             f"  steps:"]
    for s in steps:
        block.append(f'    - "{s}"')
    block += [
        f'  anti_pattern: "{row["anti_pattern"].strip()}"',
        f"  duration: {row['duration'].strip()}",
        f'  audience: "{row["audience"].strip()}"',
        f"  source_pack_id: {row['pack_id']}",
        "",
    ]
    new_lines[ins:ins] = block
    yaml_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def build_register(rows):
    pcr = []
    for r in rows:
        tier = r.get("production_tier", "").strip()
        rb = r.get("resource_baseline", "").strip() or r.get("resource_baseline_default", "").strip() or TIER_BASELINE.get(tier, "")
        steps = parse_steps(r.get("steps", ""))
        pid = r["pack_id"]
        pcr.append({
            "play_card_id": "PC-" + re.sub(r"^KP-", "", pid),
            "pack_id": pid,
            "granularity_layer": "L2",
            "consumption_purpose": "generation",
            "production_difficulty": r["production_difficulty"].strip(),
            "production_tier": tier,
            "resource_baseline": rb,
            "default_call_pool": r["default_call_pool"].strip(),
            "hook": r["hook"].strip(),
            "steps_count": len(steps),
            "anti_pattern": r["anti_pattern"].strip(),
            "duration": r["duration"].strip(),
            "audience": r["audience"].strip(),
            "source_pack_id": pid,
            "brand_layer": r.get("brand_layer_dir", ""),
        })
    return pcr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirmed", action="store_true")
    args = ap.parse_args()

    if not REVIEW.exists():
        print(f"❌ 缺 {REVIEW.relative_to(ROOT)}（先跑 build_w12_review_tables.py 并人工审填）")
        return 2

    rows = list(csv.DictReader(REVIEW.open(encoding="utf-8")))
    print("=== W12.A.5 · L2 玩法卡写回 ===\n")
    print(f"模式: {'apply' if args.apply else 'dry-run'}")
    print(f"输入: {len(rows)} L2 pack 待审表行")

    issues = validate(rows)
    if issues:
        print(f"\n❌ 校验失败 {len(issues)} 项（前 10 条）:")
        for x in issues[:10]:
            print(f"  - {x}")
        out_v = ROOT / "audit" / "_process" / "g20_pre_violations.csv"
        out_v.parent.mkdir(parents=True, exist_ok=True)
        with out_v.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(["issue"]); w.writerows([[x] for x in issues])
        print(f"  完整清单 → {out_v.relative_to(ROOT)}")
        return 1
    print("  ✅ 审表校验通过")

    register_rows = build_register(rows)
    print(f"\n--- 写回预览 ---")
    print(f"  yaml 注入 play_card: 块: {len(rows)} 个")
    print(f"  play_card_register.csv 行数: {len(register_rows)}")
    print(f"  备份目标: audit/_process/_backup_w12/<utc-ts>/")

    if not (args.apply and args.confirmed):
        print("\n💡 dry-run；--apply --confirmed 才写")
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snap = BACKUP / ts
    snap.mkdir(parents=True, exist_ok=True)
    yaml_dir = snap / "yamls"
    yaml_dir.mkdir(exist_ok=True)
    PLAY_CARDS_DIR.mkdir(parents=True, exist_ok=True)
    if REGISTER.exists():
        shutil.copy2(REGISTER, snap / "play_card_register.csv")

    for r in rows:
        ypath = find_yaml(r["pack_id"])
        if ypath:
            shutil.copy2(ypath, yaml_dir / ypath.name)
            patch_yaml(ypath, r)

    cols = list(register_rows[0].keys())
    with REGISTER.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(register_rows)

    print(f"\n✅ 写回完成")
    print(f"  备份: audit/_process/_backup_w12/{ts}")
    print(f"  yaml 注入: {len(rows)} 个")
    print(f"  play_card_register.csv: {len(register_rows)} 行 → {REGISTER.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

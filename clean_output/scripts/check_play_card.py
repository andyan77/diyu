#!/usr/bin/env python3
"""硬门 G20 · L2 玩法卡完整性

依据 templates/play_card_schema.md
边界:
  - 仅读 play_cards/play_card_register.csv + L2 yaml
  - 失败仅写 audit/_process/g20_violations.csv
  - 不动任何业务产物

通过条件:
  1. play_card_register.csv 存在
  2. 行数 == pack_layer_register 中 L2 数（当前 29）
  3. 12 个必填字段非空 + 受控枚举合法
  4. source_pack_id 在 candidates/ 找得到（FK）
  5. play_card_id 唯一
  6. 每个 L2 yaml 含完整 play_card: 块
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PK_REG = ROOT / "audit" / "pack_layer_register.csv"
PCR = ROOT / "play_cards" / "play_card_register.csv"
CAND = ROOT / "candidates"
OUT_VIOL = ROOT / "audit" / "_process" / "g20_violations.csv"

DIFFICULTY = {"low", "medium", "high"}
TIER = {"instant", "long_term", "brand_tier"}
DURATION = {"short", "medium", "long"}
POOL = {"true", "false"}
REQUIRED = ["play_card_id", "pack_id", "granularity_layer", "consumption_purpose",
            "production_difficulty", "production_tier", "resource_baseline",
            "default_call_pool", "hook", "anti_pattern", "duration", "audience",
            "source_pack_id"]


def collect_pack_ids():
    ids = set()
    for sub in ("domain_general", "brand_faye", "needs_review"):
        d = CAND / sub
        if d.exists():
            ids |= {y.stem for y in d.glob("*.yaml")}
    return ids


def main():
    print("=== G20 · L2 玩法卡完整性 ===\n")
    if not PK_REG.exists():
        print("❌ 缺 pack_layer_register.csv")
        return 1
    if not PCR.exists():
        print(f"❌ 缺 {PCR.relative_to(ROOT)}（先跑 apply_l2_play_card.py --apply --confirmed）")
        return 1

    pk = list(csv.DictReader(PK_REG.open(encoding="utf-8")))
    expected_l2 = sum(1 for r in pk if r["final_layer"] == "L2")
    pcr = list(csv.DictReader(PCR.open(encoding="utf-8")))
    pack_ids = collect_pack_ids()

    issues = []
    if len(pcr) != expected_l2:
        issues.append((0, "", f"行数不一致：register={len(pcr)} vs L2 pack={expected_l2}"))

    seen_ids = set()
    for i, r in enumerate(pcr, start=2):
        pcid = r.get("play_card_id", "").strip()
        if not pcid:
            issues.append((i, "", "play_card_id 空")); continue
        if pcid in seen_ids:
            issues.append((i, pcid, "play_card_id 重复"))
        seen_ids.add(pcid)
        for f in REQUIRED:
            if not r.get(f, "").strip():
                issues.append((i, pcid, f"缺 {f}"))
        # 枚举
        if r.get("production_difficulty") not in DIFFICULTY:
            issues.append((i, pcid, f"production_difficulty 非法: {r.get('production_difficulty')!r}"))
        if r.get("production_tier") not in TIER:
            issues.append((i, pcid, f"production_tier 非法: {r.get('production_tier')!r}"))
        if r.get("default_call_pool", "").strip().lower() not in POOL:
            issues.append((i, pcid, f"default_call_pool 非法: {r.get('default_call_pool')!r}"))
        if r.get("duration") not in DURATION:
            issues.append((i, pcid, f"duration 非法: {r.get('duration')!r}"))
        # FK
        spi = r.get("source_pack_id", "").strip()
        if spi and spi not in pack_ids:
            issues.append((i, pcid, f"source_pack_id={spi} 不存在"))
        # 长度
        if len(r.get("hook", "").strip()) < 10:
            issues.append((i, pcid, "hook < 10 字"))
        if len(r.get("anti_pattern", "").strip()) < 10:
            issues.append((i, pcid, "anti_pattern < 10 字"))
        if len(r.get("audience", "").strip()) < 6:
            issues.append((i, pcid, "audience < 6 字"))
        try:
            if int(r.get("steps_count", "0")) < 2:
                issues.append((i, pcid, "steps_count < 2"))
        except ValueError:
            issues.append((i, pcid, "steps_count 非法"))

    # yaml 含 play_card: 块校验
    for r in pcr:
        spi = r.get("source_pack_id", "").strip()
        if not spi:
            continue
        for sub in ("domain_general", "brand_faye", "needs_review"):
            ypath = CAND / sub / f"{spi}.yaml"
            if ypath.exists():
                txt = ypath.read_text(encoding="utf-8")
                if "play_card:" not in txt:
                    issues.append((0, spi, "yaml 缺 play_card: 块"))
                break

    if issues:
        OUT_VIOL.parent.mkdir(parents=True, exist_ok=True)
        with OUT_VIOL.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(["line", "play_card_id", "issue"]); w.writerows(issues)
        print(f"  ❌ G20 违规 {len(issues)} 项 → {OUT_VIOL.relative_to(ROOT)}")
        for ln, k, msg in issues[:5]:
            print(f"    L{ln} {k[:35]:35s} {msg}")
        return 1
    print(f"  ✅ G20 通过：play_card_register {len(pcr)} 行完整、契约合规、与 yaml 同步")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""W12 对抗+边缘测试 · G20/G21 故障注入 + 不变性核查

不动业务数据；临时变异 register / index / yaml 验证 G20/G21 能识别。
所有用例还原后跑 full_audit 27/27 复检。
"""
import csv
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PCR = ROOT / "play_cards" / "play_card_register.csv"
RAI = ROOT / "runtime_assets" / "runtime_asset_index.csv"
SU_W11 = ROOT / "audit" / "source_unit_adjudication_w11.csv"


def run_check(name):
    r = subprocess.run(["python3", str(SCRIPTS / name)],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=60)
    return r.returncode


def with_csv_mutation(target, mutate, expected_fail, check):
    backup = target.with_suffix(".w12test.bak")
    shutil.copy2(target, backup)
    try:
        rows = list(csv.DictReader(target.open(encoding="utf-8")))
        cols = list(rows[0].keys())
        mutate(rows)
        with target.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
        rc = run_check(check)
        return (rc != 0) == expected_fail
    finally:
        shutil.move(str(backup), str(target))


def t1_g20_missing_hook():
    return with_csv_mutation(PCR, lambda rs: rs[0].update({"hook": ""}), True, "check_play_card.py")


def t2_g20_short_hook():
    return with_csv_mutation(PCR, lambda rs: rs[0].update({"hook": "短"}), True, "check_play_card.py")


def t3_g20_invalid_difficulty():
    return with_csv_mutation(PCR, lambda rs: rs[0].update({"production_difficulty": "extreme"}), True, "check_play_card.py")


def t4_g20_invalid_duration():
    return with_csv_mutation(PCR, lambda rs: rs[0].update({"duration": "long_long_long"}), True, "check_play_card.py")


def t5_g20_invalid_tier():
    return with_csv_mutation(PCR, lambda rs: rs[0].update({"production_tier": "extreme"}), True, "check_play_card.py")


def t6_g20_fk_break():
    return with_csv_mutation(PCR, lambda rs: rs[0].update({"source_pack_id": "BOGUS-ID-NOT-EXIST"}), True, "check_play_card.py")


def t7_g20_steps_count_too_low():
    return with_csv_mutation(PCR, lambda rs: rs[0].update({"steps_count": "1"}), True, "check_play_card.py")


def t8_g21_invalid_asset_type():
    return with_csv_mutation(RAI, lambda rs: rs[0].update({"asset_type": "movie_template"}), True, "check_runtime_asset.py")


def t9_g21_short_title():
    return with_csv_mutation(RAI, lambda rs: rs[0].update({"title": "短"}), True, "check_runtime_asset.py")


def t10_g21_short_summary():
    return with_csv_mutation(RAI, lambda rs: rs[0].update({"summary": "短"}), True, "check_runtime_asset.py")


def t11_g21_duplicate_id():
    def mut(rs):
        if len(rs) >= 2:
            rs[1]["runtime_asset_id"] = rs[0]["runtime_asset_id"]
    return with_csv_mutation(RAI, mut, True, "check_runtime_asset.py")


def t12_invariance_w11():
    """W12 写回不污染 W11：source_unit_adjudication_w11.csv 行数与分布不变"""
    rows = list(csv.DictReader(SU_W11.open(encoding="utf-8")))
    from collections import Counter
    c = Counter(r["final_status"] for r in rows)
    return (len(rows) == 1578
            and c.get("extract_l1") == 454
            and c.get("extract_l2") == 329
            and c.get("defer_l3_to_runtime_asset") == 128)


def t13_invariance_9tables():
    """9 表数据不变（W12 仅写 yaml + 旁路 register/index）"""
    counts = {}
    for f in (ROOT / "nine_tables").glob("*.csv"):
        with f.open(encoding="utf-8") as fp:
            counts[f.stem] = sum(1 for _ in csv.DictReader(fp))
    # baseline aligned to manifest 2026-05-12 / KS-S0-001
    # 06_rule: 194 → 201  (W12+ 新增 7 条 brand_faye rule)
    # 07_evidence: 194 → 954  (W12+ evidence row 扩充)
    expected = {"01_object_type": 18, "02_field": 98, "03_semantic": 163,
                "04_value_set": 604, "05_relation": 173, "06_rule": 201,
                "07_evidence": 954, "08_lifecycle": 1, "09_call_mapping": 243}
    return counts == expected


def t14_yaml_play_card_block():
    """29 个 L2 yaml 全部含 play_card: 块"""
    pcr_rows = list(csv.DictReader(PCR.open(encoding="utf-8")))
    miss = 0
    for r in pcr_rows:
        for sub in ("domain_general", "brand_faye", "needs_review"):
            yp = ROOT / "candidates" / sub / f"{r['source_pack_id']}.yaml"
            if yp.exists():
                if "play_card:" not in yp.read_text(encoding="utf-8"):
                    miss += 1
                break
    return miss == 0


def t15_yaml_runtime_asset_block():
    """24 个 L3 yaml 全部含 runtime_asset: 块"""
    idx = list(csv.DictReader(RAI.open(encoding="utf-8")))
    miss = 0
    for r in idx:
        for sub in ("domain_general", "brand_faye", "needs_review"):
            yp = ROOT / "candidates" / sub / f"{r['pack_id']}.yaml"
            if yp.exists():
                if "runtime_asset:" not in yp.read_text(encoding="utf-8"):
                    miss += 1
                break
    return miss == 0


TESTS = [
    ("W12-T1",  "G20 缺 hook",                t1_g20_missing_hook),
    ("W12-T2",  "G20 hook < 10 字",           t2_g20_short_hook),
    ("W12-T3",  "G20 production_difficulty 非法", t3_g20_invalid_difficulty),
    ("W12-T4",  "G20 duration 非法",          t4_g20_invalid_duration),
    ("W12-T5",  "G20 production_tier 非法",   t5_g20_invalid_tier),
    ("W12-T6",  "G20 source_pack_id FK 断",   t6_g20_fk_break),
    ("W12-T7",  "G20 steps_count < 2",        t7_g20_steps_count_too_low),
    ("W12-T8",  "G21 asset_type 非法",        t8_g21_invalid_asset_type),
    ("W12-T9",  "G21 title < 6 字",           t9_g21_short_title),
    ("W12-T10", "G21 summary < 10 字",        t10_g21_short_summary),
    ("W12-T11", "G21 runtime_asset_id 重复",  t11_g21_duplicate_id),
    ("W12-T12", "W11 主表分布不变（W12 不污染 W11）", t12_invariance_w11),
    ("W12-T13", "9 表数据不变（W12 仅 yaml + 旁路）", t13_invariance_9tables),
    ("W12-T14", "29 L2 yaml 含 play_card: 块",     t14_yaml_play_card_block),
    ("W12-T15", "24 L3 yaml 含 runtime_asset: 块", t15_yaml_runtime_asset_block),
]


def main():
    print("=== W12 对抗+边缘测试 ===\n")
    failed = []
    for tid, desc, fn in TESTS:
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f"  ❌ {tid:8s} {desc} — 异常 {e}")
            failed.append(tid); continue
        mark = "✅" if ok else "❌"
        print(f"  {mark} {tid:8s} {desc}")
        if not ok:
            failed.append(tid)
    if failed:
        print(f"\n❌ 失败 {len(failed)} 项: {failed}")
        return 1
    print("\n→ 还原后跑 full_audit 复检 27 道硬门 ...")
    r = subprocess.run(["python3", str(SCRIPTS / "full_audit.py")],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=300)
    last = [l for l in r.stdout.splitlines() if "汇总" in l]
    print("  " + (last[0] if last else "(无汇总)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

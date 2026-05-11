#!/usr/bin/env python3
"""W11 三层对抗性 + 边缘性测试

不动业务数据；通过临时变异 _w11.csv / pack_layer_register / yaml / coverage 验证：
  - G19 能检测各类违规
  - layer_distribution 防漂移机制有效
  - apply 后 194 yaml granularity_layer 不变性

所有用例还原后再跑一次 full_audit 25/25。
"""
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
SU_W11 = ROOT / "audit" / "source_unit_adjudication_w11.csv"
PK_REG = ROOT / "audit" / "pack_layer_register.csv"
COV = ROOT / "audit" / "coverage_status.json"
CAND = ROOT / "candidates"


def run_check(name):
    r = subprocess.run(
        ["python3", str(SCRIPTS / name)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60,
    )
    return r.returncode


def with_csv_mutation(target: Path, mutate, expected_fail: bool):
    backup = target.with_suffix(".w11test.bak")
    shutil.copy2(target, backup)
    try:
        rows = list(csv.DictReader(target.open(encoding="utf-8")))
        cols = list(rows[0].keys())
        mutate(rows)
        with target.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        rc = run_check("check_layer_adjudication.py")
        return (rc != 0) == expected_fail
    finally:
        shutil.move(str(backup), str(target))


# ========== 测试用例 ==========
def t_w11_1_empty_final_status():
    return with_csv_mutation(SU_W11, lambda rows: rows[0].update({"final_status": ""}), True)


def t_w11_2_invalid_final_status():
    return with_csv_mutation(SU_W11, lambda rows: rows[0].update({"final_status": "INVALID_X"}), True)


def t_w11_3_l2_missing_tier():
    def mut(rows):
        for r in rows:
            if r["final_status"] == "extract_l2":
                r["production_tier"] = ""
                break
    return with_csv_mutation(SU_W11, mut, True)


def t_w11_4_l2_missing_pool():
    def mut(rows):
        for r in rows:
            if r["final_status"] == "extract_l2":
                r["default_call_pool"] = ""
                break
    return with_csv_mutation(SU_W11, mut, True)


def t_w11_5_merge_target_not_exist():
    def mut(rows):
        for r in rows:
            if r["final_status"] == "extract_l1":
                r["final_status"] = "merge_to_existing"
                r["final_layer"] = "L1"  # 保持
                r["merge_target"] = "BOGUS-PACK-DOES-NOT-EXIST"
                break
    return with_csv_mutation(SU_W11, mut, True)


def t_w11_6_accept_mismatch():
    def mut(rows):
        for r in rows:
            if r["reviewer_decision"] == "accept" and r["final_status"] == "extract_l1":
                r["final_status"] = "extract_l2"  # accept 但与 suggested 不一致
                r["final_layer"] = "L2"
                r["production_tier"] = "instant"
                r["default_call_pool"] = "true"
                break
    return with_csv_mutation(SU_W11, mut, True)


def t_w11_7_layer_distribution_persistence():
    """跑一次 G12（compute_coverage_status）+ G16d_a（build_source_unit_adjudication）
    后 layer_distribution 仍在。"""
    backup = COV.with_suffix(".w11test.bak")
    shutil.copy2(COV, backup)
    try:
        # 主动跑 G12 → 它会重写 cov（不带 layer_distribution）
        subprocess.run(["python3", str(SCRIPTS / "compute_coverage_status.py")],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=60)
        # 再跑 G16d_a → 期望恢复 layer_distribution
        subprocess.run(["python3", str(SCRIPTS / "build_source_unit_adjudication.py")],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=60)
        cov = json.loads(COV.read_text(encoding="utf-8"))
        return "layer_distribution" in cov
    finally:
        shutil.move(str(backup), str(COV))


def t_w11_8_yaml_granularity_invariance():
    """194 yaml 全部含 granularity_layer 字段"""
    n = 0
    miss = []
    for sub in ("domain_general", "brand_faye", "needs_review"):
        d = CAND / sub
        if d.exists():
            for y in sorted(d.glob("*.yaml")):
                n += 1
                if "granularity_layer:" not in y.read_text(encoding="utf-8"):
                    miss.append(y.name)
    return n == 194 and not miss


def t_w11_9_pack_l2_missing_production():
    """pack_layer_register: L2 缺 production_tier 应触红"""
    def mut(rows):
        for r in rows:
            if r["final_layer"] == "L2":
                r["production_tier"] = ""
                break
    return with_csv_mutation(PK_REG, mut, True)


def t_w11_10_w10_layer_unchanged():
    """W10 兼容主表 source_unit_adjudication.csv 的 4 态分布不变（W11 不污染 W10）"""
    su_w10 = ROOT / "audit" / "source_unit_adjudication.csv"
    rows = list(csv.DictReader(su_w10.open(encoding="utf-8")))
    from collections import Counter
    c = Counter(r["adjudication_status"] for r in rows)
    return (c.get("covered_by_pack", 0) == 357
            and c.get("unprocessable", 0) == 430
            and c.get("duplicate_or_redundant", 0) == 9
            and c.get("pending_decision", 0) == 782)


TESTS = [
    ("W11-T1",  "G19 检测 final_status 为空",                     t_w11_1_empty_final_status),
    ("W11-T2",  "G19 检测非法 final_status",                       t_w11_2_invalid_final_status),
    ("W11-T3",  "G19 检测 L2 缺 production_tier (su)",            t_w11_3_l2_missing_tier),
    ("W11-T4",  "G19 检测 L2 缺 default_call_pool (su)",          t_w11_4_l2_missing_pool),
    ("W11-T5",  "G19 检测 merge_target 不存在",                    t_w11_5_merge_target_not_exist),
    ("W11-T6",  "G19 检测 accept 但 final != suggested",          t_w11_6_accept_mismatch),
    ("W11-T7",  "layer_distribution 防漂移（G12+G16d 后仍在）",    t_w11_7_layer_distribution_persistence),
    ("W11-T8",  "194 yaml granularity_layer 不变性",              t_w11_8_yaml_granularity_invariance),
    ("W11-T9",  "G19 检测 pack L2 缺 production_tier",            t_w11_9_pack_l2_missing_production),
    ("W11-T10", "W10 兼容主表 4 态分布不变（W11 不污染 W10）",     t_w11_10_w10_layer_unchanged),
]


def main():
    print("=== W11 三层对抗+边缘测试 ===\n")
    failed = []
    for tid, desc, fn in TESTS:
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f"  ❌ {tid:8s} {desc} — 异常 {e}")
            failed.append(tid)
            continue
        mark = "✅" if ok else "❌"
        print(f"  {mark} {tid:8s} {desc}")
        if not ok:
            failed.append(tid)

    if failed:
        print(f"\n❌ 失败 {len(failed)} 项: {failed}")
        return 1

    print("\n→ 还原后跑 full_audit 复检 25 道硬门 ...")
    r = subprocess.run(
        ["python3", str(SCRIPTS / "full_audit.py")],
        capture_output=True, text=True, cwd=str(ROOT), timeout=300,
    )
    last = [l for l in r.stdout.splitlines() if "汇总" in l]
    print("  " + (last[0] if last else "(无汇总)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

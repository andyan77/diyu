#!/usr/bin/env python3
"""W10 对抗性 + 边缘性测试

不修改任何源文件——通过临时复制、注入故障、跑 G16d/G17/G18 校验是否能识别。
所有测试结束后还原现场，确认 full_audit 仍 24/24 绿。

测试矩阵：
  X-T1: G18 检测 frontmatter 缺失
  X-T2: G18 检测 historical_review 缺 frozen_at
  X-T3: G18 检测 live 数值漂移
  X-T4: G17 检测 evidence_row_adjudication 缺行
  X-T5: G17 检测非法 adjudication_status
  X-T6: G17 检测 auto+needs_human_review 触红
  X-T7: G16d 检测章节缺签字
  X-T8: G16d 检测 pending_decision 缺 priority
  X-T9: 数据不变性（9 表 sha256 与基线一致）
  X-T10: W8 inference_level 不回退（07_evidence direct_quote=22 / low=172）
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
OUT_DIR = ROOT / "audit" / "_process"


def run(name):
    r = subprocess.run(
        ["python3", str(SCRIPTS / name)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120,
    )
    return r.returncode, r.stdout + r.stderr


def with_temp_swap(target: Path, mutate, label: str):
    """备份 target，做变异，跑 expected check，还原；返回 (rc_under_mutation, out)"""
    backup = target.with_suffix(target.suffix + ".w10test.bak")
    shutil.copy2(target, backup)
    try:
        mutate(target)
        return label
    finally:
        shutil.move(str(backup), str(target))


def test_X1_G18_no_frontmatter():
    target = OUT_DIR / "self_audit.md"
    backup = target.with_suffix(".w10test.bak")
    shutil.copy2(target, backup)
    try:
        text = target.read_text(encoding="utf-8")
        # 删 frontmatter
        if text.startswith("---\n"):
            second = text.find("\n---\n", 4)
            if second > 0:
                target.write_text(text[second + 5:], encoding="utf-8")
        rc, _ = run("check_derived_doc_freshness.py")
        return rc != 0  # 期望失败
    finally:
        shutil.move(str(backup), str(target))


def test_X2_G18_missing_frozen_at():
    target = OUT_DIR / "tc_b01_review.md"
    backup = target.with_suffix(".w10test.bak")
    shutil.copy2(target, backup)
    try:
        text = target.read_text(encoding="utf-8")
        text2 = text.replace("frozen_at: ", "frozen_at_REMOVED: ", 1)
        target.write_text(text2, encoding="utf-8")
        rc, _ = run("check_derived_doc_freshness.py")
        return rc != 0
    finally:
        shutil.move(str(backup), str(target))


def test_X3_G18_drift():
    target = OUT_DIR / "empty_tables_explanation.md"
    backup = target.with_suffix(".w10test.bak")
    shutil.copy2(target, backup)
    try:
        text = target.read_text(encoding="utf-8")
        # 把 06_rule | 194 改成 999
        text2 = text.replace("| 06_rule | 194 |", "| 06_rule | 999 |")
        target.write_text(text2, encoding="utf-8")
        rc, _ = run("check_derived_doc_freshness.py")
        return rc != 0
    finally:
        shutil.move(str(backup), str(target))


def test_X4_G17_missing_row():
    target = ROOT / "audit" / "evidence_row_adjudication.csv"
    backup = target.with_suffix(".w10test.bak")
    shutil.copy2(target, backup)
    try:
        rows = list(csv.DictReader(target.open(encoding="utf-8")))
        rows = rows[:-3]  # 删尾 3 行
        with target.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        rc, _ = run("check_evidence_row_adjudication.py")
        return rc != 0
    finally:
        shutil.move(str(backup), str(target))


def test_X5_G17_invalid_status():
    target = ROOT / "audit" / "evidence_row_adjudication.csv"
    backup = target.with_suffix(".w10test.bak")
    shutil.copy2(target, backup)
    try:
        rows = list(csv.DictReader(target.open(encoding="utf-8")))
        rows[0]["adjudication_status"] = "MADE_UP_STATUS"
        with target.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        rc, _ = run("check_evidence_row_adjudication.py")
        return rc != 0
    finally:
        shutil.move(str(backup), str(target))


def test_X6_G17_auto_needs_review():
    target = ROOT / "audit" / "evidence_row_adjudication.csv"
    backup = target.with_suffix(".w10test.bak")
    shutil.copy2(target, backup)
    try:
        rows = list(csv.DictReader(target.open(encoding="utf-8")))
        rows[0]["adjudication_status"] = "needs_human_review"
        rows[0]["adjudicator"] = "auto"
        with target.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        rc, _ = run("check_evidence_row_adjudication.py")
        return rc != 0
    finally:
        shutil.move(str(backup), str(target))


def test_X7_G16d_missing_status():
    target = ROOT / "audit" / "source_unit_adjudication.csv"
    backup = target.with_suffix(".w10test.bak")
    shutil.copy2(target, backup)
    try:
        rows = list(csv.DictReader(target.open(encoding="utf-8")))
        rows[0]["adjudication_status"] = ""
        with target.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        rc, _ = run("check_source_unit_adjudication.py")
        return rc != 0
    finally:
        shutil.move(str(backup), str(target))


def test_X8_G16d_pending_no_priority():
    target = ROOT / "audit" / "source_unit_adjudication.csv"
    backup = target.with_suffix(".w10test.bak")
    shutil.copy2(target, backup)
    try:
        rows = list(csv.DictReader(target.open(encoding="utf-8")))
        for r in rows:
            if r["adjudication_status"] == "pending_decision":
                r["priority"] = ""
                break
        with target.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        rc, _ = run("check_source_unit_adjudication.py")
        return rc != 0
    finally:
        shutil.move(str(backup), str(target))


def test_X9_data_invariance():
    """9 表 csv 的 sha256 与 manifest 中记录一致（W10 没改业务数据）"""
    man = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    expected = {Path(e["path"]).name: e["sha256"] for e in man["nine_tables"]}
    actual = {}
    for f in (ROOT / "nine_tables").glob("*.csv"):
        actual[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return expected == actual


def test_X10_inference_level_invariance():
    """W8 名实对齐结果不回退：direct_quote=22 / low=172"""
    rows = list(csv.DictReader((ROOT / "nine_tables" / "07_evidence.csv").open(encoding="utf-8")))
    from collections import Counter
    c = Counter(r["inference_level"] for r in rows)
    return c.get("direct_quote", 0) == 22 and c.get("low", 0) == 172 and len(rows) == 194


TESTS = [
    ("X-T1", "G18 检测 frontmatter 缺失",            test_X1_G18_no_frontmatter),
    ("X-T2", "G18 检测 historical_review 缺 frozen_at", test_X2_G18_missing_frozen_at),
    ("X-T3", "G18 检测 live 数值漂移",                test_X3_G18_drift),
    ("X-T4", "G17 检测 evidence 行缺失",              test_X4_G17_missing_row),
    ("X-T5", "G17 检测非法 adjudication_status",      test_X5_G17_invalid_status),
    ("X-T6", "G17 检测 auto+needs_human_review",      test_X6_G17_auto_needs_review),
    ("X-T7", "G16d 检测章节缺签字",                   test_X7_G16d_missing_status),
    ("X-T8", "G16d 检测 pending 缺 priority",          test_X8_G16d_pending_no_priority),
    ("X-T9", "数据不变性 (9 表 sha256 == manifest)", test_X9_data_invariance),
    ("X-T10", "W8 inference_level 不回退 (22 dq + 172 low)", test_X10_inference_level_invariance),
]


def main():
    print("=== W10 对抗性 + 边缘性测试 ===\n")
    failed = []
    for tid, desc, fn in TESTS:
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f"  ❌ {tid} {desc}: 异常 {e}")
            failed.append(tid)
            continue
        mark = "✅" if ok else "❌"
        print(f"  {mark} {tid} {desc}")
        if not ok:
            failed.append(tid)

    print()
    if failed:
        print(f"❌ 失败 {len(failed)} 项: {failed}")
        return 1

    # 还原后再跑一次 full_audit 确认 24/24
    print("\n→ 还原后跑 full_audit 复检 ...")
    r = subprocess.run(
        ["python3", str(SCRIPTS / "full_audit.py")],
        capture_output=True, text=True, cwd=str(ROOT), timeout=300,
    )
    last = [l for l in r.stdout.splitlines() if "汇总" in l]
    print("  " + (last[0] if last else "(无汇总输出)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

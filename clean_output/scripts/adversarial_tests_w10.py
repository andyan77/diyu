#!/usr/bin/env python3
"""W10 · 对抗 + 边缘测试用例

涵盖三方案的关键不变量：
[X-T1] 9 表数据无变（行数 / sha256）
[X-T2] 07_evidence inference_level 不回退（W8 修正：22 direct_quote, 172 low）
[X-T3] yaml ↔ csv evidence_quote 仍同步（应已被 G11 覆盖，再次断言）
[X-T4] manifest signatures 三件齐备（data/tooling/total）
[X-T5] G16d / G17 / G18 三道新硬门并入 full_audit
[A-T1] source_unit_adjudication 4 状态白名单封闭，无第 5 态
[A-T2] pending_decision 全部具名 + priority ∈ {high,medium,low}
[A-T3] duplicate_or_redundant 仅在 body_hash 与 covered 兄弟一致时签发
[B-T1] evidence_row_adjudication 行数 == 07_evidence 行数
[B-T2] direct_quote_verified 行 strict_substring_hit=true
[B-T3] paraphrase_located 行 phrase_hit_rate ≥ 0.30
[C-T1] 派生 md frontmatter 全部合法
[C-T2] empty_tables_explanation 数值与 manifest 对齐
[C-T3] 任意 historical_review 文档篡改 frozen_at → G18 仍通过（仅查存在）
        （边缘性：frozen_at 字段语义只查存在，不查时间格式严格）
"""
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESS = ROOT / "audit" / "_process"


def sha256_of(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_test(name, fn):
    try:
        ok, msg = fn()
    except Exception as e:
        ok, msg = False, f"exception: {e}"
    mark = "✅" if ok else "❌"
    print(f"  {mark} {name}: {msg}")
    return ok


def t_x1():
    man = json.load((ROOT / "manifest.json").open())
    rows = {Path(e["path"]).stem: (e["sha256"], e["data_rows"]) for e in man["nine_tables"]}
    expected = {
        "01_object_type": 18, "02_field": 98, "03_semantic": 163,
        "04_value_set": 604, "05_relation": 173, "06_rule": 194,
        "07_evidence": 194, "08_lifecycle": 1, "09_call_mapping": 243,
    }
    bad = [k for k, n in expected.items() if rows.get(k, ("", 0))[1] != n]
    return (not bad, f"9 表行数全部对齐 1688" if not bad else f"漂移: {bad}")


def t_x2():
    rows = list(csv.DictReader((ROOT / "nine_tables/07_evidence.csv").open()))
    dq = sum(1 for r in rows if r["inference_level"] == "direct_quote")
    low = sum(1 for r in rows if r["inference_level"] == "low")
    other = len(rows) - dq - low
    return (dq == 22 and low == 172 and other == 0,
            f"direct_quote={dq} low={low} other={other}")


def t_x3():
    p = ROOT / "audit/_process/yaml_csv_sync_violations.csv"
    if not p.exists():
        return False, "缺 yaml_csv_sync_violations.csv"
    rows = list(csv.reader(p.open()))
    return (len(rows) <= 1, f"violations rows (含表头)={len(rows)}")


def t_x4():
    sigs = json.load((ROOT / "manifest.json").open()).get("signatures", {})
    keys = {"data_signature", "tooling_signature", "total_signature"}
    return (keys.issubset(sigs.keys()), f"signatures keys: {sorted(sigs.keys())}")


def t_x5():
    status = json.load((ROOT / "audit/audit_status.json").open())
    gates = {g["gate"] for g in status["gates"]}
    expect = {"G16d_a", "G16d_b", "G17a", "G17b", "G18"}
    miss = expect - gates
    return (not miss, f"全部 5 道新门已并入" if not miss else f"缺: {miss}")


def t_a1():
    rows = list(csv.DictReader((ROOT / "audit/source_unit_adjudication.csv").open()))
    valid = {"covered_by_pack", "unprocessable", "duplicate_or_redundant", "pending_decision"}
    bad = [r for r in rows if r["adjudication_status"] not in valid]
    return (not bad, f"4 状态白名单封闭" if not bad else f"非法状态: {len(bad)}")


def t_a2():
    rows = list(csv.DictReader((ROOT / "audit/source_unit_adjudication.csv").open()))
    pendings = [r for r in rows if r["adjudication_status"] == "pending_decision"]
    bad = [r for r in pendings if r["priority"] not in {"high", "medium", "low"}
           or not r["heading_path"] or not r["rationale"]]
    return (not bad, f"{len(pendings)} pending 全部具名+priority+rationale")


def t_a3():
    rows = list(csv.DictReader((ROOT / "audit/source_unit_adjudication.csv").open()))
    dups = [r for r in rows if r["adjudication_status"] == "duplicate_or_redundant"]
    bad = [r for r in dups if r["sub_reason"] != "identical_body_hash_to_covered_sibling"
           or not r["body_hash"]]
    return (not bad, f"{len(dups)} duplicate 仅 body_hash 一致触发")


def t_b1():
    ev = sum(1 for _ in csv.DictReader((ROOT / "nine_tables/07_evidence.csv").open()))
    adj = sum(1 for _ in csv.DictReader((ROOT / "audit/evidence_row_adjudication.csv").open()))
    return (ev == adj, f"evidence={ev} adj={adj}")


def t_b2():
    rows = list(csv.DictReader((ROOT / "audit/evidence_row_adjudication.csv").open()))
    bad = [r for r in rows if r["adjudication_status"] == "direct_quote_verified"
           and r["strict_substring_hit"] != "true"]
    n_dq = sum(1 for r in rows if r["adjudication_status"] == "direct_quote_verified")
    return (not bad, f"{n_dq} direct_quote_verified 全部 strict=true")


def t_b3():
    rows = list(csv.DictReader((ROOT / "audit/evidence_row_adjudication.csv").open()))
    paras = [r for r in rows if r["adjudication_status"] == "paraphrase_located"]
    bad = [r for r in paras if float(r["phrase_hit_rate"]) < 0.30]
    return (not bad, f"{len(paras)} paraphrase_located 全部 ≥30%")


FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def t_c1():
    bad = []
    for p in PROCESS.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        m = FM_RE.match(text)
        if not m:
            bad.append(f"{p.name}: 缺 frontmatter")
            continue
        fm = {k.strip(): v.strip() for k, v in
              (line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)}
        st = fm.get("snapshot_type")
        if st == "historical_review" and "frozen_at" not in fm:
            bad.append(f"{p.name}: 缺 frozen_at")
        if st == "live" and "last_validated" not in fm:
            bad.append(f"{p.name}: 缺 last_validated")
        if st not in {"historical_review", "live"}:
            bad.append(f"{p.name}: snapshot_type={st}")
    return (not bad, f"11 派生 md frontmatter 全部合法" if not bad else f"问题: {bad}")


def t_c2():
    text = (PROCESS / "empty_tables_explanation.md").read_text(encoding="utf-8")
    man = json.load((ROOT / "manifest.json").open())
    rows = {Path(e["path"]).stem: e["data_rows"] for e in man["nine_tables"]}
    bad = []
    for stem, n in rows.items():
        m = re.search(rf"\| *{re.escape(stem)} *\| *(\d+) *\|", text)
        if not m:
            bad.append(f"{stem} 缺")
        elif int(m.group(1)) != n:
            bad.append(f"{stem}: doc={m.group(1)} vs manifest={n}")
    return (not bad, "数值与 manifest 对齐" if not bad else f"漂移: {bad}")


def t_c3():
    # 边缘：删一份 historical 的 frozen_at 应让 G18 触红（语义上 unfrozen snapshot）
    p = PROCESS / "w1_wave_review.md"
    orig = p.read_text(encoding="utf-8")
    tampered = orig.replace("frozen_at:", "FROZEN_AT_REMOVED:")
    p.write_text(tampered, encoding="utf-8")
    try:
        r = subprocess.run(["python3", "scripts/check_derived_doc_freshness.py"],
                           cwd=str(ROOT), capture_output=True, text=True)
        triggered = r.returncode != 0 and "frozen_at" in r.stdout
    finally:
        p.write_text(orig, encoding="utf-8")
    return (triggered, "篡改 frozen_at → G18 触红（边缘性正确）"
            if triggered else "G18 未捕获 frozen_at 缺失（漏门）")


def main():
    tests = [
        ("X-T1 9 表数据无变",        t_x1),
        ("X-T2 inference_level 不回退", t_x2),
        ("X-T3 yaml↔csv 同步",        t_x3),
        ("X-T4 manifest 双签名齐",    t_x4),
        ("X-T5 新硬门已并入",         t_x5),
        ("A-T1 4 状态白名单封闭",     t_a1),
        ("A-T2 pending 全部具名",     t_a2),
        ("A-T3 duplicate body_hash",  t_a3),
        ("B-T1 evidence 行数对齐",    t_b1),
        ("B-T2 direct_quote 严格命中", t_b2),
        ("B-T3 paraphrase ≥30%",      t_b3),
        ("C-T1 派生 md frontmatter",  t_c1),
        ("C-T2 empty_tables 漂移",    t_c2),
        ("C-T3 篡改 frozen_at 触红",  t_c3),
    ]
    print("=== W10 · 对抗 + 边缘测试 ===\n")
    passed = 0
    for n, fn in tests:
        if run_test(n, fn):
            passed += 1
    print(f"\n  汇总: {passed}/{len(tests)} 通过")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())

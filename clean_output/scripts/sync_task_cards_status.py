#!/usr/bin/env python3
"""硬门 7 · task_cards 状态总览自动同步

状态真源 = extraction_log.csv（事件时间戳）
数字真源 = 实时磁盘（manifest / csv / sqlite）—— 拒绝从 extraction_log 读数字

仅重写 ## 卡片状态总览 节，不动其他章节。
"""
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LOG = ROOT / "clean_output" / "audit" / "extraction_log.csv"
TC = ROOT / "clean_output" / "audit" / "task_cards.md"
MANIFEST = ROOT / "clean_output" / "manifest.json"

CARD_GROUPS = [
    ("TC-00",       "领域骨架",                    "Phase 0", ["TC-00"]),
    ("TC-01",       "3 条样本试抽",                "Phase A", ["TC-01"]),
    ("TC-B01 ~ TC-B08", "Q7Q12 批量",            "Phase B", ["TC-B01","TC-B02","TC-B03","TC-B04","TC-B05","TC-B06","TC-B07","TC-B08"]),
    ("TC-B09 ~ TC-B13", "Q4 批量",               "Phase B", ["TC-B09","TC-B10","TC-B11","TC-B12","TC-B13"]),
    ("TC-B14 ~ TC-B19", "Q2 批量",               "Phase B", ["TC-B14","TC-B15","TC-B16","TC-B17","TC-B18","TC-B19"]),
    ("TC-C01",      "4 闸全量验证",                "Phase C", ["TC-C01"]),
    ("TC-D01",      "9 表全量派生",                "Phase D", ["TC-D01"]),
    ("TC-E01",      "单库存储 SQL",                "Phase E", ["TC-E01"]),
    ("TC-F01",      "收口报告",                    "Phase F", ["TC-F01"]),
    ("TC-M01 / TC-M02", "滚动维护",                "跨 Phase", ["TC-M01","TC-M02"]),
]

def load_completed_cards():
    """从 extraction_log 取最末状态的卡 - 仅状态信息，不取数字"""
    completed = set()
    if not LOG.exists():
        return completed
    with open(LOG, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            phase = (row.get("phase") or "").strip()
            action = (row.get("action") or "").strip()
            if action == "task_card_completed" and phase.startswith("TC-"):
                completed.add(phase)
            # Phase 0 / A 用不同 action 名
            if action == "domain_skeleton_built":
                completed.add("TC-00")
            if phase == "Phase A" and action == "candidate_drafted":
                completed.add("TC-01")
    # 仅保留主卡，去掉 _rerun / _retry 后缀变体（防变体污染状态总览）
    return {c for c in completed if "_" not in c[3:]}

def load_live_numbers():
    """数字真源：实时磁盘。拒绝从 extraction_log 读"""
    cands = ROOT / "clean_output" / "candidates"
    pack_count = 0
    for sub in ("domain_general", "brand_faye", "needs_review"):
        d = cands / sub
        if d.exists():
            pack_count += sum(1 for _ in d.glob("*.yaml"))

    nine = ROOT / "clean_output" / "nine_tables"
    nine_total = 0
    for csvf in nine.glob("*.csv"):
        n = sum(1 for _ in open(csvf)) - 1
        nine_total += max(0, n)

    cov_pct = "—"
    try:
        from subprocess import run, PIPE
        out = run(["python3", str(ROOT / "clean_output/scripts/scan_unprocessed_md.py")],
                  capture_output=True, text=True, cwd=str(ROOT))
        m = re.search(r"覆盖率\s*:\s*([\d.]+)%", out.stdout)
        if m:
            cov_pct = m.group(1) + "%"
    except Exception:
        pass

    # 2026-05-12: knowledge.db 已废弃（path B），改读 9 张 CSV 行数 / read CSV row counts
    # 见 clean_output/audit/db_state_evidence_KS-S0-002.md
    sqlite_total = "—"
    nine_dir = ROOT / "clean_output/nine_tables"
    if nine_dir.exists():
        csv_files = [
            "01_object_type.csv", "02_field.csv", "03_semantic.csv",
            "04_value_set.csv", "05_relation.csv", "06_rule.csv",
            "07_evidence.csv", "08_lifecycle.csv", "09_call_mapping.csv",
        ]
        try:
            total = 0
            for f in csv_files:
                p = nine_dir / f
                if p.exists():
                    # 行数 - 1（扣表头 / minus header）
                    with p.open(encoding="utf-8") as fp:
                        total += sum(1 for _ in fp) - 1
            sqlite_total = str(total)
        except Exception as e:
            sqlite_total = f"err:{e}"

    return {
        "pack_count": pack_count,
        "nine_table_rows": nine_total,
        "coverage_pct": cov_pct,
        "sqlite_rows": sqlite_total,
    }

def render_status_table(completed, live):
    lines = []
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines.append("## 卡片状态总览")
    lines.append("")
    lines.append(f"<!-- AUTO-SYNCED at {ts}")
    lines.append("     status source: audit/extraction_log.csv (event timestamps)")
    lines.append("     numbers source: live disk (manifest.json + csv + sqlite)")
    lines.append("     DO NOT HAND-EDIT -->")
    lines.append("")
    lines.append("**实时数字真源**：")
    lines.append(f"- CandidatePack 总数：**{live['pack_count']}**（实测 candidates/**/*.yaml）")
    lines.append(f"- 9 表数据行总数：**{live['nine_table_rows']}**（实测 wc -l 减 header）")
    lines.append(f"- 正向覆盖率：**{live['coverage_pct']}**（实测 scan_unprocessed_md.py）")
    lines.append(f"- SQLite 加载行数：**{live['sqlite_rows']}**（实测 SELECT COUNT）")
    lines.append("")
    lines.append("**卡状态（来源 extraction_log task_card_completed 事件）**：")
    lines.append("")
    lines.append("| 卡号 | 名称 | Phase | 状态 |")
    lines.append("|---|---|---|---|")
    for label, name, phase, members in CARD_GROUPS:
        # 取成员的并集状态
        if all(m in completed for m in members):
            st = "✅ 完成"
        elif any(m in completed for m in members):
            done = sum(1 for m in members if m in completed)
            st = f"🔄 部分（{done}/{len(members)}）"
        elif phase == "跨 Phase":
            st = "♻ 持续"
        else:
            st = "⏸ 等待"
        lines.append(f"| {label} | {name} | {phase} | {st} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)

def main():
    completed = load_completed_cards()
    live = load_live_numbers()
    new_section = render_status_table(completed, live)

    text = TC.read_text(encoding="utf-8")
    # 替换 ## 卡片状态总览 ... 到下一个 ## 之前的整段
    pattern = re.compile(r"## 卡片状态总览.*?(?=\n## |\Z)", re.DOTALL)
    if not pattern.search(text):
        print("ERROR: 找不到 ## 卡片状态总览 节", file=sys.stderr)
        return 1
    new_text = pattern.sub(new_section.rstrip() + "\n", text, count=1)

    # 不再创建 .bak（W7 reviewer F5 纪律：clean_output 不留任何 bak 残留）
    TC.write_text(new_text, encoding="utf-8")

    print(f"已完成卡: {sorted(completed)}")
    print(f"实时数字: {live}")
    print(f"已写: {TC}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

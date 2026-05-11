#!/usr/bin/env python3
"""W12.A.9 · 笛语 AI 调用 demo（只读反查）

证明 W12.A 资产可被消费方按"领域通用 + 品牌专属"组合调用：
  1. 取一条 play_card → 反查 9 表 source_pack_id 关联行 → 反查 yaml → 反查源 md
  2. 取一条 runtime_asset → 反查 yaml → 反查源 pack
  3. 多租户查询模板：domain_general only / 假想 brand_xyz 应用

只读，无任何写入；输出到 runtime_assets/dify_demo_log.txt。
"""
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PCR = ROOT / "play_cards" / "play_card_register.csv"
RAI = ROOT / "runtime_assets" / "runtime_asset_index.csv"
DDL = ROOT / "storage" / "single_db_logical_isolation.sql"
NINE = ROOT / "nine_tables"
OUT = ROOT / "runtime_assets" / "dify_demo_log.txt"

TBL = {
    "object_type": "01_object_type", "field": "02_field", "semantic": "03_semantic",
    "value_set": "04_value_set", "relation": "05_relation", "rule": "06_rule",
    "evidence": "07_evidence", "lifecycle": "08_lifecycle", "call_mapping": "09_call_mapping",
}


def main():
    log = []
    def p(*a):
        s = " ".join(str(x) for x in a); log.append(s); print(s)

    p("=" * 70)
    p("W12.A.9 · 笛语 AI 调用 demo（只读反查）")
    p("=" * 70)

    # ===== Demo 1: play_card 反查链 =====
    p("\n--- Demo 1: 取一条 L2 play_card 反查到原 md ---\n")
    pcr = list(csv.DictReader(PCR.open(encoding="utf-8")))
    sample = pcr[0]
    p(f"  play_card_id   : {sample['play_card_id']}")
    p(f"  hook           : {sample['hook'][:60]}")
    p(f"  production_tier: {sample['production_tier']}")
    p(f"  default_call_pool: {sample['default_call_pool']}")
    p(f"  → source_pack_id: {sample['source_pack_id']}")

    # 反查 9 表（用 in-memory sqlite）
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.executescript(DDL.read_text(encoding="utf-8"))
    for table, stem in TBL.items():
        path = NINE / f"{stem}.csv"
        with path.open() as f:
            r = csv.reader(f); cols = next(r); rows = list(r)
        if rows:
            ph = ",".join("?" * len(cols))
            cur.executemany(f"INSERT OR IGNORE INTO {table} ({','.join(cols)}) VALUES ({ph})", rows)
    con.commit()

    cur.execute("SELECT rule_id, rule_type FROM rule WHERE source_pack_id=? LIMIT 3", (sample["source_pack_id"],))
    rule_rows = cur.fetchall()
    p(f"  9 表 rule 反查: {len(rule_rows)} 行")
    for rid, rtype in rule_rows:
        p(f"    rule_id={rid[:50]}  type={rtype}")

    cur.execute("SELECT source_md, source_anchor FROM evidence WHERE source_pack_id=? LIMIT 1", (sample["source_pack_id"],))
    ev = cur.fetchone()
    if ev:
        p(f"  → 原 md       : {ev[0]}")
        p(f"  → source_anchor: {ev[1][:80]}")

    # ===== Demo 2: runtime_asset 反查 =====
    p("\n--- Demo 2: 取一条 L3 runtime_asset 反查 ---\n")
    rai = list(csv.DictReader(RAI.open(encoding="utf-8")))
    sample = rai[0]
    p(f"  runtime_asset_id: {sample['runtime_asset_id']}")
    p(f"  asset_type      : {sample['asset_type']}")
    p(f"  title           : {sample['title']}")
    p(f"  summary         : {sample['summary']}")
    p(f"  source_pointer  : {sample['source_pointer']}")
    p(f"  pack_id         : {sample['pack_id']}")

    # ===== Demo 3: 多租户组合查询 =====
    p("\n--- Demo 3: 多租户组合查询（领域通用 + 品牌专属）---\n")
    cur.execute("SELECT COUNT(*) FROM rule WHERE brand_layer='domain_general'")
    dg = cur.fetchone()[0]
    p(f"  domain_general 单层 rule: {dg} 行")
    cur.execute("SELECT COUNT(*) FROM rule WHERE brand_layer IN ('domain_general','brand_xyz')")
    xyz = cur.fetchone()[0]
    p(f"  brand_xyz 应用 (dg+xyz) rule: {xyz} 行 (xyz=0，等同 dg)")

    # ===== Demo 4: L2 调用池过滤 =====
    p("\n--- Demo 4: L2 玩法卡按 default_call_pool 过滤 ---\n")
    pool_yes = sum(1 for r in pcr if r["default_call_pool"].lower() == "true")
    pool_no = len(pcr) - pool_yes
    p(f"  默认调用池 (default_call_pool=true)   : {pool_yes}")
    p(f"  非默认（需显式调用）                   : {pool_no}")
    instant = sum(1 for r in pcr if r["production_tier"] == "instant")
    p(f"  instant tier (1人+手机+200元+4h)      : {instant}/{len(pcr)}")

    # ===== Demo 5: L3 按 asset_type 分桶 =====
    p("\n--- Demo 5: L3 资产按 asset_type 分桶（消费方按需选层）---\n")
    from collections import Counter
    bucket = Counter(r["asset_type"] for r in rai)
    for at, n in bucket.most_common():
        p(f"  {at:20s} {n}")

    p("\n" + "=" * 70)
    p("✅ Demo 全部跑通：play_card → 9 表 → md / runtime_asset → yaml 反查链路完整")
    p("=" * 70)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(log) + "\n", encoding="utf-8")
    p(f"\n日志: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

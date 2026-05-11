#!/usr/bin/env python3
"""Plan A-lite · 章节级裁决账本

读 audit/knowledge_point_coverage.csv（1578 source_unit）
产出 audit/source_unit_adjudication.csv，4 状态：
  - covered_by_pack          已被 pack/evidence 命中（直接或父锚点）
  - unprocessable            元层/cross-source/短节/已注册不可处理
  - duplicate_or_redundant   同一文件内 body 哈希与已 covered 章节完全一致
  - pending_decision         其他未覆盖业务章节，等待人工/下一波裁决

reviewer 指令：
- 自动只签明显低风险（covered → covered_by_pack；exempt → unprocessable；
  body 完全重复 → duplicate；其他 uncovered 全进 pending_decision）
- pending_decision 必须带 name(heading_path) + rationale + priority
- G16d 仅硬门"全章节有状态"（无 _pending_review_）；不硬门自动签发率
"""
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent
COVERAGE = ROOT / "audit" / "knowledge_point_coverage.csv"
INVENTORY = ROOT / "audit" / "source_unit_inventory.csv"
OUT = ROOT / "audit" / "source_unit_adjudication.csv"

# coverage_status → adjudication_status + sub_reason
EXEMPT_MAP = {
    "exempt_unprocessable":          ("unprocessable", "explicitly_unprocessable"),
    "exempt_short_section":          ("unprocessable", "short_section_lt_100_chars"),
    "exempt_meta_non_business":      ("unprocessable", "meta_non_business"),
    "exempt_cross_source_reference": ("unprocessable", "cross_source_reference"),
}
COVERED_PREFIXES = ("covered_by_quote_in_md", "covered_by_anchor", "covered_by_parent_anchor")


def body_text_for(unit, md_text):
    """近似取一节 body：从该 heading 后一行起到下一个 heading（任意级别）止，仅作 hash 用"""
    line_no = int(unit["line_no"])
    lines = md_text.splitlines()
    out = []
    i = line_no  # 0-based 标题行 = line_no-1，body 从 line_no 起
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            break
        out.append(line)
        i += 1
    return "\n".join(out).strip()


def priority_for(body_len: int) -> str:
    if body_len >= 300:
        return "high"
    if body_len >= 100:
        return "medium"
    return "low"


def main():
    cov = list(csv.DictReader(COVERAGE.open(encoding="utf-8")))
    inv = list(csv.DictReader(INVENTORY.open(encoding="utf-8")))
    inv_idx = {(r["source_md"], r["heading_path"], r["line_no"]): r for r in inv}

    md_cache = {}

    def md_text(path):
        if path not in md_cache:
            p = WORKSPACE / path
            md_cache[path] = p.read_text(encoding="utf-8") if p.exists() else ""
        return md_cache[path]

    # 第一遍：定 covered / exempt；记录每文件 covered 章节的 body hash
    auto = []
    pending_candidates = []
    covered_hash_by_md = defaultdict(set)
    for c in cov:
        key = (c["source_md"], c["heading_path"])
        unit_match = [r for r in inv if r["source_md"] == c["source_md"]
                      and r["heading_path"] == c["heading_path"]]
        unit = unit_match[0] if unit_match else None
        body_hash = ""
        if unit:
            text = md_text(c["source_md"])
            body = body_text_for(unit, text)
            if body:
                body_hash = hashlib.sha1(body.encode("utf-8")).hexdigest()[:12]

        status = c["coverage_status"]
        if any(status.startswith(p) for p in COVERED_PREFIXES):
            auto.append({
                "source_md": c["source_md"],
                "heading_path": c["heading_path"],
                "heading_level": c["heading_level"],
                "body_length": c["body_length"],
                "body_hash": body_hash,
                "adjudication_status": "covered_by_pack",
                "sub_reason": status.replace("covered_by_", ""),
                "adjudicator": "auto",
                "priority": "",
                "rationale": "已被 evidence 直接命中或父 pack 间接覆盖",
                "batch_target": "",
            })
            if body_hash:
                covered_hash_by_md[c["source_md"]].add(body_hash)
        elif status in EXEMPT_MAP:
            adj, sub = EXEMPT_MAP[status]
            auto.append({
                "source_md": c["source_md"],
                "heading_path": c["heading_path"],
                "heading_level": c["heading_level"],
                "body_length": c["body_length"],
                "body_hash": body_hash,
                "adjudication_status": adj,
                "sub_reason": sub,
                "adjudicator": "auto",
                "priority": "",
                "rationale": f"按 5-class 签字 / W2 决议归入 {sub}",
                "batch_target": "",
            })
        else:
            # uncovered → 留到第二遍处理（需要 covered_hash 全集）
            pending_candidates.append({
                "source_md": c["source_md"],
                "heading_path": c["heading_path"],
                "heading_level": c["heading_level"],
                "body_length": c["body_length"],
                "body_hash": body_hash,
            })

    # 第二遍：uncovered → duplicate_or_redundant or pending_decision
    final = list(auto)
    dup_count = 0
    pending_count = 0
    for u in pending_candidates:
        body_len = int(u["body_length"] or 0)
        if u["body_hash"] and u["body_hash"] in covered_hash_by_md.get(u["source_md"], set()):
            final.append({
                **u,
                "adjudication_status": "duplicate_or_redundant",
                "sub_reason": "identical_body_hash_to_covered_sibling",
                "adjudicator": "auto",
                "priority": "",
                "rationale": "同文件内已有 covered 兄弟节点 body hash 一致，视为重复",
                "batch_target": "",
            })
            dup_count += 1
        else:
            # 推断 batch_target：玩法卡 / 子节
            ht = u["heading_path"]
            if "玩法" in ht or ht.startswith("#C") or ht.startswith("玩法"):
                hint = "next_wave_play_card_extraction"
            elif "服装行业垂直加成" in ht or "制作难度判断" in ht:
                hint = "next_wave_industry_addon"
            else:
                hint = "next_wave_general_review"
            final.append({
                **u,
                "adjudication_status": "pending_decision",
                "sub_reason": "uncovered_business_chapter",
                "adjudicator": "auto",
                "priority": priority_for(body_len),
                "rationale": "未被现有 pack 命中的业务章节，待下一波裁决",
                "batch_target": hint,
            })
            pending_count += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["source_md", "heading_path", "heading_level", "body_length", "body_hash",
            "adjudication_status", "sub_reason", "adjudicator",
            "priority", "rationale", "batch_target"]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(final)

    from collections import Counter
    cnt = Counter(r["adjudication_status"] for r in final)
    print(f"=== Plan A-lite · source_unit 裁决账本 ===\n")
    print(f"  总计 {len(final)} 行")
    for k in ("covered_by_pack", "unprocessable", "duplicate_or_redundant", "pending_decision"):
        print(f"    {k:25s} {cnt.get(k, 0)}")
    print(f"  pending priority 分布: ", end="")
    pri = Counter(r["priority"] for r in final if r["adjudication_status"] == "pending_decision")
    print(dict(pri))
    print(f"\n输出: {OUT}")

    # 同步写入 coverage_status.json 的 chapter_adjudication 块
    cov_path = ROOT / "audit" / "coverage_status.json"
    if cov_path.exists():
        cov = json.loads(cov_path.read_text(encoding="utf-8"))
        kp = cov.get("knowledge_point_coverage", {})
        business_total = kp.get("business_total", 0)
        pri = Counter(r["priority"] for r in final if r["adjudication_status"] == "pending_decision")
        non_pending = (cnt.get("covered_by_pack", 0)
                       + cnt.get("unprocessable", 0)
                       + cnt.get("duplicate_or_redundant", 0))
        # 章节裁决率：业务章节中已签字非 pending 的占比
        biz_signed = (cnt.get("covered_by_pack", 0)
                      + cnt.get("duplicate_or_redundant", 0))
        chapter_adj_pct = round(biz_signed * 100 / max(business_total, 1), 1) if business_total else 0
        cov["chapter_adjudication"] = {
            "total_units": len(final),
            "covered_by_pack": cnt.get("covered_by_pack", 0),
            "unprocessable": cnt.get("unprocessable", 0),
            "duplicate_or_redundant": cnt.get("duplicate_or_redundant", 0),
            "pending_decision": cnt.get("pending_decision", 0),
            "pending_priority": {"high": pri.get("high", 0), "medium": pri.get("medium", 0), "low": pri.get("low", 0)},
            "non_pending_total": non_pending,
            "business_total": business_total,
            "chapter_adjudication_pct": chapter_adj_pct,
        }
        # W11 防漂移：若 W11 主表存在，把 layer_distribution 也持久化（避免被 G12 覆盖丢失）
        w11 = ROOT / "audit" / "source_unit_adjudication_w11.csv"
        if w11.exists():
            import csv as _csv
            from collections import Counter as _C
            w11_rows = list(_csv.DictReader(w11.open(encoding="utf-8")))
            su_dist = _C(r.get("final_status", "") for r in w11_rows)
            pk_path = ROOT / "audit" / "pack_layer_register.csv"
            pk_dist = {}
            if pk_path.exists():
                pk_rows = list(_csv.DictReader(pk_path.open(encoding="utf-8")))
                pk_dist = dict(_C(r.get("final_layer", "") for r in pk_rows))
            biz_total = kp.get("business_total", 1148) if kp else 1148
            cov["layer_distribution"] = {
                "source_unit_final_status": dict(su_dist),
                "pack_final_layer": pk_dist,
                "business_total": biz_total,
                "l1_pct": round(su_dist.get("extract_l1", 0) * 100 / max(biz_total, 1), 1),
                "l2_pct": round(su_dist.get("extract_l2", 0) * 100 / max(biz_total, 1), 1),
                "l3_pct": round(su_dist.get("defer_l3_to_runtime_asset", 0) * 100 / max(biz_total, 1), 1),
            }
        cov_path.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 coverage_status.json · chapter_adjudication (chapter_adjudication_pct={chapter_adj_pct}%)")
        if (ROOT / "audit" / "source_unit_adjudication_w11.csv").exists():
            print(f"已写入 coverage_status.json · layer_distribution (W11 三层防漂移)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

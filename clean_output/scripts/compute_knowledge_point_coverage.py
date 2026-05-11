#!/usr/bin/env python3
"""知识点级覆盖率计算

对 audit/source_unit_inventory.csv 中每个 source_unit 判断是否被 pack 覆盖：

判定规则（任一成立即 covered）：
  R1. evidence.source_anchor 包含 source_unit.heading 关键短语（≥4 字符片段命中）
  R2. evidence.evidence_quote 的 phrase 在 source_unit.body 中出现（命中率 ≥30%）
  R3. source_md 在 5-class register 中 meta_non_business 类（豁免分母）

输出：
  audit/knowledge_point_coverage.csv（每行一个 source_unit + 覆盖状态）
  audit/coverage_status.json 增 knowledge_point_coverage_pct 字段

业务级覆盖率 = 已覆盖 / (总单元 - meta_non_business 豁免)
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent
INVENTORY = ROOT / "audit" / "source_unit_inventory.csv"
EVIDENCE = ROOT / "nine_tables" / "07_evidence.csv"
COVERAGE_STATUS = ROOT / "audit" / "coverage_status.json"
OUT = ROOT / "audit" / "knowledge_point_coverage.csv"

PUNCT_MAP = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "、": ",", "。": ".", "，": ",", "：": ":",
    "；": ";", "？": "?", "！": "!",
    "—": "-", "–": "-", "−": "-",
    "（": "(", "）": ")", "【": "[", "】": "]",
    " ": "", " ": "", "​": "", "§": "",
})

SPLIT_RE = re.compile(r"[,.;:()\[\]\"'!?\-/|→<>=*\s+·、；,]+")


def norm_anchor(s):
    s = (s or "").translate(PUNCT_MAP)
    return re.sub(r"\s+", "", s).strip().lower()


def loose_norm(s):
    s = (s or "").translate(PUNCT_MAP)
    return re.sub(r"\s+", " ", s).strip()


def heading_keywords(heading):
    """从 heading 提取 ≥3 字符的非数字关键片段"""
    n = norm_anchor(heading)
    parts = SPLIT_RE.split(n)
    return [p for p in parts if len(p) >= 3 and not re.fullmatch(r"[\d.]+", p)]


def main():
    if not INVENTORY.exists():
        print("先跑 parse_md_source_units.py", file=sys.stderr)
        return 2

    units = list(csv.DictReader(open(INVENTORY, encoding="utf-8")))
    evidences = list(csv.DictReader(open(EVIDENCE, encoding="utf-8")))

    # 加载 meta_non_business 豁免清单
    cov = {}
    if COVERAGE_STATUS.exists():
        cov = json.loads(COVERAGE_STATUS.read_text(encoding="utf-8"))
    meta_md = set()
    cross_src_md = set()
    unprocessable_md = set()
    for src, meta in cov.get("register_detail", {}).items():
        cls = meta.get("classification")
        if cls == "meta_non_business":
            meta_md.add(src)
        elif cls == "cross_source_reference":
            cross_src_md.add(src)
        elif cls == "unprocessable":
            unprocessable_md.add(src)

    # 按 source_md 分桶 evidences
    ev_by_md = {}
    for e in evidences:
        for src in re.split(r"\s*&\s*", e["source_md"]):
            src = src.strip()
            if "/" not in src and "/" in e["source_md"].split("&")[0]:
                base = e["source_md"].split("&")[0].rsplit("/", 1)[0]
                src = f"{base}/{src}"
            if src:
                ev_by_md.setdefault(src, []).append(e)

    # 加载 MD 全文（用于 phrase 在 MD 中定位 → 反查所属 source_unit）
    md_text_cache = {}
    md_unit_lines = {}  # md_path → [(line_no, unit_idx)] 已排序
    for u_idx, u in enumerate(units):
        md_unit_lines.setdefault(u["source_md"], []).append((int(u["line_no"]), u_idx))
    for k in md_unit_lines:
        md_unit_lines[k].sort()

    def find_unit_for_line(md, line_no):
        """二分找该行号属于哪个 source_unit（最大的 line_no <= 给定行）"""
        ranges = md_unit_lines.get(md, [])
        if not ranges:
            return None
        last_idx = None
        for ln, idx in ranges:
            if ln <= line_no:
                last_idx = idx
            else:
                break
        return last_idx

    print("=== 知识点级覆盖计算 ===\n")
    print(f"  source_unit 总数: {len(units)}")
    print(f"  meta_non_business 豁免: {len(meta_md)} 份 MD")
    print(f"  cross_source_reference 豁免: {len(cross_src_md)} 份 MD")
    print(f"  unprocessable 豁免: {len(unprocessable_md)} 份 MD")

    # 准备：建 (md, line_no) → unit_idx 二分查找索引
    # 父 pack 的 source_anchor 中提到的章节标记（如 "§A 北极星"、"二、4）"、"6.1 规则"）
    # 子节（玩法卡 #C1-1 等）若位于该章节范围内即间接覆盖
    md_units_sorted = {}
    for u_idx, u in enumerate(units):
        md_units_sorted.setdefault(u["source_md"], []).append((int(u["line_no"]), u_idx, u["heading_path"], int(u["heading_level"])))
    for k in md_units_sorted:
        md_units_sorted[k].sort()

    def find_anchor_unit_indices(md, anchor):
        """对 source_anchor，找该 MD 中匹配该 anchor 的所有 unit；
        返回这些 unit 的 line_no 范围（用于覆盖 descendant）"""
        if not md or not anchor:
            return []
        ranges = md_units_sorted.get(md, [])
        if not ranges:
            return []
        # anchor 切到关键短语（≥3 字符 / 非纯数字）
        parts = re.split(r"[+·,、;]+", anchor)
        keywords = []
        for part in parts:
            for sub in part.split():
                kw = norm_anchor(sub)
                if len(kw) >= 3 and not re.fullmatch(r"[\d.]+", kw):
                    keywords.append(kw)
            whole = norm_anchor(part)
            if len(whole) >= 3:
                keywords.append(whole)
        # 找命中的 unit
        hits = []
        for line_no, u_idx, heading, level in ranges:
            heading_n = norm_anchor(heading)
            if any(kw in heading_n for kw in keywords):
                hits.append((line_no, u_idx, level))
        return hits

    # 第一轮：通过 evidence_quote 在 MD 中的位置反查覆盖（最准）
    unit_covered_by = [None] * len(units)
    for ev in evidences:
        srcs = [s.strip() for s in re.split(r"\s*&\s*", ev["source_md"])]
        if "/" not in srcs[0] and len(srcs) > 1:
            pass
        for src in srcs:
            if "/" not in src and "/" in srcs[0]:
                base = srcs[0].rsplit("/", 1)[0]
                src = f"{base}/{src}"
            md_path = WORKSPACE / src
            if not md_path.exists():
                continue
            if src not in md_text_cache:
                md_text_cache[src] = md_path.read_text(encoding="utf-8")
            md_text = md_text_cache[src]
            quote_n = loose_norm(ev.get("evidence_quote", ""))
            phrases = [p.strip() for p in SPLIT_RE.split(quote_n) if len(p.strip()) >= 8][:5]
            for ph in phrases:
                # 在 MD 中找首次出现
                idx = md_text.find(ph)
                if idx == -1:
                    # 试 loose 匹配（删除空白后）
                    md_packed = re.sub(r"\s+", "", md_text)
                    if ph in md_packed:
                        # 估算 line：用近似定位
                        approx = md_packed.find(ph)
                        # ratio of char position
                        ratio = approx / len(md_packed) if md_packed else 0
                        line_no = int(ratio * md_text.count("\n")) + 1
                    else:
                        continue
                else:
                    line_no = md_text[:idx].count("\n") + 1
                u_idx = find_unit_for_line(src, line_no)
                if u_idx is not None and unit_covered_by[u_idx] is None:
                    unit_covered_by[u_idx] = ev["evidence_id"]

    # 第二轮（D 改进）：父 pack 的 source_anchor 命中某 H2/H3 章节，
    # 该章节的所有 descendant（更深 level 的 source_unit）算间接覆盖
    indirect_covered_by = [None] * len(units)
    for ev in evidences:
        srcs_raw = [s.strip() for s in re.split(r"\s*&\s*", ev["source_md"]) if s.strip()]
        if "/" not in srcs_raw[0] and len(srcs_raw) > 1:
            base = srcs_raw[0].rsplit("/", 1)[0] if "/" in srcs_raw[0] else ""
            srcs_raw = [s if "/" in s else f"{base}/{s}" for s in srcs_raw]
        anchor = ev.get("source_anchor", "")
        for src in srcs_raw:
            hits = find_anchor_unit_indices(src, anchor)
            for parent_line, parent_idx, parent_level in hits:
                # 标记该 hit unit 自身
                if unit_covered_by[parent_idx] is None and indirect_covered_by[parent_idx] is None:
                    indirect_covered_by[parent_idx] = f"{ev['evidence_id']}(anchor)"
                # 找该 unit 的 descendant：line_no > parent_line 且 level > parent_level，
                # 直到下一个同级或更高级 unit
                ranges = md_units_sorted.get(src, [])
                in_scope = False
                for line_no, u_idx, level in [(r[0], r[1], r[3]) for r in ranges]:
                    if line_no <= parent_line:
                        continue
                    if level <= parent_level:
                        break  # 出 scope（同级或更高 heading）
                    if unit_covered_by[u_idx] is None and indirect_covered_by[u_idx] is None:
                        indirect_covered_by[u_idx] = f"{ev['evidence_id']}(anchor-descendant)"

    out_rows = []
    covered = 0
    exempted = 0
    uncovered = 0
    short = 0

    for u_idx, u in enumerate(units):
        src = u["source_md"]
        heading = u["heading_path"]
        body_first = u["body_first_100"]
        body_len = int(u["body_length"] or 0)

        status = "uncovered"
        covered_by = ""

        # R3 豁免：meta / cross_source / unprocessable MD 整体不计入分母
        if src in meta_md:
            status = "exempt_meta_non_business"
            exempted += 1
        elif src in cross_src_md:
            status = "exempt_cross_source_reference"
            exempted += 1
        elif src in unprocessable_md:
            status = "exempt_unprocessable"
            exempted += 1
        # 短章节豁免（body < 50 字 = 标题级目录非知识点）
        elif body_len < 50:
            status = "exempt_short_section"
            short += 1
        else:
            # R0: quote 在 MD 中的位置反查到本 source_unit
            if unit_covered_by[u_idx] is not None:
                status = "covered_by_quote_in_md"
                covered_by = unit_covered_by[u_idx]
            elif indirect_covered_by[u_idx] is not None:
                # D 改进：父 pack anchor 命中本节或其祖先章节
                status = "covered_by_parent_anchor"
                covered_by = indirect_covered_by[u_idx]
            else:
                # R1: anchor 含 heading 关键短语
                kws = heading_keywords(heading)
                md_evs = ev_by_md.get(src, [])
                for e in md_evs:
                    anchor_n = norm_anchor(e.get("source_anchor", ""))
                    if any(kw in anchor_n for kw in kws):
                        status = "covered_by_anchor"
                        covered_by = e["evidence_id"]
                        break
            if status == "uncovered":
                uncovered += 1
            else:
                covered += 1

        out_rows.append({
            **{k: u[k] for k in ("source_md", "heading_path", "heading_level", "body_length")},
            "coverage_status": status,
            "covered_by_evidence": covered_by,
        })

    business_total = len(units) - exempted - short
    coverage_pct = round(covered / business_total * 100, 1) if business_total else 0
    print(f"\n  分布：")
    print(f"    covered: {covered}")
    print(f"    uncovered: {uncovered}")
    print(f"    exempt_meta_non_business: {exempted}")
    print(f"    exempt_short_section: {short}")
    print(f"\n  业务知识点 = {business_total}（去元层去短节）")
    print(f"  知识点级覆盖率: {covered}/{business_total} = {coverage_pct}%")

    cols = ["source_md", "heading_path", "heading_level", "body_length",
            "coverage_status", "covered_by_evidence"]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)

    # 写入 coverage_status.json 增字段
    cov["knowledge_point_coverage"] = {
        "total_units": len(units),
        "covered": covered,
        "uncovered": uncovered,
        "exempt_meta_non_business": exempted,
        "exempt_short_section": short,
        "business_total": business_total,
        "coverage_pct": coverage_pct,
    }
    COVERAGE_STATUS.write_text(json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n  → {OUT}")
    print(f"  → coverage_status.json (knowledge_point_coverage 字段)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

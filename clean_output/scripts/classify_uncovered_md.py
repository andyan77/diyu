#!/usr/bin/env python3
"""硬门 7 辅助 · 分类未覆盖 MD 为 A/B 两类

A · truly_uncovered_md：scan_unprocessed_md 报未抽 + 全 yaml 中无任何引用
B · covered_via_cross_source_pack：scan_unprocessed_md 报未抽 + 至少 1 yaml 有引用
   （source_md 复合 / source_anchor / evidence_quote 直引）

输出 audit/uncovered_md_register.md（含 A/B 两节）。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_DIRS = ["Q2-内容类型种子", "Q4-人设种子", "Q7Q12-搭配陈列业务包"]
CAND = ROOT / "clean_output" / "candidates"
REGISTER = ROOT / "clean_output" / "unprocessable_register" / "register.csv"
OUT = ROOT / "clean_output" / "audit" / "uncovered_md_register.md"

PAT_SRC = re.compile(r"^\s*source_md:\s*(.+?)\s*$")

def list_input_md():
    out = []
    for d in INPUT_DIRS:
        p = ROOT / d
        if not p.exists():
            continue
        for f in sorted(p.rglob("*.md")):
            out.append(str(f.relative_to(ROOT)))
    return out

def list_processed_source_md():
    """复用 scan_unprocessed_md 同款逻辑（含复合 source_md 拆分）"""
    seen = set()
    for y in CAND.rglob("*.yaml"):
        for line in y.read_text(encoding="utf-8").splitlines():
            m = PAT_SRC.match(line)
            if m:
                v = m.group(1).strip().strip("'\"")
                if "&" in v:
                    parts = [p.strip() for p in v.split("&") if p.strip()]
                    base_dir = parts[0].rsplit("/", 1)[0] if "/" in parts[0] else ""
                    for idx, p in enumerate(parts):
                        if idx > 0 and "/" not in p and base_dir:
                            seen.add(f"{base_dir}/{p}")
                        else:
                            seen.add(p)
                else:
                    seen.add(v)
                break
    return seen

def grep_md_in_yamls(md_path):
    """在所有 yaml 中查 md 的文件名是否被引用"""
    md_filename = md_path.rsplit("/", 1)[-1]
    hits = []
    for y in CAND.rglob("*.yaml"):
        text = y.read_text(encoding="utf-8")
        if md_filename in text:
            hits.append(y.stem)
    return hits

def find_unprocessable_id(md_path):
    """register.csv 中 source_md 字段含此 md 的 unprocessable_id"""
    if not REGISTER.exists():
        return []
    import csv
    ids = []
    md_filename = md_path.rsplit("/", 1)[-1]
    with open(REGISTER, encoding="utf-8") as f:
        r = csv.reader(f)
        try:
            header = next(r)
        except StopIteration:
            return []
        # find source_md col index
        try:
            src_idx = header.index("source_md")
            id_idx = header.index("unprocessable_id")
        except ValueError:
            return []
        for row in r:
            if len(row) > max(src_idx, id_idx) and md_filename in row[src_idx]:
                ids.append(row[id_idx])
    return ids

def main():
    inputs = set(list_input_md())
    processed = list_processed_source_md()
    uncovered = sorted(inputs - processed)

    a_class = []  # truly uncovered
    b_class = []  # covered via cross-source

    for md in uncovered:
        hits = grep_md_in_yamls(md)
        if hits:
            b_class.append((md, hits))
        else:
            up_ids = find_unprocessable_id(md)
            a_class.append((md, up_ids))

    # 渲染
    lines = ["# uncovered_md_register · A/B 两类登记",
             "",
             f"> 生成于：{__import__('datetime').datetime.now().isoformat(timespec='seconds')}",
             f"> 数据源：scan_unprocessed_md 实测 + grep candidates yaml + register.csv 反查",
             f"> 全集 N = {len(uncovered)} 份未抽 MD",
             f"> A 类（真未处理）= {len(a_class)} 份 / B 类（已 cross-source 覆盖）= {len(b_class)} 份",
             "",
             "## A · truly_uncovered_md（真正未处理 · 必须有 unprocessable_id 作证）",
             "",
             "| source_md | classification | unprocessable_id | rationale | confirmed_by |",
             "|---|---|---|---|---|",
             ]
    for md, up_ids in a_class:
        # 启发式 classification
        if md.endswith("/CLAUDE.md") or md.endswith("/_index.md"):
            cls = "meta_layer_definition"
            rationale = "工作区导航 / 红线说明，非业务断言素材"
        elif "GPT5.4" in md or "compass_artifact" in md or "深度研究" in md or "deep-research" in md:
            cls = "external_reference_material"
            rationale = "外部参考资料 / 综述，已通过 unprocessable 收口"
        else:
            cls = "out_of_scope"
            rationale = "待人工核对"
        ids_str = ";".join(up_ids) if up_ids else "**MISSING**"
        lines.append(f"| {md} | {cls} | {ids_str} | {rationale} | _pending_review_ |")

    lines += ["",
              "## B · covered_via_cross_source_pack（已被 pack 间接覆盖 · 列 ≥1 covering_pack_id）",
              "",
              "| source_md | covering_pack_ids | how_covered | confirmed_by |",
              "|---|---|---|---|",
              ]
    for md, hits in b_class:
        ids_str = "; ".join(hits[:5]) + (f" ...(+{len(hits)-5})" if len(hits) > 5 else "")
        lines.append(f"| {md} | {ids_str} | yaml 中文件名直引（grep 命中 {len(hits)} 个 pack）| _pending_review_ |")

    lines += ["",
              "---",
              "",
              "## 验收门",
              "",
              "- A 类每行 unprocessable_id 非空（标 MISSING 即 FAIL）",
              "- B 类每行 covering_pack_ids 非空",
              "- 任一 confirmed_by = _pending_review_ → 仍待人工签字（执行结束前必须改为实际人/系统标识）",
              "- A+B 总数 = 全集 N",
              ]

    OUT.write_text("\n".join(lines), encoding="utf-8")

    # 一致性检查
    print(f"全集 N = {len(uncovered)}")
    print(f"A 类 truly_uncovered_md = {len(a_class)}")
    print(f"B 类 covered_via_cross_source_pack = {len(b_class)}")
    a_missing = sum(1 for md, ids in a_class if not ids)
    print(f"A 类 unprocessable_id 缺失 = {a_missing}")
    print(f"输出: {OUT}")
    return 0 if a_missing == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

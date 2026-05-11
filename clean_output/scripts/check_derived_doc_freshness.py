#!/usr/bin/env python3
"""硬门 G18 · 派生文档冻结/漂移检测

规则（reviewer 指令：仅查"明显漂移 + 未冻结快照"）：

1. audit/_process/*.md 必须有 YAML frontmatter，声明 snapshot_type
   - snapshot_type ∈ {historical_review, live}
   - historical_review: 必须带 frozen_at（ISO8601）
   - live: 必须带 last_validated（ISO 日期）

2. 对 snapshot_type=live 的文档，做数值漂移检测（仅当前已识别的 1 个）：
   - empty_tables_explanation.md 中所有"NN 行"/"NN"声明
     与 manifest.json nine_tables.data_rows 的字典一致

不在白名单的 *.md 触红。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESS = ROOT / "audit" / "_process"
MANIFEST = ROOT / "manifest.json"

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict:
    m = FM_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def main():
    issues = []
    md_files = sorted(PROCESS.glob("*.md"))
    print(f"=== G18 · 派生文档冻结/漂移检测 ===\n")
    print(f"  扫描 {len(md_files)} 份 _process/*.md")

    live_docs = []
    for p in md_files:
        text = p.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if not fm:
            issues.append(f"{p.name}: 缺 frontmatter")
            continue
        st = fm.get("snapshot_type")
        if st == "historical_review":
            if not fm.get("frozen_at"):
                issues.append(f"{p.name}: historical_review 缺 frozen_at")
        elif st == "live":
            if not fm.get("last_validated"):
                issues.append(f"{p.name}: live 缺 last_validated")
            else:
                live_docs.append(p)
        else:
            issues.append(f"{p.name}: snapshot_type 必须是 historical_review|live (实际: {st})")

    # 数值漂移：empty_tables_explanation.md
    if MANIFEST.exists():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = {}
        for entry in man.get("nine_tables", []):
            stem = Path(entry["path"]).stem  # 01_object_type
            rows[stem] = entry.get("data_rows", 0)
        target = PROCESS / "empty_tables_explanation.md"
        if target.exists() and target in live_docs:
            text = target.read_text(encoding="utf-8")
            for stem, expect in rows.items():
                # stem 形如 01_object_type；在文档表格中查找该 stem 行下的数字
                pat = re.compile(rf"\| *{re.escape(stem)} *\| *(\d+) *\|")
                m = pat.search(text)
                if m:
                    actual = int(m.group(1))
                    if actual != expect:
                        issues.append(
                            f"empty_tables_explanation.md 漂移: {stem}={actual} vs manifest={expect}"
                        )
                else:
                    issues.append(f"empty_tables_explanation.md 缺 {stem} 行声明")

    if issues:
        print(f"\n  ❌ {len(issues)} 项问题:")
        for x in issues:
            print(f"    - {x}")
        return 1
    print(f"\n  ✅ 派生文档全部带合法 frontmatter；live 文档与 manifest 数值一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())

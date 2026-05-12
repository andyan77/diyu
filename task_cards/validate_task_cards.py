#!/usr/bin/env python3
"""
task_cards 元校验器 —— CI 首道门禁

校验项：
  C1  每张 KS-*.md 含合法 YAML frontmatter
  C2  11 节齐全且顺序正确
  C3  task_id 与文件名一致
  C4  depends_on 引用的卡都存在
  C5  DAG 无环
  C6  S0-S13 每个 gate 都有 ≥1 张承载卡
  C7  仅 phase=S0 的卡允许 writes_clean_output: true
  C8  dag.csv 与各卡 frontmatter 字段一致
  C9  plan_sections 至少 1 项且引用的 §x 在 plan 中真实存在
  C10 status ∈ {not_started, in_progress, blocked, done}
  C11 写边界自检：files_touched / artifacts / 正文中出现 `clean_output/<path>` 写入
      意图，必须与 writes_clean_output 一致；非 S0 phase 卡禁止任何 clean_output 写入

退出码 0 = 全绿；非 0 = 至少一项失败。
不依赖 LLM；纯确定性逻辑。
"""
from __future__ import annotations
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PLAN_PATH = ROOT.parent / "knowledge_serving_plan_v1.1.md"
DAG_CSV = ROOT / "dag.csv"

REQUIRED_SECTIONS = [
    r"^##\s*1\.\s*任务目标",
    r"^##\s*2\.\s*前置依赖",
    r"^##\s*3\.\s*输入契约",
    r"^##\s*4\.\s*执行步骤",
    r"^##\s*5\.\s*执行交付",
    r"^##\s*6\.\s*对抗性",
    r"^##\s*7\.\s*治理语义一致性",
    r"^##\s*8\.\s*CI\s*门禁",
    r"^##\s*9\.\s*CD",
    r"^##\s*10\.\s*独立审查员",
    r"^##\s*11\.\s*DoD|^##\s*11\.\s*完成定义",
]

VALID_S_GATES = {f"S{i}" for i in range(0, 14)}
VALID_PHASES = {
    "S0", "Schema", "Compiler", "Policy", "Retrieval",
    "Vector", "Dify-ECS", "CD", "Production-Readiness",
}
VALID_STATUS = {"not_started", "in_progress", "blocked", "done"}

errors: list[str] = []


def fail(card: str, msg: str) -> None:
    errors.append(f"[{card}] {msg}")


def parse_frontmatter(text: str) -> dict | None:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    fm: dict = {}
    current_key = None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            fm.setdefault(current_key, []).append(line[4:].strip())
            continue
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            current_key = k
            if v == "":
                fm[k] = []
            elif v.startswith("["):
                fm[k] = [x.strip() for x in v.strip("[]").split(",") if x.strip()]
            elif v.lower() in ("true", "false"):
                fm[k] = v.lower() == "true"
            else:
                fm[k] = v
    return fm


def load_plan_sections() -> set[str]:
    """
    Build a set of canonical section keys from the plan.

    Recognized forms in the plan:
      ## 0. 定位                 → "0"
      ## 3.1 pack_view           → "3.1"
      # 附件 A：...              → "A"
      ## A1. ...                 → "A1"
      ## A2.4 ...                → "A2.4"
      ## B Phase 0 ...           → "B" (also "B Phase0" composite)

    A card frontmatter may reference forms like:
      §3.1, §12 S0, §A2.1, §B Phase3
    For matching, we strip the leading §, take the first whitespace-separated token,
    and require that token (or its prefix up to the first dot-or-digit boundary)
    appears in the section set.
    """
    if not PLAN_PATH.exists():
        return set()
    txt = PLAN_PATH.read_text(encoding="utf-8")
    secs: set[str] = set()
    # numeric headings at any depth: "## 3. ...", "### 3.1 ...", "#### 3.1.2 ..."
    for m in re.finditer(r"^#{2,6}\s+(\d+(?:\.\d+)*)", txt, re.MULTILINE):
        secs.add(m.group(1))
    # appendix H1: "# 附件 A：..." / "# 附件 B：..."
    for m in re.finditer(r"^#\s+附件\s+([A-Z])", txt, re.MULTILINE):
        secs.add(m.group(1))
    # appendix subsections at any depth: "## A1.", "### A2.4 ..."
    for m in re.finditer(r"^#{2,6}\s+([A-Z]\d+(?:\.\d+)*)", txt, re.MULTILINE):
        secs.add(m.group(1))
    # numbered list items under appendix sections: "1. ...", "2. ..."
    # Build A2.1, A2.2 etc by scanning numbered items inside each "## A<n>." block.
    appendix_blocks = re.split(r"^##\s+([A-Z]\d+(?:\.\d+)*)\.?\s", txt, flags=re.MULTILINE)
    for i in range(1, len(appendix_blocks), 2):
        prefix = appendix_blocks[i]
        body = appendix_blocks[i + 1] if i + 1 < len(appendix_blocks) else ""
        for m in re.finditer(r"^(\d+)\.\s", body, re.MULTILINE):
            secs.add(f"{prefix}.{m.group(1)}")
    # explicit §x references in body
    secs.update(s.lstrip("§") for s in re.findall(r"§[\w\.]+", txt))
    return secs


def section_token(ref: str) -> str:
    """
    Normalize a card's plan_section reference into a token comparable against
    the section set produced by load_plan_sections().
      "§3.1"       -> "3.1"
      "§12 S0"     -> "12"
      "§A2.1"      -> "A2.1"
      "§B Phase3"  -> "B"
    """
    s = ref.strip().lstrip("§").strip()
    # take leading token = letters/digits/dots before first space
    m = re.match(r"([A-Za-z0-9\.]+)", s)
    return m.group(1) if m else s


def main() -> int:
    cards = sorted(ROOT.glob("KS-*.md"))
    if not cards:
        print("ERROR: no KS-*.md found")
        return 2

    fm_by_id: dict[str, dict] = {}
    plan_secs = load_plan_sections()

    # C1-C3, C10
    for path in cards:
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if not fm:
            fail(path.name, "C1 missing/invalid YAML frontmatter")
            continue
        task_id = fm.get("task_id", "")
        if not task_id:
            fail(path.name, "C1 missing task_id")
            continue
        # C3
        if path.stem != task_id:
            fail(task_id, f"C3 filename {path.stem} != task_id {task_id}")
        # C2 sections
        for pat in REQUIRED_SECTIONS:
            if not re.search(pat, text, re.MULTILINE):
                fail(task_id, f"C2 missing section matching: {pat}")
        # C10
        st = fm.get("status", "")
        if st not in VALID_STATUS:
            fail(task_id, f"C10 invalid status={st!r}")
        # phase
        ph = fm.get("phase", "")
        if ph not in VALID_PHASES:
            fail(task_id, f"invalid phase={ph!r}")
        # C7
        if fm.get("writes_clean_output", False) and ph != "S0":
            fail(task_id, "C7 writes_clean_output=true but phase != S0")
        # C9
        ps = fm.get("plan_sections", [])
        if not ps:
            fail(task_id, "C9 plan_sections empty")
        else:
            for p in ps:
                p_clean = p.strip("\"' ")
                tok = section_token(p_clean)
                if plan_secs and tok not in plan_secs:
                    # accept prefix fallback: §3.1 ok if §3 exists; §A2.4 ok if A2 exists
                    prefix = re.match(r"([A-Z]?\d+)", tok)
                    if not (prefix and prefix.group(1) in plan_secs):
                        fail(task_id, f"C9 plan_section {p_clean!r} (token={tok!r}) not found in plan")
        # s_gates
        sg = fm.get("s_gates", [])
        for g in sg:
            g_clean = g.strip("\"' ")
            if g_clean and g_clean not in VALID_S_GATES:
                fail(task_id, f"invalid s_gate={g_clean!r}")
        fm_by_id[task_id] = fm

    # C11 clean_output write-intent scan
    # If the card declares writes_clean_output=false but mentions a clean_output/
    # path in files_touched / artifacts / body, that is a contradiction.
    # If the phase is not S0, ANY clean_output write reference (other than read-only
    # mentions like "git diff clean_output/" or "do not write") is a violation.
    READ_ONLY_HINTS = (
        "git diff", "git status", "git log", "ls clean_output", "wc -l",
        "grep ", "find clean_output", "read", "禁止", "不得", "不写",
        "0 写", "0 改动", "0 命中", "不改", "拒绝",
    )
    for path in cards:
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text) or {}
        tid = fm.get("task_id", path.stem)
        phase = fm.get("phase", "")
        declared = bool(fm.get("writes_clean_output", False))

        # Combine machine-readable fields
        co_in_fields = []
        for field in ("files_touched", "artifacts"):
            for item in fm.get(field, []):
                if "clean_output/" in str(item):
                    co_in_fields.append((field, str(item)))

        # Scan body lines that look like write intent.
        # Heuristic: a line that contains "clean_output/<path>" AND a write verb
        # (写 / 落 / 输出 / 创建 / 修改 / append / insert / overwrite / 灌 / 合入)
        # OR appears in 执行交付 (§5) row.
        body_writes = []
        in_section5 = False
        for line in text.splitlines():
            if re.match(r"^##\s*5\.\s*执行交付", line):
                in_section5 = True
                continue
            if in_section5 and re.match(r"^##\s*\d+\.", line):
                in_section5 = False
            if "clean_output/" not in line:
                continue
            # skip lines that are clearly read-only / prohibitive
            stripped = line.strip().lstrip("|").lstrip("-").strip()
            if any(h in stripped for h in READ_ONLY_HINTS):
                continue
            # treat §5 table rows as write intent
            write_verbs = ("写", "落", "输出", "创建", "新增", "修改", "合入", "灌",
                           "append", "insert", "overwrite", "Write", "edit", "update")
            if in_section5 or any(v in line for v in write_verbs):
                body_writes.append(line.strip()[:120])

        all_writes = co_in_fields + [("body", w) for w in body_writes]

        if all_writes and not declared:
            for kind, sample in all_writes[:3]:
                fail(tid, f"C11 declares writes_clean_output=false but {kind} writes to clean_output: {sample!r}")
        if all_writes and phase != "S0":
            for kind, sample in all_writes[:3]:
                fail(tid, f"C11 phase={phase} (non-S0) but {kind} writes to clean_output: {sample!r}")

    # C4 + C5
    for tid, fm in fm_by_id.items():
        for dep in fm.get("depends_on", []):
            dep = dep.strip("\"' ")
            if dep and dep not in fm_by_id:
                fail(tid, f"C4 depends_on references unknown card: {dep}")

    # C5 DAG cycle detection (Kahn)
    indeg = {tid: 0 for tid in fm_by_id}
    graph: dict[str, list[str]] = {tid: [] for tid in fm_by_id}
    for tid, fm in fm_by_id.items():
        for dep in fm.get("depends_on", []):
            dep = dep.strip("\"' ")
            if dep in fm_by_id:
                graph[dep].append(tid)
                indeg[tid] += 1
    queue = [t for t, d in indeg.items() if d == 0]
    visited = 0
    while queue:
        t = queue.pop()
        visited += 1
        for n in graph[t]:
            indeg[n] -= 1
            if indeg[n] == 0:
                queue.append(n)
    if visited != len(fm_by_id):
        errors.append(f"[GLOBAL] C5 DAG cycle detected (visited {visited}/{len(fm_by_id)})")

    # C6 every S gate covered
    covered: set[str] = set()
    for fm in fm_by_id.values():
        for g in fm.get("s_gates", []):
            covered.add(g.strip("\"' "))
    for g in VALID_S_GATES:
        if g not in covered:
            errors.append(f"[GLOBAL] C6 gate {g} not covered by any card")

    # C8 dag.csv consistency
    if not DAG_CSV.exists():
        errors.append("[GLOBAL] C8 dag.csv missing")
    else:
        with DAG_CSV.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            csv_ids = set()
            for row in reader:
                tid = row["task_id"]
                csv_ids.add(tid)
                if tid not in fm_by_id:
                    errors.append(f"[GLOBAL] C8 dag.csv has {tid} but no card file")
                    continue
                fm = fm_by_id[tid]
                csv_deps = set(d for d in row["depends_on"].split(";") if d)
                fm_deps = set(d.strip("\"' ") for d in fm.get("depends_on", []) if d.strip("\"' "))
                if csv_deps != fm_deps:
                    fail(tid, f"C8 depends_on mismatch: csv={csv_deps} fm={fm_deps}")
                if row["phase"] != fm.get("phase"):
                    fail(tid, f"C8 phase mismatch: csv={row['phase']} fm={fm.get('phase')}")
                csv_wco = row["writes_clean_output"].lower() == "true"
                if csv_wco != bool(fm.get("writes_clean_output", False)):
                    fail(tid, "C8 writes_clean_output mismatch")
                # 新增 / added: status / wave / s_gates / plan_sections 一致性
                # 防止"卡 frontmatter 标 done 但 dag.csv 仍 not_started"的状态账本分裂
                if row["status"] != fm.get("status"):
                    fail(tid, f"C8 status mismatch: csv={row['status']!r} fm={fm.get('status')!r}")
                csv_wave = row["wave"]
                fm_wave = fm.get("wave")
                if csv_wave != (str(fm_wave) if fm_wave is not None else ""):
                    fail(tid, f"C8 wave mismatch: csv={csv_wave!r} fm={fm_wave!r}")
                csv_gates = set(g for g in row["s_gates"].split(";") if g)
                fm_gates = set(str(g).strip("\"' ") for g in (fm.get("s_gates") or []))
                if csv_gates != fm_gates:
                    fail(tid, f"C8 s_gates mismatch: csv={sorted(csv_gates)} fm={sorted(fm_gates)}")
                csv_plan = set(s.strip().strip('"') for s in row["plan_sections"].split(";") if s.strip())
                fm_plan = set(str(s).strip().strip('"') for s in (fm.get("plan_sections") or []))
                if csv_plan != fm_plan:
                    fail(tid, f"C8 plan_sections mismatch: csv={sorted(csv_plan)} fm={sorted(fm_plan)}")
            for tid in fm_by_id:
                if tid not in csv_ids:
                    fail(tid, "C8 card exists but missing from dag.csv")

    # Report
    if errors:
        print(f"VALIDATION FAILED: {len(errors)} issue(s)\n")
        for e in errors:
            print("  " + e)
        return 1
    print(f"VALIDATION PASS: {len(fm_by_id)} cards, DAG closed, S0-S13 covered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

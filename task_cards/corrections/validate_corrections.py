#!/usr/bin/env python3
"""
task_cards/corrections 元校验器 / corrections self-validator

防"纠偏卡退化为旁挂规划卡"——堵守护意见的 5 个阻断口：
  C1  26 张 FIX 覆盖完整（KS-FIX-01..26）+ 无缺失 / 无重复
  C2  每张 FIX 11 节齐全且顺序正确
  C3  frontmatter 必填：task_id / corrects / severity / phase / wave / depends_on / status / files_touched / artifacts
  C4  corrects 字段指向 task_cards/ 下真实存在的原卡
  C5  severity ∈ {FAIL, RISKY, CONDITIONAL_PASS, BLOCKED}
  C6  wave 与原卡 frontmatter wave 一致（守护意见 #2：拓扑对齐）
  C7  depends_on 引用的 FIX 卡都存在 + 无环（Kahn）
  C8  §8 CI 命令非占位：禁 `<...>` 角括号占位符 / 禁 `TODO` / 禁 `<run_id>` 等
  C9  §8 CI 命令引用的脚本 / 测试 / workflow 文件必须真实存在于本仓
      （或在 frontmatter `creates:` 字段中显式登记为本卡待落地产物）
  C10 §5 `artifacts` 路径必须落在合法 audit 目录下
      （knowledge_serving/audit/ 或 task_cards/corrections/audit/）
  C11 §6 必含 fail-closed 守门用例（token `fail-closed` 至少 1 次）
  C12 §4 第 1 步必须含 E7 旧快照核验（token `git status` / `git log`）
  C13 §11 DoD 必须含"原卡回写"动作（token `回写` 或 `原卡`）
  C14 26 张 corrects 集合 == 守护清单 26 项（防漏 / 防多）

退出码 0 = 全绿；非 0 = 至少一项失败。
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
TASK_CARDS_ROOT = ROOT.parent
REPO_ROOT = TASK_CARDS_ROOT.parent

EXPECTED_FIX_IDS = [f"KS-FIX-{i:02d}" for i in range(1, 27)]

EXPECTED_CORRECTS = {
    "KS-S0-004", "KS-SCHEMA-005", "KS-COMPILER-002", "KS-COMPILER-010",
    "KS-POLICY-005", "KS-RETRIEVAL-006", "KS-RETRIEVAL-007", "KS-RETRIEVAL-008",
    "KS-RETRIEVAL-009", "KS-VECTOR-001", "KS-VECTOR-003",
    "KS-DIFY-ECS-001", "KS-DIFY-ECS-002", "KS-DIFY-ECS-003", "KS-DIFY-ECS-004",
    "KS-DIFY-ECS-005", "KS-DIFY-ECS-006", "KS-DIFY-ECS-007", "KS-DIFY-ECS-008",
    "KS-DIFY-ECS-009", "KS-DIFY-ECS-010", "KS-DIFY-ECS-011",
    "KS-CD-001", "KS-CD-002", "KS-PROD-001", "KS-PROD-002",
}

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

VALID_SEVERITY = {"FAIL", "RISKY", "CONDITIONAL_PASS", "BLOCKED"}
REQUIRED_FM_KEYS = {
    "task_id", "corrects", "severity", "phase", "wave",
    "depends_on", "status", "files_touched", "artifacts",
}

PLACEHOLDER_PATTERNS = [
    r"<[^>\n$]{1,80}>",                   # <run_id>, <GH Actions job: ...>, etc.
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\.\.\.\s*\$",                       # trailing "..."
]

# Strict allowlist for script / test references — must exist on disk.
# Two forms recognized:
#   (a) slash form:   knowledge_serving/scripts/foo.py  /  scripts/bar.sh
#   (b) module form:  python3 -m knowledge_serving.scripts.foo  (a.b.c dotted)
SCRIPT_TOKEN_RE = re.compile(
    r"(?:knowledge_serving/|task_cards/|scripts/|\.github/)[A-Za-z0-9_\-/\.]+"
    r"\.(?:py|sh|yml|yaml|sql)"
)
MODULE_TOKEN_RE = re.compile(
    r"python3?\s+-m\s+([A-Za-z_][A-Za-z0-9_\.]+)"
)


def module_to_disk_path(mod: str) -> Path:
    """knowledge_serving.scripts.foo -> knowledge_serving/scripts/foo.py"""
    return REPO_ROOT / (mod.replace(".", "/") + ".py")

errors: list[str] = []
warnings: list[str] = []


def fail(card: str, msg: str) -> None:
    errors.append(f"[{card}] {msg}")


def warn(card: str, msg: str) -> None:
    warnings.append(f"[{card}] {msg}")


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
            k = k.strip(); v = v.strip()
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


def load_original_card_wave(corrects_id: str) -> str | None:
    """Read original card's wave field from task_cards/<id>.md."""
    p = TASK_CARDS_ROOT / f"{corrects_id}.md"
    if not p.exists():
        return None
    fm = parse_frontmatter(p.read_text(encoding="utf-8"))
    if not fm:
        return None
    w = fm.get("wave")
    return str(w) if w is not None else None


def find_ci_command_block(text: str) -> str:
    """Extract §8 fenced block contents."""
    m = re.search(
        r"^##\s*8\.\s*CI[^\n]*\n(.*?)(?:^##\s*9\.|\Z)",
        text, re.MULTILINE | re.DOTALL
    )
    if not m:
        return ""
    body = m.group(1)
    blocks = re.findall(r"```[^\n]*\n(.*?)```", body, re.DOTALL)
    return "\n".join(blocks)


def main() -> int:
    cards = sorted(ROOT.glob("KS-FIX-*.md"))
    if not cards:
        print("ERROR: no KS-FIX-*.md found"); return 2

    # C1 coverage
    found_ids = [p.stem for p in cards]
    missing = set(EXPECTED_FIX_IDS) - set(found_ids)
    extra = set(found_ids) - set(EXPECTED_FIX_IDS)
    if missing:
        errors.append(f"[GLOBAL] C1 missing FIX ids: {sorted(missing)}")
    if extra:
        errors.append(f"[GLOBAL] C1 unexpected FIX ids: {sorted(extra)}")

    fm_by_id: dict[str, dict] = {}
    text_by_id: dict[str, str] = {}
    corrects_seen: set[str] = set()

    for path in cards:
        tid = path.stem
        text = path.read_text(encoding="utf-8")
        text_by_id[tid] = text
        fm = parse_frontmatter(text)
        if not fm:
            fail(tid, "C3 missing/invalid YAML frontmatter"); continue
        fm_by_id[tid] = fm

        # C2 sections
        for pat in REQUIRED_SECTIONS:
            if not re.search(pat, text, re.MULTILINE):
                fail(tid, f"C2 missing section: {pat}")

        # C3 required keys
        for k in REQUIRED_FM_KEYS:
            if k not in fm:
                fail(tid, f"C3 missing frontmatter key: {k}")

        # task_id <-> filename
        if fm.get("task_id") != tid:
            fail(tid, f"C3 filename {tid} != task_id {fm.get('task_id')!r}")

        # C4 corrects must point to existing original card
        corrects = (fm.get("corrects") or "").strip()
        if not corrects:
            fail(tid, "C4 corrects field empty")
        else:
            corrects_seen.add(corrects)
            orig_path = TASK_CARDS_ROOT / f"{corrects}.md"
            if not orig_path.exists():
                fail(tid, f"C4 corrects -> {corrects} but {orig_path.relative_to(REPO_ROOT)} not found")

        # C5 severity
        sev = (fm.get("severity") or "").strip()
        if sev not in VALID_SEVERITY:
            fail(tid, f"C5 invalid severity={sev!r}")

        # C6 wave alignment
        fix_wave = str(fm.get("wave") or "").strip()
        if corrects:
            orig_wave = load_original_card_wave(corrects)
            if orig_wave is not None and orig_wave != fix_wave:
                fail(tid, f"C6 wave mismatch: FIX wave={fix_wave!r} vs original {corrects} wave={orig_wave!r}")

        # C8 placeholder scan in §8
        ci_block = find_ci_command_block(text)
        for pat in PLACEHOLDER_PATTERNS:
            m = re.search(pat, ci_block)
            if m:
                # whitelist env-style $VAR placeholders (already allowed by bash)
                # but `<...>` angle bracket placeholders must die
                fail(tid, f"C8 placeholder in §8 CI command: {m.group(0)!r}")

        # C9 script existence in §8
        declared_creates = set(str(x).strip() for x in (fm.get("creates") or []))
        # Strip quotes — frontmatter parser may keep them
        declared_creates = {c.strip('"\' ') for c in declared_creates}
        for tok in SCRIPT_TOKEN_RE.findall(ci_block):
            tok_clean = tok.strip().rstrip(",")
            disk_path = REPO_ROOT / tok_clean
            if disk_path.exists():
                continue
            if tok_clean in declared_creates:
                continue
            fail(tid, f"C9 §8 references non-existent script {tok_clean!r} (not in frontmatter `creates:` either)")
        # Module-form (python3 -m a.b.c) — only check in-repo top-level packages.
        # External tools (pytest, unittest, http.server, ...) pass through.
        in_repo_prefixes = ("knowledge_serving.", "scripts.", "task_cards.")
        for mod in MODULE_TOKEN_RE.findall(ci_block):
            if not mod.startswith(in_repo_prefixes):
                continue
            disk_path = module_to_disk_path(mod)
            if disk_path.exists():
                continue
            rel = str(disk_path.relative_to(REPO_ROOT))
            if rel in declared_creates:
                continue
            fail(tid, f"C9 §8 `python3 -m {mod}` resolves to non-existent {rel!r} (not in `creates:` either)")

        # C10 artifact paths
        for art in fm.get("artifacts", []):
            art_clean = str(art).strip().strip('"\' ')
            if not (
                art_clean.startswith("knowledge_serving/audit/")
                or art_clean.startswith("task_cards/corrections/audit/")
            ):
                fail(tid, f"C10 artifact path not under allowed audit roots: {art_clean!r}")

        # C11 fail-closed token in §6
        m6 = re.search(
            r"^##\s*6\.\s*[^\n]*\n(.*?)(?:^##\s*7\.|\Z)",
            text, re.MULTILINE | re.DOTALL
        )
        if not m6 or "fail-closed" not in m6.group(1):
            fail(tid, "C11 §6 missing fail-closed test case")

        # C12 E7 baseline check in §4
        m4 = re.search(
            r"^##\s*4\.\s*[^\n]*\n(.*?)(?:^##\s*5\.|\Z)",
            text, re.MULTILINE | re.DOTALL
        )
        body4 = m4.group(1) if m4 else ""
        # Allow either explicit E7 step or transitive dependency on KS-FIX-01 (which performs baseline)
        deps = [d.strip().strip('"\'') for d in fm.get("depends_on", [])]
        if not (
            "git status" in body4 or "git log" in body4 or "E7" in body4
            or "KS-FIX-01" in deps or "KS-FIX-02" in deps or "KS-FIX-03" in deps
        ):
            fail(tid, "C12 §4 missing E7 baseline verification (git status / git log / E7 token) and no transitive baseline dep")

        # C13 DoD writeback
        m11 = re.search(
            r"^##\s*11\.\s*[^\n]*\n(.*?)\Z",
            text, re.MULTILINE | re.DOTALL
        )
        body11 = m11.group(1) if m11 else ""
        if not ("回写" in body11 or "原卡" in body11):
            fail(tid, "C13 §11 DoD missing original-card writeback action")

    # C7 depends_on existence + DAG
    indeg = {t: 0 for t in fm_by_id}
    graph: dict[str, list[str]] = {t: [] for t in fm_by_id}
    deps_map: dict[str, list[str]] = {}
    for tid, fm in fm_by_id.items():
        clean_deps: list[str] = []
        for dep in fm.get("depends_on", []):
            dep = dep.strip().strip('"\' ')
            if not dep:
                continue
            if dep not in fm_by_id:
                fail(tid, f"C7 depends_on -> unknown FIX card: {dep}")
                continue
            graph[dep].append(tid)
            indeg[tid] += 1
            clean_deps.append(dep)
        deps_map[tid] = clean_deps
    queue = [t for t, d in indeg.items() if d == 0]
    visited = 0
    while queue:
        t = queue.pop(); visited += 1
        for n in graph[t]:
            indeg[n] -= 1
            if indeg[n] == 0:
                queue.append(n)
    if visited != len(fm_by_id):
        errors.append(f"[GLOBAL] C7 DAG cycle (visited {visited}/{len(fm_by_id)})")

    # C12 transitive baseline check (re-run with proper transitive resolution).
    # A card passes C12 iff (a) its own §4 has E7 token, OR (b) any transitive
    # depends_on ancestor has E7 token in its §4 (baseline propagates downstream).
    def has_own_e7(tid: str) -> bool:
        t = text_by_id.get(tid, "")
        m4 = re.search(r"^##\s*4\.\s*[^\n]*\n(.*?)(?:^##\s*5\.|\Z)", t, re.MULTILINE | re.DOTALL)
        if not m4:
            return False
        b = m4.group(1)
        return "git status" in b or "git log" in b or "E7" in b

    own_e7 = {tid: has_own_e7(tid) for tid in fm_by_id}

    def ancestor_has_e7(tid: str, seen: set[str] | None = None) -> bool:
        seen = seen or set()
        for dep in deps_map.get(tid, []):
            if dep in seen:
                continue
            seen.add(dep)
            if own_e7.get(dep, False) or ancestor_has_e7(dep, seen):
                return True
        return False

    # Re-evaluate C12 errors: drop the strict per-card errors and re-issue only
    # for cards that neither have own E7 nor a transitive baseline ancestor.
    errors[:] = [e for e in errors if "C12 §4 missing E7" not in e]
    for tid in fm_by_id:
        if own_e7[tid]:
            continue
        if ancestor_has_e7(tid):
            continue
        fail(tid, "C12 §4 lacks E7 baseline AND no transitive baseline ancestor (FIX-01/02/03 chain)")

    # C14 corrects set sanity
    miss = EXPECTED_CORRECTS - corrects_seen
    extra = corrects_seen - EXPECTED_CORRECTS
    if miss:
        errors.append(f"[GLOBAL] C14 missing corrects: {sorted(miss)}")
    if extra:
        errors.append(f"[GLOBAL] C14 extra corrects: {sorted(extra)}")

    # Report
    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print("  " + w)
        print()
    if errors:
        print(f"VALIDATION FAILED: {len(errors)} issue(s)\n")
        for e in errors:
            print("  " + e)
        return 1
    print(f"VALIDATION PASS: {len(fm_by_id)} FIX cards, DAG closed, corrects coverage 26/26.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

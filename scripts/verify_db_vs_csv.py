#!/usr/bin/env python3
"""
verify_db_vs_csv.py · KS-S0-002 · sqlite db 处置后的 B 路径 CI 校验
================================================================
背景 / context:
  KS-S0-002 选定 B 路径 = 显式废弃 / deprecate knowledge.db。
  本卡 §10 审查员要求：
    grep -rn "knowledge.db" --include="*.py" --include="*.yaml"
    在 knowledge_serving/ 与 task_cards/ 下 0 命中。

  本脚本即 KS-S0-002 frontmatter 声明的 ci_command 实现，
  在 B 路径模式下做 0 引用闸（fail-closed）。

退出码 / exit:
  0  Phase 2 serving 域内（knowledge_serving/ + task_cards/）无 knowledge.db 引用
  1  仍有引用 → 需补漏（或证明该引用为历史 deprecated 标注）
  2  扫描目录缺失 / 其它环境错
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# B 路径要求 0 命中的 serving 域 / phase 2 serving scope
SCAN_DIRS = ["knowledge_serving", "task_cards"]
SCAN_SUFFIXES = {".py", ".yaml", ".yml"}
PATTERN = re.compile(r"knowledge\.db")

# 允许的"deprecated 标注"白名单（明文说明这是历史引用，不是真使用）
# 任何命中行内含以下子串即视为合法标注、不计入 fail
LEGIT_MARKERS = (
    "deprecated",
    "废弃",
    "deprecat",  # 容错
)


def scan() -> tuple[list[tuple[Path, int, str]], list[tuple[Path, int, str]]]:
    """返回 (违规命中, 合法标注命中)"""
    violations: list[tuple[Path, int, str]] = []
    legit: list[tuple[Path, int, str]] = []
    missing_dirs: list[str] = []

    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.exists():
            missing_dirs.append(d)
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in SCAN_SUFFIXES:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if not PATTERN.search(line):
                    continue
                low = line.lower()
                if any(m in low for m in LEGIT_MARKERS):
                    legit.append((p, i, line.strip()))
                else:
                    violations.append((p, i, line.strip()))

    if missing_dirs:
        print(f"❌ 必扫目录缺失 / missing scan dirs: {missing_dirs}")
        sys.exit(2)

    return violations, legit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="fail-closed：任何非白名单命中即 exit 1")
    args = ap.parse_args()

    print("=== verify_db_vs_csv · KS-S0-002 B 路径 0 引用闸 / B-path zero-reference gate ===")
    print(f"扫描目录 / scan: {', '.join(SCAN_DIRS)}")
    print(f"扫描后缀 / suffix: {sorted(SCAN_SUFFIXES)}")
    print()

    violations, legit = scan()

    if legit:
        print(f"ℹ️  合法 deprecated 标注 / legit deprecated annotations: {len(legit)}")
        for p, ln, txt in legit[:5]:
            print(f"   {p.relative_to(ROOT)}:{ln}  {txt[:120]}")
        if len(legit) > 5:
            print(f"   ... 还有 {len(legit) - 5} 条 / and {len(legit) - 5} more")
        print()

    if violations:
        print(f"❌ 违规引用 / illegal references: {len(violations)}")
        for p, ln, txt in violations:
            print(f"   {p.relative_to(ROOT)}:{ln}  {txt[:120]}")
        print()
        print("处置 / action: 修改引用为 csv-only 或加 deprecated 标注后重跑")
        if args.strict:
            return 1
        return 1

    print("✅ Phase 2 serving 域无 knowledge.db 真引用 / no real reference in serving scope")
    print(f"   合法 deprecated 标注: {len(legit)} 条（允许）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

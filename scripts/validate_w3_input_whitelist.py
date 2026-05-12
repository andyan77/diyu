#!/usr/bin/env python3
"""validate_w3_input_whitelist.py · W3+ serving 输入白名单守门器

裁决来源 / decision source:
  task_cards/README.md §7.1 "W3+ serving 输入白名单"（faye, 2026-05-12）

本脚本的三件事 / what this script checks:
  C1. 11 张 W3 卡（KS-COMPILER-001/002/004..012）正文必须含禁止读取 ECS PG /
      备份 / 历史临时目录的硬约束声明
  C2. 11 张 W3 卡 frontmatter `files_touched` 字段不得包含禁止路径
      （`clean_output/`、`/data/clean_output.bak_`、`/tmp/itr`、`knowledge.` PG schema）
  C3. task_cards/README.md 必须存在 "## 7.1 W3+ serving 输入白名单" 章节

退出码 / exit:
  0  全部 PASS
  1  有违规
  2  脚本内部异常 / fail-closed
"""
from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASK_CARDS = REPO_ROOT / "task_cards"
README = TASK_CARDS / "README.md"

W3_CARDS = [
    f"KS-COMPILER-{n:03d}" for n in [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12]
]

# C1：W3 卡正文必须含的硬约束关键短语
REQUIRED_CONSTRAINT_TOKENS = [
    "W3+ 输入白名单硬约束",
    "禁止读取 ECS PG",
    "knowledge_serving/schema/",
]

# C2：files_touched 禁止出现的路径片段
FORBIDDEN_PATH_FRAGMENTS = [
    "clean_output/",            # 真源不得被 W3 卡 touched（W3 是派生层）
    "/data/clean_output.bak_",  # ECS 备份
    "/tmp/itr",                 # 历史临时目录
    "knowledge.",               # PG schema 形如 knowledge.brand_tone
]

# C3：README 必须存在的章节标题
REQUIRED_README_SECTION = "## 7.1 W3+ serving 输入白名单"


def parse_files_touched(card_text: str) -> list[str]:
    """从 frontmatter 提取 files_touched 列表（容忍 yaml 简单格式）"""
    m = re.search(r"^---\s*\n(.*?)\n---", card_text, re.DOTALL | re.MULTILINE)
    if not m:
        return []
    fm = m.group(1)
    paths: list[str] = []
    in_block = False
    for line in fm.splitlines():
        if re.match(r"^files_touched:", line):
            in_block = True
            continue
        if in_block:
            if re.match(r"^[a-z_]+:", line):  # 下一个 frontmatter key
                break
            m2 = re.match(r"^\s*-\s*(.+?)\s*$", line)
            if m2:
                paths.append(m2.group(1).strip().strip("\"'"))
    return paths


def check_card(card_id: str) -> list[str]:
    errors: list[str] = []
    p = TASK_CARDS / f"{card_id}.md"
    if not p.exists():
        return [f"[MISS] 卡文件不存在 / card missing: {p}"]
    text = p.read_text(encoding="utf-8")

    # C1 正文约束声明
    for tok in REQUIRED_CONSTRAINT_TOKENS:
        if tok not in text:
            errors.append(
                f"[C1] {card_id} 正文缺约束 token / missing constraint token: {tok!r}"
            )

    # C2 files_touched 禁止路径
    paths = parse_files_touched(text)
    for path in paths:
        for forbidden in FORBIDDEN_PATH_FRAGMENTS:
            if forbidden in path:
                errors.append(
                    f"[C2] {card_id} files_touched 含禁止路径片段 / forbidden fragment "
                    f"{forbidden!r} in {path!r}"
                )

    return errors


def check_readme() -> list[str]:
    errors: list[str] = []
    if not README.exists():
        return [f"[MISS] README 不存在 / missing: {README}"]
    text = README.read_text(encoding="utf-8")
    if REQUIRED_README_SECTION not in text:
        errors.append(
            f"[C3] README 缺章节 / missing section: {REQUIRED_README_SECTION!r}"
        )
    return errors


def main() -> int:
    try:
        all_errors: list[str] = []
        for cid in W3_CARDS:
            all_errors.extend(check_card(cid))
        all_errors.extend(check_readme())

        if all_errors:
            print(f"[FAIL] W3+ 输入白名单守门 / W3+ input whitelist guard FAILED "
                  f"({len(all_errors)} 项):", file=sys.stderr)
            for e in all_errors:
                print(f"  {e}", file=sys.stderr)
            return 1

        print(f"[OK] W3+ 输入白名单守门 / W3+ input whitelist guard PASSED")
        print(f"     卡数 / cards checked: {len(W3_CARDS)}")
        print(f"     检查项 / checks: C1 (constraint tokens) + "
              f"C2 (files_touched safe) + C3 (README section)")
        return 0
    except Exception:
        print("[FATAL] validate_w3_input_whitelist 内部异常:", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

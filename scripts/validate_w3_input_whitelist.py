#!/usr/bin/env python3
"""validate_w3_input_whitelist.py · W3-W14 serving 输入白名单守门器

裁决来源 / decision source:
  task_cards/README.md §7.1 "W3+ serving 输入白名单"（faye, 2026-05-12）

两层检查 / two-tier check:
  Tier-1（强约束 / hard）: 11 张 W3 编译卡（KS-COMPILER-001/002/004..012）
                          必须含约束 token 声明（"W3+ 输入白名单硬约束"等）
  Tier-2（路径守门 / path guard）: 全部 W3-W14 卡（除 W2 已收口的 ECS 对账例外）
                          frontmatter `files_touched` 不得含禁止路径片段

  C3（章节存在）: task_cards/README.md 必须存在 "## 7.1 W3+ serving 输入白名单"

例外白名单 / explicit exemptions（README §7.1 显式授权）:
  - KS-DIFY-ECS-002（已收口 · ECS PG 对账，只读）
  - KS-DIFY-ECS-003（待立 · serving views 回灌 ECS PG）

退出码 / exit:
  0  全部 PASS
  1  有违规
  2  脚本内部异常 / fail-closed
"""
from __future__ import annotations

import csv
import re
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASK_CARDS = REPO_ROOT / "task_cards"
README = TASK_CARDS / "README.md"
DAG_CSV = TASK_CARDS / "dag.csv"

# Tier-1 强约束：W3 编译卡（必须含约束 token）
TIER1_CARDS = [f"KS-COMPILER-{n:03d}" for n in [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12]]

# Tier-2 路径守门覆盖范围：W3-W14 全部波次
TIER2_WAVES = {f"W{n}" for n in range(3, 15)}

# Tier-2 例外卡：README §7.1 明文授权可读 ECS PG / 历史 PG 写
TIER2_EXEMPTIONS = {"KS-DIFY-ECS-002", "KS-DIFY-ECS-003"}

# Tier-1 卡正文必须含的约束 token
REQUIRED_CONSTRAINT_TOKENS = [
    "W3+ 输入白名单硬约束",
    "禁止读取 ECS PG",
    "README §7.1",
]

# Tier-2 files_touched 禁止出现的路径片段
FORBIDDEN_PATH_FRAGMENTS = [
    "/data/clean_output.bak_",  # ECS 备份
    "/tmp/itr",                 # 历史临时目录
    "knowledge.brand_tone",     # PG schema 表名（精确防误伤代码注释）
    "knowledge.global_knowledge",
    "knowledge.role_profile",
    "knowledge.persona",
    "knowledge.content_type",
    "knowledge.content_blueprint",
    "knowledge.compliance_rule",
    "knowledge.narrative_arc",
    "knowledge.enterprise_narrative_example",
]

# Tier-2 写入侧禁止：clean_output/ 是真源，W3-W14 卡（非 S0）禁止 touched
# （此项与 validate_task_cards.py C7 重复但口径独立）
FORBIDDEN_WRITE_PREFIXES = ["clean_output/"]

REQUIRED_README_SECTION = "## 7.1 W3+ serving 输入白名单"


def parse_files_touched(card_text: str) -> list[str]:
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
            if re.match(r"^[a-z_]+:", line):
                break
            m2 = re.match(r"^\s*-\s*(.+?)\s*$", line)
            if m2:
                paths.append(m2.group(1).strip().strip("\"'"))
    return paths


def load_post_w2_cards() -> list[tuple[str, str]]:
    """从 dag.csv 读 W3-W14 卡 (id, wave) 列表"""
    cards: list[tuple[str, str]] = []
    with DAG_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["wave"] in TIER2_WAVES:
                cards.append((row["task_id"], row["wave"]))
    return cards


def check_tier1(card_id: str) -> list[str]:
    p = TASK_CARDS / f"{card_id}.md"
    if not p.exists():
        return [f"[T1-MISS] 卡文件不存在 / card missing: {p}"]
    text = p.read_text(encoding="utf-8")
    errors = []
    for tok in REQUIRED_CONSTRAINT_TOKENS:
        if tok not in text:
            errors.append(
                f"[T1] {card_id} 正文缺约束 token / missing constraint token: {tok!r}"
            )
    return errors


def check_tier2(card_id: str) -> list[str]:
    p = TASK_CARDS / f"{card_id}.md"
    if not p.exists():
        return [f"[T2-MISS] 卡文件不存在 / card missing: {p}"]
    text = p.read_text(encoding="utf-8")
    errors = []
    paths = parse_files_touched(text)
    for path in paths:
        # 禁止路径片段
        for forbidden in FORBIDDEN_PATH_FRAGMENTS:
            if forbidden in path:
                errors.append(
                    f"[T2-PATH] {card_id} files_touched 含禁止路径片段 / "
                    f"forbidden fragment {forbidden!r} in {path!r}"
                )
        # 禁止写真源
        for forbidden in FORBIDDEN_WRITE_PREFIXES:
            if path.startswith(forbidden) or path.lstrip("./").startswith(forbidden):
                errors.append(
                    f"[T2-WRITE] {card_id} files_touched 写入真源禁区 / "
                    f"writes SSOT prefix {forbidden!r}: {path!r}"
                )
    return errors


def check_readme() -> list[str]:
    if not README.exists():
        return [f"[C3-MISS] README 不存在 / missing: {README}"]
    text = README.read_text(encoding="utf-8")
    if REQUIRED_README_SECTION not in text:
        return [f"[C3] README 缺章节 / missing section: {REQUIRED_README_SECTION!r}"]
    return []


def main() -> int:
    try:
        all_errors: list[str] = []

        # Tier-1: 11 张 W3 编译卡必含约束 token
        for cid in TIER1_CARDS:
            all_errors.extend(check_tier1(cid))

        # Tier-2: W3-W14 全部卡 files_touched 路径守门（除例外）
        post_w2 = load_post_w2_cards()
        tier2_checked = 0
        tier2_exempted = 0
        for cid, wave in post_w2:
            if cid in TIER2_EXEMPTIONS:
                tier2_exempted += 1
                continue
            tier2_checked += 1
            all_errors.extend(check_tier2(cid))

        # C3: README 章节存在
        all_errors.extend(check_readme())

        if all_errors:
            print(f"[FAIL] W3-W14 输入白名单守门 FAILED ({len(all_errors)} 项):",
                  file=sys.stderr)
            for e in all_errors:
                print(f"  {e}", file=sys.stderr)
            return 1

        print("[OK] W3-W14 输入白名单守门 PASSED")
        print(f"     Tier-1 强约束 / W3 编译卡: {len(TIER1_CARDS)} 张全过 (含约束 token)")
        print(f"     Tier-2 路径守门 / W3-W14 卡: {tier2_checked} 张全过 "
              f"(例外 {tier2_exempted} 张: {sorted(TIER2_EXEMPTIONS)})")
        print(f"     C3 README §7.1 章节存在: ✓")
        return 0
    except Exception:
        print("[FATAL] validate_w3_input_whitelist 内部异常:", file=sys.stderr)
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

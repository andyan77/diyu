#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_serving_tree.py — KS-SCHEMA-005 校验脚本 / serving tree validator.

校验 knowledge_serving/ 实际目录树是否与 knowledge_serving_plan_v1.1.md §11
+ W0/W1 已落白名单完全一致。

退出码 / exit codes:
  0 = 完全一致 / fully aligned
  1 = 缺目录 / 缺文件 / 多文件（未在 §11 也不在 W0/W1 白名单）
  2 = fail-closed（脚本内部异常 / unexpected runtime error）
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# 仓库根 / repo root（脚本位于 scripts/ 子目录）
REPO_ROOT = Path(__file__).resolve().parent.parent
SERVING = REPO_ROOT / "knowledge_serving"

# §11 期望目录 / expected subdirs
EXPECTED_DIRS = {
    "schema",
    "views",
    "control",
    "policies",
    "vector_payloads",
    "logs",
    "scripts",
    "audit",
}

# §11 期望文件（相对 knowledge_serving/ 路径）/ expected §11 files
EXPECTED_FILES_PLAN = {
    # 顶层
    "README.md",
    # schema/
    "schema/serving_views.schema.json",
    "schema/control_tables.schema.json",
    "schema/context_bundle.schema.json",
    "schema/business_brief.schema.json",
    # views/ — KS-SCHEMA-005 落空表头
    "views/pack_view.csv",
    "views/content_type_view.csv",
    "views/generation_recipe_view.csv",
    "views/play_card_view.csv",
    "views/runtime_asset_view.csv",
    "views/brand_overlay_view.csv",
    "views/evidence_view.csv",
    # control/ — KS-SCHEMA-005 落空表头
    "control/tenant_scope_registry.csv",
    "control/field_requirement_matrix.csv",
    "control/retrieval_policy_view.csv",
    "control/merge_precedence_policy.csv",
    "control/context_bundle_log.csv",
    # policies/ — 5 yaml（含 W1 已落 model_policy.yaml）
    "policies/fallback_policy.yaml",
    "policies/guardrail_policy.yaml",
    "policies/merge_precedence_policy.yaml",
    "policies/retrieval_policy.yaml",
    "policies/model_policy.yaml",
}

# W0/W1 已落白名单（不在 §11 默认骨架内，但属于派生层 canonical 真源）
EXPECTED_FILES_PRE_EXISTING = {
    "control/content_type_canonical.csv",   # W0 KS-S0-007
    "policies/qdrant_fallback.yaml",         # W0 KS-S0-006
}

# 空目录占位 / placeholder for empty subdirs（git 不跟踪空目录）
GITKEEP_DIRS = {"vector_payloads", "logs", "scripts", "audit"}
EXPECTED_GITKEEPS = {f"{d}/.gitkeep" for d in GITKEEP_DIRS}

# 全部允许文件 = §11 + W0/W1 白名单 + .gitkeep 占位
ALLOWED_FILES = EXPECTED_FILES_PLAN | EXPECTED_FILES_PRE_EXISTING | EXPECTED_GITKEEPS

# 必须存在的文件 = §11 + W0/W1 + .gitkeep 占位（缺一即 fail）
REQUIRED_FILES = ALLOWED_FILES


def main() -> int:
    errors: list[str] = []

    # 1) 根目录存在 / serving root exists
    if not SERVING.is_dir():
        errors.append(f"[MISS] knowledge_serving/ 不存在: {SERVING}")
        _report(errors)
        return 1

    # 2) 子目录齐全 / all subdirs present
    actual_dirs = {p.name for p in SERVING.iterdir() if p.is_dir()}
    missing_dirs = EXPECTED_DIRS - actual_dirs
    extra_dirs = actual_dirs - EXPECTED_DIRS
    for d in sorted(missing_dirs):
        errors.append(f"[MISS] 缺子目录 / missing dir: knowledge_serving/{d}/")
    for d in sorted(extra_dirs):
        errors.append(f"[EXTRA] 多子目录 / unexpected dir: knowledge_serving/{d}/")

    # 3) 文件清单 / file inventory（递归）
    actual_files: set[str] = set()
    for p in SERVING.rglob("*"):
        if p.is_file():
            rel = p.relative_to(SERVING).as_posix()
            actual_files.add(rel)

    # 缺文件 / missing
    missing_files = REQUIRED_FILES - actual_files
    for f in sorted(missing_files):
        errors.append(f"[MISS] 缺文件 / missing file: knowledge_serving/{f}")

    # 多文件 / extras（不在 §11 + W0/W1 + .gitkeep 白名单）
    # 例外 / exemption: audit/ 是 runtime 证据目录，下游卡按需写
    # reconcile_*.json / *_audit.json 等运行证据；不视为 skeleton 多余文件
    extra_files = actual_files - ALLOWED_FILES
    for f in sorted(extra_files):
        if f.startswith("audit/"):
            continue  # audit/ 内容由下游卡按需追加 runtime 证据，不参与骨架校验
        errors.append(
            f"[EXTRA] 多文件 / unexpected file: knowledge_serving/{f} "
            f"(不在 §11 期望、不在 W0/W1 白名单、不是 .gitkeep)"
        )

    return _report(errors)


def _report(errors: list[str]) -> int:
    if not errors:
        print("[OK] knowledge_serving/ 与 §11 + W0/W1 白名单完全一致")
        print(f"     根目录 / root: {SERVING}")
        print(f"     §11 期望文件数: {len(EXPECTED_FILES_PLAN)}")
        print(f"     W0/W1 白名单数: {len(EXPECTED_FILES_PRE_EXISTING)}")
        print(f"     .gitkeep 占位数: {len(EXPECTED_GITKEEPS)}")
        return 0
    print("[FAIL] knowledge_serving/ 校验未通过 / validation failed:")
    for e in errors:
        print(f"  - {e}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # fail-closed：任何未预期异常都退 2
        print("[FATAL] validate_serving_tree 内部异常 / unexpected error:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(2)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_serving_tree.py — serving tree 目录纯净度校验 / purity gate.

校验 knowledge_serving/ 实际目录树是否与 knowledge_serving_plan_v1.1.md §11
+ W0/W1 + W3 已落白名单完全一致。每个新波次落盘新文件时必须同步扩白名单。

退出码 / exit codes:
  0 = 完全一致 / fully aligned
  1 = 缺目录 / 缺文件 / 多文件（未在 §11 也不在 W0/W1 白名单）
  2 = fail-closed（脚本内部异常 / unexpected runtime error）
"""

from __future__ import annotations

import argparse
import datetime as _dt
import csv
import json
import subprocess
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
    # W4 新增 / W4-added：召回入口模块 + 测试根
    "serving",
    "tests",
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
    "scripts/run_qdrant_health_check.sh",    # W0 KS-FIX-01 · staging Qdrant health 外审 wrapper
    "tests/test_qdrant_health_schema_gate.py",  # W0 KS-FIX-01 §13 · schema gate + wrapper cleanup 自动化用例
    "tests/test_task_card_ci_contract.py",       # W0 KS-FIX-01 §15 · 任务卡 ci_commands artifact 契约测试
    "tests/test_serving_tree_whitelist_provenance.py",  # W0 KS-FIX-01 §15 · 白名单溯源测试
    "tests/test_corrections_meta.py",                    # META · META-01 通用机器校验（6 AT case）
    "tests/test_ecs_mirror_fail_closed.py",              # W1 KS-FIX-02 R2 · ECS mirror fail-closed 用例（commit 1cc2715）
}

# W3 已落白名单 / W3-landed allowlist
# W3 group A：6 view 编译器 + 共享基础设施 + 测试套（KS-COMPILER-001/002/004/005/006/007）
# W3 group B：5 control 编译器 + lint + 测试套（KS-COMPILER-008/009/010/011/012）
EXPECTED_FILES_W3 = {
    "scripts/_common.py",                            # 共享治理基础设施 / shared compile-time helpers
    # group A: 6 view compilers
    "scripts/compile_pack_view.py",                  # KS-COMPILER-001
    "scripts/compile_content_type_view.py",          # KS-COMPILER-002
    "scripts/compile_play_card_view.py",             # KS-COMPILER-004
    "scripts/compile_runtime_asset_view.py",         # KS-COMPILER-005
    "scripts/compile_brand_overlay_view.py",         # KS-COMPILER-006
    "scripts/compile_evidence_view.py",              # KS-COMPILER-007
    # group B: 5 control compilers + 1 lint
    "scripts/compile_tenant_scope_registry.py",      # KS-COMPILER-008
    "scripts/compile_field_requirement_matrix.py",   # KS-COMPILER-009
    "scripts/compile_retrieval_policy_view.py",      # KS-COMPILER-010
    "scripts/compile_merge_precedence_policy.py",    # KS-COMPILER-011
    "scripts/lint_no_duplicate_log.sh",              # KS-COMPILER-012
    # group A tests
    "scripts/tests/test_compile_pack_view.py",
    "scripts/tests/test_compile_content_type_view.py",
    "scripts/tests/test_compile_play_card_view.py",
    "scripts/tests/test_compile_runtime_asset_view.py",
    "scripts/tests/test_compile_brand_overlay_view.py",
    "scripts/tests/test_compile_evidence_view.py",
    # group B tests
    "scripts/tests/test_compile_tenant_scope_registry.py",
    "scripts/tests/test_compile_field_requirement_matrix.py",
    "scripts/tests/test_compile_retrieval_policy_view.py",
    "scripts/tests/test_compile_merge_precedence_policy.py",
    "scripts/tests/test_lint_no_duplicate_log.py",
}

# W3-FIX 收口债白名单 / W3-FIX follow-up allowlist
# 注：与 EXPECTED_FILES_W3 分开维护——这两个文件来自 W3 之后的 KS-FIX-* 纠偏卡，
# 不属于 W3 原始编译卡（KS-COMPILER-001~012）的产物；混进 EXPECTED_FILES_W3
# 会让 W3 原始卡的 frontmatter `files_touched` 与白名单语义不一致。
EXPECTED_FILES_W3_FIX = {
    "scripts/rerank_runtime_check.py",          # KS-FIX-21 · rerank runtime 探针（commit a2f7416）
    "tests/test_compiler_coverage.py",          # KS-FIX-06 · compile_run_id coverage 断言（commit a2f7416）
}

# W4 已落白名单 / W4-landed allowlist
# W4 共 6 张卡：
#   KS-COMPILER-003     · generation_recipe_view 编译
#   KS-POLICY-003 / 004 · 双源 yaml（仅复用现有 policies/*.yaml 占位，不增文件）
#   KS-RETRIEVAL-001    · tenant_scope_resolver
#   KS-RETRIEVAL-002    · intent_classifier + content_type_router + 跨文件桥接回归
#   KS-RETRIEVAL-003    · business_brief_checker
# 新增 10 个文件（按卡 frontmatter `files_touched` 严格授权，不放宽通配）
EXPECTED_FILES_W4 = {
    # KS-COMPILER-003 · compiler + test
    "scripts/compile_generation_recipe_view.py",
    "scripts/tests/test_compile_generation_recipe_view.py",
    # KS-RETRIEVAL-001 · tenant_scope_resolver
    "serving/tenant_scope_resolver.py",
    "tests/test_tenant_resolver.py",
    # KS-RETRIEVAL-002 · intent_classifier + content_type_router + 跨文件桥接回归
    "serving/intent_classifier.py",
    "serving/content_type_router.py",
    "tests/test_routing.py",
    "tests/test_intent_policy_bridge.py",
    # KS-RETRIEVAL-003 · business_brief_checker
    "serving/business_brief_checker.py",
    "tests/test_brief.py",
}

# W5 已落白名单 / W5-landed allowlist
# W5 KS-COMPILER-013 · 治理总闸 S1-S7（只读跨表校验器 + ≥14 case 测试）
# 注：audit/validate_serving_governance.report 不在白名单（CI artifact，运行时产物）
EXPECTED_FILES_W5 = {
    "scripts/validate_serving_governance.py",                  # KS-COMPILER-013
    "scripts/tests/test_validate_serving_governance.py",       # 14+ case 测试
}

# W6 已落白名单 / W6-landed allowlist
# 注：所有文件均已 commit；卡 status 详见 task_cards/dag.csv
EXPECTED_FILES_W6 = {
    # KS-POLICY-002 (done) · guardrail_policy 测试（yaml 本身在 EXPECTED_FILES_PLAN）
    "scripts/tests/test_validate_guardrail_policy.py",
    # KS-POLICY-001 (done) · fallback_policy 测试（commit 0255727）
    "scripts/tests/test_validate_policy_yaml.py",
    # KS-RETRIEVAL-005 (in_progress) · structured retrieval 实现 + 测试（commit 5301242）
    # 文件已落盘但卡待审查员验收；标 in_progress 而非 not_started，避免"悬空"
    "serving/structured_retrieval.py",
    "tests/test_struct_retrieval.py",
    # KS-DIFY-ECS-003 (done) · serving views 回灌 ECS PG（commit dda4f56）
    "scripts/upload_serving_views_to_ecs.py",
    # KS-VECTOR-001 (done) · 离线 Qdrant chunks 构建器 + 测试 + jsonl 产物（commit f4c2254）
    # 卡 §5 三项均声明"入 git: 是"——脚本 / 测试 / jsonl 全部纳入版本控制
    "scripts/build_qdrant_payloads.py",
    "scripts/tests/test_build_qdrant_payloads.py",
    "vector_payloads/qdrant_chunks.jsonl",
}

# 空目录占位 / placeholder for empty subdirs（git 不跟踪空目录）
# 注：scripts/ 与 audit/ 已被 W3 实文件填充，无须 .gitkeep
GITKEEP_DIRS = {"vector_payloads", "logs"}
EXPECTED_GITKEEPS = {f"{d}/.gitkeep" for d in GITKEEP_DIRS}

# W7 已落白名单 / W7-landed allowlist
# 注：W7 涵盖 KS-RETRIEVAL-006 / KS-VECTOR-002 / KS-VECTOR-003 / KS-DIFY-ECS-004。
# audit/smoke_*.json、audit/qdrant_filter_smoke_*.json 等是运行时 CI artifact，不进白名单。
EXPECTED_FILES_W7 = {
    # KS-RETRIEVAL-006 (done) · vector_retrieval + payload hard filter（commit 88363e5）
    "serving/vector_retrieval.py",
    "tests/test_vector_filter.py",
    "scripts/smoke_vector_retrieval.py",
    # KS-VECTOR-002 (done) · qdrant payload jsonschema（commit abf1054）
    "vector_payloads/qdrant_payload_schema.json",
    # KS-VECTOR-003 · offline filter smoke + 单测（本卡）
    "scripts/qdrant_filter_smoke.py",
    "tests/test_vector_offline.py",
    # KS-DIFY-ECS-004 (in_progress) · Qdrant chunks 灌库脚本（commit cf38315）
    "scripts/upload_qdrant_chunks.py",
    # KS-RETRIEVAL-004 (done) · recipe + requirement check 召回链
    "serving/recipe_selector.py",
    "serving/requirement_checker.py",
    "tests/test_recipe.py",
    # KS-DIFY-ECS-009 · guardrail 检查器（forbidden_patterns + required_evidence
    # + business_brief hard fields），消费 policies/guardrail_policy.yaml；
    # 卡 §5 两项均声明"入 git: 是"。
    "serving/guardrail.py",
    "tests/test_guardrail.py",
}

# W8 已落白名单 / W8-landed allowlist
# KS-RETRIEVAL-007 + KS-CD-002（commit 4eaa37e）
EXPECTED_FILES_W8 = {
    "serving/merge_context.py",           # KS-RETRIEVAL-007
    "serving/fallback_decider.py",        # KS-RETRIEVAL-007
    "serving/brand_overlay_retrieval.py", # KS-RETRIEVAL-007
    "tests/test_merge_fallback.py",       # KS-RETRIEVAL-007
}

# W9 已落白名单 / W9-landed allowlist
# KS-RETRIEVAL-008（commit d58f2e0）
EXPECTED_FILES_W9 = {
    "serving/context_bundle_builder.py",
    "serving/log_writer.py",
    "tests/test_bundle_log.py",
}

# W10 已落白名单 / W10-landed allowlist
# KS-RETRIEVAL-009 / KS-DIFY-ECS-005 / KS-PROD-003
EXPECTED_FILES_W10 = {
    # KS-RETRIEVAL-009（commit df62d3c）· 端到端 13 步召回 demo
    "scripts/run_context_retrieval_demo.py",
    "logs/retrieval_eval_sample.csv",
    # 注：logs/run_context_retrieval_demo.log 是 *.log gitignore 命中的 runtime log，
    # 不入白名单（由下文 logs/*.log 排除规则放行）
    # KS-DIFY-ECS-005（commit fac113b）· context_bundle_log CSV+PG mirror 双写
    "scripts/reconcile_context_bundle_log_mirror.py",
    "tests/test_log_dual_write.py",
    # KS-PROD-003（commit 18d8ab8）· LLM assist 边界回归
    "tests/test_llm_assist_boundary.py",
}

# W11 已落白名单 / W11-landed allowlist
# KS-DIFY-ECS-006 / KS-DIFY-ECS-007 / KS-DIFY-ECS-010
EXPECTED_FILES_W11 = {
    # KS-DIFY-ECS-006（commit 6e16a96）· ECS 端到端冒烟 outbox
    "control/context_bundle_log_outbox.jsonl",
    # KS-DIFY-ECS-007（commit 17e41d8）· retrieve_context HTTP API wrapper
    "serving/api/__init__.py",
    "serving/api/openapi.yaml",
    "serving/api/retrieve_context.py",
    "tests/test_api.py",
    # KS-DIFY-ECS-010（commit 89f7f35）· context_bundle 日志回放
    "tests/test_replay.py",
}

# W12 已落白名单 / W12-landed allowlist
# KS-DIFY-ECS-008 / KS-CD-001 / KS-PROD-002
EXPECTED_FILES_W12 = {
    # KS-DIFY-ECS-008（commit a6b3de0）· Dify Chatflow 10 节点 DSL 校验
    "scripts/tests/test_validate_dify_dsl.py",
    # KS-CD-001（commit 65408bb）· PG mirror DDL
    "scripts/pg_mirror_context_bundle_log.ddl.sql",
    # KS-PROD-002（commit f75a894）· 跨租户隔离 e2e 回归
    "tests/test_tenant_isolation_e2e.py",
}

# 全部允许文件 = §11 + W0/W1 + W3..W12 白名单 + .gitkeep 占位
ALLOWED_FILES = (
    EXPECTED_FILES_PLAN
    | EXPECTED_FILES_PRE_EXISTING
    | EXPECTED_FILES_W3
    | EXPECTED_FILES_W3_FIX
    | EXPECTED_FILES_W4
    | EXPECTED_FILES_W5
    | EXPECTED_FILES_W6
    | EXPECTED_FILES_W7
    | EXPECTED_FILES_W8
    | EXPECTED_FILES_W9
    | EXPECTED_FILES_W10
    | EXPECTED_FILES_W11
    | EXPECTED_FILES_W12
    | EXPECTED_GITKEEPS
)

# 必须存在的文件 = §11 + W0/W1 + W3 + .gitkeep 占位（缺一即 fail）
REQUIRED_FILES = ALLOWED_FILES

VIEW_CSVS = {
    "pack_view": "views/pack_view.csv",
    "content_type_view": "views/content_type_view.csv",
    "generation_recipe_view": "views/generation_recipe_view.csv",
    "play_card_view": "views/play_card_view.csv",
    "runtime_asset_view": "views/runtime_asset_view.csv",
    "brand_overlay_view": "views/brand_overlay_view.csv",
    "evidence_view": "views/evidence_view.csv",
}

CONTROL_CSVS = {
    "tenant_scope_registry": "control/tenant_scope_registry.csv",
    "field_requirement_matrix": "control/field_requirement_matrix.csv",
    "retrieval_policy_view": "control/retrieval_policy_view.csv",
    "merge_precedence_policy": "control/merge_precedence_policy.csv",
    "context_bundle_log": "control/context_bundle_log.csv",
}


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
    # 排除 Python 运行时缓存：__pycache__/ / .pyc / .pyo（非 git 跟踪）
    actual_files: set[str] = set()
    for p in SERVING.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(SERVING).as_posix()
        if "__pycache__/" in rel or rel.endswith((".pyc", ".pyo")):
            continue
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
        if f.startswith("logs/") and f.endswith(".log"):
            continue  # logs/*.log 是运行时日志（.gitignore 命中），不参与骨架校验
        errors.append(
            f"[EXTRA] 多文件 / unexpected file: knowledge_serving/{f} "
            f"(不在 §11 期望、不在 W0/W1 白名单、不是 .gitkeep)"
        )

    _check_readme_boundary(errors)
    _check_context_bundle_log_singleton(actual_files, errors)
    _check_csv_headers(errors)
    _check_csv_encoding_newlines(errors)

    return _report(errors)


def _load_schema(rel: str) -> dict:
    return json.loads((SERVING / rel).read_text(encoding="utf-8"))


def _required_fields(schema: dict, def_name: str) -> list[str]:
    item = schema["$defs"][def_name]
    required: list[str] = []
    for part in item.get("allOf", []):
        ref = part.get("$ref", "")
        if ref.startswith("#/$defs/"):
            required.extend(schema["$defs"][ref.rsplit("/", 1)[-1]].get("required", []))
    required.extend(item.get("required", []))
    return required


def _csv_header(rel: str) -> list[str]:
    with (SERVING / rel).open("r", encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh), [])


def _check_readme_boundary(errors: list[str]) -> None:
    readme = SERVING / "README.md"
    if not readme.exists():
        return
    text = readme.read_text(encoding="utf-8")
    checks = {
        "clean_output 真源 / source of truth": "clean_output/" in text and ("真源" in text or "source of truth" in text),
        "knowledge_serving 派生 / derived": "knowledge_serving/" in text and ("派生" in text or "derived" in text),
        "可删可重建 / rebuildable": "可删可重建" in text or "重建" in text or "rebuild" in text,
    }
    for label, ok in checks.items():
        if not ok:
            errors.append(f"[README] 缺边界声明 / missing boundary statement: {label}")


def _check_context_bundle_log_singleton(actual_files: set[str], errors: list[str]) -> None:
    hits = sorted(f for f in actual_files if f.endswith("context_bundle_log.csv"))
    if hits != ["control/context_bundle_log.csv"]:
        errors.append(
            "[DUP] context_bundle_log.csv canonical 位置错误 / invalid canonical location: "
            + ", ".join(hits)
        )


def _check_csv_headers(errors: list[str]) -> None:
    view_schema = _load_schema("schema/serving_views.schema.json")
    control_schema = _load_schema("schema/control_tables.schema.json")
    for def_name, rel in VIEW_CSVS.items():
        path = SERVING / rel
        if not path.exists():
            continue
        expected = _required_fields(view_schema, def_name)
        actual = _csv_header(rel)
        if actual != expected:
            errors.append(f"[HEADER] {rel} header 与 schema required 不一致 / mismatch")
    for def_name, rel in CONTROL_CSVS.items():
        path = SERVING / rel
        if not path.exists():
            continue
        expected = _required_fields(control_schema, def_name)
        actual = _csv_header(rel)
        if actual != expected:
            errors.append(f"[HEADER] {rel} header 与 schema required 不一致 / mismatch")


def _check_csv_encoding_newlines(errors: list[str]) -> None:
    for rel in sorted(set(VIEW_CSVS.values()) | set(CONTROL_CSVS.values())):
        path = SERVING / rel
        if not path.exists():
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            errors.append(f"[ENCODING] CSV 含 BOM / BOM found: {rel}")
        if b"\r\n" in raw:
            errors.append(f"[NEWLINE] CSV 含 CRLF / Windows newline found: {rel}")


def _git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _build_payload(errors: list[str], exit_code: int, *,
                   strict: bool = False, e8_decision: dict | None = None) -> dict:
    return {
        "card": "KS-SCHEMA-005" if not strict else "KS-FIX-04",
        "checked_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "env": "local",
        "git_commit": _git_commit(),
        "evidence_level": "runtime_verified" if exit_code == 0 else "runtime_verified_fail",
        "exit_code": exit_code,
        "strict": strict,
        "expected_plan_files": len(EXPECTED_FILES_PLAN),
        "allowed_file_count": len(ALLOWED_FILES),
        "required_file_count": len(REQUIRED_FILES),
        "gitkeep_count": len(EXPECTED_GITKEEPS),
        "errors": errors,
        "e8_decision": e8_decision,
    }


def _write_out_audit(out_path: Path, payload: dict) -> None:
    """KS-FIX-04 §8 audit sink：白名单守门，禁写 clean_output/"""
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    resolved = out_path.resolve()
    clean_output = (REPO_ROOT / "clean_output").resolve()
    if str(resolved).startswith(str(clean_output)):
        sys.stderr.write(
            f"❌ --out 拒绝指向 clean_output/ 子树 / clean_output is SSOT, not audit sink: {resolved}\n"
        )
        sys.exit(2)
    allowed = [
        (REPO_ROOT / "knowledge_serving" / "audit").resolve(),
        (REPO_ROOT / "task_cards" / "corrections" / "audit").resolve(),
    ]
    if not any(str(resolved).startswith(str(r)) for r in allowed):
        sys.stderr.write(f"❌ --out 路径不在允许的 audit 目录下 / illegal audit sink: {resolved}\n")
        sys.exit(2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_report_artifact(errors: list[str], exit_code: int) -> None:
    payload = {
        "card": "KS-SCHEMA-005",
        "checked_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "env": "local",
        "git_commit": _git_commit(),
        "evidence_level": "runtime_verified" if exit_code == 0 else "runtime_verified_fail",
        "exit_code": exit_code,
        "expected_plan_files": len(EXPECTED_FILES_PLAN),
        "whitelist_w0w1": len(EXPECTED_FILES_PRE_EXISTING),
        "whitelist_w3": len(EXPECTED_FILES_W3),
        "whitelist_w3_fix": len(EXPECTED_FILES_W3_FIX),
        "whitelist_w4": len(EXPECTED_FILES_W4),
        "whitelist_w5": len(EXPECTED_FILES_W5),
        "whitelist_w6": len(EXPECTED_FILES_W6),
        "whitelist_w7": len(EXPECTED_FILES_W7),
        "whitelist_w8": len(EXPECTED_FILES_W8),
        "whitelist_w9": len(EXPECTED_FILES_W9),
        "whitelist_w10": len(EXPECTED_FILES_W10),
        "whitelist_w11": len(EXPECTED_FILES_W11),
        "whitelist_w12": len(EXPECTED_FILES_W12),
        "allowed_file_count": len(ALLOWED_FILES),
        "required_file_count": len(REQUIRED_FILES),
        "gitkeep_count": len(EXPECTED_GITKEEPS),
        "errors": errors,
    }
    out = REPO_ROOT / "scripts" / "validate_serving_tree.report"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _report(errors: list[str]) -> int:
    if not errors:
        print("[OK] knowledge_serving/ 与 §11 + W0/W1 + W3..W12 白名单完全一致")
        print(f"     根目录 / root: {SERVING}")
        print(f"     §11 期望文件数: {len(EXPECTED_FILES_PLAN)}")
        print(f"     W0/W1 白名单数: {len(EXPECTED_FILES_PRE_EXISTING)}")
        print(f"     W3..W12 白名单数: {len(ALLOWED_FILES - EXPECTED_FILES_PLAN - EXPECTED_FILES_PRE_EXISTING - EXPECTED_GITKEEPS)}")
        print(f"     .gitkeep 占位数: {len(EXPECTED_GITKEEPS)}")
        _write_report_artifact(errors, 0)
        return 0
    print("[FAIL] knowledge_serving/ 校验未通过 / validation failed:")
    for e in errors:
        print(f"  - {e}")
    _write_report_artifact(errors, 1)
    return 1


E8_DECISION_DEFAULT = {
    "decision": "spec_holds_data_aligns",
    "rationale": (
        "W3+ 已落新文件全部通过 EXPECTED_FILES_W3..W12 白名单立法纳入；"
        "purity 当前 exit 0 = 目录数据已与 spec 对齐，不需要反向放宽 spec。"
    ),
    "signed_by": "faye",
    "signed_at": "2026-05-14",
    "scope": "KS-FIX-04 W2 closure",
}


def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="serving tree purity gate (KS-SCHEMA-005 + KS-FIX-04 --strict --out)"
    )
    parser.add_argument("--strict", action="store_true",
                        help="KS-FIX-04: 严格模式 + 落 e8_decision 到 --out artifact")
    parser.add_argument("--out", default=None,
                        help="KS-FIX-04 §8 audit sink；白名单 knowledge_serving/audit/ 或 "
                             "task_cards/corrections/audit/；禁写 clean_output/")
    args = parser.parse_args()
    exit_code = main()
    if args.out:
        payload = _build_payload(
            [], exit_code,
            strict=args.strict,
            e8_decision=E8_DECISION_DEFAULT if args.strict else None,
        )
        _write_out_audit(Path(args.out), payload)
    if args.strict and exit_code != 0:
        return 1
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(_cli_main())
    except Exception:
        # fail-closed：任何未预期异常都退 2
        print("[FATAL] validate_serving_tree 内部异常 / unexpected error:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(2)

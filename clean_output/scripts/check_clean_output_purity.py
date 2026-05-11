#!/usr/bin/env python3
"""硬门 15 · clean_output 目录纯净度

prompt §2 严格列了产出目录清单，未经明确要求不得创建额外目录或文件。
本检查列举顶层结构，与白名单比对；扫描所有 *.bak.* / __pycache__ 残留。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWED_TOP_DIRS = {
    "domain_skeleton", "candidates", "nine_tables",
    "unprocessable_register", "storage", "audit", "templates", "scripts", "schema",
    # W12 三层资产旁路（B-lite 决议下不进 9 表，进独立目录）
    "play_cards", "runtime_assets",
}
ALLOWED_TOP_FILES = {"README.md", "manifest.json", "checksums.sha256"}

# audit 顶层白名单（prompt §2 明文 + W8 reviewer 要求 SSOT 数据 + W8 工程必要文件）
# 工程过程产物归 audit/_process/ 子目录
ALLOWED_AUDIT_TOP = {
    # prompt §2 明文要求
    "extraction_log.csv", "four_gate_results.csv", "brand_layer_review_queue.csv",
    "blockers.md", "final_report.md", "phase_a_review.md",
    # SSOT 数据 + 渲染产物
    "coverage_report.md", "coverage_status.json", "audit_status.json",
    # W8 reviewer 要求成果文件
    "task_cards.md", "uncovered_md_register.md",
    "schema_extension_register.csv", "knowledge_point_coverage.csv",
    "source_unit_inventory.csv", "gap_decision_recommendations.md",
    # W10 新增 row/章节级裁决账本
    "evidence_row_adjudication.csv",
    "source_unit_adjudication.csv",
    # W11 三层裁决预分清单
    "source_unit_adjudication_v2.csv",
    "source_unit_adjudication_w11.csv",
    "pack_dispute_review.csv",
    "w11_acceptance_report.md",
    "w12_acceptance_report.md",
    "l2_play_card_review.csv",
    "l3_runtime_asset_review.csv",
    "pack_layer_register.csv",
    "review_must.csv",
    "review_sample.csv",
    "pack_review_must.csv",
    "_process",  # 工程过程产物子目录
    # KS-S0-001 / 002 / 003 · Phase 2 启动期 audit 证据 / Phase 2 kickoff audit evidence
    "baseline_alignment_KS-S0-001.md",     # W12 基线对齐证据 / baseline alignment evidence
    "db_state_evidence_KS-S0-002.md",      # knowledge.db 废弃事实快照 / deprecation state snapshot
    "key_rotation_log_KS-S0-003.md",       # 密钥治理日志 / key governance log
    "known_risk_accepted_2026-05-12.md",   # 已知风险接受记录 / known risk accepted log
}


def main():
    bad_dirs = []
    bad_files = []
    bak_files = []
    pycache = []

    for child in ROOT.iterdir():
        name = child.name
        if child.is_dir():
            if name not in ALLOWED_TOP_DIRS:
                bad_dirs.append(name)
        else:
            if name not in ALLOWED_TOP_FILES:
                bad_files.append(name)

    for p in ROOT.rglob("*"):
        if ".bak" in p.name:
            bak_files.append(str(p.relative_to(ROOT)))
        if p.is_dir() and p.name == "__pycache__":
            pycache.append(str(p.relative_to(ROOT)))

    # audit 顶层校验
    audit_dir = ROOT / "audit"
    audit_top_extra = []
    if audit_dir.exists():
        for child in audit_dir.iterdir():
            if child.name not in ALLOWED_AUDIT_TOP:
                audit_top_extra.append(child.name)

    print("=== 硬门 15 · clean_output 纯净度 ===\n")
    print(f"  顶层目录: {len(list(ROOT.iterdir()))} 项")
    print(f"  audit 顶层文件: {len(list(audit_dir.iterdir()))} 项")
    issues = 0
    if audit_top_extra:
        print(f"  ❌ audit 顶层非白名单（应进 _process/）: {audit_top_extra}")
        issues += 1
    if bad_dirs:
        print(f"  ❌ 顶层非白名单目录: {bad_dirs}")
        issues += 1
    if bad_files:
        print(f"  ❌ 顶层非白名单文件: {bad_files}")
        issues += 1
    if bak_files:
        print(f"  ❌ .bak 残留: {len(bak_files)} 个")
        issues += 1
    if pycache:
        print(f"  ❌ __pycache__ 残留: {len(pycache)} 个")
        issues += 1
    if not issues:
        print("  ✅ 顶层结构 + 残留扫描全绿（prompt §2 七子目录纪律遵守）")

    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())

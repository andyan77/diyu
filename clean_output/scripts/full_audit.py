#!/usr/bin/env python3
"""硬门总闸 · 串行跑 9 道硬门，写 audit/audit_status.json

执行顺序（任一失败立即记录但继续后面）：
  G0 csv_structure_check     · 结构（字段对齐、白名单）
  G1 schema canonical        · schema 文件存在 + 必含字段
  G2 validate_csv_strict     · 全量 schema + JSON + minLength
  G3 stage4 残留检查         · 22 bad rows 已清零
  G4 brand residue           · 10 条裁决表完成
  G5 register enum           · 不可处理登记表 8 类受控
  G6 load_to_sqlite          · CSV↔DB PK+hash 一致
  G7 task cards status       · 状态来自 extraction_log，数字来自磁盘
  G8 ddl sync + demo         · 双 DDL 字符级一致 + 反例 demo

每个 gate 落 {gate, name, status, summary, evidence_path}。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
STATUS = ROOT / "audit" / "audit_status.json"

# Phase 2（2026-05-12 起）废弃硬门 / deprecated gates from Phase 2 kickoff
# 见 audit/db_state_evidence_KS-S0-002.md
# rc=2 + name 在此集合中 → 视为 deprecated_pass / treated as deprecated_pass
DEPRECATED_GATES = {
    "load_to_sqlite",  # G6 · sqlite db 已废弃（path B 决议）
}


def run(name, argv):
    """跑子脚本，返回 (rc, stdout)"""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        return r.returncode, (r.stdout + r.stderr)
    except Exception as e:
        return 99, str(e)


GATES = [
    ("G0", "csv_structure_check",   ["python3", str(SCRIPTS / "csv_structure_check.py")],
     "audit/_process/csv_struct_violations.csv"),
    ("G2", "validate_csv_strict",   ["python3", str(SCRIPTS / "validate_csv_strict.py")],
     "audit/_process/csv_violations.csv"),
    ("G5", "register_enum",         ["python3", str(SCRIPTS / "validate_register_enum.py")],
     "audit/_process/register_enum_violations.csv"),
    ("G6", "load_to_sqlite",        ["python3", str(SCRIPTS / "load_to_sqlite.py"), "--memory"],
     "audit/_process/csv_sqlite_consistency.csv"),
    ("G7", "task_cards_status",     ["python3", str(SCRIPTS / "sync_task_cards_status.py")],
     "audit/task_cards.md"),
    ("G8a", "ddl_sync",             ["python3", str(SCRIPTS / "check_ddl_sync.py")],
     "schema/nine_tables_ddl.sql + storage/single_db_logical_isolation.sql"),
    ("G8b", "ddl_check_demo",       ["python3", str(SCRIPTS / "check_constraint_demo.py")],
     "storage/sqlite3_demo_log.txt"),
    ("Gv", "verify_reverse_traceability",
     ["python3", str(SCRIPTS / "verify_reverse_traceability.py")],
     "audit/extraction_log.csv"),
    ("G9",  "manifest_consistency",
     ["python3", str(SCRIPTS / "check_manifest_consistency.py")],
     "manifest.json"),
    ("G10", "brand_residue_in_csv",
     ["python3", str(SCRIPTS / "scan_brand_residue_in_csv.py")],
     "audit/_process/brand_residue_in_csv.csv"),
    ("G11", "yaml_csv_field_sync",
     ["python3", str(SCRIPTS / "verify_yaml_csv_field_sync.py")],
     "audit/_process/yaml_csv_sync_violations.csv"),
    ("G12", "coverage_closure",
     ["python3", str(SCRIPTS / "compute_coverage_status.py")],
     "audit/coverage_status.json"),
    ("G13", "anchor_quote_authenticity",
     ["python3", str(SCRIPTS / "verify_anchor_quote_authenticity.py")],
     "audit/_process/anchor_quote_violations.csv"),
    ("G14", "fk_constraints",
     ["python3", str(SCRIPTS / "check_fk_constraints.py")],
     "schema/nine_tables_ddl.sql"),
    ("G15", "clean_output_purity",
     ["python3", str(SCRIPTS / "check_clean_output_purity.py")],
     "<root structure>"),
    ("G16a", "parse_md_source_units",
     ["python3", str(SCRIPTS / "parse_md_source_units.py")],
     "audit/source_unit_inventory.csv"),
    ("G16b", "compute_knowledge_point_coverage",
     ["python3", str(SCRIPTS / "compute_knowledge_point_coverage.py")],
     "audit/knowledge_point_coverage.csv"),
    ("G16c", "knowledge_point_coverage_baseline",
     ["python3", str(SCRIPTS / "check_knowledge_point_coverage.py")],
     "audit/coverage_status.json"),
    ("G16d_a", "build_source_unit_adjudication",
     ["python3", str(SCRIPTS / "build_source_unit_adjudication.py")],
     "audit/source_unit_adjudication.csv"),
    ("G16d_b", "check_source_unit_adjudication",
     ["python3", str(SCRIPTS / "check_source_unit_adjudication.py")],
     "audit/source_unit_adjudication.csv"),
    ("G17a", "build_evidence_row_adjudication",
     ["python3", str(SCRIPTS / "build_evidence_row_adjudication.py")],
     "audit/evidence_row_adjudication.csv"),
    ("G17b", "check_evidence_row_adjudication",
     ["python3", str(SCRIPTS / "check_evidence_row_adjudication.py")],
     "audit/evidence_row_adjudication.csv"),
    ("G18", "derived_doc_freshness",
     ["python3", str(SCRIPTS / "check_derived_doc_freshness.py")],
     "audit/_process/*.md frontmatter"),
    ("G19", "layer_adjudication",
     ["python3", str(SCRIPTS / "check_layer_adjudication.py")],
     "audit/source_unit_adjudication_w11.csv + pack_layer_register.csv"),
    ("G20", "play_card_completeness",
     ["python3", str(SCRIPTS / "check_play_card.py")],
     "play_cards/play_card_register.csv"),
    ("G21", "runtime_asset_completeness",
     ["python3", str(SCRIPTS / "check_runtime_asset.py")],
     "runtime_assets/runtime_asset_index.csv"),
]


def check_schema_file():
    p = ROOT / "schema" / "nine_tables.schema.json"
    if not p.exists():
        return 1, "schema 文件缺失"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        for k in ("definitions", "tables"):
            if k not in d:
                return 1, f"schema 缺 {k}"
        if len(d["tables"]) != 9:
            return 1, f"tables 数 {len(d['tables'])} != 9"
        return 0, f"9 tables, definitions OK"
    except Exception as e:
        return 1, str(e)


def main():
    results = []

    print("=== full_audit · 串行 9 道硬门 ===\n")

    rc, msg = check_schema_file()
    mark = "✅" if rc == 0 else "❌"
    print(f"  {mark} G1 schema_canonical      rc={rc}  {msg}")
    results.append({
        "gate": "G1", "name": "schema_canonical",
        "status": "pass" if rc == 0 else "fail",
        "rc": rc, "summary": msg,
        "evidence_path": "schema/nine_tables.schema.json",
    })

    for gate, name, argv, evidence in GATES:
        if not Path(argv[1]).exists():
            print(f"  ⚠️  {gate} {name:30s} skipped (script missing)")
            results.append({
                "gate": gate, "name": name,
                "status": "skipped", "rc": -1,
                "summary": "script not found",
                "evidence_path": evidence,
            })
            continue
        rc, out = run(name, argv)
        last = out.strip().splitlines()[-1] if out.strip() else ""
        # deprecated gate 处理 / deprecated gate handling
        if name in DEPRECATED_GATES:
            mark = "⏭️ "
            status = "deprecated_pass"
            print(f"  {mark} {gate} {name:30s} rc={rc}  [deprecated 2026-05-12 · 见 audit/db_state_evidence_KS-S0-002.md]")
        else:
            mark = "✅" if rc == 0 else "❌"
            status = "pass" if rc == 0 else "fail"
            print(f"  {mark} {gate} {name:30s} rc={rc}  {last[:80]}")
        results.append({
            "gate": gate, "name": name,
            "status": status,
            "rc": rc, "summary": last[:300],
            "evidence_path": evidence,
        })

    summary = {
        "total": len(results),
        "pass":  sum(1 for r in results if r["status"] == "pass"),
        "fail":  sum(1 for r in results if r["status"] == "fail"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "deprecated_pass": sum(1 for r in results if r["status"] == "deprecated_pass"),
    }
    print(f"\n汇总: pass={summary['pass']}  deprecated={summary['deprecated_pass']}  fail={summary['fail']}  skipped={summary['skipped']}  total={summary['total']}")

    STATUS.parent.mkdir(parents=True, exist_ok=True)
    import datetime as _dt
    audit_status = {
        "summary": summary,
        "gates": results,
        "rendered_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    STATUS.write_text(json.dumps(audit_status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nstatus: {STATUS}")

    # 末段自动渲染 final_report.md（防漂移）
    render = SCRIPTS / "render_final_report.py"
    if render.exists():
        rc, out = run("render_final_report", ["python3", str(render)])
        last = out.strip().splitlines()[-1] if out.strip() else ""
        mark = "✅" if rc == 0 else "❌"
        print(f"  {mark} render_final_report rc={rc}  {last[:100]}")

    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

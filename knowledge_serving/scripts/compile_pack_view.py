#!/usr/bin/env python3
"""
KS-COMPILER-001 · compile_pack_view.py

把 clean_output/candidates/**/*.yaml 投影为 knowledge_serving/views/pack_view.csv
（最小知识单元读模型 / minimal knowledge unit serving view，对应 plan §3.1）。

硬约束 / hard constraints：
  - W3+ 输入白名单（README §7.1）：只读 clean_output/ + knowledge_serving/schema/ +
    knowledge_serving/control/；禁止读 ECS PG knowledge.* / ECS 备份 / 旧临时目录。
  - clean_output/ 0 写。
  - 不调 LLM。
  - 同输入幂等：sha256(pack_view.csv) 重复运行一致。

退出码 / exit codes：
  0  正常 / OK
  2  输入异常 / input invalid（重复 pack_id / 非法 brand_layer / 断 FK / 缺字段）
  3  schema 校验失败 / schema validation failed
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATES_DIR = REPO_ROOT / "clean_output" / "candidates"
DEFAULT_NINE_TABLES_DIR = REPO_ROOT / "clean_output" / "nine_tables"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "clean_output" / "audit" / "source_manifest.json"
DEFAULT_SCHEMA_PATH = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"
DEFAULT_CONTROL_CANONICAL = REPO_ROOT / "knowledge_serving" / "control" / "content_type_canonical.csv"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "knowledge_serving" / "views" / "pack_view.csv"
DEFAULT_LOG_PATH = REPO_ROOT / "knowledge_serving" / "audit" / "pack_view.compile.log"

BRAND_LAYER_RE = re.compile(r"^(domain_general|needs_review|brand_[a-z][a-z0-9_]*)$")
GRANULARITY_ENUM = {"L1", "L2", "L3"}
GATE_STATUS_ENUM = {"active", "draft", "deprecated", "frozen"}

CSV_COLUMNS = [
    # governance_common_fields (13)
    "source_pack_id",
    "brand_layer",
    "granularity_layer",
    "gate_status",
    "source_table_refs",
    "evidence_ids",
    "traceability_status",
    "default_call_pool",
    "review_status",
    "compile_run_id",
    "source_manifest_hash",
    "view_schema_version",
    "chunk_text_hash",
    # pack_view business fields (11)
    "pack_id",
    "pack_type",
    "knowledge_title",
    "knowledge_assertion",
    "applicable_when",
    "success_scenario",
    "flip_scenario",
    "alternative_boundary",
    "content_type_tags",
    "object_type_tags",
    "embedding_text",
]

logger = logging.getLogger("compile_pack_view")


@dataclass
class CompileContext:
    candidates_dir: Path
    nine_tables_dir: Path
    manifest_path: Path
    schema_path: Path
    output_csv: Path
    log_path: Path
    include_inactive: bool
    strict_fk: bool


class CompileError(Exception):
    """已记录上下文的可控编译错误 / compile-time controlled error."""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _safe_relative(p: Path) -> str:
    """log 中尽量用相对路径；不在 REPO_ROOT 子树内（如 tmp 测试目录）时退回绝对路径。"""
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def derive_view_schema_version(schema_path: Path) -> str:
    """view_schema_version = sha256(schema_file)[:12]，schema 漂移即版本变。"""
    return _sha256_bytes(schema_path.read_bytes())[:12]


def derive_compile_run_id(source_manifest_hash: str, view_schema_version: str) -> str:
    raw = f"{source_manifest_hash}|{view_schema_version}".encode("utf-8")
    return _sha256_bytes(raw)[:16]


def load_manifest_hash(manifest_path: Path) -> str:
    if not manifest_path.exists():
        raise CompileError(f"source_manifest 不存在 / missing: {manifest_path}")
    data = json.loads(_read_text(manifest_path))
    h = data.get("manifest_hash")
    if not isinstance(h, str) or not h:
        raise CompileError("source_manifest.manifest_hash 缺失 / missing")
    return h


def load_evidence_id_set(nine_tables_dir: Path) -> set[str]:
    path = nine_tables_dir / "07_evidence.csv"
    ids: set[str] = set()
    if not path.exists():
        return ids
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            eid = (row.get("evidence_id") or "").strip()
            if eid:
                ids.add(eid)
    return ids


def discover_candidate_files(candidates_dir: Path) -> list[Path]:
    if not candidates_dir.exists():
        return []
    files = sorted(candidates_dir.rglob("*.yaml"))
    return files


def derive_gate_status(candidate: dict) -> str:
    """
    多租户 4-闸 active 判定 / multi-tenant 4-gate active rule（见 task card §4 表）：

      - domain_general：gate_1/2/3/4 全 pass → active；否则 draft
      - brand_<name> / needs_review：gate_1/2/4 必须 pass；gate_3 允许 partial
        （品牌专属知识按定义就不期望跨品牌可泛化）

    租户隔离由 retrieval 层 allowed_layers 过滤承担，不在 compile 阶段滤掉品牌包。
    """
    gsc = candidate.get("gate_self_check") or {}
    brand_layer = (candidate.get("brand_layer") or "").strip()
    universal_keys = (
        "gate_1_closed_scenario",
        "gate_2_reverse_infer",
        "gate_4_production_feasible",
    )
    universal_pass = all((gsc.get(k) or "").strip() == "pass" for k in universal_keys)
    gate3 = (gsc.get("gate_3_rule_generalizable") or "").strip()

    if not universal_pass:
        return "draft"

    if brand_layer == "domain_general":
        return "active" if gate3 == "pass" else "draft"
    # brand_<name> 或 needs_review：gate_3 允许 pass / partial
    if gate3 in ("pass", "partial"):
        return "active"
    return "draft"


def derive_traceability_status(candidate: dict) -> str:
    """根据 evidence.inference_level 与 nine_table_projection.evidence 推 traceability。"""
    proj_ev = (candidate.get("nine_table_projection") or {}).get("evidence") or []
    top_ev = candidate.get("evidence") or {}
    inference_level = (top_ev.get("inference_level") or "").strip()
    has_evidence = bool(proj_ev) and bool(top_ev.get("source_md"))
    if not has_evidence:
        return "missing"
    if inference_level in ("direct_quote", "paraphrase_high"):
        return "full"
    if inference_level == "paraphrase_mid":
        return "partial"
    if inference_level == "paraphrase_low":
        return "weak"
    if inference_level == "inferred":
        return "weak"
    return "partial"


def derive_review_status(candidate: dict) -> str:
    blr = candidate.get("brand_layer_review") or {}
    if blr.get("faye_review_required") is True:
        return "pending_review"
    decision = (blr.get("decision_suggestion") or "").strip()
    if decision:
        return "approved"
    return "needs_review"


def derive_source_table_refs(candidate: dict) -> list[str]:
    proj = candidate.get("nine_table_projection") or {}
    name_map = {
        "object_type": "01_object_type.csv",
        "field": "02_field.csv",
        "semantic": "03_semantic.csv",
        "value_set": "04_value_set.csv",
        "relation": "05_relation.csv",
        "rule": "06_rule.csv",
        "evidence": "07_evidence.csv",
        "lifecycle": "08_lifecycle.csv",
        "call_mapping": "09_call_mapping.csv",
    }
    refs = []
    for key, fname in name_map.items():
        rows = proj.get(key)
        if rows:
            refs.append(fname)
    return refs


def _entry_id(entry: Any, *id_keys: str) -> str:
    """projection 行有两种形态：dict（带显式 id 字段）或裸字符串（id 简写）。统一取 id。"""
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        for k in id_keys:
            v = entry.get(k)
            if v:
                return str(v).strip()
    return ""


def derive_evidence_ids(candidate: dict) -> list[str]:
    proj_ev = (candidate.get("nine_table_projection") or {}).get("evidence") or []
    out: list[str] = []
    for e in proj_ev:
        eid = _entry_id(e, "evidence_id")
        if eid:
            out.append(eid)
    return out


def derive_object_type_tags(candidate: dict) -> list[str]:
    proj_ot = (candidate.get("nine_table_projection") or {}).get("object_type") or []
    out: list[str] = []
    for ot in proj_ot:
        tid = _entry_id(ot, "type_id")
        if tid:
            out.append(tid)
    return out


def derive_content_type_tags(candidate: dict) -> list[str]:
    """call_mapping.runtime_method → content_type_tag。
    裸字符串形态下无 runtime_method 字段，跳过（结果可能为空 list，schema 允许）。"""
    proj_cm = (candidate.get("nine_table_projection") or {}).get("call_mapping") or []
    tags: list[str] = []
    seen: set[str] = set()
    for cm in proj_cm:
        if isinstance(cm, dict):
            rm = (cm.get("runtime_method") or "").strip()
            if rm and rm not in seen:
                seen.add(rm)
                tags.append(rm)
    return tags


def derive_knowledge_title(candidate: dict) -> str:
    """从 pack_id 尾部 slug 派生人类可读 title；fallback 用 pack_id 自身。"""
    pid = (candidate.get("pack_id") or "").strip()
    if not pid:
        return ""
    if pid.startswith("KP-"):
        return pid[len("KP-"):].replace("-", " ")
    return pid


def derive_applicable_when(candidate: dict) -> str:
    scenario = candidate.get("scenario") or {}
    boundary = scenario.get("boundary") or {}
    val = (boundary.get("applicable_when") or "").strip()
    return val


def derive_alternative_boundary(candidate: dict) -> str:
    scenario = candidate.get("scenario") or {}
    boundary = scenario.get("boundary") or {}
    not_applicable = (boundary.get("not_applicable_when") or "").strip()
    alt_path = scenario.get("alternative_path") or []
    parts: list[str] = []
    if not_applicable:
        parts.append(f"not_applicable_when: {not_applicable}")
    if alt_path:
        joined = "; ".join(str(p).strip() for p in alt_path if str(p).strip())
        if joined:
            parts.append(f"alternative_path: {joined}")
    return " | ".join(parts)


def derive_success_flip(candidate: dict) -> tuple[str, str]:
    scenario = candidate.get("scenario") or {}
    result = scenario.get("result") or {}
    success = (result.get("success_pattern") or "").strip()
    flip = (result.get("flip_pattern") or "").strip()
    return success, flip


def derive_embedding_text(
    knowledge_assertion: str,
    applicable_when: str,
    success: str,
    flip: str,
) -> str:
    chunks = [
        f"assertion: {knowledge_assertion}".strip(),
        f"applicable_when: {applicable_when}".strip() if applicable_when else "",
        f"success: {success}".strip() if success else "",
        f"flip: {flip}".strip() if flip else "",
    ]
    return "\n".join(c for c in chunks if c)


def derive_default_call_pool(candidate: dict) -> bool:
    proj_cm = (candidate.get("nine_table_projection") or {}).get("call_mapping") or []
    return bool(proj_cm)


def build_row(
    candidate: dict,
    *,
    compile_run_id: str,
    source_manifest_hash: str,
    view_schema_version: str,
) -> dict[str, Any]:
    pack_id = (candidate.get("pack_id") or "").strip()
    brand_layer = (candidate.get("brand_layer") or "").strip()
    granularity_layer = (candidate.get("granularity_layer") or "").strip()
    pack_type = (candidate.get("pack_type") or "").strip()
    knowledge_assertion = (candidate.get("knowledge_assertion") or "").strip()

    if not pack_id:
        raise CompileError("缺 pack_id / missing pack_id")
    if not BRAND_LAYER_RE.match(brand_layer):
        raise CompileError(
            f"非法 brand_layer / invalid brand_layer={brand_layer!r} (pack_id={pack_id})"
        )
    if granularity_layer not in GRANULARITY_ENUM:
        raise CompileError(
            f"非法 granularity_layer={granularity_layer!r} (pack_id={pack_id})"
        )
    if not pack_type:
        raise CompileError(f"缺 pack_type / missing (pack_id={pack_id})")
    if not knowledge_assertion:
        raise CompileError(f"缺 knowledge_assertion (pack_id={pack_id})")

    gate_status = derive_gate_status(candidate)
    if gate_status not in GATE_STATUS_ENUM:
        raise CompileError(f"derived gate_status invalid={gate_status} pack={pack_id}")

    success, flip = derive_success_flip(candidate)
    applicable_when = derive_applicable_when(candidate)
    alt_boundary = derive_alternative_boundary(candidate)
    title = derive_knowledge_title(candidate)
    content_type_tags = derive_content_type_tags(candidate)
    object_type_tags = derive_object_type_tags(candidate)
    embedding_text = derive_embedding_text(knowledge_assertion, applicable_when, success, flip)
    chunk_text_hash = _sha256_text(embedding_text)
    source_table_refs = derive_source_table_refs(candidate)
    evidence_ids = derive_evidence_ids(candidate)
    traceability_status = derive_traceability_status(candidate)
    default_call_pool = derive_default_call_pool(candidate)
    review_status = derive_review_status(candidate)

    return {
        "source_pack_id": pack_id,
        "brand_layer": brand_layer,
        "granularity_layer": granularity_layer,
        "gate_status": gate_status,
        "source_table_refs": source_table_refs,
        "evidence_ids": evidence_ids,
        "traceability_status": traceability_status,
        "default_call_pool": default_call_pool,
        "review_status": review_status,
        "compile_run_id": compile_run_id,
        "source_manifest_hash": source_manifest_hash,
        "view_schema_version": view_schema_version,
        "chunk_text_hash": chunk_text_hash,
        "pack_id": pack_id,
        "pack_type": pack_type,
        "knowledge_title": title,
        "knowledge_assertion": knowledge_assertion,
        "applicable_when": applicable_when,
        "success_scenario": success,
        "flip_scenario": flip,
        "alternative_boundary": alt_boundary,
        "content_type_tags": content_type_tags,
        "object_type_tags": object_type_tags,
        "embedding_text": embedding_text,
    }


def row_to_csv_dict(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for col in CSV_COLUMNS:
        v = row[col]
        if isinstance(v, list):
            out[col] = json.dumps(v, ensure_ascii=False, sort_keys=False)
        elif isinstance(v, bool):
            out[col] = "true" if v else "false"
        elif v is None:
            out[col] = ""
        else:
            out[col] = str(v)
    return out


def validate_row_schema(row: dict[str, Any], schema: dict) -> list[str]:
    """对一行做 pack_view JSON-Schema 校验，返回错误列表。"""
    defs = schema["$defs"]
    pack_view_schema = {
        "$schema": schema["$schema"],
        "$defs": defs,
        "allOf": [
            {"$ref": "#/$defs/governance_common_fields"},
            {"$ref": "#/$defs/pack_view"},
        ],
    }
    validator = Draft202012Validator(pack_view_schema)
    errors = sorted(validator.iter_errors(row), key=lambda e: list(e.path))
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in errors
    ]


def compile_pack_view(ctx: CompileContext) -> dict[str, Any]:
    schema = json.loads(_read_text(ctx.schema_path))
    view_schema_version = derive_view_schema_version(ctx.schema_path)
    source_manifest_hash = load_manifest_hash(ctx.manifest_path)
    compile_run_id = derive_compile_run_id(source_manifest_hash, view_schema_version)
    evidence_id_set = load_evidence_id_set(ctx.nine_tables_dir)

    files = discover_candidate_files(ctx.candidates_dir)
    rows: list[dict[str, Any]] = []
    seen_pack_ids: set[str] = set()
    filtered_inactive = 0
    schema_errors: list[str] = []

    for fp in files:
        try:
            data = yaml.safe_load(_read_text(fp)) or {}
        except yaml.YAMLError as e:
            raise CompileError(f"YAML 解析失败 / parse fail: {fp}: {e}")
        if not isinstance(data, dict):
            raise CompileError(f"candidate 顶层非 dict: {fp}")

        row = build_row(
            data,
            compile_run_id=compile_run_id,
            source_manifest_hash=source_manifest_hash,
            view_schema_version=view_schema_version,
        )

        # 重复 pack_id 阻断 / duplicate pack_id blocks
        if row["pack_id"] in seen_pack_ids:
            raise CompileError(f"重复 pack_id / duplicate: {row['pack_id']} @ {fp}")
        seen_pack_ids.add(row["pack_id"])

        # FK 检查：evidence_ids 必须存在于 07_evidence.csv
        if ctx.strict_fk and evidence_id_set:
            missing = [e for e in row["evidence_ids"] if e not in evidence_id_set]
            if missing:
                raise CompileError(
                    f"断 FK / dangling evidence_id pack={row['pack_id']} missing={missing}"
                )

        # 默认过滤 inactive
        if row["gate_status"] != "active" and not ctx.include_inactive:
            filtered_inactive += 1
            continue

        errs = validate_row_schema(row, schema)
        if errs:
            schema_errors.append(f"{fp.name}: {'; '.join(errs)}")
            continue

        rows.append(row)

    if schema_errors:
        raise CompileError(
            f"schema 校验失败 / schema validation failed (count={len(schema_errors)})\n  "
            + "\n  ".join(schema_errors[:5])
        )

    # 幂等排序：按 pack_id 字典序
    rows.sort(key=lambda r: r["pack_id"])

    # 写 CSV
    ctx.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with ctx.output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=CSV_COLUMNS,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(row_to_csv_dict(r))

    csv_sha256 = _sha256_bytes(ctx.output_csv.read_bytes())

    report = {
        "task_card": "KS-COMPILER-001",
        "candidates_scanned": len(files),
        "rows_emitted": len(rows),
        "filtered_inactive": filtered_inactive,
        "include_inactive": ctx.include_inactive,
        "strict_fk": ctx.strict_fk,
        "source_manifest_hash": source_manifest_hash,
        "view_schema_version": view_schema_version,
        "compile_run_id": compile_run_id,
        "output_csv": _safe_relative(ctx.output_csv),
        "output_csv_sha256": csv_sha256,
    }

    return report


def write_log(report: dict[str, Any], log_path: Path, *, ok: bool, message: str = "") -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": ok,
        "message": message,
        **report,
    }
    log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_context(args: argparse.Namespace) -> CompileContext:
    return CompileContext(
        candidates_dir=Path(args.candidates_dir).resolve(),
        nine_tables_dir=Path(args.nine_tables_dir).resolve(),
        manifest_path=Path(args.manifest).resolve(),
        schema_path=Path(args.schema).resolve(),
        output_csv=Path(args.output).resolve(),
        log_path=Path(args.log).resolve(),
        include_inactive=args.include_inactive,
        strict_fk=not args.no_fk_check,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="KS-COMPILER-001 · 编译 pack_view 服务读模型 / compile pack_view serving view"
    )
    parser.add_argument("--check", action="store_true", help="CI 默认入口 / CI entrypoint")
    parser.add_argument("--candidates-dir", default=str(DEFAULT_CANDIDATES_DIR))
    parser.add_argument("--nine-tables-dir", default=str(DEFAULT_NINE_TABLES_DIR))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--log", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--include-inactive", action="store_true", help="包含非 active pack")
    parser.add_argument("--no-fk-check", action="store_true", help="跳过 evidence FK 检查")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    ctx = build_context(args)
    try:
        report = compile_pack_view(ctx)
    except CompileError as e:
        write_log({"task_card": "KS-COMPILER-001"}, ctx.log_path, ok=False, message=str(e))
        logger.error("compile failed: %s", e)
        return 2
    except Exception as e:  # noqa: BLE001
        write_log({"task_card": "KS-COMPILER-001"}, ctx.log_path, ok=False, message=f"unexpected: {e}")
        logger.exception("unexpected error")
        return 3

    write_log(report, ctx.log_path, ok=True)
    if report["rows_emitted"] == 0:
        logger.warning("emitted 0 rows (candidates_scanned=%d)", report["candidates_scanned"])
    logger.info(
        "pack_view emitted rows=%d filtered_inactive=%d sha256=%s",
        report["rows_emitted"],
        report["filtered_inactive"],
        report["output_csv_sha256"][:12],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

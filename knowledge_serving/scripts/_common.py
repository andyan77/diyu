"""
knowledge_serving/scripts/_common.py · 6 个 view 编译器共享基础设施
shared compile-time helpers for the 6 W3 view compilers (KS-COMPILER-001/002/004/005/006/007).

不调 LLM；只做幂等纯函数。
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATES_DIR = REPO_ROOT / "clean_output" / "candidates"
DEFAULT_NINE_TABLES_DIR = REPO_ROOT / "clean_output" / "nine_tables"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "clean_output" / "audit" / "source_manifest.json"
DEFAULT_SCHEMA_PATH = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"
DEFAULT_CONTROL_DIR = REPO_ROOT / "knowledge_serving" / "control"
DEFAULT_VIEWS_DIR = REPO_ROOT / "knowledge_serving" / "views"
DEFAULT_AUDIT_DIR = REPO_ROOT / "knowledge_serving" / "audit"

BRAND_LAYER_RE = re.compile(r"^(domain_general|needs_review|brand_[a-z][a-z0-9_]*)$")
GRANULARITY_ENUM = {"L1", "L2", "L3"}
GATE_STATUS_ENUM = {"active", "draft", "deprecated", "frozen"}
REVIEW_STATUS_ENUM = {"approved", "pending_review", "needs_review", "rejected"}
TRACEABILITY_ENUM = {"full", "partial", "weak", "missing"}

GOVERNANCE_FIELDS = [
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
]


class CompileError(Exception):
    """已记录上下文的可控编译错误 / compile-time controlled error."""


# ---------- hashing ----------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


# ---------- schema-version / run id ----------

def derive_view_schema_version(schema_path: Path) -> str:
    """view_schema_version = sha256(schema_file)[:12]，schema 漂移即版本变。"""
    return sha256_bytes(schema_path.read_bytes())[:12]


def derive_compile_run_id(source_manifest_hash: str, view_schema_version: str) -> str:
    raw = f"{source_manifest_hash}|{view_schema_version}".encode("utf-8")
    return sha256_bytes(raw)[:16]


# ---------- manifest ----------

def load_manifest_hash(manifest_path: Path) -> str:
    if not manifest_path.exists():
        raise CompileError(f"source_manifest 不存在 / missing: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    h = data.get("manifest_hash")
    if not isinstance(h, str) or not h:
        raise CompileError("source_manifest.manifest_hash 缺失 / missing")
    return h


# ---------- evidence FK ----------

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


# ---------- projection shapes ----------

def entry_id(entry: Any, *id_keys: str) -> str:
    """projection 行有两种形态：dict 或裸字符串。统一取 id。"""
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        for k in id_keys:
            v = entry.get(k)
            if v:
                return str(v).strip()
    return ""


# ---------- jsonschema view-level validation ----------

def build_view_validator(schema: dict, view_def_name: str) -> Draft202012Validator:
    """Build a Draft 2020-12 validator merging governance_common_fields + view_def_name."""
    return Draft202012Validator({
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "allOf": [
            {"$ref": "#/$defs/governance_common_fields"},
            {"$ref": f"#/$defs/{view_def_name}"},
        ],
    })


def validate_row(validator: Draft202012Validator, row: dict[str, Any]) -> list[str]:
    errors = sorted(validator.iter_errors(row), key=lambda e: list(e.path))
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in errors
    ]


# ---------- CSV row serialization ----------

def row_to_csv_dict(row: dict[str, Any], columns: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for col in columns:
        v = row[col]
        if isinstance(v, list):
            out[col] = json.dumps(v, ensure_ascii=False, sort_keys=False)
        elif isinstance(v, dict):
            out[col] = json.dumps(v, ensure_ascii=False, sort_keys=True)
        elif isinstance(v, bool):
            out[col] = "true" if v else "false"
        elif v is None:
            out[col] = ""
        else:
            out[col] = str(v)
    return out


def write_csv(output_csv: Path, columns: list[str], rows: Iterable[dict[str, Any]]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=columns,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(row_to_csv_dict(r, columns))


# ---------- audit log ----------

def safe_relative(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def _git_commit() -> str:
    try:
        import subprocess
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return "unknown"


def write_log(report: dict[str, Any], log_path: Path, *, ok: bool, message: str = "") -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    import datetime as _dt
    governance = {
        "checked_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "env": "local",
        "git_commit": _git_commit(),
        "evidence_level": "runtime_verified" if ok else "runtime_verified_fail",
    }
    payload = {"ok": ok, "message": message, **governance, **report}
    log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------- governance row builder ----------

@dataclass
class GovernanceContext:
    compile_run_id: str
    source_manifest_hash: str
    view_schema_version: str


def make_governance(
    *,
    source_pack_id: str,
    brand_layer: str,
    granularity_layer: str,
    gate_status: str,
    source_table_refs: list[str],
    evidence_ids: list[str],
    traceability_status: str,
    default_call_pool: bool,
    review_status: str,
    ctx: GovernanceContext,
    chunk_text_hash: str,
) -> dict[str, Any]:
    if not BRAND_LAYER_RE.match(brand_layer):
        raise CompileError(f"非法 brand_layer / invalid: {brand_layer!r} (source_pack_id={source_pack_id})")
    if granularity_layer not in GRANULARITY_ENUM:
        raise CompileError(f"非法 granularity_layer: {granularity_layer!r} (id={source_pack_id})")
    if gate_status not in GATE_STATUS_ENUM:
        raise CompileError(f"非法 gate_status: {gate_status!r} (id={source_pack_id})")
    if traceability_status not in TRACEABILITY_ENUM:
        raise CompileError(f"非法 traceability_status: {traceability_status!r} (id={source_pack_id})")
    if review_status not in REVIEW_STATUS_ENUM:
        raise CompileError(f"非法 review_status: {review_status!r} (id={source_pack_id})")
    return {
        "source_pack_id": source_pack_id,
        "brand_layer": brand_layer,
        "granularity_layer": granularity_layer,
        "gate_status": gate_status,
        "source_table_refs": source_table_refs,
        "evidence_ids": evidence_ids,
        "traceability_status": traceability_status,
        "default_call_pool": default_call_pool,
        "review_status": review_status,
        "compile_run_id": ctx.compile_run_id,
        "source_manifest_hash": ctx.source_manifest_hash,
        "view_schema_version": ctx.view_schema_version,
        "chunk_text_hash": chunk_text_hash,
    }

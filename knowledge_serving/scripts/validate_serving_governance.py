#!/usr/bin/env python3
"""
KS-COMPILER-013 · validate_serving_governance.py

治理总闸 / governance super-gate：在 W3+W4 编译产物之上跑 plan §12 的 S1-S7 七道门。
只读、跨表、fail-closed；不调 LLM；不写 clean_output；不修任何 view/control 产物。

退出码 / exit codes:
  0  S1-S7 全绿 / all gates pass
  2  任一 S 门 fail / any gate fails
  3  内部 schema 校验失败 / schema validation failed
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import glob
import json
import logging
import sys
from pathlib import Path, PurePosixPath
from typing import Any

# 复用 _common 共享枚举（与本目录同级，导入路径 trick）/ reuse shared enums
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    BRAND_LAYER_RE,
    DEFAULT_AUDIT_DIR,
    DEFAULT_CONTROL_DIR,
    DEFAULT_VIEWS_DIR,
    GATE_STATUS_ENUM,
    GOVERNANCE_FIELDS,
    GRANULARITY_ENUM,
    REPO_ROOT,
    REVIEW_STATUS_ENUM,
    TRACEABILITY_ENUM,
    build_view_validator,
    derive_compile_run_id,
    derive_view_schema_version,
    load_manifest_hash,
    validate_row,
)

# 共享 schema 路径（preflight + #3 governance ID 重算所需）
DEFAULT_SERVING_SCHEMA_PATH = REPO_ROOT / "knowledge_serving" / "schema" / "serving_views.schema.json"
DEFAULT_CONTROL_SCHEMA_PATH = REPO_ROOT / "knowledge_serving" / "schema" / "control_tables.schema.json"

# View name → schema $defs 内的定义名（1:1 同名）
VIEW_SCHEMA_DEFS = {
    "pack_view": "pack_view",
    "content_type_view": "content_type_view",
    "play_card_view": "play_card_view",
    "runtime_asset_view": "runtime_asset_view",
    "brand_overlay_view": "brand_overlay_view",
    "evidence_view": "evidence_view",
    "generation_recipe_view": "generation_recipe_view",
}

# Control table → schema $defs 内的定义名（control_tables.schema.json 当前不带 governance_common_fields，
# 因此 control 不通过 build_view_validator 走 view-级 allOf；走原始 $defs 节点直接校验）
CONTROL_SCHEMA_DEFS = {
    "field_requirement_matrix": "field_requirement_matrix",
    "retrieval_policy_view": "retrieval_policy_view",
    "merge_precedence_policy": "merge_precedence_policy",
    "tenant_scope_registry": "tenant_scope_registry",
    "context_bundle_log": "context_bundle_log",
}

DEFAULT_MANIFEST_PATH = REPO_ROOT / "clean_output" / "audit" / "source_manifest.json"
DEFAULT_REPORT_PATH = DEFAULT_AUDIT_DIR / "validate_serving_governance.report"

# 7 view 名（顺序固定，便于 report 复现）/ 7 views fixed order
VIEW_NAMES = [
    "pack_view",
    "content_type_view",
    "play_card_view",
    "runtime_asset_view",
    "brand_overlay_view",
    "evidence_view",
    "generation_recipe_view",
]

# S1 反查分层 / S1 lookup tiers
# 真候选 view：source_pack_id 必须能反查 clean_output/candidates/**/*.yaml
S1_RESOLVE_REQUIRED_VIEWS = {
    "pack_view",
    "play_card_view",
    "runtime_asset_view",
    "brand_overlay_view",
    "evidence_view",
}
# 合成 ID view：source_pack_id 是 W3/W4 编译器有意合成的自身标识，免反查；额外强校验前缀
S1_SYNTHETIC_ID_VIEWS = {
    "content_type_view",
    "generation_recipe_view",
}
S1_SYNTHETIC_PREFIX = {
    "content_type_view": "CT-",
    "generation_recipe_view": "RECIPE-",
}

# S2 默认池规约：gate_status=active 允许；非 active 行 review_status 必须显式 include
S2_NON_ACTIVE_INCLUDE_REVIEW = {"approved", "pending_review"}

# 可空字段（governance 13 字段中允许空字符串的列）/ nullable governance cols
GOVERNANCE_NULLABLE = {"source_table_refs", "evidence_ids"}


# ---------- 工具 / helpers ----------

def _read_csv(path: Path) -> list[dict[str, str]]:
    """fail-closed: 缺文件 / 不可读 / 损坏均向上抛 / raise."""
    if not path.exists():
        raise FileNotFoundError(f"输入缺失 / missing input: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def _build_candidate_index(candidates_root: Path) -> set[str]:
    """一次扫盘建 pack_id 索引（文件名 stem）/ build index once."""
    if not candidates_root.exists():
        return set()
    return {Path(p).stem for p in glob.glob(str(candidates_root / "**" / "*.yaml"), recursive=True)}


def _resolve_source_md_parts(source_md: str) -> list[str]:
    """9 表多文件聚合解析 / multi-file source_md parsing.

    格式 / format: "dir/file1.md & file2.md & file3.md"
    第 1 段含完整相对路径；第 2/3+ 段省略目录，继承第 1 段的目录前缀。
    返回完整相对路径列表（相对仓库根）。空字符串返回空列表（由调用方判 fail）。
    """
    if not source_md or not source_md.strip():
        return []
    raw_parts = [p.strip() for p in source_md.split(" & ") if p.strip()]
    if not raw_parts:
        return []
    first = raw_parts[0]
    base_dir = str(PurePosixPath(first).parent)  # e.g. "Q2-内容类型种子" or "."
    resolved = [first]
    for p in raw_parts[1:]:
        if "/" in p:
            resolved.append(p)
        else:
            resolved.append(f"{base_dir}/{p}" if base_dir not in (".", "") else p)
    return resolved


# ---------- 跨门：governance 13 字段一致性 ----------

def _validate_governance_row(row: dict[str, str], view_name: str, row_idx: int) -> list[str]:
    """13 governance 字段每行存在、非可空字段非空、枚举合法。"""
    violations: list[str] = []
    for col in GOVERNANCE_FIELDS:
        if col not in row:
            violations.append(f"{view_name}[{row_idx}] 缺字段 / missing col: {col}")
            continue
        val = (row.get(col) or "").strip()
        if not val and col not in GOVERNANCE_NULLABLE:
            violations.append(f"{view_name}[{row_idx}] 空值 / empty: {col}")
    # 枚举（不强制 brand_layer——S3 负责）
    gl = (row.get("granularity_layer") or "").strip()
    if gl and gl not in GRANULARITY_ENUM:
        violations.append(f"{view_name}[{row_idx}] granularity_layer 非法 / invalid: {gl!r}")
    gs = (row.get("gate_status") or "").strip()
    if gs and gs not in GATE_STATUS_ENUM:
        violations.append(f"{view_name}[{row_idx}] gate_status 非法: {gs!r}")
    ts = (row.get("traceability_status") or "").strip()
    if ts and ts not in TRACEABILITY_ENUM:
        violations.append(f"{view_name}[{row_idx}] traceability_status 非法: {ts!r}")
    rs = (row.get("review_status") or "").strip()
    if rs and rs not in REVIEW_STATUS_ENUM:
        violations.append(f"{view_name}[{row_idx}] review_status 非法: {rs!r}")
    return violations


# ---------- preflight schema 校验（post-audit finding #1） ----------

def _coerce_cell(value: str, prop_schema: dict[str, Any]) -> Any:
    """根据 schema 字段类型把 csv string cell 转回原 type。

    schema 校验用 jsonschema，type=array/object/boolean/integer/number 期望 native；
    csv 全是字符串，必须先反序列化再校验，否则会出 spurious type 错。
    """
    t = prop_schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), t[0] if t else None)
    if value == "":
        if t == "array":
            return []
        if t == "object":
            return {}
        return value  # 空字符串交给 schema enum/minLength 等约束兜底
    if t in ("array", "object"):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value  # 让 schema 报 type mismatch
    if t == "boolean":
        if value == "true":
            return True
        if value == "false":
            return False
        return value
    if t == "integer":
        try:
            return int(value)
        except ValueError:
            return value
    if t == "number":
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _typed_row(raw_row: dict[str, str], schema_doc: dict[str, Any], def_name: str) -> dict[str, Any]:
    """从 csv str → schema-typed dict。governance_common_fields 自动合并。"""
    defs = schema_doc.get("$defs", {}) or {}
    target_def = defs.get(def_name, {})
    gcf = defs.get("governance_common_fields", {}) if "governance_common_fields" in defs else {}
    all_props: dict[str, Any] = {}
    all_props.update(gcf.get("properties", {}) or {})
    all_props.update(target_def.get("properties", {}) or {})
    typed: dict[str, Any] = {}
    for k, v in raw_row.items():
        ps = all_props.get(k)
        if ps is None:
            typed[k] = v
        else:
            typed[k] = _coerce_cell(v, ps)
    return typed


def _validate_against_def(schema_doc: dict[str, Any], def_name: str, has_governance: bool):
    """构造一个独立 Validator：control 表无 governance；view 表合并 governance_common_fields."""
    from jsonschema import Draft202012Validator
    if has_governance:
        return build_view_validator(schema_doc, def_name)
    return Draft202012Validator({
        "$schema": schema_doc["$schema"],
        "$defs": schema_doc["$defs"],
        "$ref": f"#/$defs/{def_name}",
    })


def check_preflight_schema(
    views: dict[str, list[dict[str, str]]],
    controls: dict[str, list[dict[str, str]]],
    serving_schema_path: Path = DEFAULT_SERVING_SCHEMA_PATH,
    control_schema_path: Path = DEFAULT_CONTROL_SCHEMA_PATH,
) -> dict[str, Any]:
    """preflight schema_validation: 逐行 jsonschema 校验 7 view + 5 control。

    finding #1 守门：必填列缺失 / 类型错 / 枚举越界都必须在此 fail-closed，
    不允许下游 S1-S7 在结构坏的产物上"绿"。
    """
    violations: list[str] = []
    checked = 0
    try:
        serving_schema = json.loads(serving_schema_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return {
            "name": "preflight schema_validation",
            "status": "fail",
            "checked_rows": 0,
            "violations": [f"serving schema load failed: {exc}"],
        }
    try:
        control_schema = json.loads(control_schema_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return {
            "name": "preflight schema_validation",
            "status": "fail",
            "checked_rows": 0,
            "violations": [f"control schema load failed: {exc}"],
        }

    for view_name in VIEW_NAMES:
        rows = views.get(view_name, [])
        if not rows:
            continue
        try:
            validator = _validate_against_def(serving_schema, VIEW_SCHEMA_DEFS[view_name], has_governance=True)
        except KeyError as exc:
            violations.append(f"{view_name}: schema $def 缺失 / missing def: {exc}")
            continue
        for i, raw in enumerate(rows):
            typed = _typed_row(raw, serving_schema, VIEW_SCHEMA_DEFS[view_name])
            errs = validate_row(validator, typed)
            checked += 1
            for e in errs:
                violations.append(f"{view_name}[{i}]: {e}")

    for ctl_name, def_name in CONTROL_SCHEMA_DEFS.items():
        rows = controls.get(ctl_name, [])
        if not rows:
            continue
        try:
            validator = _validate_against_def(control_schema, def_name, has_governance=False)
        except KeyError as exc:
            violations.append(f"{ctl_name}: schema $def 缺失: {exc}")
            continue
        for i, raw in enumerate(rows):
            typed = _typed_row(raw, control_schema, def_name)
            errs = validate_row(validator, typed)
            checked += 1
            for e in errs:
                violations.append(f"{ctl_name}[{i}]: {e}")

    # 报告列表上限：避免 100+ 错误压垮 report 可读性，超过 50 截断并标 truncated
    truncated = False
    if len(violations) > 50:
        truncated = True
        violations = violations[:50] + [f"... (truncated, total={len(violations)})"]

    return {
        "name": "preflight schema_validation",
        "status": "fail" if violations else "pass",
        "checked_rows": checked,
        "violations": violations,
        "truncated": truncated,
    }


# ---------- 7 道门 / 7 gates ----------

def _empty_input_fail(gate_name: str, missing_inputs: list[str]) -> dict[str, Any] | None:
    """post-audit finding #2: 空输入禁止静默 pass。

    每 S 门入口检查"必需输入是否非空"；任一必需输入为空 → 立即 fail-closed，
    不进入后续 per-row 检查（per-row 在 0 行下会 trivially 通过造成假绿）。
    返回 None 表示输入完整可继续；返回 dict 表示已 fail，调用者直接 return。
    """
    if missing_inputs:
        return {
            "name": gate_name,
            "status": "fail",
            "checked_rows": 0,
            "violations": [
                f"empty input: {v} (任务卡 §6 / post-audit #2: 禁止静默 pass)"
                for v in missing_inputs
            ],
        }
    return None


def _expected_governance_ids(
    manifest_path: Path,
    serving_schema_path: Path = DEFAULT_SERVING_SCHEMA_PATH,
) -> dict[str, str] | None:
    """post-audit finding #3: 重算 governance 链路 IDs，用于行级一致性比对。

    返回 {source_manifest_hash, view_schema_version, compile_run_id}；
    若 manifest 或 schema 缺失 / 解析失败 → 返回 None，由调用者把"无法重算"视为 S1 fail-closed。
    """
    try:
        mh = load_manifest_hash(manifest_path)
        vsv = derive_view_schema_version(serving_schema_path)
        crid = derive_compile_run_id(mh, vsv)
    except Exception:
        return None
    return {
        "source_manifest_hash": mh,
        "view_schema_version": vsv,
        "compile_run_id": crid,
    }


def check_s1_source_traceability(
    views: dict[str, list[dict[str, str]]],
    candidate_pack_ids: set[str],
    expected_ids: dict[str, str] | None = None,
) -> dict[str, Any]:
    """S1 source_traceability · 分层语义 / tiered semantics.

    所有 7 view 均必查 source_pack_id 非空；反查分两类：
      - 真候选 view（S1_RESOLVE_REQUIRED_VIEWS）：必须能反查 clean_output/candidates/**/<id>.yaml
      - 合成 ID view（S1_SYNTHETIC_ID_VIEWS）：source_pack_id 是 W3/W4 编译器有意合成的自身标识，
        免反查；额外强校验前缀（CT- / RECIPE-）防漂移
    额外门：content_type_view.source_pack_ids（复数列）若非空，每元素必须能反查；空 list 跳过。
    """
    # finding #2: 空输入禁止静默 pass（S1 需要全 7 view 至少各 1 行）
    missing = [v for v in VIEW_NAMES if not views.get(v)]
    if missing:
        empty = _empty_input_fail("S1 source_traceability", missing)
        if empty is not None:
            empty.update({
                "resolved_views_checked": 0,
                "synthetic_views_checked": 0,
                "plural_refs_checked": 0,
            })
            return empty

    # finding #3: 若无法重算 expected_ids → S1 fail-closed（manifest/schema 缺失等价 ID 不可信）
    if expected_ids is None:
        return {
            "name": "S1 source_traceability",
            "status": "fail",
            "checked_rows": 0,
            "resolved_views_checked": 0,
            "synthetic_views_checked": 0,
            "plural_refs_checked": 0,
            "violations": [
                "expected governance IDs unavailable (manifest or schema missing) — fail-closed"
            ],
        }

    violations: list[str] = []
    checked = 0
    resolved_checked = 0
    synthetic_checked = 0
    plural_refs_checked = 0
    id_mismatches = 0

    for view_name in VIEW_NAMES:
        rows = views.get(view_name, [])
        for idx, row in enumerate(rows):
            checked += 1
            # 跨门 governance 检查
            violations.extend(_validate_governance_row(row, view_name, idx))

            # finding #3: 治理链路 3 个 IDs 与重算值逐行比对
            for id_col in ("source_manifest_hash", "view_schema_version", "compile_run_id"):
                actual = (row.get(id_col) or "").strip()
                expected = expected_ids[id_col]
                if actual and actual != expected:
                    id_mismatches += 1
                    violations.append(
                        f"{view_name}[{idx}] {id_col} mismatch / governance ID mismatch: "
                        f"row={actual!r} expected={expected!r}"
                    )

            pid = (row.get("source_pack_id") or "").strip()
            if not pid:
                violations.append(f"{view_name}[{idx}] empty source_pack_id")
                continue

            if view_name in S1_RESOLVE_REQUIRED_VIEWS:
                resolved_checked += 1
                if pid not in candidate_pack_ids:
                    violations.append(
                        f"{view_name}[{idx}] orphan source_pack_id / 反查失败: {pid!r}"
                    )
            elif view_name in S1_SYNTHETIC_ID_VIEWS:
                synthetic_checked += 1
                expected_prefix = S1_SYNTHETIC_PREFIX[view_name]
                if not pid.startswith(expected_prefix):
                    violations.append(
                        f"{view_name}[{idx}] unexpected synthetic prefix: {pid!r} "
                        f"(expected '{expected_prefix}*')"
                    )
            # 防漏：view 未登记到任一分层 → 视为反查必查（保守 fail-closed）
            else:
                resolved_checked += 1
                if pid not in candidate_pack_ids:
                    violations.append(
                        f"{view_name}[{idx}] orphan source_pack_id / 反查失败: {pid!r}"
                    )

    # 额外门：content_type_view.source_pack_ids（复数列）
    for idx, row in enumerate(views.get("content_type_view", [])):
        raw = (row.get("source_pack_ids") or "").strip()
        if not raw:
            continue
        try:
            arr = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            violations.append(
                f"content_type_view[{idx}] malformed source_pack_ids (not JSON): {raw!r}"
            )
            continue
        if not isinstance(arr, list):
            violations.append(
                f"content_type_view[{idx}] malformed source_pack_ids (not JSON list): {raw!r}"
            )
            continue
        for el in arr:
            plural_refs_checked += 1
            el_id = str(el).strip() if el is not None else ""
            if not el_id:
                violations.append(
                    f"content_type_view[{idx}] plural source_pack_ids 含空元素 / empty element"
                )
                continue
            if el_id not in candidate_pack_ids:
                violations.append(
                    f"content_type_view[{idx}] plural source_pack_ids orphan: {el_id!r}"
                )

    return {
        "name": "S1 source_traceability",
        "status": "pass" if not violations else "fail",
        "checked_rows": checked,
        "resolved_views_checked": resolved_checked,
        "synthetic_views_checked": synthetic_checked,
        "plural_refs_checked": plural_refs_checked,
        "id_mismatches": id_mismatches,
        "violations": violations,
    }


def check_s2_gate_filter(views: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    """S2: 默认池只允许 gate_status=active；non-active 必须 review_status ∈ {approved, pending_review}."""
    # finding #2: 空输入禁止静默 pass
    missing = [v for v in VIEW_NAMES if not views.get(v)]
    if missing:
        empty = _empty_input_fail("S2 gate_filter", missing)
        if empty is not None:
            empty["gate_status_distribution"] = {}
            return empty
    violations: list[str] = []
    checked = 0
    dist: dict[str, dict[str, int]] = {}
    for view_name in VIEW_NAMES:
        rows = views.get(view_name, [])
        view_dist: dict[str, int] = {}
        for idx, row in enumerate(rows):
            checked += 1
            gs = (row.get("gate_status") or "").strip()
            view_dist[gs] = view_dist.get(gs, 0) + 1
            if gs == "active":
                continue
            if not gs:
                violations.append(f"{view_name}[{idx}] gate_status 空 / empty")
                continue
            rs = (row.get("review_status") or "").strip()
            if rs not in S2_NON_ACTIVE_INCLUDE_REVIEW:
                violations.append(
                    f"{view_name}[{idx}] non-active(gate_status={gs!r}) 未显式 include / review_status={rs!r}"
                )
        dist[view_name] = view_dist
    return {
        "name": "S2 gate_filter",
        "status": "pass" if not violations else "fail",
        "checked_rows": checked,
        "violations": violations,
        "gate_status_distribution": dist,
    }


def check_s3_brand_layer_scope(views: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    """S3: brand_layer ∈ BRAND_LAYER_RE；brand_overlay_view 严禁 domain_general."""
    # finding #2
    missing = [v for v in VIEW_NAMES if not views.get(v)]
    if missing:
        empty = _empty_input_fail("S3 brand_layer_scope", missing)
        if empty is not None:
            return empty
    violations: list[str] = []
    checked = 0
    for view_name in VIEW_NAMES:
        rows = views.get(view_name, [])
        for idx, row in enumerate(rows):
            checked += 1
            bl = (row.get("brand_layer") or "").strip()
            if not bl or not BRAND_LAYER_RE.match(bl):
                violations.append(f"{view_name}[{idx}] brand_layer 非法: {bl!r}")
                continue
            if view_name == "brand_overlay_view" and bl == "domain_general":
                violations.append(
                    f"brand_overlay_view[{idx}] 串味 / domain_general 不得入 overlay 视图"
                )
    return {
        "name": "S3 brand_layer_scope",
        "status": "pass" if not violations else "fail",
        "checked_rows": checked,
        "violations": violations,
    }


def check_s4_granularity_integrity(views: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    """S4: granularity_layer ∈ {L1,L2,L3}；空值视为 fail."""
    # finding #2
    missing = [v for v in VIEW_NAMES if not views.get(v)]
    if missing:
        empty = _empty_input_fail("S4 granularity_integrity", missing)
        if empty is not None:
            return empty
    violations: list[str] = []
    checked = 0
    for view_name in VIEW_NAMES:
        rows = views.get(view_name, [])
        for idx, row in enumerate(rows):
            checked += 1
            gl = (row.get("granularity_layer") or "").strip()
            if gl not in GRANULARITY_ENUM:
                violations.append(f"{view_name}[{idx}] granularity_layer 非法 / 空: {gl!r}")
    return {
        "name": "S4 granularity_integrity",
        "status": "pass" if not violations else "fail",
        "checked_rows": checked,
        "violations": violations,
    }


def check_s5_evidence_linkage(views: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    """S5: evidence_view 每行 source_md（多文件聚合解析后）所有段都在
    REPO_ROOT/clean_output 下真实存在。

    post-audit finding #5（真源补录后口径）:
      锚点 = REPO_ROOT / "clean_output" / <source_md>，**不**允许漂移到 REPO_ROOT。
      源 MD 已通过 scripts/ingest_source_md_to_clean_output.py 物理纳入
      clean_output/Q*/，43 minimum 范围；anchor 走 clean_output 是真源边界要求。
      历史漂移：早先 W3 KS-COMPILER-007 透传 9 表 repo-root-relative 路径，
      W5 第一版校验器漂移到 REPO_ROOT 锚点匹配数据 = "drift normalization" 反模式。
    """
    rows = views.get("evidence_view", [])
    # finding #2
    if not rows:
        return {
            "name": "S5 evidence_linkage",
            "status": "fail",
            "checked_rows": 0,
            "violations": [
                "empty input: evidence_view (任务卡 §6 / post-audit #2: 禁止静默 pass)"
            ],
        }
    violations: list[str] = []
    checked = len(rows)
    anchor = REPO_ROOT / "clean_output"
    for idx, row in enumerate(rows):
        sm = row.get("source_md") or ""
        parts = _resolve_source_md_parts(sm)
        if not parts:
            violations.append(f"evidence_view[{idx}] source_md 空 / empty")
            continue
        for p in parts:
            full = anchor / p
            if not full.is_file():
                violations.append(
                    f"evidence_view[{idx}] source_md 段缺失 / missing segment under "
                    f"clean_output/: {p!r} (raw={sm!r})"
                )
    return {
        "name": "S5 evidence_linkage",
        "status": "pass" if not violations else "fail",
        "checked_rows": checked,
        "violations": violations,
    }


def check_s6_play_card_completeness(views: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    """S6: play_card_view 每行 completeness_status 非空."""
    rows = views.get("play_card_view", [])
    # finding #2
    if not rows:
        return {
            "name": "S6 play_card_completeness",
            "status": "fail",
            "checked_rows": 0,
            "violations": [
                "empty input: play_card_view (任务卡 §6 / post-audit #2: 禁止静默 pass)"
            ],
        }
    violations: list[str] = []
    checked = len(rows)
    for idx, row in enumerate(rows):
        cs = (row.get("completeness_status") or "").strip()
        if not cs:
            violations.append(f"play_card_view[{idx}] completeness_status 空 / empty")
    return {
        "name": "S6 play_card_completeness",
        "status": "pass" if not violations else "fail",
        "checked_rows": checked,
        "violations": violations,
    }


def check_s7_fallback_policy_coverage(
    frm_rows: list[dict[str, str]],
    canonical_rows: list[dict[str, str]],
) -> dict[str, Any]:
    """S7: set(frm.content_type) == set(canonical.canonical_content_type_id)，严格相等."""
    violations: list[str] = []
    canonical_ids = sorted({(r.get("canonical_content_type_id") or "").strip()
                            for r in canonical_rows if (r.get("canonical_content_type_id") or "").strip()})
    frm_types = sorted({(r.get("content_type") or "").strip()
                        for r in frm_rows if (r.get("content_type") or "").strip()})
    missing_in_frm = sorted(set(canonical_ids) - set(frm_types))
    extra_in_frm = sorted(set(frm_types) - set(canonical_ids))
    if missing_in_frm:
        violations.append(f"frm 缺 canonical content_type: {missing_in_frm}")
    if extra_in_frm:
        violations.append(f"frm 多 extra content_type: {extra_in_frm}")
    return {
        "name": "S7 fallback_policy_coverage",
        "status": "pass" if not violations else "fail",
        "checked_rows": len(frm_rows),
        "violations": violations,
        "canonical_count": len(canonical_ids),
        "frm_count": len(frm_types),
    }


# ---------- 运行 / runner ----------

GATE_FUNCS = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]


def run_gates(
    selected: list[str],
    views_dir: Path,
    control_dir: Path,
    candidates_root: Path,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    run_preflight: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    """跑选中的门，返回 (results, exit_code_hint).

    preflight schema_validation 在 S1-S7 之前跑一次（覆盖 7 view + 5 control），
    failure 不阻断 S1-S7 继续跑（让 report 信息完整），但 final exit 非 0。
    """
    # 1. 加载 7 view csv（任一缺失 → 抛）
    views: dict[str, list[dict[str, str]]] = {}
    for v in VIEW_NAMES:
        views[v] = _read_csv(views_dir / f"{v}.csv")

    # 2. 加载 control（preflight + S7 都用；fail-closed 早读早抛）
    control_data: dict[str, list[dict[str, str]]] = {}
    for ctl_name in (
        "field_requirement_matrix",
        "content_type_canonical",
        "retrieval_policy_view",
        "merge_precedence_policy",
        "tenant_scope_registry",
        "context_bundle_log",
    ):
        ctl_path = control_dir / f"{ctl_name}.csv"
        if ctl_path.exists():
            control_data[ctl_name] = _read_csv(ctl_path)
        else:
            control_data[ctl_name] = []
    frm_rows = control_data.get("field_requirement_matrix", [])
    canonical_rows = control_data.get("content_type_canonical", [])

    # 3. 建 candidate pack_id 索引
    pack_index = _build_candidate_index(candidates_root)

    # 4. 重算 expected governance IDs（finding #3）
    expected_ids = _expected_governance_ids(manifest_path)

    results: list[dict[str, Any]] = []
    # preflight first（post-audit finding #1）
    if run_preflight:
        preflight = check_preflight_schema(
            views=views,
            controls=control_data,
        )
        results.append(preflight)

    for g in selected:
        if g == "S1":
            results.append(check_s1_source_traceability(views, pack_index, expected_ids))
        elif g == "S2":
            results.append(check_s2_gate_filter(views))
        elif g == "S3":
            results.append(check_s3_brand_layer_scope(views))
        elif g == "S4":
            results.append(check_s4_granularity_integrity(views))
        elif g == "S5":
            results.append(check_s5_evidence_linkage(views))
        elif g == "S6":
            results.append(check_s6_play_card_completeness(views))
        elif g == "S7":
            results.append(check_s7_fallback_policy_coverage(frm_rows, canonical_rows))
        else:
            raise ValueError(f"unknown gate: {g}")
    failed = any(r["status"] == "fail" for r in results)
    return results, (2 if failed else 0)


def write_report(
    report_path: Path,
    results: list[dict[str, Any]],
    compile_run_id: str | None,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# validate_serving_governance.report")
    lines.append(f"generated_at: {_dt.datetime.now(_dt.timezone.utc).isoformat()}")
    lines.append(f"compile_run_id: {compile_run_id or 'n/a'}")
    lines.append("")
    for r in results:
        lines.append(f"[{r['name']}]")
        lines.append(f"status: {r['status']}")
        lines.append(f"checked_rows: {r['checked_rows']}")
        if "resolved_views_checked" in r:
            lines.append(f"resolved_views_checked: {r['resolved_views_checked']}")
            lines.append(f"synthetic_views_checked: {r['synthetic_views_checked']}")
            lines.append(f"plural_refs_checked: {r['plural_refs_checked']}")
        if "id_mismatches" in r:
            lines.append(f"id_mismatches: {r['id_mismatches']}")
        if "gate_status_distribution" in r:
            lines.append(f"gate_status_distribution: {r['gate_status_distribution']}")
        if "canonical_count" in r:
            lines.append(f"canonical_count: {r['canonical_count']}")
            lines.append(f"frm_count: {r['frm_count']}")
        if r.get("truncated"):
            lines.append("truncated: true")
        vs = r.get("violations") or []
        if vs:
            lines.append("violations:")
            for v in vs:
                lines.append(f"  - {v}")
        else:
            lines.append("violations: ()")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W5 治理总闸 / governance super-gate (S1-S7)."
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="跑全部 S1-S7 / run all gates")
    g.add_argument("--gate", choices=GATE_FUNCS, help="跑单门 / run a single gate")
    parser.add_argument("--views-dir", type=Path, default=DEFAULT_VIEWS_DIR)
    parser.add_argument("--control-dir", type=Path, default=DEFAULT_CONTROL_DIR)
    parser.add_argument(
        "--candidates-root",
        type=Path,
        default=REPO_ROOT / "clean_output" / "candidates",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )
    log = logging.getLogger("validate_serving_governance")

    selected = GATE_FUNCS if args.all else [args.gate]

    # compile_run_id 取 manifest_hash 前 16；缺 manifest 不算 fail-closed（只是 report 标 n/a）
    compile_run_id: str | None = None
    try:
        if args.manifest.exists():
            mh = load_manifest_hash(args.manifest)
            compile_run_id = mh[:16]
    except Exception as exc:  # pragma: no cover
        log.warning("manifest 解析失败 / parse failure: %s", exc)

    try:
        results, exit_hint = run_gates(
            selected, args.views_dir, args.control_dir, args.candidates_root
        )
    except FileNotFoundError as exc:
        log.error("输入缺失 / missing input: %s", exc)
        return 3
    except (csv.Error, ValueError) as exc:
        log.error("schema/csv 错误 / schema-or-csv error: %s", exc)
        return 3

    write_report(args.report, results, compile_run_id)

    failed = [r["name"] for r in results if r["status"] == "fail"]
    if failed:
        log.error("[FAIL] 治理总闸未过 / gates failed: %s", failed)
        log.error("       详见 report / see: %s", args.report)
        return 2

    log.info("[OK] S1-S7 全绿 / all gates pass (report=%s)", args.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

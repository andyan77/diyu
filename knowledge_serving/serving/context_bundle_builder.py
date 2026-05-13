"""KS-RETRIEVAL-008 · context_bundle_builder.

13 步召回流程第 12 步：把 merge / fallback / governance / 候选打包成 LLM 可消费
context_bundle，按 schema 校验，输出可重放的 bundle_hash + user_query_hash。

边界 / scope:
- 不调 LLM
- 不写 log（log 写入由 log_writer.py 承担）
- user_query 明文绝不落 bundle；只暴露 user_query_hash（W8 隐私守门）
- merged_overlay_payload={} 时如实落空集，禁止占位（W8 外审守门）

入参 / inputs:
- 上游模块（KS-RETRIEVAL-007 merge_context / fallback_decider）输出对象透传
- governance 三件套（compile_run_id / source_manifest_hash / view_schema_version）由调用方
  从最新一份 serving view csv 头行读取（KS-COMPILER-013 保证全链路存在）

产出 / outputs:
- (bundle: dict, meta: dict) — bundle 已通过 schema 16 必填字段校验；
  meta 含 bundle_hash / user_query_hash / 用于 log_writer 的辅助字段。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "knowledge_serving" / "schema" / "context_bundle.schema.json"

_BRAND_LAYER_RE = re.compile(r"^(domain_general|needs_review|brand_[a-z][a-z0-9_]*)$")
_VALID_FALLBACK = {
    "brand_full_applied",
    "brand_partial_fallback",
    "domain_only",
    "blocked_missing_required_brand_fields",
    "blocked_missing_business_brief",
}
_VALID_INFERENCE = {
    "direct_quote",
    "paraphrase_high",
    "paraphrase_mid",
    "paraphrase_low",
    "inferred",
}
_VALID_TRACE_QUALITY = {"high", "mid", "low"}
_VALID_GRAN = {"L1", "L2", "L3"}

_REQUIRED_BUNDLE_FIELDS = [
    "request_id",
    "tenant_id",
    "resolved_brand_layer",
    "allowed_layers",
    "content_type",
    "recipe",
    "business_brief",
    "domain_packs",
    "play_cards",
    "runtime_assets",
    "brand_overlays",
    "evidence",
    "missing_fields",
    "fallback_status",
    "generation_constraints",
    "governance",
]

_REQUIRED_GOVERNANCE_FIELDS = [
    "gate_policy",
    "granularity_layers",
    "traceability_required",
    "compile_run_id",
    "source_manifest_hash",
    "view_schema_version",
]


class BundleValidationError(ValueError):
    """bundle 不满足 schema / 业务硬约束。"""


def _ensure_non_empty_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise BundleValidationError(f"{label} must be non-empty string, got {value!r}")
    return value


def _ensure_brand_layer(value: Any, label: str) -> str:
    s = _ensure_non_empty_str(value, label)
    if not _BRAND_LAYER_RE.match(s):
        raise BundleValidationError(f"{label}={s!r} 不符合 brand_layer 模式")
    return s


def hash_user_query(user_query: str) -> str:
    """user_query → sha256 hex。强制脱敏，避免明文落 bundle / log。"""
    if not isinstance(user_query, str):
        raise BundleValidationError("user_query must be a string")
    return "sha256:" + hashlib.sha256(user_query.encode("utf-8")).hexdigest()


def _canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_bundle_hash(bundle: dict[str, Any]) -> str:
    """bundle_hash = sha256(canonical_json(bundle))。

    bundle 内部所有字段都参与（包含 governance），且不含时间戳——保证
    同 request_id + 同上游输入 → 同 hash，满足 S8 回放一致性。
    """
    return "sha256:" + hashlib.sha256(_canonical_dumps(bundle).encode("utf-8")).hexdigest()


def _load_schema(schema_path: Path | None) -> dict:
    path = schema_path or DEFAULT_SCHEMA_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_evidence_item(item: dict, idx: int) -> None:
    if not isinstance(item, dict):
        raise BundleValidationError(f"evidence[{idx}] must be dict")
    eid = item.get("evidence_id")
    if not isinstance(eid, str) or not eid:
        raise BundleValidationError(f"evidence[{idx}].evidence_id required non-empty string")
    inf = item.get("inference_level")
    if inf is not None and inf not in _VALID_INFERENCE:
        raise BundleValidationError(f"evidence[{idx}].inference_level={inf!r} invalid")
    tq = item.get("trace_quality")
    if tq is not None and tq not in _VALID_TRACE_QUALITY:
        raise BundleValidationError(f"evidence[{idx}].trace_quality={tq!r} invalid")
    bl = item.get("brand_layer")
    if bl is not None:
        _ensure_brand_layer(bl, f"evidence[{idx}].brand_layer")


def _validate_governance(gov: Any) -> None:
    if not isinstance(gov, dict):
        raise BundleValidationError("governance must be dict")
    for f in _REQUIRED_GOVERNANCE_FIELDS:
        if f not in gov:
            raise BundleValidationError(f"governance missing required field: {f}")
    if not isinstance(gov["traceability_required"], bool):
        raise BundleValidationError("governance.traceability_required must be bool")
    grans = gov["granularity_layers"]
    if not isinstance(grans, list) or any(g not in _VALID_GRAN for g in grans):
        raise BundleValidationError(f"governance.granularity_layers invalid: {grans!r}")
    for f in ("gate_policy", "compile_run_id", "source_manifest_hash", "view_schema_version"):
        _ensure_non_empty_str(gov[f], f"governance.{f}")


def validate_bundle(bundle: dict[str, Any], schema_path: Path | None = None) -> None:
    """对 bundle 做 schema + 业务硬约束校验；失败抛 BundleValidationError。

    校验项覆盖 context_bundle.schema.json 全部 required + $defs。
    """
    if not isinstance(bundle, dict):
        raise BundleValidationError("bundle must be dict")
    for f in _REQUIRED_BUNDLE_FIELDS:
        if f not in bundle:
            raise BundleValidationError(f"bundle missing required field: {f}")

    _ensure_non_empty_str(bundle["request_id"], "request_id")
    _ensure_non_empty_str(bundle["tenant_id"], "tenant_id")
    _ensure_brand_layer(bundle["resolved_brand_layer"], "resolved_brand_layer")

    allowed = bundle["allowed_layers"]
    if not isinstance(allowed, list) or not allowed:
        raise BundleValidationError("allowed_layers must be non-empty list")
    for layer in allowed:
        _ensure_brand_layer(layer, "allowed_layers item")

    _ensure_non_empty_str(bundle["content_type"], "content_type")

    if not isinstance(bundle["recipe"], dict):
        raise BundleValidationError("recipe must be dict")
    if not isinstance(bundle["business_brief"], dict):
        raise BundleValidationError("business_brief must be dict")

    for f in ("domain_packs", "play_cards", "runtime_assets", "brand_overlays"):
        if not isinstance(bundle[f], list):
            raise BundleValidationError(f"{f} must be list")
        for i, item in enumerate(bundle[f]):
            if not isinstance(item, dict):
                raise BundleValidationError(f"{f}[{i}] must be dict")

    evid = bundle["evidence"]
    if not isinstance(evid, list):
        raise BundleValidationError("evidence must be list")
    for i, item in enumerate(evid):
        _validate_evidence_item(item, i)

    mf = bundle["missing_fields"]
    if not isinstance(mf, list) or any(not isinstance(x, str) for x in mf):
        raise BundleValidationError("missing_fields must be list[str]")

    fs = bundle["fallback_status"]
    if fs not in _VALID_FALLBACK:
        raise BundleValidationError(f"fallback_status={fs!r} not in {_VALID_FALLBACK}")

    gc = bundle["generation_constraints"]
    if not isinstance(gc, list) or any(not isinstance(x, str) for x in gc):
        raise BundleValidationError("generation_constraints must be list[str]")

    _validate_governance(bundle["governance"])

    # 隐私守门：bundle 任何顶层字段都不许直接暴露 user_query 明文。
    # 我们不存 user_query 在 bundle 中（只存 hash 落 log），这里防回归。
    if "user_query" in bundle:
        raise BundleValidationError(
            "bundle 不允许出现明文 user_query 字段；只能通过 user_query_hash 落 log"
        )


def _build_governance(governance: dict[str, Any]) -> dict[str, Any]:
    """governance 三件套 + 元字段必须全部由调用方显式提供；缺字段 = 立刻 raise，
    禁止默认值（卡 §7 治理一致性 / W8 守门）。"""
    for f in _REQUIRED_GOVERNANCE_FIELDS:
        if f not in governance:
            raise BundleValidationError(f"governance missing required field: {f}")
    return {
        "gate_policy": governance["gate_policy"],
        "granularity_layers": list(governance["granularity_layers"]),
        "traceability_required": governance["traceability_required"],
        "compile_run_id": governance["compile_run_id"],
        "source_manifest_hash": governance["source_manifest_hash"],
        "view_schema_version": governance["view_schema_version"],
    }


def build_context_bundle(
    *,
    request_id: str,
    tenant_id: str,
    resolved_brand_layer: str,
    allowed_layers: list[str],
    user_query: str,
    content_type: str,
    recipe: dict | None,
    business_brief: dict | None,
    merge_result: dict,
    fallback_decision: dict,
    governance: dict,
    schema_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """构造 context_bundle + 计算 bundle_hash / user_query_hash。

    参数对应 13 步召回流程的上游输出：
      - merge_result: KS-RETRIEVAL-007 merge_context() 返回
      - fallback_decision: KS-RETRIEVAL-007 decide_fallback() 返回（FallbackDecision dict）
      - governance: {gate_policy, granularity_layers, traceability_required,
                     compile_run_id, source_manifest_hash, view_schema_version}

    返回:
      (bundle, meta)
        bundle: 16 必填字段，已过 schema 校验
        meta:   {
          "bundle_hash":     str,
          "user_query_hash": str,
          "merged_overlay_payload_empty": bool,  # W8 守门标记
        }
    """
    if not isinstance(merge_result, dict):
        raise BundleValidationError("merge_result must be dict")
    if not isinstance(fallback_decision, dict):
        raise BundleValidationError("fallback_decision must be dict")
    if not isinstance(governance, dict):
        raise BundleValidationError("governance must be dict")

    structured = merge_result.get("structured_candidates") or {}
    vector_cands = merge_result.get("vector_candidates") or []

    domain_packs = list(structured.get("pack_view") or [])
    play_cards = list(structured.get("play_card_view") or [])
    runtime_assets = list(structured.get("runtime_asset_view") or [])

    # brand_overlays: 透传 overlay 候选；merged_payload 单独嵌在每个 overlay 行的
    # _merged_payload 字段里（W8 守门：空 payload 如实落空 dict，禁止占位）。
    overlay_layers = merge_result.get("_meta", {}).get("overlay_layers_seen", [])
    merged_payload = merge_result.get("merged_overlay_payload") or {}
    brand_overlays: list[dict] = []
    if overlay_layers or merged_payload:
        brand_overlays.append(
            {
                "merged_overlay_payload": merged_payload,
                "overlay_layers_seen": overlay_layers,
                "precedence_rule": merge_result.get("_meta", {}).get(
                    "precedence_rule", "brand_<name> > domain_general"
                ),
            }
        )

    # evidence: 从 structured + vector 候选里抽取携带 evidence_id 的项；
    # 不调 LLM，不构造新 evidence。
    evidence: list[dict] = []
    seen_evidence: set[str] = set()
    for src in (domain_packs, play_cards, runtime_assets):
        for row in src:
            eid = row.get("evidence_id") if isinstance(row, dict) else None
            if isinstance(eid, str) and eid and eid not in seen_evidence:
                evidence.append({"evidence_id": eid})
                seen_evidence.add(eid)
    for v in vector_cands:
        pl = (v or {}).get("payload") or {}
        eid = pl.get("evidence_id")
        if isinstance(eid, str) and eid and eid not in seen_evidence:
            evidence.append({"evidence_id": eid, "brand_layer": pl.get("brand_layer")})
            seen_evidence.add(eid)

    # missing_fields / fallback_status / generation_constraints from fallback_decision
    fb_status = fallback_decision.get("status")
    if fb_status not in _VALID_FALLBACK:
        raise BundleValidationError(
            f"fallback_decision.status={fb_status!r} not in {_VALID_FALLBACK}"
        )
    missing_fields = list(fallback_decision.get("missing_fields") or [])
    output_strategy = fallback_decision.get("output_strategy") or {}
    constraints = list(output_strategy.get("constraints") or [])

    bundle = {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "resolved_brand_layer": resolved_brand_layer,
        "allowed_layers": list(allowed_layers),
        "content_type": content_type,
        "recipe": dict(recipe or {}),
        "business_brief": dict(business_brief or {}),
        "domain_packs": domain_packs,
        "play_cards": play_cards,
        "runtime_assets": runtime_assets,
        "brand_overlays": brand_overlays,
        "evidence": evidence,
        "missing_fields": missing_fields,
        "fallback_status": fb_status,
        "generation_constraints": constraints,
        "governance": _build_governance(governance),
    }

    validate_bundle(bundle, schema_path=schema_path)

    meta = {
        "bundle_hash": compute_bundle_hash(bundle),
        "user_query_hash": hash_user_query(user_query),
        "merged_overlay_payload_empty": not bool(merged_payload),
    }
    return bundle, meta

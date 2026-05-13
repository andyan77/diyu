"""KS-RETRIEVAL-007 · fallback_decider / 降级决策（§6.11 第 11 步）.

W8 波次实现。按 KS-POLICY-001 fallback_policy.yaml 五状态枚举 + evaluation_pipeline
决策最终 fallback_status。

硬纪律 / hard rules:
- no_llm_in_decision: 严禁 LLM；只走结构化 status 输入
- 五状态枚举严格闭合，不许新增 / 改名
- evaluation_pipeline 顺序：
    1. business_brief_status missing → blocked_missing_business_brief（最高优先）
    2. brand_required_fields_status missing → blocked_missing_required_brand_fields
    3. brand_overlay_resolved false → domain_only
    4. brand_soft_fields_status partial_missing → brand_partial_fallback
       brand_soft_fields_status complete → brand_full_applied
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

__all__ = ["decide_fallback", "FallbackDecision", "FALLBACK_STATES"]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = (
    REPO_ROOT / "knowledge_serving" / "policies" / "fallback_policy.yaml"
)

FALLBACK_STATES = (
    "brand_full_applied",
    "brand_partial_fallback",
    "domain_only",
    "blocked_missing_required_brand_fields",
    "blocked_missing_business_brief",
)

# 允许的字段状态枚举（来自 fallback_policy）
_BRIEF_ENUM = {"complete", "missing"}
_REQUIRED_ENUM = {"complete", "missing", "not_applicable"}
_SOFT_ENUM = {"complete", "partial_missing", "not_applicable"}


class FallbackDecision(dict):
    """fallback 决策结果：含 status + output_strategy + downstream_signal."""


def _load_policy(policy_path: Path | None) -> dict:
    path = Path(policy_path) if policy_path else DEFAULT_POLICY_PATH
    if not path.exists():
        raise FileNotFoundError(f"fallback_policy 缺失 / missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not data.get("states"):
        raise RuntimeError("fallback_policy.states 缺失")
    if not data.get("no_llm_in_decision", False):
        raise RuntimeError("fallback_policy.no_llm_in_decision 必须为 true")
    return data


def _state_by_name(policy: dict, name: str) -> dict:
    for s in policy["states"]:
        if s.get("name") == name:
            return s
    raise KeyError(f"fallback_policy.states 缺 {name}")


def _validate_inputs(
    *,
    business_brief_status: str,
    brand_required_fields_status: str,
    brand_soft_fields_status: str,
    brand_overlay_resolved: bool,
) -> None:
    if business_brief_status not in _BRIEF_ENUM:
        raise ValueError(
            f"business_brief_status 非法：{business_brief_status!r}，必须 ∈ {_BRIEF_ENUM}"
        )
    if brand_required_fields_status not in _REQUIRED_ENUM:
        raise ValueError(
            f"brand_required_fields_status 非法：{brand_required_fields_status!r}，"
            f"必须 ∈ {_REQUIRED_ENUM}"
        )
    if brand_soft_fields_status not in _SOFT_ENUM:
        raise ValueError(
            f"brand_soft_fields_status 非法：{brand_soft_fields_status!r}，必须 ∈ {_SOFT_ENUM}"
        )
    if not isinstance(brand_overlay_resolved, bool):
        raise ValueError("brand_overlay_resolved 必须为 bool")


def decide_fallback(
    *,
    business_brief_status: str,
    brand_required_fields_status: str,
    brand_soft_fields_status: str,
    brand_overlay_resolved: bool,
    policy_path: Path | None = None,
) -> FallbackDecision:
    """13 步召回流程第 11 步：降级决策。

    Args:
        business_brief_status: 'complete' / 'missing'（来自 business_brief_checker）
        brand_required_fields_status: 'complete' / 'missing' / 'not_applicable'
            （来自 requirement_checker 对 required_level=hard 字段的判定）
        brand_soft_fields_status: 'complete' / 'partial_missing' / 'not_applicable'
            （来自 requirement_checker 对 required_level=soft 字段的判定）
        brand_overlay_resolved: True/False（来自 brand_overlay_retrieve._meta）

    Returns:
        FallbackDecision dict:
            - status: 五状态之一
            - output_strategy: policy 中的 strategy block
            - downstream_signal: policy 中的 signal block（log_marker / alert）
            - is_blocking / severity
            - evaluation_trace: 决策路径记录
    """
    _validate_inputs(
        business_brief_status=business_brief_status,
        brand_required_fields_status=brand_required_fields_status,
        brand_soft_fields_status=brand_soft_fields_status,
        brand_overlay_resolved=brand_overlay_resolved,
    )
    policy = _load_policy(policy_path)

    trace: list[dict[str, Any]] = []

    def _emit(state_name: str, reason: str) -> FallbackDecision:
        state = _state_by_name(policy, state_name)
        trace.append({"matched_state": state_name, "reason": reason})
        return FallbackDecision({
            "status": state_name,
            "severity": state.get("severity"),
            "is_blocking": state.get("is_blocking", False),
            "output_strategy": state.get("output_strategy", {}),
            "downstream_signal": state.get("downstream_signal", {}),
            "block_reason": state.get("block_reason"),
            "evaluation_trace": trace,
            "_meta": {
                "policy_id": policy.get("policy_id"),
                "schema_version": policy.get("schema_version"),
                "inputs": {
                    "business_brief_status": business_brief_status,
                    "brand_required_fields_status": brand_required_fields_status,
                    "brand_soft_fields_status": brand_soft_fields_status,
                    "brand_overlay_resolved": brand_overlay_resolved,
                },
            },
        })

    # evaluation_pipeline（严格按 policy 顺序）
    # 1. business_brief 缺 → 最高优先 block
    trace.append({"check": "business_brief_status", "value": business_brief_status})
    if business_brief_status == "missing":
        return _emit("blocked_missing_business_brief", "business_brief missing")

    # 2. brand required (hard) 缺 → block
    trace.append({"check": "brand_required_fields_status", "value": brand_required_fields_status})
    if brand_required_fields_status == "missing":
        return _emit(
            "blocked_missing_required_brand_fields",
            "required_level=hard field missing",
        )

    # 3. overlay 未命中 → domain_only
    trace.append({"check": "brand_overlay_resolved", "value": brand_overlay_resolved})
    if not brand_overlay_resolved:
        return _emit("domain_only", "brand_overlay_view miss")

    # 4. soft 字段判定
    trace.append({"check": "brand_soft_fields_status", "value": brand_soft_fields_status})
    if brand_soft_fields_status == "partial_missing":
        return _emit("brand_partial_fallback", "soft field partial_missing")

    # complete / not_applicable + 前置全 OK → brand_full_applied
    return _emit("brand_full_applied", "all checks passed")

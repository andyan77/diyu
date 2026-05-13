"""KS-RETRIEVAL-007 · merge_context / 上下文合并（§6.10 第 10 步）.

W8 波次实现。按 KS-POLICY-003 merge_precedence_policy 合并 domain_general + brand_<name>
overlay 字段，附带 structured / vector 候选透传到统一 context bundle。

硬纪律 / hard rules:
- precedence_order: `brand_<name> > domain_general`（与 policy 严格一致）
- domain_general 不许 override brand_<name>；allow_override=false 时强拒
- conflict_action 严格按 policy 5 种语义：override / append / block / needs_review / （隐式跳过）
- 不调 LLM；不写 clean_output
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import yaml

__all__ = ["merge_context", "MergeConflictBlocked"]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = (
    REPO_ROOT / "knowledge_serving" / "policies" / "merge_precedence_policy.yaml"
)

# overlay 字段抽取来源映射：哪个 conflict_key 对应 overlay row 的哪个位置
# - 直列：overlay row 直接列名
# - tone_constraints / output_structure：嵌套 JSON 取 key
_OVERLAY_DIRECT_COLS = frozenset({"forbidden_words", "signature_phrases"})
_OVERLAY_TONE_KEYS = frozenset({"tone", "brand_values", "tagline"})
_OVERLAY_STRUCTURE_KEYS = frozenset({"founder_profile"})
# persona_* 视为 persona target_type 字段（在 overlay row 的 brand_overlay_kind=team_persona_overlay /
# founder_persona 上承载）；本卡 thin 实现：从 tone_constraints_json 内 persona_role / persona_voice 取
_OVERLAY_PERSONA_KEYS = frozenset({"persona_role", "persona_voice"})


class MergeConflictBlocked(RuntimeError):
    """conflict_action=block 命中真冲突；caller 必须降级为 structured-only。"""


def _load_policy(policy_path: Path | None) -> list[dict]:
    path = Path(policy_path) if policy_path else DEFAULT_POLICY_PATH
    if not path.exists():
        raise FileNotFoundError(f"merge_precedence_policy 缺失 / missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("merge_precedence_policy") or []
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("merge_precedence_policy 内容为空")
    return rows


def _parse_json_maybe(raw: Any, fallback: Any) -> Any:
    if raw is None or raw == "":
        return fallback
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return fallback


def _extract_overlay_field(overlay_row: dict, conflict_key: str) -> Any:
    """从单个 overlay row 中提取 conflict_key 对应的字段值（None 表示该 row 无此字段）。"""
    if conflict_key in _OVERLAY_DIRECT_COLS:
        v = _parse_json_maybe(overlay_row.get(conflict_key), [])
        return v if v else None
    if conflict_key in _OVERLAY_TONE_KEYS:
        tone = _parse_json_maybe(overlay_row.get("tone_constraints_json"), {})
        if isinstance(tone, dict):
            return tone.get(conflict_key)
        return None
    if conflict_key in _OVERLAY_STRUCTURE_KEYS:
        struct = _parse_json_maybe(overlay_row.get("output_structure_json"), {})
        if isinstance(struct, dict):
            return struct.get(conflict_key)
        return None
    if conflict_key in _OVERLAY_PERSONA_KEYS:
        tone = _parse_json_maybe(overlay_row.get("tone_constraints_json"), {})
        if isinstance(tone, dict):
            return tone.get(conflict_key)
        return None
    return None


def _collect_field_by_layer(
    overlays: Iterable[dict],
    conflict_key: str,
) -> dict[str, list[Any]]:
    """按 brand_layer 收集 conflict_key 的非空取值列表。"""
    by_layer: dict[str, list[Any]] = {}
    for row in overlays:
        layer = row.get("brand_layer")
        if not layer:
            continue
        v = _extract_overlay_field(row, conflict_key)
        if v is None or v == [] or v == {}:
            continue
        by_layer.setdefault(layer, []).append(v)
    return by_layer


def _apply_action(
    *,
    conflict_key: str,
    action: str,
    allow_override: bool,
    brand_values: list[Any],
    domain_values: list[Any],
    resolved_brand_layer: str,
) -> tuple[Any, dict | None, dict | None]:
    """返回 (merged_value, conflict_log_entry, needs_review_entry).

    优先级铁律：brand_<name> > domain_general。
    """
    has_brand = bool(brand_values)
    has_domain = bool(domain_values)

    if not has_brand and not has_domain:
        return None, None, None

    log = None
    review = None

    if action == "override":
        # 允许 brand 覆盖 domain；不允许反向
        if has_brand:
            merged = brand_values[0] if len(brand_values) == 1 else brand_values
            if has_domain and not allow_override:
                # 显式记录 domain 试图 override brand 但被拒
                log = {
                    "conflict_key": conflict_key,
                    "action": action,
                    "decision": "brand_wins_domain_rejected",
                    "reason": "allow_override=false; domain_general cannot override brand",
                }
            elif has_domain:
                log = {
                    "conflict_key": conflict_key,
                    "action": action,
                    "decision": "brand_overrides_domain",
                }
            return merged, log, None
        # 只有 domain：在 brand 已 resolved 的情况下，按"domain 不许 override brand"原则
        # 这里 brand 侧本来就空（不存在覆盖关系）；domain 值合法承载
        return (domain_values[0] if len(domain_values) == 1 else domain_values), None, None

    if action == "append":
        # 列表型字段：brand + domain 拼接，brand 在前；非列表型按 brand 优先单值
        merged_list: list[Any] = []
        for v in brand_values + domain_values:
            if isinstance(v, list):
                merged_list.extend(v)
            else:
                merged_list.append(v)
        # 去重保序
        seen: list[Any] = []
        for item in merged_list:
            if item not in seen:
                seen.append(item)
        return seen, None, None

    if action == "block":
        if has_brand and has_domain:
            # 真冲突：两侧都有取值，按 block 语义不允许 merge
            log = {
                "conflict_key": conflict_key,
                "action": action,
                "decision": "blocked",
                "reason": "brand and domain both present; merge forbidden",
            }
            # caller 决定要不要 raise；此处不 raise，返回 brand 侧值并打 log
            return (brand_values[0] if len(brand_values) == 1 else brand_values), log, None
        if has_brand:
            return (brand_values[0] if len(brand_values) == 1 else brand_values), None, None
        return (domain_values[0] if len(domain_values) == 1 else domain_values), None, None

    if action == "needs_review":
        review = {
            "conflict_key": conflict_key,
            "action": action,
            "brand_values": brand_values,
            "domain_values": domain_values,
            "resolved_brand_layer": resolved_brand_layer,
        }
        # 不擅自定夺，brand 侧优先暴露
        if has_brand:
            return (brand_values[0] if len(brand_values) == 1 else brand_values), None, review
        return (domain_values[0] if len(domain_values) == 1 else domain_values), None, review

    # 未知 action：保守拒绝
    log = {
        "conflict_key": conflict_key,
        "action": action,
        "decision": "unknown_action_skipped",
    }
    return None, log, None


def merge_context(
    *,
    resolved_brand_layer: str,
    structured: dict | None = None,
    vector: dict | None = None,
    overlay: dict | None = None,
    policy_path: Path | None = None,
    block_raises: bool = False,
) -> dict:
    """13 步召回流程第 10 步：合并 domain + brand 上下文。

    Args:
        resolved_brand_layer: 由 KS-RETRIEVAL-001 解析的当前租户品牌层
        structured: KS-RETRIEVAL-005 structured_retrieve 输出（透传）
        vector: KS-RETRIEVAL-006 vector_retrieve 输出（透传）
        overlay: KS-RETRIEVAL-007.step1 brand_overlay_retrieve 输出
        policy_path: merge_precedence_policy.yaml 路径
        block_raises: True 则 conflict_action=block 真冲突时抛 MergeConflictBlocked；
                      默认 False，把 block 事件落 conflict_log，让 fallback_decider 决策

    Returns:
        {
            "merged_overlay_payload": {conflict_key: merged_value, ...},
            "structured_candidates": {view_name: [rows]},  # 透传 structured["pack_view"] etc.
            "vector_candidates": [...],                     # 透传 vector["candidates"]
            "conflict_log": [...],
            "needs_review_queue": [...],
            "_meta": {
                "resolved_brand_layer": str,
                "precedence_rule": "brand_<name> > domain_general",
                "overlay_layers_seen": [...],
                "policy_rules_applied": int,
            },
        }

    Raises:
        MergeConflictBlocked: 仅当 block_raises=True 且命中 block 真冲突时
    """
    if not isinstance(resolved_brand_layer, str) or not resolved_brand_layer:
        raise ValueError("resolved_brand_layer 必须为非空字符串")

    policy_rows = _load_policy(policy_path)

    overlay_rows = (overlay or {}).get("overlays") or []
    overlay_layers_seen = sorted({r.get("brand_layer") for r in overlay_rows if r.get("brand_layer")})

    merged_overlay_payload: dict[str, Any] = {}
    conflict_log: list[dict] = []
    needs_review_queue: list[dict] = []
    rules_applied = 0

    for rule in policy_rows:
        key = rule.get("conflict_key")
        action = rule.get("conflict_action")
        allow_override = bool(rule.get("allow_override", False))
        if not key or not action:
            continue
        by_layer = _collect_field_by_layer(overlay_rows, key)
        brand_vals: list[Any] = []
        domain_vals: list[Any] = []
        for layer, vals in by_layer.items():
            if layer == "domain_general":
                domain_vals.extend(vals)
            else:
                brand_vals.extend(vals)

        merged_val, log_entry, review_entry = _apply_action(
            conflict_key=key,
            action=action,
            allow_override=allow_override,
            brand_values=brand_vals,
            domain_values=domain_vals,
            resolved_brand_layer=resolved_brand_layer,
        )
        rules_applied += 1
        if merged_val is not None:
            merged_overlay_payload[key] = merged_val
        if log_entry:
            conflict_log.append(log_entry)
            if block_raises and log_entry.get("decision") == "blocked":
                raise MergeConflictBlocked(
                    f"conflict_key={key} block; brand+domain 均有取值"
                )
        if review_entry:
            needs_review_queue.append(review_entry)

    return {
        "merged_overlay_payload": merged_overlay_payload,
        "structured_candidates": {
            k: v for k, v in (structured or {}).items() if not k.startswith("_")
        },
        "vector_candidates": (vector or {}).get("candidates", []),
        "conflict_log": conflict_log,
        "needs_review_queue": needs_review_queue,
        "_meta": {
            "resolved_brand_layer": resolved_brand_layer,
            "precedence_rule": "brand_<name> > domain_general",
            "overlay_layers_seen": overlay_layers_seen,
            "policy_rules_applied": rules_applied,
        },
    }

"""KS-RETRIEVAL-004 · requirement_checker / 必需字段校验器.

任务卡 KS-RETRIEVAL-004 · W7 · S gate S7.

语义 / semantics:
  - 数据源 / data sources:
      knowledge_serving/control/field_requirement_matrix.csv  (KS-COMPILER-009)
      knowledge_serving/policies/fallback_policy.yaml         (KS-POLICY-001)
  - 入参：recipe row dict（须含 content_type）+ available_fields（实际已具备的字段名集合）。
  - 决策表（与 fallback_policy.yaml matrix_alignment 严格对齐）：
      required_level=hard + 字段缺  → fallback_status = blocked_missing_required_brand_fields
      required_level=soft + 字段缺  → fallback_status = brand_partial_fallback
      上述全部齐全                 → fallback_status = brand_full_applied
      content_type 在矩阵中无任何条目 →
          warning + 保守阻断（卡 §6 "field_matrix 缺该 content_type → warning + 保守阻断"）
          fallback_status = blocked_missing_required_brand_fields
  - required_level=none 的字段不进入降级判定（policy `none_level_to_state: not_in_scope`）。

红线 / red lines:
  - 不调任何 LLM。
  - 不写 clean_output/。
  - hard 缺字段必阻断（卡 §10 阻断项）。
  - 模块 load 期读 CSV / YAML 一次；运行期纯函数 + 确定性。
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Optional

import yaml

_MATRIX_CSV: Path = (
    Path(__file__).resolve().parents[1]
    / "control"
    / "field_requirement_matrix.csv"
)
_POLICY_YAML: Path = (
    Path(__file__).resolve().parents[1]
    / "policies"
    / "fallback_policy.yaml"
)

STATUS_BRAND_FULL = "brand_full_applied"
STATUS_BRAND_PARTIAL = "brand_partial_fallback"
STATUS_BLOCKED_HARD = "blocked_missing_required_brand_fields"

WARNING_MATRIX_MISS = "field_matrix_missing_content_type"


def _load_matrix() -> dict[str, list[dict]]:
    """content_type → list of requirement rows."""
    by_ct: dict[str, list[dict]] = {}
    with _MATRIX_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ct = (row.get("content_type") or "").strip()
            if not ct:
                continue
            by_ct.setdefault(ct, []).append({
                "field_key": (row.get("field_key") or "").strip(),
                "required_level": (row.get("required_level") or "").strip(),
                "fallback_action": (row.get("fallback_action") or "").strip(),
                "ask_user_question": (row.get("ask_user_question") or "").strip(),
                "block_reason": (row.get("block_reason") or "").strip(),
            })
    return by_ct


def _load_policy_alignment() -> dict:
    with _POLICY_YAML.open("r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    return policy.get("matrix_alignment", {})


_MATRIX: dict[str, list[dict]] = _load_matrix()
_POLICY_ALIGNMENT: dict = _load_policy_alignment()


def check(recipe: dict, available_fields: Optional[Iterable[str]]) -> dict:
    """校验配方必需字段 / check recipe required fields.

    Args:
        recipe: ``recipe_selector.select(...)`` 的返回值（须含 ``content_type``）。
        available_fields: 实际已具备的字段名 iterable；None / 空集合等价。

    Returns:
        dict with keys:
          - satisfied:        bool（无 hard 与 soft 缺失 且非保守阻断）
          - missing_hard:     list[str]（required_level=hard 且不在 available 的字段）
          - missing_soft:     list[str]（required_level=soft 且不在 available 的字段）
          - fallback_status:  str（policy 状态枚举之一）
          - block_reasons:    list[str]（hard 缺字段时取 matrix.block_reason）
          - ask_user_questions: list[str]（hard / soft 缺字段时取 matrix.ask_user_question）
          - warnings:         list[str]（如 field_matrix_missing_content_type）
          - content_type:     str（透传，便于下游日志）
    """
    if not isinstance(recipe, dict):
        raise TypeError("recipe must be a dict")
    content_type = recipe.get("content_type")
    if not isinstance(content_type, str) or not content_type.strip():
        raise ValueError("recipe['content_type'] must be non-empty str")

    have: set[str] = set(available_fields or ())

    rows = _MATRIX.get(content_type)
    if not rows:
        # 卡 §6 "field_matrix 缺该 content_type → warning + 保守阻断"
        return {
            "satisfied": False,
            "missing_hard": [],
            "missing_soft": [],
            "fallback_status": _POLICY_ALIGNMENT.get(
                "hard_missing_to_state", STATUS_BLOCKED_HARD
            ),
            "block_reasons": [
                f"content_type={content_type} 未登记在 field_requirement_matrix，"
                f"保守阻断 / conservative block"
            ],
            "ask_user_questions": [],
            "warnings": [WARNING_MATRIX_MISS],
            "content_type": content_type,
        }

    missing_hard: list[str] = []
    missing_soft: list[str] = []
    block_reasons: list[str] = []
    ask_user_questions: list[str] = []

    for r in rows:
        field = r["field_key"]
        level = r["required_level"]
        if not field:
            continue
        if level == "none":
            continue
        if field in have:
            continue
        if level == "hard":
            missing_hard.append(field)
            if r["block_reason"]:
                block_reasons.append(r["block_reason"])
            if r["ask_user_question"]:
                ask_user_questions.append(r["ask_user_question"])
        elif level == "soft":
            missing_soft.append(field)
            if r["ask_user_question"]:
                ask_user_questions.append(r["ask_user_question"])

    if missing_hard:
        status = _POLICY_ALIGNMENT.get(
            "hard_missing_to_state", STATUS_BLOCKED_HARD
        )
    elif missing_soft:
        status = _POLICY_ALIGNMENT.get(
            "soft_missing_to_state", STATUS_BRAND_PARTIAL
        )
    else:
        status = STATUS_BRAND_FULL

    return {
        "satisfied": not (missing_hard or missing_soft),
        "missing_hard": missing_hard,
        "missing_soft": missing_soft,
        "fallback_status": status,
        "block_reasons": block_reasons,
        "ask_user_questions": ask_user_questions,
        "warnings": [],
        "content_type": content_type,
    }

"""KS-RETRIEVAL-004 · recipe_selector / 生产配方选择器.

任务卡 KS-RETRIEVAL-004 · W7 · S gate S7.

语义 / semantics:
  - 入参：content_type / platform / output_format / brand_layer（可选）
  - 数据源：knowledge_serving/views/generation_recipe_view.csv（KS-COMPILER-003 产物）
  - 命中规则：行的 content_type / platform / output_format 三键全等于入参；
    可选 brand_layer 过滤（命中 brand_<x> 优先，回落到 domain_general）。
  - 多 recipe 命中 → 按 _priority_key 取一（gate_status=active 优先，
    review_status=approved 优先，brand_layer 精确优先 domain_general，
    recipe_id 字典序保持确定性）。
  - 无命中 → raise RecipeNotFoundError（卡 §6 "无 recipe 匹配 → raise"）。

红线 / red lines:
  - 不调任何 LLM / 不调任何外部模型生成端点。
  - 不写 clean_output/。
  - 不执行召回（卡 §1 非目标）。
  - 模块 load 期一次性读 CSV；运行期纯函数 + 确定性。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

_RECIPE_CSV: Path = (
    Path(__file__).resolve().parents[1]
    / "views"
    / "generation_recipe_view.csv"
)

_JSON_FIELDS = (
    "source_table_refs",
    "evidence_ids",
    "required_views",
    "retrieval_plan_json",
    "step_sequence_json",
    "context_budget_json",
)


class RecipeNotFoundError(LookupError):
    """无 recipe 匹配 / no recipe matched."""


def _parse_json_cell(value: str):
    if value is None or value == "":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _load_recipes() -> list[dict]:
    rows: list[dict] = []
    with _RECIPE_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = dict(raw)
            for key in _JSON_FIELDS:
                if key in row:
                    row[key] = _parse_json_cell(row[key])
            rows.append(row)
    return rows


_RECIPES: list[dict] = _load_recipes()


def _priority_key(row: dict, brand_layer: Optional[str]) -> tuple:
    # 越小越优先 / lower-is-better tuple
    gate_rank = 0 if row.get("gate_status") == "active" else 1
    review_rank = 0 if row.get("review_status") == "approved" else 1
    row_brand = row.get("brand_layer")
    if brand_layer and row_brand == brand_layer:
        brand_rank = 0
    elif row_brand == "domain_general":
        brand_rank = 1
    else:
        brand_rank = 2
    return (gate_rank, review_rank, brand_rank, row.get("recipe_id") or "")


def select(
    content_type: str,
    platform: str,
    output_format: str,
    brand_layer: Optional[str] = None,
) -> dict:
    """选生产配方 / select generation recipe.

    Args:
        content_type: canonical content_type（如 ``"behind_the_scenes"``）。
        platform: canonical platform（如 ``"xiaohongshu"``）。
        output_format: canonical output_format（如 ``"text"``）。
        brand_layer: 可选，``"brand_faye"`` / ``"domain_general"`` 等；
            命中精确 brand 行优先，否则回落到 domain_general 行。

    Returns:
        recipe row dict（JSON 字段已 parse）。

    Raises:
        RecipeNotFoundError: 三元组 (content_type, platform, output_format) 无任何匹配。
        TypeError: 必填入参为 None 或非 str。
    """
    for name, value in (
        ("content_type", content_type),
        ("platform", platform),
        ("output_format", output_format),
    ):
        if not isinstance(value, str) or not value.strip():
            raise TypeError(f"{name} must be non-empty str")

    candidates = [
        r for r in _RECIPES
        if r.get("content_type") == content_type
        and r.get("platform") == platform
        and r.get("output_format") == output_format
    ]
    if brand_layer:
        scoped = [
            r for r in candidates
            if r.get("brand_layer") in (brand_layer, "domain_general")
        ]
        if scoped:
            candidates = scoped

    if not candidates:
        raise RecipeNotFoundError(
            f"no recipe matched content_type={content_type!r} "
            f"platform={platform!r} output_format={output_format!r} "
            f"brand_layer={brand_layer!r}"
        )

    candidates.sort(key=lambda r: _priority_key(r, brand_layer))
    return candidates[0]

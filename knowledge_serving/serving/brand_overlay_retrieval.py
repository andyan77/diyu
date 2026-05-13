"""KS-RETRIEVAL-007 · brand_overlay_retrieval / 品牌叠层召回（§6.9 第 9 步）.

W8 波次实现。从 brand_overlay_view.csv 按 resolved_brand_layer 拿 overlay。

硬纪律 / hard rules:
- 入参 resolved_brand_layer 由 KS-RETRIEVAL-001 tenant_scope_resolver 解析得到，
  **禁止**从 user_query 自然语言解析品牌（即便 query 含品牌名）
- 禁止 LLM 介入 overlay 选择
- domain_general 不存在 overlay（overlay 按定义是品牌特化层）→ 命中 overlay_miss
- gate_status 必须 active、granularity_layer 必须 ∈ {L1, L2, L3}
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

__all__ = ["brand_overlay_retrieve", "OverlayMiss"]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OVERLAY_VIEW_PATH = (
    REPO_ROOT / "knowledge_serving" / "views" / "brand_overlay_view.csv"
)

ALLOWED_GRANULARITY = frozenset({"L1", "L2", "L3"})
GATE_ACTIVE = "active"
_BRAND_LAYER_RE = re.compile(r"^(domain_general|brand_[a-z0-9_]+)$")


class OverlayMiss(LookupError):
    """resolved_brand_layer 在 brand_overlay_view 0 命中（用于 fallback_decider 触发 domain_only）。"""


def _validate_brand_layer(layer: str) -> None:
    if not isinstance(layer, str) or not _BRAND_LAYER_RE.match(layer):
        raise ValueError(f"非法 brand_layer 命名：{layer!r}")


def _load_view(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"brand_overlay_view 不存在 / missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def brand_overlay_retrieve(
    *,
    resolved_brand_layer: str,
    content_type: Optional[str] = None,
    target_pack_id: Optional[str] = None,
    overlay_view_path: Path | None = None,
) -> dict:
    """13 步召回流程第 9 步：拿 resolved_brand_layer 对应 overlay。

    Args:
        resolved_brand_layer: KS-RETRIEVAL-001 解析结果（如 'brand_faye' / 'domain_general'）
        content_type: 可选，canonical content_type id（来自 KS-RETRIEVAL-003）
        target_pack_id: 可选，按 target_pack_id 精确过滤
        overlay_view_path: 可选，brand_overlay_view.csv 路径

    Returns:
        {
            "overlays": [overlay_row, ...],   # 命中行（hard filter 后）
            "overlay_resolved": bool,         # 是否有命中（fallback_decider 消费）
            "_meta": {
                "resolved_brand_layer": str,
                "content_type": str | None,
                "target_pack_id": str | None,
                "view_path": str,
                "total_rows_in_view": int,
                "filter_dropped": {"brand_layer": n, "gate": n, "granularity": n,
                                   "content_type": n, "pack_id": n},
            }
        }

    Raises:
        ValueError: brand_layer 命名非法
        FileNotFoundError: overlay_view 缺失
    """
    _validate_brand_layer(resolved_brand_layer)
    path = Path(overlay_view_path) if overlay_view_path else DEFAULT_OVERLAY_VIEW_PATH
    rows = _load_view(path)

    # domain_general 按定义无 overlay（overlay 仅承载 brand 特化），直接 short-circuit
    if resolved_brand_layer == "domain_general":
        return {
            "overlays": [],
            "overlay_resolved": False,
            "_meta": {
                "resolved_brand_layer": resolved_brand_layer,
                "content_type": content_type,
                "target_pack_id": target_pack_id,
                "view_path": _display_path(path),
                "total_rows_in_view": len(rows),
                "filter_dropped": {
                    "brand_layer": len(rows),
                    "gate": 0,
                    "granularity": 0,
                    "content_type": 0,
                    "pack_id": 0,
                },
                "short_circuit_reason": "domain_general_has_no_overlay",
            },
        }

    dropped = {"brand_layer": 0, "gate": 0, "granularity": 0, "content_type": 0, "pack_id": 0}
    kept: list[dict] = []
    for row in rows:
        if row.get("brand_layer") != resolved_brand_layer:
            dropped["brand_layer"] += 1
            continue
        if row.get("gate_status") != GATE_ACTIVE:
            dropped["gate"] += 1
            continue
        if row.get("granularity_layer") not in ALLOWED_GRANULARITY:
            dropped["granularity"] += 1
            continue
        if content_type and row.get("target_content_type") and row.get("target_content_type") != content_type:
            # target_content_type 为空表示 overlay 适用所有 content_type；只在显式不匹配时排除
            dropped["content_type"] += 1
            continue
        if target_pack_id and row.get("target_pack_id") != target_pack_id:
            dropped["pack_id"] += 1
            continue
        kept.append(row)

    return {
        "overlays": kept,
        "overlay_resolved": bool(kept),
        "_meta": {
            "resolved_brand_layer": resolved_brand_layer,
            "content_type": content_type,
            "target_pack_id": target_pack_id,
            "view_path": _display_path(path),
            "total_rows_in_view": len(rows),
            "filter_dropped": dropped,
        },
    }

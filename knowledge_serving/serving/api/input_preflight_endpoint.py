"""KS-CD-003-A · /v1/input_preflight deterministic HTTP wrapper.

目的 / Purpose:
  消除 Dify chatflow n1-n4 中 tenant / intent / content_type / business_brief
  四处硬编码（双源漂移源头）。本 endpoint 是**纯组合** —— 只调用 4 个既有
  serving module，读 control/view 真源 CSV；不发明任何新 SSOT，不调 LLM。

红线 / Red lines:
  - 不调 LLM / Agent
  - 不写 clean_output/
  - 不新增 tenant / alias / content_type / requirement 真源；只读既有
    tenant_scope_registry.csv / content_type_canonical.csv / field_requirement_matrix.csv
  - 任一上游 module raise → 转 4xx/5xx，不静默兜底
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from knowledge_serving.serving import (
    content_type_router as _ct_router,
    intent_classifier as _intent_mod,
    tenant_scope_resolver as _tenant_mod,
)

router = APIRouter()

# field_requirement_matrix 真源（CLAUDE.md 红线：本仓 serving control 区）
_MATRIX_PATH = (
    Path(__file__).resolve().parents[2]
    / "control"
    / "field_requirement_matrix.csv"
)


# ============================================================
# Pydantic schema
# ============================================================

class PreflightRequest(BaseModel):
    tenant_id_hint: str = Field(..., min_length=1, description="租户 id；走 tenant_scope_registry")
    intent_hint: str = Field(..., min_length=1, description="canonical intent；走 intent_classifier")
    content_type_hint: str = Field(..., min_length=1, description="canonical 或 alias；走 content_type_router")
    business_brief: Optional[dict[str, Any]] = Field(
        default=None, description="brief；null/缺失 → 归一为 {}（Dify 留空时传 null）"
    )

    @field_validator("business_brief", mode="before")
    @classmethod
    def _coerce_brief(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            import json as _json
            try:
                parsed = _json.loads(v) if v.strip() else {}
            except Exception:
                raise ValueError("business_brief 是字符串但不是合法 JSON")
            if not isinstance(parsed, dict):
                raise ValueError("business_brief 必须是 JSON object")
            return parsed
        raise ValueError(f"business_brief 必须是 dict / null / JSON 字符串，得到 {type(v).__name__}")


# ============================================================
# field_requirement_matrix 读取（按 content_type 取 hard 字段集）
# ============================================================

_MATRIX_CACHE: dict[str, list[str]] | None = None


def _load_hard_fields_by_content_type() -> dict[str, list[str]]:
    """读取 control/field_requirement_matrix.csv，按 content_type 索引 hard field_key。

    cached at import-process scope；canonical SSOT 文件级修改需要进程重启 — 与
    其他 serving module 行为一致（_REGISTRY / _CANONICAL_IDS 同理）。
    """
    global _MATRIX_CACHE
    if _MATRIX_CACHE is not None:
        return _MATRIX_CACHE
    if not _MATRIX_PATH.is_file():
        raise FileNotFoundError(f"field_requirement_matrix.csv 不存在: {_MATRIX_PATH}")
    out: dict[str, list[str]] = {}
    with _MATRIX_PATH.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if (row.get("required_level") or "").strip().lower() == "hard":
                ct = (row.get("content_type") or "").strip()
                fk = (row.get("field_key") or "").strip()
                if ct and fk:
                    out.setdefault(ct, []).append(fk)
    _MATRIX_CACHE = out
    return out


def _check_brief_hard_missing(content_type: Optional[str], brief: dict) -> dict:
    """对齐 field_requirement_matrix.csv：按 content_type 找 hard 字段，brief 缺即 missing。"""
    if not content_type:
        return {"business_brief_status": "needs_review",
                "missing_fields": [],
                "note": "content_type unresolved → cannot evaluate hard requirements"}
    matrix = _load_hard_fields_by_content_type()
    hard_fields = matrix.get(content_type, [])
    missing = [k for k in hard_fields if not brief.get(k)]
    return {
        "business_brief_status": "complete" if not missing else "missing",
        "missing_fields": missing,
    }


# ============================================================
# 主组合 / main composition
# ============================================================

def _resolve_tenant(tenant_id: str) -> dict:
    try:
        row = _tenant_mod.resolve(tenant_id)
    except _tenant_mod.TenantNotAuthorized:
        return {
            "tenant_ok": False,
            "resolved_brand_layer": None,
            "allowed_layers": [],
        }
    except _tenant_mod.RegistryCorrupted as e:
        raise HTTPException(status_code=500, detail={
            "error": "tenant_registry_corrupted", "message": str(e)})
    return {
        "tenant_ok": True,
        "resolved_brand_layer": row["brand_layer"],
        "allowed_layers": list(row["allowed_layers"]),
    }


def _resolve_intent(intent_hint: str) -> dict:
    res = _intent_mod.classify(intent_hint)
    return {
        "classified_intent": res.get("intent") or "",
        "intent_status": res.get("status", "needs_review"),
    }


def _resolve_content_type(hint: str) -> dict:
    res = _ct_router.route(hint)
    return {
        "content_type": res.get("content_type") or "",
        "content_type_status": res.get("status", "needs_review"),
        "matched_alias": res.get("matched_alias"),
    }


def _aggregate_status(tenant: dict, intent: dict, ct: dict, brief: dict) -> str:
    """组合 4 段 status 给一个聚合判定。

    - 任一为 needs_review/missing/!ok → 不为 ok
    - tenant_ok=False → blocked
    - 其它 review 类问题 → needs_review
    """
    if not tenant.get("tenant_ok"):
        return "blocked"
    sub_statuses = [
        intent.get("intent_status"),
        ct.get("content_type_status"),
        brief.get("business_brief_status"),
    ]
    if any(s != "ok" and s != "complete" for s in sub_statuses):
        return "needs_review"
    return "ok"


# ============================================================
# Route
# ============================================================

@router.post("/v1/input_preflight")
def post_preflight(req: PreflightRequest) -> dict[str, Any]:
    tenant = _resolve_tenant(req.tenant_id_hint.strip())
    intent = _resolve_intent(req.intent_hint.strip())
    ct = _resolve_content_type(req.content_type_hint.strip())
    brief_dict = req.business_brief or {}
    brief = _check_brief_hard_missing(ct.get("content_type"), brief_dict)

    return {
        "preflight_status": _aggregate_status(tenant, intent, ct, brief),
        "tenant": tenant,
        "intent": intent,
        "content_type": ct,
        "business_brief": brief,
    }

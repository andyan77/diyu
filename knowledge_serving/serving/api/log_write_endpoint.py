"""KS-CD-003 · log_write HTTP wrapper.

包一层 HTTP，调用既有 `serving/log_writer.py:write_context_bundle_log(...)`。
不动 log_writer.py 本体；不写 PG mirror（PG mirror 由 reconcile 流程独立负责）。

KS-CD-003 reimport reality-fix（2026-05-14）：
  Dify chatflow 上游的 n5/retrieve_context 已经返回完整 bundle + meta；
  让 wrapper 同时接受两种 schema：
    A) **Dify-friendly**（推荐）：传 n5 整包 response + classified_intent + 可选 final_output_text
    B) **canonical**（兼容旧测试）：拆好的 bundle + bundle_meta + classified_intent + ...
  server 内部对齐到 log_writer 的 29 字段 canonical CSV。

红线 / red lines：
  - canonical CSV 路径只能落 `knowledge_serving/control/context_bundle_log.csv`
    或测试用 tmp 路径（env DIYU_LOG_CSV_OVERRIDE）
  - bundle 必含 request_id（pydantic 验）
  - 同 request_id 重复写 → log_writer 已 raise → 这里 409
  - **不调 LLM**；不做业务判断
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from knowledge_serving.serving import log_writer as _log_writer_mod

router = APIRouter()


class BundleMeta(BaseModel):
    bundle_hash: str = Field(default="", description="64-hex context_bundle_hash")
    user_query_hash: str = Field(default="", description="64-hex user_query_hash")
    merged_overlay_payload_empty: bool = Field(default=False)


class LogWriteRequest(BaseModel):
    # === Dify-friendly schema（推荐）===
    # 直接吃 n5 retrieve_context 整包 response；server 拆 bundle + meta
    retrieve_context_response: Optional[dict[str, Any]] = Field(
        default=None,
        description="n5 retrieve_context API 整包响应 {request_id, status, bundle, meta, ...}",
    )
    # === Canonical schema（兼容旧测试 / 直接客户端）===
    bundle: Optional[dict[str, Any]] = None
    bundle_meta: Optional[BundleMeta] = None
    # === 共用字段 ===
    classified_intent: Optional[str] = Field(default=None, min_length=1)
    selected_recipe_id: Optional[str] = Field(default=None, min_length=1)
    retrieved_ids: Optional[dict[str, Any]] = None
    model_policy: Optional[dict[str, Any]] = None
    # 终稿文本 / final output；用于 final_output_hash 计算（KS-DIFY-ECS-010 S8 回放需要）
    final_output_text: Optional[str] = None
    final_output_hash: Optional[str] = None
    blocked_reason: Optional[str] = None


def _log_path() -> Path | None:
    """允许测试通过 env 重定向 CSV 路径；None → log_writer 用 canonical 默认值。"""
    override = os.environ.get("DIYU_LOG_CSV_OVERRIDE")
    return Path(override) if override else None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _coalesce_inputs(req: LogWriteRequest) -> dict[str, Any]:
    """两种 schema 归一为 write_context_bundle_log 调用所需的 kwargs。"""
    # 1) bundle / bundle_meta：retrieve_context_response 优先
    rcr = req.retrieve_context_response or {}
    bundle = req.bundle if req.bundle is not None else (rcr.get("bundle") or {})
    if not isinstance(bundle, dict) or not bundle:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_bundle", "hint": "需要 retrieve_context_response.bundle 或 bundle 字段"},
        )

    meta_dict: dict[str, Any]
    if req.bundle_meta is not None:
        meta_dict = req.bundle_meta.model_dump()
    else:
        meta_dict = (rcr.get("meta") or {})
        # 字段对齐：确保至少有 bundle_hash / user_query_hash / merged_overlay_payload_empty
        meta_dict.setdefault("bundle_hash", "")
        meta_dict.setdefault("user_query_hash", "")
        meta_dict.setdefault("merged_overlay_payload_empty", False)

    # 2) request_id 必须存在于 bundle（log_writer._build_row 直接读 bundle.request_id）
    request_id = bundle.get("request_id") or rcr.get("request_id")
    if not request_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_request_id", "hint": "bundle.request_id 或 retrieve_context_response.request_id 必填"},
        )
    bundle.setdefault("request_id", request_id)

    # 3) classified_intent：必填，缺省 "disabled"（避免空字段触发 LogWriteError）
    classified_intent = req.classified_intent or "disabled"

    # 4) selected_recipe_id：优先用入参；否则从 bundle.recipe.recipe_id 提取
    selected_recipe_id = req.selected_recipe_id
    if not selected_recipe_id:
        recipe = bundle.get("recipe") or {}
        selected_recipe_id = recipe.get("recipe_id") or recipe.get("source_pack_id") or "disabled"

    # 5) retrieved_ids：优先入参；否则从 bundle.recipe.evidence_ids + bundle 内 ids 推
    retrieved_ids = req.retrieved_ids
    if retrieved_ids is None:
        recipe = bundle.get("recipe") or {}
        retrieved_ids = {
            "pack_ids": bundle.get("retrieved_pack_ids") or [],
            "play_card_ids": bundle.get("retrieved_play_card_ids") or [],
            "asset_ids": bundle.get("retrieved_asset_ids") or [],
            "overlay_ids": bundle.get("retrieved_overlay_ids") or [],
            "evidence_ids": recipe.get("evidence_ids") or bundle.get("retrieved_evidence_ids") or [],
        }

    # 6) model_policy：缺省空 dict（log_writer._resolve_model_field 会用 "disabled" 兜底）
    model_policy = req.model_policy or {}

    # 7) final_output_hash：如传了 final_output_text 但没 hash，server 算
    final_output_hash = req.final_output_hash
    if final_output_hash is None and req.final_output_text:
        final_output_hash = _sha256(req.final_output_text)

    return {
        "bundle": bundle,
        "bundle_meta": meta_dict,
        "classified_intent": classified_intent,
        "selected_recipe_id": selected_recipe_id,
        "retrieved_ids": retrieved_ids,
        "model_policy": model_policy,
        "final_output_hash": final_output_hash,
        "blocked_reason": req.blocked_reason,
    }


@router.post("/internal/context_bundle_log")
def post_log_write(req: LogWriteRequest) -> dict[str, Any]:
    kwargs = _coalesce_inputs(req)

    try:
        target, _row = _log_writer_mod.write_context_bundle_log(
            **kwargs,
            log_path=_log_path(),
            pg_writer=None,         # PG mirror 由 reconcile 流程独立负责
            fsync_csv=False,        # 容器内 tmpfs 也能跑
        )
    except _log_writer_mod.LogWriteError as e:
        msg = str(e)
        if "duplicate" in msg.lower() or "重复" in msg or "已存在" in msg:
            raise HTTPException(status_code=409, detail={"error": "duplicate_request_id", "message": msg})
        raise HTTPException(status_code=400, detail={"error": "log_write_error", "message": msg})
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={"error": "log_write_internal", "type": type(e).__name__, "message": str(e)},
        )

    return {
        "status": "ok",
        "request_id": kwargs["bundle"]["request_id"],
        "csv_path": str(target),
    }

"""KS-CD-003 · log_write HTTP wrapper.

只包一层 HTTP，调用既有 `serving/log_writer.py:write_context_bundle_log(...)`。
不动 log_writer.py 本体；不写 PG mirror（PG mirror 由 reconcile_context_bundle_log_mirror.py 独立流程负责）。

红线 / red lines：
  - canonical CSV 路径只能落 `knowledge_serving/control/context_bundle_log.csv`
    或测试用 tmp 路径（env DIYU_LOG_CSV_OVERRIDE）
  - bundle 必含 request_id（pydantic 验）
  - 同 request_id 重复写 → log_writer 已 raise → 这里 409
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from knowledge_serving.serving import log_writer as _log_writer_mod

router = APIRouter()


class BundleMeta(BaseModel):
    bundle_hash: str = Field(..., description="64-hex context_bundle_hash")
    user_query_hash: str = Field(..., description="64-hex user_query_hash")
    merged_overlay_payload_empty: bool = Field(default=False)


class LogWriteRequest(BaseModel):
    bundle: dict[str, Any] = Field(..., description="full context_bundle，必含 request_id")
    bundle_meta: BundleMeta
    classified_intent: str = Field(..., min_length=1)
    selected_recipe_id: str = Field(..., min_length=1)
    retrieved_ids: dict[str, Any] = Field(default_factory=dict)
    model_policy: dict[str, Any] = Field(default_factory=dict)
    final_output_hash: str | None = None
    blocked_reason: str | None = None


def _log_path() -> Path | None:
    """允许测试通过 env 重定向 CSV 路径；None → log_writer 用 canonical 默认值。"""
    override = os.environ.get("DIYU_LOG_CSV_OVERRIDE")
    return Path(override) if override else None


@router.post("/internal/context_bundle_log")
def post_log_write(req: LogWriteRequest) -> dict[str, Any]:
    # bundle 必含 request_id（log_writer 内部要从 bundle 读）
    request_id = req.bundle.get("request_id")
    if not request_id or not isinstance(request_id, str):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_request_id",
                "hint": "bundle.request_id 必须为非空 string",
            },
        )

    try:
        target, _row = _log_writer_mod.write_context_bundle_log(
            bundle=req.bundle,
            bundle_meta=req.bundle_meta.model_dump(),
            classified_intent=req.classified_intent,
            selected_recipe_id=req.selected_recipe_id,
            retrieved_ids=req.retrieved_ids,
            model_policy=req.model_policy,
            final_output_hash=req.final_output_hash,
            blocked_reason=req.blocked_reason,
            log_path=_log_path(),
            pg_writer=None,  # 不在 wrapper 里同步写 PG；reconcile 流程独立负责
            fsync_csv=False,  # 测试 / 容器内 tmpfs 也能跑
        )
    except _log_writer_mod.LogWriteError as e:
        msg = str(e)
        # 同 request_id 重复 → 409
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
        "request_id": request_id,
        "csv_path": str(target),
    }

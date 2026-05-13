"""KS-DIFY-ECS-007 · retrieve_context HTTP API wrapper.

把 13 步 retrieve_context 链路（KS-RETRIEVAL-001..009）包装成 FastAPI HTTP 接口，
供 Dify Chatflow（编排） / 上游应用调用。

边界 / scope:
- 不在 API 层接受 `brand_layer`（红线 / red line）：brand_layer 必须由
  KS-RETRIEVAL-001 tenant_scope_resolver 从 tenant_id 推断；任何让调用方
  "override" brand_layer 的入参都拒绝
- 不在 API 层调 LLM；不写 clean_output；secrets 仅走 env
- internal error → 5xx 但 request_id 仍随响应体返回，用于运营关联

错误码 / error codes:
  400  入参语法错误（pydantic 校验失败 / 缺 tenant_id / 缺 user_query）
  403  tenant 未登记 / disabled / api_key mismatch（TenantNotAuthorized）
  413  user_query 超过 MAX_USER_QUERY_LEN
  500  内部异常（含 request_id 用于追踪）

可用 endpoint:
  GET  /healthz
  POST /v1/retrieve_context
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.serving import tenant_scope_resolver as tsr  # noqa: E402
from knowledge_serving.serving import intent_classifier as ic  # noqa: E402
from knowledge_serving.serving import content_type_router as ctr  # noqa: E402
from knowledge_serving.serving import business_brief_checker as bbc  # noqa: E402
from knowledge_serving.serving import recipe_selector as rsel  # noqa: E402
from knowledge_serving.serving import requirement_checker as rchk  # noqa: E402
from knowledge_serving.serving import structured_retrieval as sret  # noqa: E402
from knowledge_serving.serving import brand_overlay_retrieval as bovr  # noqa: E402
from knowledge_serving.serving import merge_context as mctx  # noqa: E402
from knowledge_serving.serving import fallback_decider as fdec  # noqa: E402
from knowledge_serving.serving import context_bundle_builder as cbb  # noqa: E402
from knowledge_serving.serving import log_writer as lw  # noqa: E402

MAX_USER_QUERY_LEN = 4000  # 413 阈值；4k chars 已远超日常 LLM 输入；防滥用
DEFAULT_PLATFORM = "xiaohongshu"
DEFAULT_OUTPUT_FORMAT = "text"


class NeedsReviewException(Exception):
    """input-first 非法输入 / unknown alias → 短路返 200 needs_review 结构.

    plan §6 step 2/3（2026-05-12 用户裁决）：intent / content_type 非法不允许
    LLM 推断、不允许兜底；返 needs_review 让前端补字段。
    """

    def __init__(self, *, kind: str, reason: str, hint: Any):
        self.kind = kind
        self.reason = reason
        self.hint = hint
        super().__init__(f"needs_review:{kind}:{reason}")


# ============================================================
# pydantic 入参模型 / request model
# ============================================================

class RetrieveContextRequest(BaseModel):
    """retrieve_context API 入参。

    红线 / red line：
    1) 模型刻意 **不含** `brand_layer` 字段；调用方任何带 `brand_layer` 的请求
       由 `extra="forbid"` 直接 400 拒绝
    2) **input-first / no-LLM**（plan §6 step 2/3，2026-05-12 用户裁决）：
       `intent_hint` 和 `content_type` 必须由 Dify 开始节点 / API 显式入参提供；
       缺失 → pydantic required 400；非法 / 别名未知 → 200 + `needs_review` 响应结构，
       禁止 LLM 推断、禁止从 user_query 关键词猜、禁止兜底 product_review 等 canonical
    """

    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(..., min_length=1, max_length=200, description="租户 ID / tenant id；brand_layer 由后端推断")
    user_query: str = Field(..., min_length=1, description="用户自然语言查询 / user natural-language query")
    # plan §6 step 3：content_type 必填，无兜底；非法 → needs_review
    content_type: str = Field(..., min_length=1, description="content_type 显式输入（canonical id 或 alias）；缺失/非法 → needs_review")
    # plan §6 step 2：intent 必填，无兜底；非法 → needs_review
    intent_hint: str = Field(..., min_length=1, description="意图 hint 显式输入；缺失/非法 → needs_review，禁止 LLM 推断")
    platform: Optional[str] = Field(default=DEFAULT_PLATFORM, description="目标平台 / target platform")
    output_format: Optional[str] = Field(default=DEFAULT_OUTPUT_FORMAT, description="输出格式 / output format")
    fallback_mode: Optional[str] = Field(default=None, description="降级策略 hint；当前由 fallback_decider 自决，仅记录")
    business_brief: dict[str, Any] = Field(default_factory=dict, description="业务 brief（sku / category / season / channel 等）")

    @field_validator("user_query")
    @classmethod
    def _query_length_413(cls, v: str) -> str:
        if len(v) > MAX_USER_QUERY_LEN:
            # 用专门 HTTPException 让 FastAPI 走 413 而不是 422
            raise HTTPException(
                status_code=413,
                detail=f"user_query 超长 / payload too large: len={len(v)} > {MAX_USER_QUERY_LEN}",
            )
        return v


# ============================================================
# 13 步装配 helper（与 smoke / demo 同款，省去重复 import）
# ============================================================

def _read_governance() -> dict[str, Any]:
    """从 pack_view.csv 头行抽 governance 三件套（KS-COMPILER-013 保证全链路存在）。"""
    import csv
    view = REPO_ROOT / "knowledge_serving" / "views" / "pack_view.csv"
    with view.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        row = next(reader, None)
    if not row:
        raise RuntimeError("pack_view.csv 为空，governance 不可读")
    return {
        "gate_policy": "active_only",
        "granularity_layers": ["L1", "L2", "L3"],
        "traceability_required": True,
        "compile_run_id": row["compile_run_id"],
        "source_manifest_hash": row["source_manifest_hash"],
        "view_schema_version": row["view_schema_version"],
    }


def _gen_request_id() -> str:
    """生成 API 请求级 unique request_id；含 utc 时间 + uuid4 短前缀。"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"req_api_{ts}_{uuid.uuid4().hex[:8]}"


def _orchestrate(
    *,
    req: RetrieveContextRequest,
    request_id: str,
    governance: dict[str, Any],
) -> tuple[dict, dict]:
    """复用 13 步链路，构造并落盘 bundle + log；返回 (bundle, meta)。

    任何步骤抛异常 → 由 caller 捕获转 500。
    """
    # 1 tenant_scope（403 路径：TenantNotAuthorized 由 caller 捕获）
    scope = tsr.resolve(req.tenant_id)
    allowed_layers = scope["allowed_layers"]
    resolved_brand_layer = scope["brand_layer"]

    # 2 intent — input-first（plan §6 step 2 / 2026-05-12 用户裁决）；非法 → needs_review
    intent_res = ic.classify(req.intent_hint)
    if intent_res.get("status") != "ok":
        raise NeedsReviewException(
            kind="intent",
            reason=intent_res.get("reason") or "unknown intent_hint",
            hint=req.intent_hint,
        )
    intent = intent_res["intent"]
    policy_intent = ic.intent_to_policy_key(intent).get("policy_key") or "generate"

    # 3 content_type — input-first（plan §6 step 3 / 2026-05-12 用户裁决）；
    # 别名未知 / 非 canonical → needs_review，绝不兜底
    ct_res = ctr.route(req.content_type)
    if ct_res.get("status") != "ok":
        raise NeedsReviewException(
            kind="content_type",
            reason=ct_res.get("reason") or "unknown content_type",
            hint=req.content_type,
        )
    content_type = ct_res["content_type"]

    # 4 brief
    brief_res = bbc.check(req.business_brief or {})
    business_brief_status = "complete" if brief_res["status"] == "ok" else "missing"

    # 5 recipe
    recipe = rsel.select(
        content_type=content_type,
        platform=req.platform or DEFAULT_PLATFORM,
        output_format=req.output_format or DEFAULT_OUTPUT_FORMAT,
        brand_layer=resolved_brand_layer,
    )
    recipe_id = recipe.get("recipe_id", "")

    # 6 requirement
    available = set((req.business_brief or {}).keys())
    req_res = rchk.check(recipe, available)
    if req_res["missing_hard"]:
        brand_required_fields_status = "missing"
    elif req_res.get("missing_soft") is not None and len(req_res["missing_soft"]) == 0:
        brand_required_fields_status = "not_applicable"
    else:
        brand_required_fields_status = "complete"
    brand_soft_fields_status = (
        "partial_missing" if req_res["missing_soft"] else "not_applicable"
    )

    # 7 structured
    structured = sret.structured_retrieve(
        intent=policy_intent,
        content_type=content_type,
        allowed_layers=allowed_layers,
    )

    # 8 vector：API 层默认 structured_only（live qdrant 由 smoke / batch eval 跑）
    vector_res = None

    # 9 overlay
    overlay = bovr.brand_overlay_retrieve(
        resolved_brand_layer=resolved_brand_layer, content_type=content_type,
    )
    brand_overlay_resolved = overlay["overlay_resolved"]

    # 10 merge
    merge_res = mctx.merge_context(
        resolved_brand_layer=resolved_brand_layer,
        structured=structured, vector=vector_res, overlay=overlay,
    )

    # 11 fallback
    fb = fdec.decide_fallback(
        business_brief_status=business_brief_status,
        brand_required_fields_status=brand_required_fields_status,
        brand_soft_fields_status=brand_soft_fields_status,
        brand_overlay_resolved=brand_overlay_resolved,
    )
    fb_dict = dict(fb)
    actual_fallback = fb_dict["status"]

    # 12 bundle
    bundle, bundle_meta = cbb.build_context_bundle(
        request_id=request_id,
        tenant_id=req.tenant_id,
        resolved_brand_layer=resolved_brand_layer,
        allowed_layers=allowed_layers,
        user_query=req.user_query,
        content_type=content_type,
        recipe=recipe,
        business_brief=req.business_brief,
        merge_result=merge_res,
        fallback_decision=fb_dict,
        governance=governance,
    )

    # 13 log write（best-effort PG mirror；CSV 是 canonical）
    model_policy = {
        "model_policy_version": "mp_20260512_002",
        "embedding": {"model": "text-embedding-v3", "model_version": "v3"},
        "rerank": {"enabled": False},
        "llm_assist": {"enabled": False},
    }
    retrieved_ids = {
        "pack_ids": [r.get("source_pack_id") for r in structured.get("pack_view", []) if isinstance(r, dict)][:5],
        "play_card_ids": [r.get("play_card_id") for r in structured.get("play_card_view", []) if isinstance(r, dict)][:5],
        "asset_ids": [r.get("runtime_asset_id") for r in structured.get("runtime_asset_view", []) if isinstance(r, dict)][:5],
        "overlay_ids": [r.get("overlay_id") for r in overlay.get("overlays", []) if isinstance(r, dict)][:5],
        "evidence_ids": [ev.get("evidence_id") for ev in bundle["evidence"]][:10],
    }
    blocked_reason = None
    if actual_fallback.startswith("blocked_"):
        if actual_fallback == "blocked_missing_business_brief":
            blocked_reason = f"business_brief missing: {brief_res['blocked_fields']}"
        else:
            blocked_reason = f"brand required missing: {req_res.get('block_reasons', [])}"

    lw.write_context_bundle_log(
        bundle=bundle,
        bundle_meta=bundle_meta,
        classified_intent=intent,
        selected_recipe_id=recipe_id,
        retrieved_ids=retrieved_ids,
        model_policy=model_policy,
        blocked_reason=blocked_reason,
    )

    return bundle, bundle_meta


# ============================================================
# FastAPI app
# ============================================================

def create_app() -> FastAPI:
    app = FastAPI(
        title="diyu retrieve_context API",
        version="1.0.0",
        description="KS-DIFY-ECS-007 · retrieve_context HTTP wrapper for Dify Chatflow",
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "retrieve_context", "version": "1.0.0"}

    @app.post("/v1/retrieve_context")
    def post_retrieve_context(req: RetrieveContextRequest) -> dict[str, Any]:
        request_id = _gen_request_id()
        t0 = time.time()
        try:
            governance = _read_governance()
            bundle, bundle_meta = _orchestrate(
                req=req, request_id=request_id, governance=governance,
            )
        except NeedsReviewException as e:
            # plan §6 step 2/3：非法 intent / content_type → 200 + needs_review；
            # 不走 5xx，因为这是业务上"等前端补字段"的合法流转状态
            return {
                "request_id": request_id,
                "status": "needs_review",
                "needs_review": {
                    "field": e.kind,
                    "received": e.hint,
                    "reason": e.reason,
                },
                "elapsed_ms": int((time.time() - t0) * 1000),
            }
        except tsr.TenantNotAuthorized as e:
            # 403：tenant 未登记 / disabled
            raise HTTPException(
                status_code=403,
                detail={"request_id": request_id, "error": "tenant_not_authorized", "message": str(e)},
            )
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 — 5xx 兜底；request_id 必须随响应回传
            sys.stderr.write(
                f"[retrieve_context] internal_error request_id={request_id} "
                f"type={type(e).__name__} msg={e}\n"
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "request_id": request_id,
                    "error": "internal_error",
                    "type": type(e).__name__,
                    "message": str(e),
                },
            )

        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "request_id": request_id,
            "status": "ok",
            "elapsed_ms": elapsed_ms,
            "bundle": bundle,
            "meta": {
                "bundle_hash": bundle_meta["bundle_hash"],
                "user_query_hash": bundle_meta["user_query_hash"],
                "merged_overlay_payload_empty": bundle_meta["merged_overlay_payload_empty"],
            },
        }

    # 把 pydantic 422（缺字段 / 类型错）显式转 400，对齐卡 §6
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    def _validation_exception_400(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "bad_request", "detail": exc.errors()},
        )

    return app


# 默认 app 实例供 uvicorn 直接拉起
app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8088"))
    uvicorn.run(app, host=host, port=port)

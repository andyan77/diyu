#!/usr/bin/env python3
"""KS-DIFY-ECS-006 · ECS 端到端冒烟 / end-to-end smoke.

W11 波次 / wave W11。

从 ECS（阿里云服务器）部署位发起 retrieve_context（上下文召回） →
Qdrant（向量数据库）→ PG（PostgreSQL 关系库）→ log 写入 / log write
全链路数据穿透验证。

边界 / scope:
- 3 类样例 / 3 samples：product_review（产品评测）/ store_daily（门店日常）/
  founder_ip（创始人 IP），各自有期望 fallback_status，不允许 silent pass / 静默通过
- S9 跨租户隔离 / cross-tenant isolation：每个样例计算 structured 候选中
  非 allowed_layers 行数，必须为 0
- log canonical CSV 28 字段（卡描述 "24 字段" 是约述；实际 LOG_FIELDS=28）
  必须全部非空（"disabled" / "none" 也算非空）
- PG mirror（PG 镜像）通过 KS-DIFY-ECS-005 的 reconcile callable 接口探测；
  PG 不可达 → 标 degraded（降级），不阻断；CSV 写失败 → smoke fail
- **本卡到此为止**：不做 replay / 回放验证（属 KS-DIFY-ECS-010 职责）
- 不调 LLM
- secrets / 密钥走 env / 环境变量（DASHSCOPE_API_KEY / PG_* / ECS_*）

退出码 / exit codes:
  0  smoke pass（含 degraded 标记）
  1  smoke fail（CSV / S9 / 字段 / silent_pass / 任一硬门）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _auto_load_dotenv() -> dict[str, str]:
    """启动 best-effort 加载仓库根 `.env`（不覆盖已存在 env）。

    审查员复跑无 `source scripts/load_env.sh` 时，避免 PG/ECS 探测因 env 缺
    集体退化为 degraded（W11 finding #3 守门）。已设置的 env 不动；只补缺。
    """
    loaded: dict[str, str] = {}
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return loaded
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        # 展开 ${VAR} / ${HOME} 等简单变量引用，与 set -a 行为一致
        value = os.path.expandvars(value)
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


# 在 import serving 模块之前先 load env，避免 model_policy / dashscope key 等
# 模块级读取漏掉 .env 真值。
_DOTENV_LOADED = _auto_load_dotenv()

from knowledge_serving.serving import tenant_scope_resolver as tsr
from knowledge_serving.serving import intent_classifier as ic
from knowledge_serving.serving import content_type_router as ctr
from knowledge_serving.serving import business_brief_checker as bbc
from knowledge_serving.serving import recipe_selector as rsel
from knowledge_serving.serving import requirement_checker as rchk
from knowledge_serving.serving import structured_retrieval as sret
from knowledge_serving.serving import vector_retrieval as vret
from knowledge_serving.serving import brand_overlay_retrieval as bovr
from knowledge_serving.serving import merge_context as mctx
from knowledge_serving.serving import fallback_decider as fdec
from knowledge_serving.serving import context_bundle_builder as cbb
from knowledge_serving.serving import log_writer as lw

AUDIT_PATH = (
    REPO_ROOT / "knowledge_serving" / "audit" / "ecs_e2e_smoke_KS-DIFY-ECS-006.json"
)
PG_CONTAINER = "diyu-infra-postgres-1"
SMOKE_RUN_TAG = "ks-dify-ecs-006"


# ============================================================
# samples
# ============================================================
# 每个样例 / sample：tenant + content_type + business_brief + 期望 fallback_status。
# 期望与 KS-RETRIEVAL-009 demo 已落盘行为一致；用作 silent-pass 守门。
SAMPLES: list[dict[str, Any]] = [
    {
        "case_id": "sample_product_review",
        "tenant_id": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "product_review",
        "user_query": "请帮我写一段产品测评",
        "business_brief": {
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
        "available_fields_extra": [],
        "expected_fallback_status": "blocked_missing_business_brief",
    },
    {
        "case_id": "sample_store_daily",
        "tenant_id": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "store_daily",
        "user_query": "门店今日营业花絮",
        "business_brief": {
            "sku": "SKU-SMOKE-001",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
        "available_fields_extra": [],
        "expected_fallback_status": "brand_partial_fallback",
    },
    {
        "case_id": "sample_founder_ip",
        "tenant_id": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "founder_ip",
        "user_query": "讲讲创始人故事",
        "business_brief": {
            "sku": "SKU-SMOKE-002",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
        "available_fields_extra": [],
        "expected_fallback_status": "blocked_missing_required_brand_fields",
    },
]

# S9 跨租户对照 / cross-tenant control：domain_general-only 租户做同样请求。
# 用于验证 allowed_layers 收紧时不会出现非允许 brand_layer。
S9_CONTROL = {
    "case_id": "s9_cross_tenant_control",
    "tenant_id": "tenant_demo",
    "intent_hint": "content_generation",
    "content_type_hint": "product_review",
    "user_query": "产品测评",
    "business_brief": {
        "sku": "SKU-SMOKE-S9",
        "category": "outerwear",
        "season": "winter",
        "channel": ["xiaohongshu"],
    },
    "available_fields_extra": ["brand_tone"],
    "expected_fallback_status": "domain_only",
}


# ============================================================
# infra probes / 基础设施探测
# ============================================================

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def probe_qdrant() -> dict[str, Any]:
    """探测 ECS Qdrant 健康（通过本地 tunnel）；不可达即 degraded。"""
    url = os.environ.get("QDRANT_URL_STAGING") or "http://127.0.0.1:6333"
    try:
        req = urllib_request.Request(url.rstrip("/") + "/readyz")
        with urllib_request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            ok = resp.status == 200
            return {"reachable": ok, "url": url, "status": resp.status, "body_head": body[:80]}
    except (urllib_error.URLError, urllib_error.HTTPError, OSError) as e:
        return {"reachable": False, "url": url, "error": f"{type(e).__name__}: {e}"}


def probe_pg() -> dict[str, Any]:
    """探测 ECS PG（通过 SSH + docker exec psql）；env / 网络任一不齐 → degraded。"""
    needed = ["ECS_HOST", "ECS_USER", "ECS_SSH_KEY_PATH", "PG_USER", "PG_DATABASE"]
    missing = [k for k in needed if not os.environ.get(k)]
    if missing:
        return {"reachable": False, "reason": f"env missing: {missing}"}
    cmd = (
        f"ssh -i {shlex.quote(os.environ['ECS_SSH_KEY_PATH'])} "
        f"-o StrictHostKeyChecking=no -o ConnectTimeout=5 "
        f"{shlex.quote(os.environ['ECS_USER'])}@{shlex.quote(os.environ['ECS_HOST'])} "
        f"docker exec -i {shlex.quote(PG_CONTAINER)} "
        f"psql -U {shlex.quote(os.environ['PG_USER'])} "
        f"-d {shlex.quote(os.environ['PG_DATABASE'])} -At -c 'SELECT 1;'"
    )
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=15
        )
    except subprocess.TimeoutExpired as e:
        return {"reachable": False, "reason": f"timeout: {e}"}
    if proc.returncode != 0:
        return {
            "reachable": False,
            "reason": f"exit={proc.returncode}",
            "stderr_head": (proc.stderr or "").strip()[:200],
        }
    return {"reachable": True, "select1": (proc.stdout or "").strip()}


def pg_writer_factory():
    """构造 pg_writer callable / 失败入 outbox 即可，不抛。

    与 KS-DIFY-ECS-005 reconcile 同款 SSH+psql 通道；INSERT ON CONFLICT DO NOTHING。
    """
    def _writer(row: dict[str, str]) -> None:
        cols = ", ".join(lw.LOG_FIELDS)
        # 走 dollar-quoted literal，规避特殊字符转义
        placeholders = ", ".join(
            "$$" + (row.get(f, "") or "").replace("$$", "$$$$") + "$$"
            for f in lw.LOG_FIELDS
        )
        sql = (
            f"INSERT INTO {lw.PG_MIRROR_TABLE} ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT (request_id) DO NOTHING;"
        )
        cmd = (
            f"ssh -i {shlex.quote(os.environ['ECS_SSH_KEY_PATH'])} "
            f"-o StrictHostKeyChecking=no -o ConnectTimeout=5 "
            f"{shlex.quote(os.environ['ECS_USER'])}@{shlex.quote(os.environ['ECS_HOST'])} "
            f"docker exec -i {shlex.quote(PG_CONTAINER)} "
            f"psql -v ON_ERROR_STOP=1 -U {shlex.quote(os.environ['PG_USER'])} "
            f"-d {shlex.quote(os.environ['PG_DATABASE'])} -At"
        )
        proc = subprocess.run(
            cmd, input=sql, shell=True, capture_output=True, text=True, timeout=20
        )
        # psql 默认对 SQL ERROR 仍 exit 0；ON_ERROR_STOP=1 才让 exit != 0；同时再扫
        # stderr 兜底（防止极端情况下未触发的语法层错误被吃掉）/ fail-closed check.
        stderr = (proc.stderr or "").strip()
        if proc.returncode != 0 or "ERROR:" in stderr:
            raise RuntimeError(
                f"pg insert failed exit={proc.returncode} stderr={stderr[:200]}"
            )

    return _writer


# ============================================================
# governance（从 view csv 头部抽取） / governance from view
# ============================================================

def read_governance_from_view() -> dict[str, Any]:
    view = REPO_ROOT / "knowledge_serving" / "views" / "pack_view.csv"
    with view.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        row = next(reader, None)
    if not row:
        raise RuntimeError("pack_view.csv 为空 / empty，governance 三件套不可读")
    return {
        "gate_policy": "active_only",
        "granularity_layers": ["L1", "L2", "L3"],
        "traceability_required": True,
        "compile_run_id": row["compile_run_id"],
        "source_manifest_hash": row["source_manifest_hash"],
        "view_schema_version": row["view_schema_version"],
    }


# ============================================================
# 13 步召回 / 13-step retrieval（精简自 KS-RETRIEVAL-009 demo）
# ============================================================

def _count_cross_tenant_leak(structured: dict, allowed: set[str]) -> tuple[int, list[str]]:
    leak = 0
    bad: set[str] = set()
    for view_name, rows in structured.items():
        if view_name == "_meta" or not isinstance(rows, list):
            continue
        for r in rows:
            bl = r.get("brand_layer") if isinstance(r, dict) else None
            if bl and bl not in allowed:
                leak += 1
                bad.add(bl)
    return leak, sorted(bad)


def _build_live_qdrant_call(
    qdrant_url: str,
) -> tuple[Any, Any] | None:
    """构造 live Qdrant client + embed_fn / return None when deps missing.

    Qdrant reachable 时由 smoke 主调用真 `vector_retrieve`（W11 finding #2 守门：
    业务目标 §1 写明 retrieve_context → Qdrant 穿透，不能止步 /readyz 探活）。
    缺包或缺 key → 返回 None，回退 structured_only + 标 degraded.qdrant_live=true。
    """
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        return None
    try:
        from qdrant_client import QdrantClient  # type: ignore
        import dashscope  # type: ignore
    except ImportError:
        return None

    def _embed(text: str) -> list[float]:
        dashscope.api_key = api_key
        r = dashscope.TextEmbedding.call(model="text-embedding-v3", input=text)
        if r.status_code != 200 or not getattr(r, "output", None):
            raise RuntimeError(f"dashscope embed failed: status={r.status_code} msg={r.message}")
        return list(r.output["embeddings"][0]["embedding"])

    client = QdrantClient(url=qdrant_url, timeout=10.0)
    return client, _embed


def run_retrieve_context(
    case: dict,
    *,
    request_id: str,
    governance: dict,
    pg_writer,
    qdrant_live: tuple[Any, Any] | None,
) -> dict:
    """跑完 13 步 + 写 canonical log。

    Returns 行级 smoke 结果（含 actual_fallback / cross_tenant_leak / 字段完整性）。
    """
    notes: list[str] = []
    # 1 tenant_scope
    scope = tsr.resolve(case["tenant_id"])
    allowed_layers = scope["allowed_layers"]
    resolved_brand_layer = scope["brand_layer"]

    # 2 intent
    intent_res = ic.classify(case["intent_hint"])
    intent = intent_res["intent"]
    bridge = ic.intent_to_policy_key(intent)
    policy_intent = bridge.get("policy_key") or "generate"

    # 3 content_type
    ct_res = ctr.route(case["content_type_hint"])
    content_type = ct_res["content_type"]

    # 4 brief
    brief_res = bbc.check(case["business_brief"])
    business_brief_status = "complete" if brief_res["status"] == "ok" else "missing"

    # 5 recipe
    recipe = rsel.select(
        content_type=content_type, platform="xiaohongshu",
        output_format="text", brand_layer=resolved_brand_layer,
    )
    recipe_id = recipe.get("recipe_id", "")

    # 6 requirement
    available = (
        set(case.get("business_brief", {}).keys())
        | set(case.get("available_fields_extra", []))
    )
    req_res = rchk.check(recipe, available)
    if req_res["missing_hard"]:
        brand_required_fields_status = "missing"
    elif (
        not req_res.get("missing_hard")
        and req_res.get("missing_soft") is not None
        and len(req_res["missing_soft"]) == 0
    ):
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

    # 8 vector：Qdrant reachable 时调真 vector_retrieve（W11 finding #2 守门）；
    # 任一环节失败 → 降级 structured_only + notes 记录，smoke 仍 pass（卡 §6 Qdrant down）
    vector_res = None
    vector_mode = "structured_only_offline"
    vector_candidates_total = 0
    vector_brand_leak = 0
    if qdrant_live is not None:
        qclient, embed_fn = qdrant_live
        try:
            vector_res = vret.vector_retrieve(
                query=case["user_query"],
                allowed_layers=allowed_layers,
                content_type=content_type,
                embed_fn=embed_fn,
                qdrant_client=qclient,
            )
            vector_mode = vector_res.get("mode", "unknown")
            cands = vector_res.get("candidates") or []
            vector_candidates_total = len(cands)
            allowed_set = set(allowed_layers)
            for c in cands:
                pl = (c or {}).get("payload") or {}
                bl = pl.get("brand_layer")
                if bl and bl not in allowed_set:
                    vector_brand_leak += 1
        except Exception as e:  # noqa: BLE001
            vector_res = None
            vector_mode = "structured_only_vector_error"
            notes.append(f"vector_live_failed: {type(e).__name__}: {e}")

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
        tenant_id=case["tenant_id"],
        resolved_brand_layer=resolved_brand_layer,
        allowed_layers=allowed_layers,
        user_query=case["user_query"],
        content_type=content_type,
        recipe=recipe,
        business_brief=case["business_brief"],
        merge_result=merge_res,
        fallback_decision=fb_dict,
        governance=governance,
    )

    # 13 log write
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

    log_path, log_row = lw.write_context_bundle_log(
        bundle=bundle,
        bundle_meta=bundle_meta,
        classified_intent=intent,
        selected_recipe_id=recipe_id,
        retrieved_ids=retrieved_ids,
        model_policy=model_policy,
        blocked_reason=blocked_reason,
        pg_writer=pg_writer,
    )

    # S9 leak count（structured + vector 两侧合并；任一侧出现非 allowed brand_layer 都算泄漏）
    leak_count, bad_layers = _count_cross_tenant_leak(structured, set(allowed_layers))
    leak_count += vector_brand_leak

    # 字段完整性（log_writer 内已守门空字段，这里再断言一次便于 audit 显式列出）
    empty_fields = [f for f in lw.LOG_FIELDS if not log_row.get(f, "")]
    if empty_fields:
        notes.append(f"empty_log_fields: {empty_fields}")

    return {
        "case_id": case["case_id"],
        "request_id": request_id,
        "tenant_id": case["tenant_id"],
        "resolved_brand_layer": resolved_brand_layer,
        "allowed_layers": list(allowed_layers),
        "content_type": content_type,
        "recipe_id": recipe_id,
        "expected_fallback_status": case["expected_fallback_status"],
        "actual_fallback_status": actual_fallback,
        "fallback_match": actual_fallback == case["expected_fallback_status"],
        "cross_tenant_leak_count": leak_count,
        "cross_tenant_leak_layers": bad_layers,
        "context_bundle_hash": bundle_meta["bundle_hash"],
        "user_query_hash": bundle_meta["user_query_hash"],
        "log_row_field_count": len(log_row),
        "log_empty_fields": empty_fields,
        "vector_mode": vector_mode,
        "vector_candidates_total": vector_candidates_total,
        "vector_brand_leak": vector_brand_leak,
        "notes": notes,
    }


# ============================================================
# CSV / outbox post-check
# ============================================================

def verify_csv_log(request_ids: list[str]) -> dict[str, Any]:
    rows = lw.read_log_rows()
    by_id = {r["request_id"]: r for r in rows}
    detail: dict[str, Any] = {"found": [], "missing": [], "field_issues": []}
    for rid in request_ids:
        if rid not in by_id:
            detail["missing"].append(rid)
            continue
        detail["found"].append(rid)
        r = by_id[rid]
        empties = [f for f in lw.LOG_FIELDS if not r.get(f, "")]
        if empties:
            detail["field_issues"].append({"request_id": rid, "empty_fields": empties})
    detail["expected_field_count"] = len(lw.LOG_FIELDS)
    return detail


def verify_outbox(request_ids: list[str]) -> dict[str, Any]:
    entries = lw.read_outbox()
    pending: list[str] = []
    replayed: list[str] = []
    by_id: dict[str, list[dict]] = {}
    for e in entries:
        by_id.setdefault(e.get("request_id"), []).append(e)
    for rid in request_ids:
        statuses = {e.get("status") for e in by_id.get(rid, [])}
        if lw.OUTBOX_STATUS_PENDING in statuses and lw.OUTBOX_STATUS_REPLAYED not in statuses:
            pending.append(rid)
        if lw.OUTBOX_STATUS_REPLAYED in statuses:
            replayed.append(rid)
    return {
        "pending_pg_sync": pending,
        "replayed": replayed,
        "outbox_path": str(lw.CANONICAL_OUTBOX_PATH),
    }


# ============================================================
# main
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="KS-DIFY-ECS-006 ECS 端到端冒烟")
    parser.add_argument(
        "--env", choices=["staging", "prod"], default="staging",
        help="目标环境（默认 staging）",
    )
    parser.add_argument(
        "--audit", type=Path, default=AUDIT_PATH,
        help="audit JSON 输出路径（默认 canonical）",
    )
    args = parser.parse_args()

    started_at = _now()
    t0 = time.time()

    # 探测基础设施 / probe infra
    qdrant_probe = probe_qdrant()
    pg_probe = probe_pg()
    pg_writer = pg_writer_factory() if pg_probe.get("reachable") else None
    qdrant_degraded = not qdrant_probe.get("reachable", False)
    pg_degraded = not pg_probe.get("reachable", False)

    qdrant_live = None
    qdrant_live_reason: str | None = None
    if not qdrant_degraded:
        qdrant_live = _build_live_qdrant_call(qdrant_probe.get("url") or "http://127.0.0.1:6333")
        if qdrant_live is None:
            qdrant_live_reason = (
                "missing DASHSCOPE_API_KEY or qdrant_client/dashscope packages — "
                "vector retrieval degraded to structured_only"
            )

    governance = read_governance_from_view()

    # 同 run 内 unique request_id；避免 CSV unique 约束触发 dedup
    run_token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    case_rows: list[dict] = []
    case_exceptions: list[dict] = []
    all_cases = SAMPLES + [S9_CONTROL]
    for case in all_cases:
        request_id = f"{SMOKE_RUN_TAG}-{case['case_id']}-{run_token}"
        try:
            row = run_retrieve_context(
                case, request_id=request_id, governance=governance,
                pg_writer=pg_writer, qdrant_live=qdrant_live,
            )
            case_rows.append(row)
        except Exception as e:  # noqa: BLE001
            case_exceptions.append({
                "case_id": case["case_id"],
                "request_id": request_id,
                "exception": f"{type(e).__name__}: {e}",
            })

    # CSV / outbox 后置校验 / post-checks
    all_request_ids = [r["request_id"] for r in case_rows]
    csv_detail = verify_csv_log(all_request_ids)
    outbox_detail = verify_outbox(all_request_ids)

    # 闸门 / gates
    gate_csv_complete = (
        not case_exceptions
        and not csv_detail["missing"]
        and not csv_detail["field_issues"]
    )
    gate_cross_tenant = all(r["cross_tenant_leak_count"] == 0 for r in case_rows)
    gate_no_silent_pass = all(r["fallback_match"] for r in case_rows)
    gate_three_samples_ran = (
        sum(1 for r in case_rows if r["case_id"].startswith("sample_")) == 3
    )
    gate_s9_ran = any(r["case_id"] == "s9_cross_tenant_control" for r in case_rows)
    # vector evidence：advisory（不阻断 smoke pass，按卡 §6 Qdrant down → degraded）
    # 但记录到 audit，让审查员能看到本次跑了真 Qdrant 还是降级 structured_only
    vector_modes_seen = sorted({r.get("vector_mode") for r in case_rows if r.get("vector_mode")})
    vector_live_evidence = any(
        r.get("vector_mode") == "vector" and r.get("vector_candidates_total", 0) > 0
        for r in case_rows
    )

    smoke_pass = (
        gate_csv_complete
        and gate_cross_tenant
        and gate_no_silent_pass
        and gate_three_samples_ran
        and gate_s9_ran
    )

    # PG mirror 状态 / pg mirror status
    if pg_degraded:
        pg_status = "degraded_pg_unreachable"
    elif outbox_detail["pending_pg_sync"]:
        pg_status = "degraded_outbox_pending"
    else:
        pg_status = "ok"

    audit = {
        "task_id": "KS-DIFY-ECS-006",
        "env": args.env,
        "started_at": started_at,
        "finished_at": _now(),
        "elapsed_seconds": round(time.time() - t0, 3),
        "run_token": run_token,
        "infra_probe": {
            "qdrant": qdrant_probe,
            "pg": pg_probe,
        },
        "degraded": {
            "qdrant_unreachable": qdrant_degraded,
            "qdrant_live_skipped": qdrant_live is None,
            "qdrant_live_skip_reason": qdrant_live_reason,
            "pg": pg_degraded,
        },
        "dotenv_loaded_keys": sorted(_DOTENV_LOADED.keys()),
        "governance_snapshot": governance,
        "samples": case_rows,
        "case_exceptions": case_exceptions,
        "csv_log": csv_detail,
        "pg_mirror": {
            "status": pg_status,
            "outbox": outbox_detail,
        },
        "gates": {
            "csv_log_complete_28_fields": gate_csv_complete,
            "s9_cross_tenant_zero_leak": gate_cross_tenant,
            "no_silent_pass": gate_no_silent_pass,
            "three_samples_ran": gate_three_samples_ran,
            "s9_control_ran": gate_s9_ran,
        },
        "vector_evidence": {
            "modes_seen": vector_modes_seen,
            "live_hit": vector_live_evidence,
            "note": (
                "vector_live_evidence=true 表示本次确实跑了真 Qdrant 召回；"
                "false 表示 Qdrant 不可达或缺 embedding 依赖，按卡 §6 降级 structured_only"
            ),
        },
        "smoke_result": "pass" if smoke_pass else "fail",
    }

    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # 打印 / print summary
    print(f"=== KS-DIFY-ECS-006 ECS e2e smoke (env={args.env}) ===")
    print(f"  qdrant.reachable={qdrant_probe.get('reachable')} qdrant_live_hit={vector_live_evidence}")
    print(f"  pg.reachable={pg_probe.get('reachable')} dotenv_loaded={len(_DOTENV_LOADED)} keys")
    for r in case_rows:
        marker = "✅" if (r["fallback_match"] and r["cross_tenant_leak_count"] == 0) else "❌"
        print(
            f"  {marker} {r['case_id']:32s} "
            f"fallback={r['actual_fallback_status']:46s} "
            f"leak={r['cross_tenant_leak_count']} "
            f"empty_fields={len(r['log_empty_fields'])}"
        )
    for ex in case_exceptions:
        print(f"  ❌ {ex['case_id']:32s} EXCEPTION: {ex['exception']}")
    print(f"  gates={audit['gates']}")
    print(f"  pg_mirror.status={pg_status}")
    print(f"  smoke_result={audit['smoke_result']}")
    print(f"  audit → {args.audit.relative_to(REPO_ROOT)}")

    return 0 if smoke_pass else 1


if __name__ == "__main__":
    sys.exit(main())

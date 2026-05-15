#!/usr/bin/env python3
"""KS-RETRIEVAL-009 · 端到端 retrieve_context() demo / 13 步召回联调.

把 KS-RETRIEVAL-001..008 全链路在 3 类 fallback 用例 + 1 个 S9 跨租户用例上跑通；
输出 retrieval_eval_sample.csv 作为运行证据。

边界 / scope:
- 不接 Dify、不灌库 prod
- 不调 LLM 做最终判断
- 默认走 structured-only fallback（vector_retrieve 在 offline 模式跳过），
  保证本地 CI 跑通；--live 时启用真 dashscope + 真 Qdrant（需 WSL2 出网 + tunnel）
- 任一 case 静默 PASS 视为 fail（每 case 必须打印 actual vs expected 对比）
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

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

EVAL_CSV = REPO_ROOT / "knowledge_serving" / "logs" / "retrieval_eval_sample.csv"
RUN_LOG = REPO_ROOT / "knowledge_serving" / "logs" / "run_context_retrieval_demo.log"
DEMO_BUNDLE_LOG = Path("/tmp") / f"run_context_retrieval_demo_bundle_log.csv"

EVAL_FIELDS = [
    "case_id",
    "request_id",
    "tenant_id",
    "resolved_brand_layer",
    "allowed_layers",
    "content_type",
    "selected_recipe_id",
    "structured_views_count",
    "vector_mode",
    "vector_candidate_count",
    "overlay_layers_seen",
    "merged_overlay_payload_empty",
    "expected_fallback_status",
    "actual_fallback_status",
    "fallback_match",
    "cross_tenant_leak_count",
    "cross_tenant_pass",
    "bundle_hash",
    "case_status",
    "notes",
    "env",
    "checked_at",
    "git_commit",
    "evidence_level",
]


# ============================================================
# helpers
# ============================================================

def _log_line(buf: list[str], msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    print(line)
    buf.append(line)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_governance_from_view() -> dict[str, str]:
    """从 pack_view.csv 第 2 行抽 compile_run_id / source_manifest_hash / view_schema_version.

    KS-COMPILER-013 保证三件套写到每个 view csv 每一行；任取一行即可。
    """
    view = REPO_ROOT / "knowledge_serving" / "views" / "pack_view.csv"
    with view.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        row = next(reader, None)
    if not row:
        raise RuntimeError("pack_view.csv 为空，无法抽 governance")
    return {
        "gate_policy": "active_only",
        "granularity_layers": ["L1", "L2", "L3"],
        "traceability_required": True,
        "compile_run_id": row["compile_run_id"],
        "source_manifest_hash": row["source_manifest_hash"],
        "view_schema_version": row["view_schema_version"],
    }


def _count_brand_leaks(structured: dict, allowed: set[str]) -> tuple[int, set[str]]:
    """扫 structured_retrieve 返回的所有 view 候选；返回不在 allowed 内的 brand_layer 行数 + 命中集合。"""
    leak = 0
    seen_bad: set[str] = set()
    for view_name, rows in structured.items():
        if view_name == "_meta":
            continue
        if not isinstance(rows, list):
            continue
        for r in rows:
            bl = r.get("brand_layer") if isinstance(r, dict) else None
            if bl and bl not in allowed:
                leak += 1
                seen_bad.add(bl)
    return leak, seen_bad


# ============================================================
# 13 步链路 / single case
# ============================================================

def run_case(case: dict, *, live: bool, log_buf: list[str]) -> dict:
    case_id = case["case_id"]
    t0 = time.time()
    _log_line(log_buf, f"=== {case_id} 开始 ===")

    notes: list[str] = []
    # 确定性 request_id（R4 byte-identical）；运行时戳只在 run_log 体现
    request_id = f"req_demo_{case_id}_v1"

    # ---- 步 1: tenant_scope_resolver ----
    scope = tsr.resolve(case["tenant_id"])
    allowed_layers = scope["allowed_layers"]
    resolved_brand_layer = scope["brand_layer"]
    _log_line(log_buf, f"  step1 tenant_scope: brand={resolved_brand_layer} allowed={allowed_layers}")

    # ---- 步 2: intent_classifier ----
    intent_res = ic.classify(case["intent_hint"])
    if intent_res["status"] != "ok":
        raise RuntimeError(f"intent_classifier 拒绝 hint={case['intent_hint']!r}: {intent_res}")
    intent = intent_res["intent"]
    bridge = ic.intent_to_policy_key(intent)
    policy_intent = bridge.get("policy_key") or "generate"
    _log_line(log_buf, f"  step2 intent: {intent} (policy_intent={policy_intent})")

    # ---- 步 3: content_type_router ----
    ct_res = ctr.route(case["content_type_hint"])
    if ct_res["status"] != "ok":
        raise RuntimeError(f"content_type_router 拒绝 hint={case['content_type_hint']!r}")
    content_type = ct_res["content_type"]
    _log_line(log_buf, f"  step3 content_type: {content_type}")

    # ---- 步 4: business_brief_checker ----
    brief_res = bbc.check(case["business_brief"])
    business_brief_status = (
        "complete" if brief_res["status"] == "ok" else "missing"
    )
    _log_line(
        log_buf,
        f"  step4 brief: status={business_brief_status} blocked={brief_res['blocked_fields']} "
        f"missing={brief_res['missing_fields']}",
    )

    # ---- 步 5: recipe_selector ----
    try:
        recipe = rsel.select(
            content_type=content_type,
            platform="xiaohongshu",
            output_format="text",
            brand_layer=resolved_brand_layer,
        )
    except Exception as e:
        raise RuntimeError(f"recipe_selector 失败: {e}") from e
    recipe_id = recipe.get("recipe_id", "")
    _log_line(log_buf, f"  step5 recipe: {recipe_id}")

    # ---- 步 6: requirement_checker ----
    available = set(case.get("business_brief", {}).keys()) | set(case.get("available_fields_extra", []))
    req_res = rchk.check(recipe, available)
    brand_required_fields_status = (
        "missing" if req_res["missing_hard"] else "not_applicable" if not req_res.get("missing_hard") and not req_res.get("missing_soft") else "complete"
    )
    if req_res["missing_hard"]:
        brand_required_fields_status = "missing"
    elif req_res.get("missing_soft") is not None and len(req_res["missing_soft"]) == 0 and len(req_res.get("missing_hard", [])) == 0:
        brand_required_fields_status = "not_applicable"
    else:
        brand_required_fields_status = "complete"

    brand_soft_fields_status = (
        "partial_missing" if req_res["missing_soft"] else "not_applicable"
    )
    _log_line(
        log_buf,
        f"  step6 requirement: hard_missing={req_res['missing_hard']} soft_missing={req_res['missing_soft']}",
    )

    # ---- 步 7: structured_retrieval ----
    try:
        structured = sret.structured_retrieve(
            intent=policy_intent,
            content_type=content_type,
            allowed_layers=allowed_layers,
        )
    except Exception as e:
        notes.append(f"structured_retrieve_exception: {type(e).__name__}: {e}")
        structured = {"_meta": {"error": str(e)}}
    structured_views_count = sum(
        len(v) for k, v in structured.items() if k != "_meta" and isinstance(v, list)
    )
    _log_line(log_buf, f"  step7 structured: total_rows={structured_views_count}")

    # ---- 步 8: vector_retrieval (offline 默认跳过) ----
    if live:
        vector_res = None
        vector_mode = "structured_only"
        vector_candidate_count = 0
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                from qdrant_client import QdrantClient
                import dashscope

                def _embed(text: str) -> list[float]:
                    dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]
                    r = dashscope.TextEmbedding.call(model="text-embedding-v3", input=text)
                    return list(r.output["embeddings"][0]["embedding"])

                qclient = QdrantClient(url=os.environ["QDRANT_URL_STAGING"], timeout=10.0)
                vector_res = vret.vector_retrieve(
                    query=case["user_query"],
                    allowed_layers=allowed_layers,
                    content_type=content_type,
                    embed_fn=_embed,
                    qdrant_client=qclient,
                )
                vector_mode = vector_res["mode"]
                vector_candidate_count = len(vector_res.get("candidates") or [])
                if attempt > 1:
                    notes.append(f"vector_live_retry_ok: attempt={attempt}")
                break
            except Exception as e:
                last_error = e
                time.sleep(1)
        if vector_res is None and last_error is not None:
            notes.append(f"vector_live_failed: {type(last_error).__name__}: {last_error}")
    else:
        vector_res = None
        vector_mode = "structured_only_offline"
        vector_candidate_count = 0
    _log_line(log_buf, f"  step8 vector: mode={vector_mode} candidates={vector_candidate_count}")

    # ---- 步 9: brand_overlay_retrieve ----
    overlay = bovr.brand_overlay_retrieve(
        resolved_brand_layer=resolved_brand_layer,
        content_type=content_type,
    )
    brand_overlay_resolved = overlay["overlay_resolved"]
    _log_line(
        log_buf,
        f"  step9 overlay: resolved={brand_overlay_resolved} rows={len(overlay['overlays'])}",
    )

    # ---- 步 10: merge_context ----
    merge_res = mctx.merge_context(
        resolved_brand_layer=resolved_brand_layer,
        structured=structured,
        vector=vector_res,
        overlay=overlay,
    )
    overlay_layers_seen = merge_res["_meta"].get("overlay_layers_seen", [])
    merged_payload_empty = not bool(merge_res.get("merged_overlay_payload"))
    _log_line(
        log_buf,
        f"  step10 merge: overlay_layers={overlay_layers_seen} "
        f"payload_empty={merged_payload_empty} conflicts={len(merge_res['conflict_log'])}",
    )

    # ---- 步 11: fallback_decider ----
    fb = fdec.decide_fallback(
        business_brief_status=business_brief_status,
        brand_required_fields_status=brand_required_fields_status,
        brand_soft_fields_status=brand_soft_fields_status,
        brand_overlay_resolved=brand_overlay_resolved,
    )
    fb_dict = dict(fb)
    actual_fallback = fb_dict["status"]
    _log_line(log_buf, f"  step11 fallback: actual={actual_fallback}")

    # ---- 步 12: context_bundle_builder ----
    governance = _read_governance_from_view()
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
    _log_line(log_buf, f"  step12 bundle: hash={bundle_meta['bundle_hash'][:30]}...")

    # ---- 步 13: log_writer ----
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
        log_path=DEMO_BUNDLE_LOG,
    )
    _log_line(log_buf, f"  step13 log: appended → {DEMO_BUNDLE_LOG}")

    # ---- S9 cross-tenant leak 计算 ----
    leak_count, bad_layers = _count_brand_leaks(structured, set(allowed_layers))
    cross_tenant_pass = leak_count == 0
    if not cross_tenant_pass:
        notes.append(f"cross_tenant_leak_layers: {sorted(bad_layers)}")

    # ---- 期望对比 ----
    expected_fb = case["expected_fallback_status"]
    fallback_match = actual_fallback == expected_fb
    case_status = "PASS" if (fallback_match and cross_tenant_pass) else "FAIL"
    elapsed_ms = int((time.time() - t0) * 1000)
    _log_line(
        log_buf,
        f"  ✅ {case_id} {case_status} fallback={actual_fallback} "
        f"(expected {expected_fb}) cross_tenant_leak={leak_count} elapsed={elapsed_ms}ms",
    )

    return {
        "case_id": case_id,
        "request_id": request_id,
        "tenant_id": case["tenant_id"],
        "resolved_brand_layer": resolved_brand_layer,
        "allowed_layers": ";".join(allowed_layers),
        "content_type": content_type,
        "selected_recipe_id": recipe_id,
        "structured_views_count": str(structured_views_count),
        "vector_mode": vector_mode,
        "vector_candidate_count": str(vector_candidate_count),
        "overlay_layers_seen": ";".join(overlay_layers_seen) or "none",
        "merged_overlay_payload_empty": str(merged_payload_empty),
        "expected_fallback_status": expected_fb,
        "actual_fallback_status": actual_fallback,
        "fallback_match": str(fallback_match),
        "cross_tenant_leak_count": str(leak_count),
        "cross_tenant_pass": str(cross_tenant_pass),
        "bundle_hash": bundle_meta["bundle_hash"],
        "case_status": case_status,
        "notes": ";".join(notes) if notes else "none",
    }


# ============================================================
# cases
# ============================================================

CASES = [
    {
        "case_id": "case_1_product_review_blocked_brief",
        "tenant_id": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "product_review",
        "user_query": "请帮我写一段产品测评",
        "business_brief": {
            # 缺 hard required sku → blocked_missing_business_brief
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
        "available_fields_extra": [],
        "expected_fallback_status": "blocked_missing_business_brief",
    },
    {
        "case_id": "case_2_store_daily_partial_fallback",
        "tenant_id": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "store_daily",
        "user_query": "门店今日营业花絮",
        "business_brief": {
            "sku": "SKU-DEMO-001",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
        # team_persona 是 store_daily 的 soft；available 不含 → partial_missing
        "available_fields_extra": [],
        "expected_fallback_status": "brand_partial_fallback",
    },
    {
        "case_id": "case_3_founder_ip_blocked_hard",
        "tenant_id": "tenant_faye_main",
        "intent_hint": "content_generation",
        "content_type_hint": "founder_ip",
        "user_query": "讲讲创始人故事",
        "business_brief": {
            "sku": "SKU-DEMO-002",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
        # founder_profile / brand_values 是 hard；available 不含 → blocked_missing_required_brand_fields
        "available_fields_extra": [],
        "expected_fallback_status": "blocked_missing_required_brand_fields",
    },
    {
        "case_id": "case_S9_cross_tenant_isolation",
        "tenant_id": "tenant_demo",   # allowed=[domain_general] only
        "intent_hint": "content_generation",
        "content_type_hint": "product_review",
        "user_query": "产品测评",
        "business_brief": {
            "sku": "SKU-DEMO-003",
            "category": "outerwear",
            "season": "winter",
            "channel": ["xiaohongshu"],
        },
        # brand_tone 是 product_review 的 soft；预先补齐避免触发 partial
        "available_fields_extra": ["brand_tone"],
        # tenant_demo brand_layer=domain_general，无 brand overlay → domain_only
        "expected_fallback_status": "domain_only",
    },
]


# ============================================================
# main
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="KS-RETRIEVAL-009 端到端 demo")
    parser.add_argument("--all", action="store_true", help="跑全部 4 个 case")
    parser.add_argument("--case", type=int, help="只跑某一个 case（1..4）")
    parser.add_argument("--live", action="store_true", help="启用真 dashscope + Qdrant（需出网 + tunnel）")
    parser.add_argument("--staging", action="store_true", help="标记本次验收使用 staging 外部依赖")
    parser.add_argument(
        "--default-mode",
        choices=("offline", "vector_enabled"),
        default="offline",
        help="demo 默认模式；vector_enabled 会启用真 Qdrant/DashScope 路径",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="写 runtime audit JSON",
    )
    parser.add_argument(
        "--eval-csv", type=Path, default=EVAL_CSV, help="输出 eval csv 路径（默认 canonical）"
    )
    args = parser.parse_args()

    if args.default_mode == "vector_enabled":
        args.live = True
        if not args.all and args.case is None:
            args.all = True

    if not args.all and args.case is None:
        parser.error("必须指定 --all 或 --case=N")

    cases_to_run = CASES if args.all else [CASES[args.case - 1]]
    checked_at = _now_iso()
    git_commit = _git_commit()
    env = "staging" if args.staging else "local"
    evidence_level = "runtime_verified" if args.live else "offline_auxiliary"
    log_buf: list[str] = []
    _log_line(
        log_buf,
        f"KS-RETRIEVAL-009 demo 启动 live={args.live} cases={len(cases_to_run)} "
        f"env={env} checked_at={checked_at} git_commit={git_commit} "
        f"evidence_level={evidence_level}",
    )

    # 清理 bundle log（每次 demo 重新写）
    if DEMO_BUNDLE_LOG.exists():
        DEMO_BUNDLE_LOG.unlink()

    rows: list[dict] = []
    for case in cases_to_run:
        try:
            row = run_case(case, live=args.live, log_buf=log_buf)
        except Exception as e:
            _log_line(log_buf, f"  ❌ {case['case_id']} EXCEPTION: {type(e).__name__}: {e}")
            row = {f: "" for f in EVAL_FIELDS}
            row["case_id"] = case["case_id"]
            row["case_status"] = "FAIL"
            row["notes"] = f"exception:{type(e).__name__}:{e}"
        row["env"] = env
        row["checked_at"] = checked_at
        row["git_commit"] = git_commit
        row["evidence_level"] = evidence_level
        rows.append(row)

    # 写 eval csv（覆盖式，确定性 evidence）
    args.eval_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.eval_csv.open("w", encoding="utf-8", newline="\n") as f:
        writer = csv.DictWriter(f, fieldnames=EVAL_FIELDS, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in EVAL_FIELDS})

    # 写 run log
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    RUN_LOG.write_text("\n".join(log_buf) + "\n", encoding="utf-8")

    # 汇总
    pass_count = sum(1 for r in rows if r.get("case_status") == "PASS")
    fail_count = len(rows) - pass_count
    print("\n=== 汇总 / summary ===")
    for r in rows:
        marker = "✅" if r.get("case_status") == "PASS" else "❌"
        print(
            f"  {marker} {r['case_id']:50s} fallback={r.get('actual_fallback_status','?'):40s} "
            f"leak={r.get('cross_tenant_leak_count','?')}"
        )
    print(f"\n  PASS={pass_count}  FAIL={fail_count}")
    print(f"  eval_csv = {args.eval_csv.relative_to(REPO_ROOT)}")
    print(f"  run_log  = {RUN_LOG.relative_to(REPO_ROOT)}")
    print(f"  bundle_log (CI artifact) = {DEMO_BUNDLE_LOG}")

    vector_rows = [r for r in rows if r.get("vector_mode") == "vector"]
    vector_hits = sum(int(r.get("vector_candidate_count") or 0) for r in vector_rows)
    strict_vector_ok = (
        args.default_mode != "vector_enabled"
        or (len(vector_rows) == len(rows) and vector_hits > 0)
    )
    if args.out:
        audit = {
            "audit_for": "KS-RETRIEVAL-009",
            "env": env,
            "checked_at": checked_at,
            "timestamp": checked_at,
            "git_commit": git_commit,
            "evidence_level": evidence_level,
            "default_mode": args.default_mode,
            "live": args.live,
            "case_count": len(rows),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "vector_cases_count": len(vector_rows),
            "vector_hits": vector_hits,
            "min_vector_candidate_count": min(
                [int(r.get("vector_candidate_count") or 0) for r in rows],
                default=0,
            ),
            "strict_vector_ok": strict_vector_ok,
            "eval_csv": str(args.eval_csv.relative_to(REPO_ROOT)),
            "eval_csv_sha256": _sha256_file(args.eval_csv),
            "run_log": str(RUN_LOG.relative_to(REPO_ROOT)),
            "rows": rows,
            "verdict": "PASS" if fail_count == 0 and pass_count > 0 and strict_vector_ok else "FAIL",
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"  audit = {args.out.resolve().relative_to(REPO_ROOT)}")

    # 任一 fail / 任一 case 未跑 = 整体 fail
    if fail_count > 0 or pass_count == 0 or not strict_vector_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

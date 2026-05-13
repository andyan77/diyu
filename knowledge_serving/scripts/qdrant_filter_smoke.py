#!/usr/bin/env python3
"""KS-VECTOR-003 · vector payload filter 回归 + structured-only fallback smoke.

【目标 / goal】
  - 验证 payload filter 真生效（4 类抽样 + 1 类批次锚定）
  - Qdrant 不可用时降级可用（structured-only）
  - 不调 LLM；不灌库；不写 clean_output

【运行模式 / modes】
  --offline （默认，CI 用）：直接读 qdrant_chunks.jsonl 做 filter 模拟
  --online  （CD 用，KS-CD-001 触发）：调 staging Qdrant 实跑

【输入 / inputs】
  - knowledge_serving/vector_payloads/qdrant_chunks.jsonl
  - knowledge_serving/policies/qdrant_fallback.yaml
  - env QDRANT_URL_STAGING（仅 online 模式需要）

【输出 / output】
  - knowledge_serving/audit/qdrant_filter_smoke_KS-VECTOR-003.json
  - stdout 报告 + 退出码（pass=0 / fail=1）

【对抗矩阵 / adversarial matrix · 卡 §6】
  1) brand_a 请求 → brand_b 命中：永不发生
  2) 旧批次 compile_run_id 请求 → 当前批次命中：永不发生
  3) inactive 命中：永不发生（语料全 active；构造合成 inactive 验证）
  4) Qdrant down → fallback 启用 + offline 报告
  5) filter 缺字段：fail-closed
  6) 维度不匹配：raise（KS-POLICY-005 联动；本卡 offline 不覆盖，已在 test_vector_filter.py 覆盖）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = REPO_ROOT / "knowledge_serving" / "vector_payloads" / "qdrant_chunks.jsonl"
FALLBACK_PATH = REPO_ROOT / "knowledge_serving" / "policies" / "qdrant_fallback.yaml"
AUDIT_PATH = REPO_ROOT / "knowledge_serving" / "audit" / "qdrant_filter_smoke_KS-VECTOR-003.json"

ALLOWED_GRAN = {"L1", "L2", "L3"}
HARD_FILTER_KEYS = ("brand_layer", "gate_status", "granularity_layer")


# ---------- payload filter （与 serving/vector_retrieval.py 对齐） ----------

def build_payload_filter(
    *,
    allowed_layers: list[str],
    content_type: str | None = None,
    compile_run_id: str | None = None,
) -> dict[str, Any]:
    """构造 Qdrant 风格 must-filter（offline 模拟与服务端语义一致）。"""
    if not allowed_layers:
        raise ValueError("allowed_layers 不可空 / empty allowed_layers")
    must: list[dict[str, Any]] = [
        {"key": "brand_layer", "match": {"any": list(allowed_layers)}},
        {"key": "gate_status", "match": {"value": "active"}},
        {"key": "granularity_layer", "match": {"any": sorted(ALLOWED_GRAN)}},
    ]
    if content_type is not None:
        must.append({"key": "content_type", "match": {"value": content_type}})
    if compile_run_id is not None:
        must.append({"key": "compile_run_id", "match": {"value": compile_run_id}})
    return {"must": must}


def match(payload: dict, qf: dict) -> bool:
    """fail-closed：payload 缺 hard filter 任一字段直接判 False。"""
    for cond in qf.get("must", []):
        key = cond["key"]
        if key in HARD_FILTER_KEYS and key not in payload:
            return False
        m = cond["match"]
        val = payload.get(key)
        if "value" in m and val != m["value"]:
            return False
        if "any" in m and val not in set(m["any"]):
            return False
    return True


# ---------- 语料加载 ----------

def load_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        sys.exit(f"❌ qdrant_chunks.jsonl 不存在 / missing: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rows.append({"chunk_id": rec.get("chunk_id"), "payload": rec.get("payload", {})})
    if not rows:
        sys.exit(f"❌ qdrant_chunks.jsonl 为空 / empty corpus: {path}")
    return rows


def apply_filter(corpus: list[dict[str, Any]], qf: dict) -> list[dict[str, Any]]:
    return [r for r in corpus if match(r["payload"], qf)]


# ---------- offline 5 类 filter 抽样 ----------

def run_offline_cases(corpus: list[dict[str, Any]]) -> dict[str, Any]:
    brand_layers = sorted({r["payload"].get("brand_layer") for r in corpus})
    current_run = next(
        (r["payload"].get("compile_run_id") for r in corpus if r["payload"].get("compile_run_id")),
        None,
    )
    if not current_run:
        sys.exit("❌ 语料缺 compile_run_id / corpus missing compile_run_id（KS-VECTOR-001 漂移）")

    cases: list[dict[str, Any]] = []

    # case 1: brand_faye + domain_general（笛语应用真实 allowed_layers）
    qf1 = build_payload_filter(allowed_layers=["brand_faye", "domain_general"])
    hits1 = apply_filter(corpus, qf1)
    leak1 = sorted({h["payload"].get("brand_layer") for h in hits1} - {"brand_faye", "domain_general"})
    cases.append({
        "case_id": "C1_brand_faye_plus_domain_general",
        "filter": qf1,
        "hits_count": len(hits1),
        "brands_hit": sorted({h["payload"].get("brand_layer") for h in hits1}),
        "expected": "hits>0 且只命中 {brand_faye, domain_general}",
        "pass": len(hits1) > 0 and not leak1,
        "leak": leak1,
    })

    # case 2: 仅 domain_general（跨品牌通用规则）
    qf2 = build_payload_filter(allowed_layers=["domain_general"])
    hits2 = apply_filter(corpus, qf2)
    leak2 = sorted({h["payload"].get("brand_layer") for h in hits2} - {"domain_general"})
    cases.append({
        "case_id": "C2_domain_general_only",
        "filter": qf2,
        "hits_count": len(hits2),
        "brands_hit": sorted({h["payload"].get("brand_layer") for h in hits2}),
        "expected": "hits>0 且全部 brand_layer=domain_general",
        "pass": len(hits2) > 0 and not leak2,
        "leak": leak2,
    })

    # case 3: gate=active 恒等过滤（用合成 inactive 验证 hard filter）
    synthetic = list(corpus) + [{
        "chunk_id": "synthetic_inactive_probe",
        "payload": {
            "brand_layer": "brand_faye",
            "gate_status": "deprecated",
            "granularity_layer": "L2",
            "compile_run_id": current_run,
        },
    }]
    qf3 = build_payload_filter(allowed_layers=["brand_faye", "domain_general"])
    hits3 = apply_filter(synthetic, qf3)
    inactive_leaked = any(h["chunk_id"] == "synthetic_inactive_probe" for h in hits3)
    gates_hit3 = sorted({h["payload"].get("gate_status") for h in hits3})
    cases.append({
        "case_id": "C3_gate_active_only",
        "filter": qf3,
        "hits_count": len(hits3),
        "gate_status_hit": gates_hit3,
        "expected": "synthetic_inactive_probe 0 命中 且 gate_status 全 active",
        "pass": (not inactive_leaked) and gates_hit3 == ["active"],
        "inactive_leaked": inactive_leaked,
    })

    # case 4: cross-tenant 串味（brand_b 应用对真实语料 0 命中）
    qf4 = build_payload_filter(allowed_layers=["brand_b"])
    hits4 = apply_filter(corpus, qf4)
    cases.append({
        "case_id": "C4_cross_tenant_zero_hit",
        "filter": qf4,
        "hits_count": len(hits4),
        "brands_hit": sorted({h["payload"].get("brand_layer") for h in hits4}),
        "expected": "0 命中（brand_b 不在语料）",
        "pass": len(hits4) == 0,
    })

    # case 5: 批次锚定 — 旧 compile_run_id 0 命中
    stale_run = "deadbeefcafef00d"  # 显式不存在的旧批次
    assert stale_run != current_run, "测试桩与当前批次不应相同"
    qf5 = build_payload_filter(
        allowed_layers=["brand_faye", "domain_general"],
        compile_run_id=stale_run,
    )
    hits5 = apply_filter(corpus, qf5)
    cases.append({
        "case_id": "C5_batch_anchor_stale_run_zero_hit",
        "filter": qf5,
        "stale_compile_run_id": stale_run,
        "current_compile_run_id": current_run,
        "hits_count": len(hits5),
        "expected": "0 命中（旧批次 compile_run_id 应被服务端 hard filter 拒绝）",
        "pass": len(hits5) == 0,
    })

    # 当前批次正例（防 case 5 因 filter 写挂而总过）
    qf5b = build_payload_filter(
        allowed_layers=["brand_faye", "domain_general"],
        compile_run_id=current_run,
    )
    hits5b = apply_filter(corpus, qf5b)
    cases.append({
        "case_id": "C5b_batch_anchor_current_run_positive",
        "filter": qf5b,
        "hits_count": len(hits5b),
        "expected": "hits>0（当前批次 compile_run_id 必须可召回）",
        "pass": len(hits5b) > 0,
    })

    # case 7: content_type 过滤（正例 + 反例，对应卡 §6 第 4 类 filter）
    # 选语料里真实出现的非空 content_type 作为正例；用合成 token 作为反例
    ct_distribution: dict[str, int] = {}
    for r in corpus:
        ct_distribution[r["payload"].get("content_type", "")] = ct_distribution.get(
            r["payload"].get("content_type", ""), 0
        ) + 1
    # 选样本数最多的非空 content_type 做正例（避免抖动）
    nonempty_cts = sorted(
        [(ct, n) for ct, n in ct_distribution.items() if ct],
        key=lambda x: (-x[1], x[0]),
    )
    if nonempty_cts:
        ct_positive = nonempty_cts[0][0]
        qf7p = build_payload_filter(
            allowed_layers=["brand_faye", "domain_general"],
            content_type=ct_positive,
        )
        hits7p = apply_filter(corpus, qf7p)
        cts_hit_pos = sorted({h["payload"].get("content_type") for h in hits7p})
        cases.append({
            "case_id": "C7p_content_type_positive",
            "filter": qf7p,
            "content_type_probe": ct_positive,
            "hits_count": len(hits7p),
            "content_types_hit": cts_hit_pos,
            "expected": "hits>0 且 content_type 全部等于 probe（hard filter 真生效）",
            "pass": len(hits7p) > 0 and cts_hit_pos == [ct_positive],
        })

        # 反例：用一个不存在的 content_type，必须 0 命中
        ct_stale = "synthetic_unknown_content_type_probe"
        assert ct_stale not in ct_distribution, "合成 content_type 不应与真语料重名"
        qf7n = build_payload_filter(
            allowed_layers=["brand_faye", "domain_general"],
            content_type=ct_stale,
        )
        hits7n = apply_filter(corpus, qf7n)
        cases.append({
            "case_id": "C7n_content_type_negative_zero_hit",
            "filter": qf7n,
            "content_type_probe": ct_stale,
            "hits_count": len(hits7n),
            "expected": "0 命中（未知 content_type 必须被 hard filter 拒绝）",
            "pass": len(hits7n) == 0,
        })
    else:
        # 语料无任何非空 content_type → 显式声明，不静默跳过
        cases.append({
            "case_id": "C7_content_type_skipped_no_corpus_signal",
            "filter": None,
            "hits_count": 0,
            "expected": "语料无非空 content_type，case 7 不适用（声明而非掩盖）",
            "pass": False,
        })

    # fail-closed 探针：payload 缺 hard filter 字段
    bad_corpus = [{"chunk_id": "missing_brand_layer", "payload": {
        "gate_status": "active", "granularity_layer": "L2", "compile_run_id": current_run,
    }}]
    qf_fc = build_payload_filter(allowed_layers=["brand_faye"])
    fc_hits = apply_filter(bad_corpus, qf_fc)
    cases.append({
        "case_id": "C6_fail_closed_missing_field",
        "filter": qf_fc,
        "hits_count": len(fc_hits),
        "expected": "0 命中（缺 brand_layer 必须 fail-closed）",
        "pass": len(fc_hits) == 0,
    })

    return {"cases": cases, "current_compile_run_id": current_run, "brand_layers_in_corpus": brand_layers}


# ---------- fallback / structured-only 探针（offline 不连 Qdrant） ----------

def fallback_signal_offline() -> dict[str, Any]:
    """offline 模式下不连真 Qdrant；声明降级路径 ready，由 online 模式实测。"""
    yaml_text = FALLBACK_PATH.read_text(encoding="utf-8") if FALLBACK_PATH.exists() else ""
    has_marker = "FALLBACK_STRUCTURED_ONLY" in yaml_text and "structured_only" in yaml_text
    return {
        "policy_loaded": FALLBACK_PATH.exists(),
        "log_marker_present": has_marker,
        "strategy_name_present": "structured_only" in yaml_text,
        "pass": FALLBACK_PATH.exists() and has_marker,
    }


# ---------- main ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="KS-VECTOR-003 vector filter smoke")
    parser.add_argument("--offline", action="store_true", default=True,
                        help="offline 模式（默认）：直读 jsonl 模拟 filter")
    parser.add_argument("--online", action="store_true",
                        help="online 模式：实跑 staging Qdrant（KS-CD-001）")
    args = parser.parse_args()

    if args.online:
        sys.exit("❌ online 模式由 KS-CD-001 触发，请用 smoke_vector_retrieval.py；本卡 §8 CI 命令是 --offline")

    corpus = load_chunks(CHUNKS_PATH)
    cases_result = run_offline_cases(corpus)
    fb = fallback_signal_offline()

    cases = cases_result["cases"]
    sampled = [c for c in cases if c["case_id"].startswith(
        ("C1_", "C2_", "C3_", "C4_", "C5_", "C5b_", "C7p_", "C7n_")
    )]
    sampled_pass = sum(1 for c in sampled if c["pass"])
    cross_tenant_case = next(c for c in cases if c["case_id"] == "C4_cross_tenant_zero_hit")
    cross_tenant_hits = cross_tenant_case["hits_count"]

    all_pass = all(c["pass"] for c in cases) and fb["pass"]

    report = {
        "task_card": "KS-VECTOR-003",
        "mode": "offline",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "chunks_corpus_path": str(CHUNKS_PATH.relative_to(REPO_ROOT)),
        "chunks_total": len(corpus),
        "current_compile_run_id": cases_result["current_compile_run_id"],
        "brand_layers_in_corpus": cases_result["brand_layers_in_corpus"],
        "sampled_filter_pass_ratio": f"{sampled_pass}/{len(sampled)}",
        "cross_tenant_hits": cross_tenant_hits,
        "fallback_probe": fb,
        "cases": cases,
        "verdict": "pass" if all_pass else "fail",
    }

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    print("=== KS-VECTOR-003 offline filter smoke ===")
    print(f"  corpus                = {CHUNKS_PATH.relative_to(REPO_ROOT)} ({len(corpus)} chunks)")
    print(f"  current_compile_run   = {cases_result['current_compile_run_id']}")
    print(f"  brand_layers_in_corpus= {cases_result['brand_layers_in_corpus']}")
    print(f"  sampled filter pass   = {sampled_pass}/{len(sampled)}")
    print(f"  cross_tenant_hits     = {cross_tenant_hits}  {'✅' if cross_tenant_hits == 0 else '❌'}")
    print(f"  fallback policy ready = {fb['pass']}  {'✅' if fb['pass'] else '❌'}")
    print(f"  audit                 = {AUDIT_PATH.relative_to(REPO_ROOT)}")
    for c in cases:
        flag = "✅" if c["pass"] else "❌"
        print(f"    {flag} {c['case_id']}  hits={c['hits_count']}  {c['expected']}")
    print(f"\n  {'✅ SMOKE PASS' if all_pass else '❌ SMOKE FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

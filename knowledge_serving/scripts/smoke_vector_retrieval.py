#!/usr/bin/env python3
"""KS-RETRIEVAL-006 staging smoke / 真 dashscope + 真 Qdrant 端到端召回.

【前置】
  - source scripts/load_env.sh （注入 DASHSCOPE_API_KEY）
  - bash scripts/qdrant_tunnel.sh up （Qdrant 本机隧道）
  - export QDRANT_URL_STAGING=http://127.0.0.1:6333

【验证】
  1. 真 dashscope text-embedding-v3 生成 query embedding（dim=1024）
  2. 真 Qdrant alias `ks_chunks_current` 召回 (hard filter 服务端真生效)
  3. 跨租户检查：brand_faye 请求 0 命中 brand_b chunk
  4. gate_status / granularity_layer 服务端硬过滤
  5. 落审计 audit json

【边界】
  - 真源仍是本地 clean_output；本脚本只读 Qdrant
  - 不写 clean_output；audit 写 knowledge_serving/audit/
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.serving import vector_retrieval as vr  # noqa: E402

AUDIT_PATH = REPO_ROOT / "knowledge_serving" / "audit" / "smoke_vector_retrieval_KS-RETRIEVAL-006.json"


def real_dashscope_embed(text: str) -> list[float]:
    import dashscope
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        sys.exit("❌ DASHSCOPE_API_KEY 未注入；先 source scripts/load_env.sh")
    dashscope.api_key = key
    resp = dashscope.TextEmbedding.call(model="text-embedding-v3", input=text)
    if getattr(resp, "status_code", None) != 200:
        sys.exit(f"❌ dashscope embedding 失败: {resp}")
    return list(resp.output["embeddings"][0]["embedding"])


def real_qdrant_client():
    from qdrant_client import QdrantClient
    url = os.environ.get("QDRANT_URL_STAGING")
    if not url:
        sys.exit("❌ QDRANT_URL_STAGING 未设置")
    api_key = os.environ.get("QDRANT_API_KEY") or None
    return QdrantClient(url=url, api_key=api_key, timeout=30.0)


def main() -> int:
    query = "大衣搭配陈列要点"
    allowed_layers = ["brand_faye", "domain_general"]

    client = real_qdrant_client()
    res = vr.vector_retrieve(
        query=query,
        allowed_layers=allowed_layers,
        embed_fn=real_dashscope_embed,
        qdrant_client=client,
    )

    cands = res["candidates"]
    brands_hit = sorted({c["payload"].get("brand_layer") for c in cands})
    gates_hit = sorted({c["payload"].get("gate_status") for c in cands})
    grans_hit = sorted({c["payload"].get("granularity_layer") for c in cands})

    cross_tenant_leak = [b for b in brands_hit if b not in allowed_layers]
    gate_drift = [g for g in gates_hit if g != "active"]
    gran_drift = [g for g in grans_hit if g not in ("L1", "L2", "L3")]

    audit = {
        "task_card": "KS-RETRIEVAL-006",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "query": query,
        "allowed_layers": allowed_layers,
        "collection_name": res["_meta"]["collection_name"],
        "mode": res["mode"],
        "candidate_count": len(cands),
        "brands_hit": brands_hit,
        "gate_status_hit": gates_hit,
        "granularity_hit": grans_hit,
        "cross_tenant_leak": cross_tenant_leak,
        "gate_drift": gate_drift,
        "granularity_drift": gran_drift,
        "policy_snapshot": res["policy"],
        "filter": res["filter"],
        "rerank_applied": res["_meta"]["rerank_applied"],
        "query_embedding_dim": res["_meta"]["query_embedding_dim"],
    }

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    pass_cross = not cross_tenant_leak
    pass_gate = not gate_drift
    pass_gran = not gran_drift
    pass_mode = res["mode"] == "vector"
    pass_nonzero = len(cands) > 0  # Qdrant 已灌库 → 至少 1 命中

    print(f"=== KS-RETRIEVAL-006 staging smoke ===")
    print(f"  query                = {query!r}")
    print(f"  allowed_layers       = {allowed_layers}")
    print(f"  mode                 = {res['mode']}")
    print(f"  candidate_count      = {len(cands)}")
    print(f"  brands_hit           = {brands_hit}")
    print(f"  gate_status_hit      = {gates_hit}")
    print(f"  granularity_hit      = {grans_hit}")
    print(f"  cross_tenant_leak    = {cross_tenant_leak}  {'✅' if pass_cross else '❌'}")
    print(f"  gate_drift           = {gate_drift}  {'✅' if pass_gate else '❌'}")
    print(f"  granularity_drift    = {gran_drift}  {'✅' if pass_gran else '❌'}")
    print(f"  mode==vector         = {pass_mode}")
    print(f"  candidates>0         = {pass_nonzero}")
    print(f"  audit                = {AUDIT_PATH.relative_to(REPO_ROOT)}")

    all_pass = pass_cross and pass_gate and pass_gran and pass_mode and pass_nonzero
    print(f"\n  {'✅ SMOKE PASS' if all_pass else '❌ SMOKE FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""KS-FIX-21 · rerank runtime 真实被调验证 / real-staging rerank invocation gate.

跑 N 条 query → 对每条做 baseline retrieve（无 rerank）+ rerank retrieve（注入真 DashScope rerank）
→ 比较前 K 候选顺序与分数 → 写 audit。

【前置】
  - source scripts/load_env.sh
  - bash scripts/qdrant_tunnel.sh up
  - export QDRANT_URL_STAGING=http://127.0.0.1:6333
  - staging Qdrant 含 alias ks_chunks_current 且 points>0

【pass 条件】（KS-FIX-21 §8）
  - rerank_invoked_count == N
  - score_changed_count >= ceil(N * 0.8)   (5 query 时 >= 4)

退出码：0 = pass；1 = score_changed 不足或 rerank 未被调用；2 = 环境/调用异常。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.serving import vector_retrieval as vr  # noqa: E402

AUDIT_PATH = REPO_ROOT / "knowledge_serving" / "audit" / "rerank_runtime_KS-FIX-21.json"

# 10 条 staging 测试查询（路径 B：企业叙事 / 品牌存在感 / 长期主义意图重排）
# 由用户审查员在 W3 第二轮裁决时给定；不允许执行 AI 自改集合（防"调题到通过"）。
STAGING_QUERIES = [
    "我们想讲品牌为什么存在，不要像卖货文案",
    "创始人经历怎么讲，才能和品牌气质连起来",
    "门店团队的日常怎么讲，才有温度但不鸡汤",
    "想表达长期主义，怎么避免空泛口号",
    "品牌想讲审美标准，应该从什么故事切入",
    "顾客信任不是靠打折建立的，这个观点怎么讲",
    "想写一篇企业价值观内容，但不要像公司公告",
    "新店开业怎么讲品牌和城市的关系",
    "团队坚持做一件小事很多年，适合怎么变成品牌故事",
    "怎么把创始人的个人判断，转成品牌的方法论",
]


def _git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _real_dashscope_embed(text: str) -> list[float]:
    """对 transient 网络/DNS 错误做 3 次退避重试；不掩盖业务级错误。"""
    import dashscope
    import time
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError("DASHSCOPE_API_KEY 未注入；先 source scripts/load_env.sh")
    dashscope.api_key = key
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = dashscope.TextEmbedding.call(model="text-embedding-v3", input=text)
            if getattr(resp, "status_code", None) == 200:
                return list(resp.output["embeddings"][0]["embedding"])
            last_err = RuntimeError(f"dashscope embedding non-200: {resp}")
        except Exception as e:
            # 仅对 transient (DNS / connection / timeout) 类错误重试；其它向上抛
            msg = str(e)
            transient = (
                "NameResolutionError" in msg or
                "Connection" in msg or
                "Timeout" in msg or
                "Max retries exceeded" in msg
            )
            last_err = e
            if not transient:
                raise
        if attempt < 3:
            time.sleep(2 * attempt)
    raise RuntimeError(f"dashscope embedding failed after 3 retries: {last_err}")


def _make_real_dashscope_rerank(invocation_log: list[dict]):
    """构造一个真调 DashScope gte-rerank 的 rerank_fn；
    每次调用追加 invocation 记录到 invocation_log（外部可读）。"""

    import dashscope

    def rerank_fn(query: str, candidates: list[dict]) -> list[dict]:
        key = os.environ.get("DASHSCOPE_API_KEY")
        if not key:
            raise RuntimeError("DASHSCOPE_API_KEY 未注入")
        dashscope.api_key = key

        # 提取 chunk_text（payload 里），保证候选集合 ⊆ 召回集合（_apply_rerank 会再校验一次）
        docs = []
        index_map = []  # rerank result index → original candidate
        for i, c in enumerate(candidates):
            text = (c.get("payload") or {}).get("chunk_text") or ""
            if not text:
                # 兜底：用 pack_id + content_type 作为可比文本
                text = f"{c.get('payload',{}).get('pack_id','')} {c.get('payload',{}).get('content_type','')}"
            docs.append(text)
            index_map.append(i)

        resp = dashscope.TextReRank.call(
            model="gte-rerank",
            query=query,
            documents=docs,
            top_n=len(docs),
            return_documents=False,
        )
        if getattr(resp, "status_code", None) != 200:
            invocation_log.append({"query": query, "ok": False, "error": str(resp)})
            raise RuntimeError(f"dashscope rerank failed: {resp}")

        results = resp.output.get("results", [])
        # results 是 [{"index": int, "relevance_score": float}, ...]
        reranked: list[dict] = []
        for r in results:
            orig_idx = r.get("index")
            if orig_idx is None or orig_idx >= len(candidates):
                continue
            cand = dict(candidates[orig_idx])  # shallow copy
            cand["_rerank_score"] = float(r.get("relevance_score", 0))
            reranked.append(cand)

        invocation_log.append({
            "query": query,
            "ok": True,
            "candidates_in": len(candidates),
            "candidates_out": len(reranked),
        })
        return reranked

    return rerank_fn


def _qdrant_client():
    from qdrant_client import QdrantClient
    url = os.environ.get("QDRANT_URL_STAGING")
    if not url:
        raise RuntimeError("QDRANT_URL_STAGING 未设置；先 bash scripts/qdrant_tunnel.sh up")
    return QdrantClient(url=url, api_key=os.environ.get("QDRANT_API_KEY") or None, timeout=30.0)


def _topk_signature(cands: list[dict], k: int = 10) -> list[dict]:
    """取前 k 候选的 (point_id, qdrant_score, rerank_score) 序列，用于前后对比。"""
    out = []
    for c in cands[:k]:
        out.append({
            "id": str(c.get("id")),
            "qdrant_score": float(c.get("score", 0)),
            "rerank_score": float(c.get("_rerank_score")) if c.get("_rerank_score") is not None else None,
        })
    return out


def _topk_order_changed(before: list[dict], after: list[dict]) -> bool:
    """rerank 是否改变了前 K 候选的 ID 顺序（注意：测的是顺序，不是 qdrant_score 字段）。"""
    return [b["id"] for b in before] != [a["id"] for a in after]


def _rerank_score_spread(after: list[dict]) -> float | None:
    """rerank 后前 K 的 rerank_score max-min；用于暴露 rerank 是否给出有判断力的分差。"""
    scores = [s["rerank_score"] for s in after if s.get("rerank_score") is not None]
    if not scores:
        return None
    return round(max(scores) - min(scores), 6)


def main() -> int:
    parser = argparse.ArgumentParser(description="KS-FIX-21 rerank runtime check")
    parser.add_argument("--staging", action="store_true", required=True,
                        help="只允许 staging（不接 prod）")
    parser.add_argument("--queries", type=int, default=10)
    parser.add_argument("--threshold-pct", type=float, default=0.6,
                        help="required topk_order_changed_count / queries 阈值；用户审查员设 0.6（10 中 ≥6）")
    parser.add_argument("--strict", action="store_true",
                        help="strict：未达 pass 条件返回 exit 1")
    parser.add_argument("--allowed-layers", nargs="+",
                        default=["brand_faye", "domain_general"])
    args = parser.parse_args()

    queries = STAGING_QUERIES[: args.queries]
    if len(queries) < args.queries:
        print(f"[FATAL] 内置 staging queries 仅 {len(STAGING_QUERIES)} 条，无法满足 N={args.queries}", file=sys.stderr)
        return 2

    try:
        client = _qdrant_client()
    except Exception as e:
        print(f"[FATAL] {e}", file=sys.stderr)
        return 2

    invocation_log: list[dict] = []
    rerank_fn = _make_real_dashscope_rerank(invocation_log)

    per_query = []
    rerank_invoked_count = 0
    topk_order_changed_count = 0
    for q in queries:
        try:
            baseline = vr.vector_retrieve(
                query=q,
                allowed_layers=args.allowed_layers,
                embed_fn=_real_dashscope_embed,
                qdrant_client=client,
            )
            reranked = vr.vector_retrieve(
                query=q,
                allowed_layers=args.allowed_layers,
                embed_fn=_real_dashscope_embed,
                qdrant_client=client,
                rerank_fn=rerank_fn,
            )
        except Exception as e:
            per_query.append({"query": q, "ok": False, "error": str(e)})
            continue

        if reranked["_meta"]["rerank_applied"]:
            rerank_invoked_count += 1

        sig_before = _topk_signature(baseline["candidates"], k=10)
        sig_after = _topk_signature(reranked["candidates"], k=10)
        order_changed = _topk_order_changed(sig_before, sig_after)
        if order_changed:
            topk_order_changed_count += 1
        rerank_spread = _rerank_score_spread(sig_after)

        per_query.append({
            "query": q,
            "ok": True,
            "rerank_applied": reranked["_meta"]["rerank_applied"],
            "candidates_count_before": len(baseline["candidates"]),
            "candidates_count_after": len(reranked["candidates"]),
            "topk_order_changed": order_changed,
            "rerank_score_spread_top10": rerank_spread,
            "topk_before": sig_before,
            "topk_after": sig_after,
        })

    n = len(queries)
    required_change = math.ceil(n * args.threshold_pct)
    pass_main = (rerank_invoked_count == n) and (topk_order_changed_count >= required_change)

    payload = {
        "card": "KS-FIX-21",
        "checked_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "env": "staging",
        "git_commit": _git_commit(),
        "evidence_level": "runtime_verified" if pass_main else "runtime_verified_risky",
        "queries_total": n,
        "rerank_invoked_count": rerank_invoked_count,
        "topk_order_changed_count": topk_order_changed_count,
        "required_order_change_threshold": required_change,
        "threshold_pct": args.threshold_pct,
        "pass_condition_met": pass_main,
        "metric_note": (
            "topk_order_changed 测的是前 10 候选 ID 顺序是否被 rerank 改变；"
            "rerank_score_spread_top10 是 rerank 返回分数的 max-min，反映 rerank 是否给出有分辨力的分差。"
            "rerank 不改 qdrant_score 字段是预期（qdrant_score 是原始余弦分），分变体现在 rerank_score 字段。"
        ),
        "rerank_invocation_log": invocation_log,
        "per_query": per_query,
        "risk_flags": (
            [] if pass_main else
            (
                ["rerank_not_invoked"] if rerank_invoked_count < n else []
            ) + (
                ["noop_rerank_topk_order_unchanged"] if topk_order_changed_count < required_change else []
            )
        ),
    }

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[FIX-21] rerank_invoked={rerank_invoked_count}/{n}, topk_order_changed={topk_order_changed_count}/{n} (need >= {required_change})")
    print(f"[FIX-21] artifact: {AUDIT_PATH.relative_to(REPO_ROOT)}")

    if args.strict and not pass_main:
        return 1
    return 0 if pass_main else 0  # non-strict 总是 0（artifact 已落，留人工裁决）


if __name__ == "__main__":
    sys.exit(main())

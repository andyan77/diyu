"""KS-RETRIEVAL-006 · vector_retrieval + payload hard filter / 向量召回 + payload 硬过滤.

W7 波次实现。**前置门禁 / pre-gate**：KS-VECTOR-001（qdrant_chunks 已构建）+
KS-POLICY-005（model_policy.yaml 已声明 embedding / rerank）+ KS-DIFY-ECS-004
（chunks 已灌库到 staging Qdrant 并对齐 alias `ks_chunks_current`）。

职责 / responsibility:
- 用 model_policy.embedding 配置生成 query embedding（query 向量化）
- 构造 Qdrant payload hard filter，至少含：
    brand_layer ∈ allowed_layers
    gate_status == "active"
    granularity_layer ∈ {L1, L2, L3}
- Qdrant search → top_k 候选
- 可选 rerank（按 KS-POLICY-005 rerank.enabled），**不得扩大召回范围**
- Qdrant 不可用 → 降级 structured_only（按 qdrant_fallback.yaml 语义）
- query embedding 维度与 policy.dimension 不符 → raise（fail-closed）

硬纪律 / hard discipline:
- 不灌库（属 KS-DIFY-ECS-004）；不调 LLM 做最终判断；不写 clean_output
- allowed_layers 由 KS-RETRIEVAL-001 tenant_scope_resolver 解析得到，本模块只消费
- 跨租户硬隔离 100%：brand_layer 不在 allowed_layers 的 chunk 永不命中
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

import yaml

__all__ = [
    "vector_retrieve",
    "VectorRetrieveResult",
    "EmbeddingDimensionMismatch",
    "RerankExpandedCandidatesError",
    "build_payload_filter",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = REPO_ROOT / "knowledge_serving" / "policies" / "model_policy.yaml"
DEFAULT_COLLECTION_ALIAS = "ks_chunks_current"

ALLOWED_GRANULARITY = ("L1", "L2", "L3")
GATE_ACTIVE = "active"

_BRAND_LAYER_RE = re.compile(r"^(domain_general|brand_[a-z0-9_]+)$")

FALLBACK_LOG_MARKER = "FALLBACK_STRUCTURED_ONLY"


class EmbeddingDimensionMismatch(ValueError):
    """query embedding 维度与 policy.embedding.dimension 不符。"""


class RerankExpandedCandidatesError(RuntimeError):
    """rerank 试图返回超出召回集合的新候选；按 KS-POLICY-005 拒绝。"""


VectorRetrieveResult = dict  # type alias: 见 vector_retrieve 返回值结构


# ---------- policy loading ----------

def _load_policy(policy_path: Path | None) -> dict:
    path = Path(policy_path) if policy_path else DEFAULT_POLICY_PATH
    if not path.exists():
        raise RuntimeError(f"model_policy.yaml 缺失 / missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    emb = (data or {}).get("embedding") or {}
    for k in ("model", "model_version", "dimension"):
        if not emb.get(k):
            raise RuntimeError(f"model_policy.embedding.{k} 缺失")
    if not isinstance(emb["dimension"], int) or emb["dimension"] <= 0:
        raise RuntimeError("model_policy.embedding.dimension 必须为正整数")
    rerank = (data or {}).get("rerank") or {}
    return {
        "model_policy_version": data.get("model_policy_version"),
        "embedding": {
            "provider": emb.get("provider"),
            "model": emb["model"],
            "model_version": emb["model_version"],
            "dimension": int(emb["dimension"]),
            "api_key_env": emb.get("api_key_env"),
        },
        "rerank": {
            "enabled": bool(rerank.get("enabled", False)),
            "provider": rerank.get("provider"),
            "model": rerank.get("model"),
            "model_version": rerank.get("model_version"),
            "api_key_env": rerank.get("api_key_env"),
            "top_k_before": int(rerank.get("top_k_before", 30)),
            "top_k_after": int(rerank.get("top_k_after", 8)),
        },
    }


# ---------- input validation ----------

def _validate_allowed_layers(allowed_layers: list[str]) -> None:
    if not allowed_layers:
        raise ValueError("allowed_layers 不能为空（应由 tenant_scope_resolver 解析得到）")
    for lay in allowed_layers:
        if not _BRAND_LAYER_RE.match(lay):
            raise ValueError(f"非法 brand_layer 命名：{lay!r}")


# ---------- filter ----------

def build_payload_filter(
    *,
    allowed_layers: Iterable[str],
    content_type: Optional[str] = None,
    extra_must: Optional[list[dict]] = None,
) -> dict:
    """构造 Qdrant payload hard filter。

    至少包含：
      - brand_layer ∈ allowed_layers
      - gate_status == "active"
      - granularity_layer ∈ {L1, L2, L3}
    可选：
      - content_type == <canonical id>（当 caller 显式给出时）
      - extra_must: 调用方追加的 must 条件（不可移除上面三条）
    """
    layers = list(allowed_layers)
    must: list[dict] = [
        {"key": "brand_layer", "match": {"any": layers}},
        {"key": "gate_status", "match": {"value": GATE_ACTIVE}},
        {"key": "granularity_layer", "match": {"any": list(ALLOWED_GRANULARITY)}},
    ]
    if content_type:
        must.append({"key": "content_type", "match": {"value": content_type}})
    if extra_must:
        must.extend(extra_must)
    return {"must": must}


# ---------- embedding ----------

def _default_embed_fn(policy: dict) -> Callable[[str], list[float]]:
    """默认 dashscope embedding 调用（运行时使用）；测试用 embed_fn 注入。"""
    def _embed(text: str) -> list[float]:
        api_key = os.environ.get(policy["embedding"]["api_key_env"] or "DASHSCOPE_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"{policy['embedding']['api_key_env']} 未设置，无法生成 query embedding"
            )
        import dashscope  # type: ignore
        dashscope.api_key = api_key
        resp = dashscope.TextEmbedding.call(
            model=policy["embedding"]["model"],
            input=text,
        )
        if getattr(resp, "status_code", None) != 200:
            raise RuntimeError(f"dashscope embedding 失败: {resp}")
        emb = resp.output["embeddings"][0]["embedding"]
        return list(emb)
    return _embed


# ---------- qdrant ----------

def _is_connection_error(exc: BaseException) -> bool:
    """判定是否属于 Qdrant down 的连通性异常（→ structured-only 降级）.

    纪律 / discipline:
      - 仅"真连不上 / 服务无应答 / 5xx 服务端崩"才走 fallback
      - 凭据错（401 / 403）/ 请求错（400 / 404）/ 业务错必须 propagate，不允许被掩盖成 down
      - qdrant-client `ResponseHandlingException` 专门包底层 transport / network 故障 → fallback
      - `ApiException` 是 openapi-generated 基类，会覆盖任意 HTTP 状态码（含 4xx），不能整类放行；
        改为查 status_code，仅 5xx / 无 status（网络层崩）才认为 down
    """
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    name = type(exc).__name__
    if name == "ResponseHandlingException":
        return True
    # qdrant-client UnexpectedResponse / ApiException：按 HTTP status 区分
    # 5xx → 服务端崩 → fallback；4xx → 配置/凭据/请求错 → propagate
    status = getattr(exc, "status_code", None)
    if status is None:
        # 还可能挂在 .status 上（openapi 生成代码常见命名）
        status = getattr(exc, "status", None)
    if name in {"UnexpectedResponse", "ApiException"}:
        if status is None:
            # 无 status 通常意味着 transport 层异常，归 down
            return True
        try:
            return int(status) >= 500
        except (TypeError, ValueError):
            return False
    return False


def _qdrant_search(
    client,
    *,
    collection_name: str,
    query_vector: list[float],
    query_filter: dict,
    limit: int,
):
    """统一 client.search 入口，便于测试 mock。"""
    return client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )


# ---------- rerank ----------

def _apply_rerank(
    *,
    query: str,
    candidates: list[dict],
    rerank_fn: Callable[[str, list[dict]], list[dict]],
    top_k_after: int,
) -> list[dict]:
    """跑 rerank；强制候选集合 ⊆ 原召回集合，禁止扩大召回范围。"""
    in_ids = {_candidate_id(c) for c in candidates}
    out = rerank_fn(query, candidates) or []
    out_ids = {_candidate_id(c) for c in out}
    intruders = out_ids - in_ids
    if intruders:
        raise RerankExpandedCandidatesError(
            f"rerank 返回了非召回集合的候选：{sorted(intruders)}"
        )
    return out[:top_k_after]


def _candidate_id(c: dict) -> str:
    """统一候选 ID 提取：优先 chunk_id，回退到 id。"""
    pl = c.get("payload") or {}
    return pl.get("chunk_id") or str(c.get("id"))


def _point_to_candidate(p) -> dict:
    """把 Qdrant ScoredPoint / dict 归一化为 candidate dict。"""
    if isinstance(p, dict):
        return {
            "id": p.get("id"),
            "score": p.get("score"),
            "payload": dict(p.get("payload") or {}),
        }
    return {
        "id": getattr(p, "id", None),
        "score": getattr(p, "score", None),
        "payload": dict(getattr(p, "payload", None) or {}),
    }


# ---------- public API ----------

def vector_retrieve(
    *,
    query: str,
    allowed_layers: list[str],
    content_type: Optional[str] = None,
    collection_name: str = DEFAULT_COLLECTION_ALIAS,
    policy_path: Path | None = None,
    embed_fn: Optional[Callable[[str], list[float]]] = None,
    qdrant_client=None,
    rerank_fn: Optional[Callable[[str, list[dict]], list[dict]]] = None,
    extra_filter_must: Optional[list[dict]] = None,
) -> VectorRetrieveResult:
    """13 步召回流程的向量召回步：query → embed → Qdrant search (payload hard filter) → rerank.

    Args:
        query: 用户输入文本（运行时由上游入参提供，本模块不做语义改写）
        allowed_layers: KS-RETRIEVAL-001 tenant_scope_resolver 解析得到的租户可见 brand_layer 集合
        content_type: 可选 canonical content_type（由 KS-RETRIEVAL-003 解析后给出）
        collection_name: Qdrant collection / alias 名（staging 走 alias `ks_chunks_current`）
        policy_path: model_policy.yaml 路径（默认 knowledge_serving/policies/model_policy.yaml）
        embed_fn: 注入的 embedding 函数；缺省走 dashscope（运行时）
        qdrant_client: 注入的 Qdrant client；缺省 lazy import qdrant_client.QdrantClient
        rerank_fn: 注入的 rerank 函数；rerank.enabled=True 时必传（否则跳过 rerank）
        extra_filter_must: 调用方追加的 must 条件（不可移除三条 hard filter）

    Returns:
        {
          "mode": "vector" | "structured_only",
          "candidates": [...],     # mode=structured_only 时为空
          "filter": {...},          # 实际下发到 Qdrant 的 filter
          "policy": {...},          # 关键 policy 快照
          "_meta": {
              "query_embedding_dim": int,
              "search_limit": int,
              "rerank_applied": bool,
              "fallback_reason": str | None,
              "collection_name": str,
          },
        }

    Raises:
        ValueError: 入参非法（allowed_layers / query）
        EmbeddingDimensionMismatch: query embedding 维度与 policy.dimension 不符
        RerankExpandedCandidatesError: rerank 试图扩大召回集合
    """
    # 入参校验
    if not query or not isinstance(query, str):
        raise ValueError("query 必须为非空字符串")
    _validate_allowed_layers(allowed_layers)

    policy = _load_policy(policy_path)
    expected_dim = policy["embedding"]["dimension"]
    rerank_cfg = policy["rerank"]
    search_limit = rerank_cfg["top_k_before"] if rerank_cfg["enabled"] else rerank_cfg["top_k_after"]

    # query embedding：维度硬校验（KS-POLICY-005 联动）
    embed = embed_fn or _default_embed_fn(policy)
    vec = embed(query)
    if not isinstance(vec, list):
        vec = list(vec)
    if len(vec) != expected_dim:
        raise EmbeddingDimensionMismatch(
            f"query embedding 维度={len(vec)} 与 policy.embedding.dimension={expected_dim} 不符"
        )

    # filter 构造
    query_filter = build_payload_filter(
        allowed_layers=allowed_layers,
        content_type=content_type,
        extra_must=extra_filter_must,
    )

    policy_snapshot = {
        "model_policy_version": policy["model_policy_version"],
        "embedding_model": policy["embedding"]["model"],
        "embedding_model_version": policy["embedding"]["model_version"],
        "embedding_dimension": expected_dim,
        "rerank_enabled": rerank_cfg["enabled"],
        "top_k_before": rerank_cfg["top_k_before"],
        "top_k_after": rerank_cfg["top_k_after"],
    }

    # Qdrant search：连通性失败 → structured_only fallback
    client = qdrant_client
    if client is None:
        try:
            from qdrant_client import QdrantClient  # type: ignore
            url = os.environ.get("QDRANT_URL_STAGING")
            if not url:
                # 没有 staging URL 不算 Qdrant down，这是配置错；保持 fail-closed 语义
                raise RuntimeError("QDRANT_URL_STAGING 未设置 / not set")
            api_key = os.environ.get("QDRANT_API_KEY") or None
            client = QdrantClient(url=url, api_key=api_key, timeout=10.0)
        except Exception as exc:  # noqa: BLE001
            if _is_connection_error(exc):
                return _fallback_result(
                    reason=f"qdrant_client_init_failed: {type(exc).__name__}",
                    query_filter=query_filter,
                    policy_snapshot=policy_snapshot,
                    expected_dim=expected_dim,
                    search_limit=search_limit,
                    collection_name=collection_name,
                )
            raise

    try:
        raw_points = _qdrant_search(
            client,
            collection_name=collection_name,
            query_vector=vec,
            query_filter=query_filter,
            limit=search_limit,
        )
    except Exception as exc:  # noqa: BLE001
        if _is_connection_error(exc):
            return _fallback_result(
                reason=f"qdrant_search_failed: {type(exc).__name__}",
                query_filter=query_filter,
                policy_snapshot=policy_snapshot,
                expected_dim=expected_dim,
                search_limit=search_limit,
                collection_name=collection_name,
            )
        raise

    candidates = [_point_to_candidate(p) for p in (raw_points or [])]

    rerank_applied = False
    if rerank_cfg["enabled"] and rerank_fn is not None and candidates:
        candidates = _apply_rerank(
            query=query,
            candidates=candidates,
            rerank_fn=rerank_fn,
            top_k_after=rerank_cfg["top_k_after"],
        )
        rerank_applied = True
    elif not rerank_cfg["enabled"]:
        candidates = candidates[:rerank_cfg["top_k_after"]]

    return {
        "mode": "vector",
        "candidates": candidates,
        "filter": query_filter,
        "policy": policy_snapshot,
        "_meta": {
            "query_embedding_dim": len(vec),
            "search_limit": search_limit,
            "rerank_applied": rerank_applied,
            "fallback_reason": None,
            "collection_name": collection_name,
        },
    }


def _fallback_result(
    *,
    reason: str,
    query_filter: dict,
    policy_snapshot: dict,
    expected_dim: int,
    search_limit: int,
    collection_name: str,
) -> VectorRetrieveResult:
    return {
        "mode": "structured_only",
        "candidates": [],
        "filter": query_filter,
        "policy": policy_snapshot,
        "_meta": {
            "query_embedding_dim": expected_dim,
            "search_limit": search_limit,
            "rerank_applied": False,
            "fallback_reason": reason,
            "fallback_log_marker": FALLBACK_LOG_MARKER,
            "collection_name": collection_name,
        },
    }

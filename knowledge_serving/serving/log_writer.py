"""KS-RETRIEVAL-008 · log_writer.

13 步召回流程第 13 步：把已构造好的 context_bundle 落到 §4.5 唯一 canonical
log 文件 `knowledge_serving/control/context_bundle_log.csv`，28 字段全填，
embedding / rerank / llm_assist 未启用时**显式**填 `"disabled"`，禁止留空。

S8 回放约束 / replay invariants:
- 单真源：拒绝写到非 canonical 路径（尤其是 `knowledge_serving/logs/...`）
- 同 request_id + 同上游输入 → 同 bundle_hash（由 context_bundle_builder 保证）
- 任何字段空字符串 → raise（disabled 必须显式）
"""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_LOG_PATH = REPO_ROOT / "knowledge_serving" / "control" / "context_bundle_log.csv"
FORBIDDEN_LOG_DIR = REPO_ROOT / "knowledge_serving" / "logs"

LOG_FIELDS = [
    "request_id",
    "tenant_id",
    "resolved_brand_layer",
    "allowed_layers",
    "user_query_hash",
    "classified_intent",
    "content_type",
    "selected_recipe_id",
    "retrieved_pack_ids",
    "retrieved_play_card_ids",
    "retrieved_asset_ids",
    "retrieved_overlay_ids",
    "retrieved_evidence_ids",
    "fallback_status",
    "missing_fields",
    "blocked_reason",
    "context_bundle_hash",
    "final_output_hash",
    "compile_run_id",
    "source_manifest_hash",
    "view_schema_version",
    "embedding_model",
    "embedding_model_version",
    "rerank_model",
    "rerank_model_version",
    "llm_assist_model",
    "model_policy_version",
    "created_at",
]


class LogWriteError(Exception):
    """log 写入违反 §4.5 单真源 / 字段完整性约束。

    刻意不继承 ValueError，避免 _ensure_canonical 内 try/except ValueError
    把自己抛出的异常吞掉。
    """


def _is_under(path: Path, parent: Path) -> bool:
    """path 是否在 parent 目录下；不使用 try/except，避免与 LogWriteError 冲突。"""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _ensure_canonical(path: Path) -> Path:
    """拒绝写到非 canonical 位置。

    硬规则：log 写入路径必须等于 control/context_bundle_log.csv，或在
    测试用 tmp 目录里（pytest tmp_path）。明确黑名单 `knowledge_serving/logs/`，
    阻止 §4.5 双真源回归。
    """
    p = path.resolve()
    if p == CANONICAL_LOG_PATH.resolve():
        return p
    # tmp 路径放行（用于单测）；但 knowledge_serving/logs/ 永远拒绝
    if _is_under(p, FORBIDDEN_LOG_DIR.resolve()):
        raise LogWriteError(
            f"禁止写到 knowledge_serving/logs/ 下；§4.5 单真源 = {CANONICAL_LOG_PATH}"
        )
    # 同名文件出现在仓库内其他目录 = 双真源风险
    if (
        p.name == "context_bundle_log.csv"
        and p.parent != CANONICAL_LOG_PATH.parent
        and _is_under(p, REPO_ROOT.resolve())
    ):
        raise LogWriteError(
            f"context_bundle_log.csv 仅允许 canonical 位置 {CANONICAL_LOG_PATH}，"
            f"实际写入 {p}"
        )
    return p


def _join_ids(values: Iterable[Any] | None) -> str:
    """list[str] → ';' joined；空列表 → 'none'（显式标记，禁止空字符串）。"""
    if values is None:
        return "none"
    vals = [str(v) for v in values if v is not None and str(v) != ""]
    return ";".join(vals) if vals else "none"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_model_field(model_policy: dict, section: str, key: str) -> str:
    """从 model_policy.yaml 派生的 dict 里取 section.key，未启用 → 'disabled'。"""
    sec = model_policy.get(section)
    if not isinstance(sec, dict):
        return "disabled"
    if not sec.get("enabled", True) and section != "embedding":
        # embedding 默认启用；rerank / llm_assist 按 enabled 决定
        return "disabled"
    val = sec.get(key)
    if val is None or val == "":
        return "disabled"
    return str(val)


def _build_row(
    *,
    bundle: dict,
    bundle_meta: dict,
    classified_intent: str,
    selected_recipe_id: str,
    retrieved_ids: dict,
    model_policy: dict,
    final_output_hash: str | None,
    blocked_reason: str | None,
    created_at: str | None,
) -> dict[str, str]:
    gov = bundle.get("governance") or {}

    row = {
        "request_id": bundle.get("request_id", ""),
        "tenant_id": bundle.get("tenant_id", ""),
        "resolved_brand_layer": bundle.get("resolved_brand_layer", ""),
        "allowed_layers": _join_ids(bundle.get("allowed_layers")),
        "user_query_hash": str(bundle_meta.get("user_query_hash", "")),
        "classified_intent": classified_intent or "",
        "content_type": bundle.get("content_type", ""),
        "selected_recipe_id": selected_recipe_id or "",
        "retrieved_pack_ids": _join_ids(retrieved_ids.get("pack_ids")),
        "retrieved_play_card_ids": _join_ids(retrieved_ids.get("play_card_ids")),
        "retrieved_asset_ids": _join_ids(retrieved_ids.get("asset_ids")),
        "retrieved_overlay_ids": _join_ids(retrieved_ids.get("overlay_ids")),
        "retrieved_evidence_ids": _join_ids(retrieved_ids.get("evidence_ids")),
        "fallback_status": bundle.get("fallback_status", ""),
        "missing_fields": _join_ids(bundle.get("missing_fields")),
        "blocked_reason": blocked_reason or "none",
        "context_bundle_hash": str(bundle_meta.get("bundle_hash", "")),
        "final_output_hash": final_output_hash or "disabled",
        "compile_run_id": str(gov.get("compile_run_id", "")),
        "source_manifest_hash": str(gov.get("source_manifest_hash", "")),
        "view_schema_version": str(gov.get("view_schema_version", "")),
        "embedding_model": _resolve_model_field(model_policy, "embedding", "model"),
        "embedding_model_version": _resolve_model_field(model_policy, "embedding", "model_version"),
        "rerank_model": _resolve_model_field(model_policy, "rerank", "model"),
        "rerank_model_version": _resolve_model_field(model_policy, "rerank", "model_version"),
        "llm_assist_model": _resolve_model_field(model_policy, "llm_assist", "model"),
        "model_policy_version": str(model_policy.get("model_policy_version") or "disabled"),
        "created_at": created_at or _now_iso(),
    }

    # 字段完整性硬门：任一字段空字符串 → raise（强制 "disabled" 显式）。
    for f in LOG_FIELDS:
        if row.get(f, "") == "":
            raise LogWriteError(
                f"log 字段 {f!r} 为空；未启用必须显式填 'disabled' / 'none'，"
                f"row request_id={row.get('request_id')!r}"
            )
    return row


def write_context_bundle_log(
    *,
    bundle: dict,
    bundle_meta: dict,
    classified_intent: str,
    selected_recipe_id: str,
    retrieved_ids: dict,
    model_policy: dict,
    final_output_hash: str | None = None,
    blocked_reason: str | None = None,
    log_path: Path | None = None,
    created_at: str | None = None,
) -> tuple[Path, dict[str, str]]:
    """追加一行 log 到 canonical csv；返回写入路径 + 写入行。

    Args:
        bundle: context_bundle_builder.build_context_bundle 的 bundle 输出
        bundle_meta: 同函数的 meta 输出（带 bundle_hash / user_query_hash）
        classified_intent: 由 Dify 开始节点 / API 入参提供（intent_classifier 输出）
        selected_recipe_id: recipe_selector 输出
        retrieved_ids: {pack_ids, play_card_ids, asset_ids, overlay_ids, evidence_ids}
            各 list[str]；空列表会写 'none'，禁止留空字符串
        model_policy: model_policy.yaml 解析结果
        final_output_hash: 若 LLM 未实际产出文案则填 None → log 写 'disabled'
        blocked_reason: fallback 是 blocked_* 时的 reason；否则 None → 'none'
        log_path: 默认 canonical；测试用 tmp_path
        created_at: 默认 utc now；回放测试可注入固定值
    """
    target = _ensure_canonical(log_path or CANONICAL_LOG_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)

    row = _build_row(
        bundle=bundle,
        bundle_meta=bundle_meta,
        classified_intent=classified_intent,
        selected_recipe_id=selected_recipe_id,
        retrieved_ids=retrieved_ids,
        model_policy=model_policy,
        final_output_hash=final_output_hash,
        blocked_reason=blocked_reason,
        created_at=created_at,
    )

    write_header = not target.exists() or target.stat().st_size == 0
    with target.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    return target, row


def read_log_rows(log_path: Path | None = None) -> list[dict[str, str]]:
    """按 S8 回放读 log；调试 / 测试用。"""
    target = (log_path or CANONICAL_LOG_PATH).resolve()
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

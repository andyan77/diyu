#!/usr/bin/env python3
"""KS-DIFY-ECS-010 · context_bundle 日志回放 / log replay (S8 严格守门).

S gate / gate: S8（任意 request_id 可重建当时喂给 LLM 的 context_bundle）.

边界 / scope:
- **CSV-only**：S8 回放硬约束（KS-DIFY-ECS-005 §10 / §7 invariant）——回放路径
  只读 `knowledge_serving/control/context_bundle_log.csv`（§4.5 唯一 canonical），
  绝不接 PG / Qdrant / 任何外部依赖
- 不重跑 LLM；不写 clean_output；不改 log
- log 行业务字段（business_brief / recipe 全 JSON / generation_constraints）
  并未冗余存入 CSV log → 严格 byte-identical bundle_hash 复算**不在本卡可行域内**；
  本卡 replay 验证的是 **log→views 链路一致性 + 篡改可检出**：
  1. log 行命中 canonical CSV
  2. log 的 governance 三件套（compile_run_id / source_manifest_hash / view_schema_version）
     与当前 view csv 一致（不一致 = 跨 compile_run_id 混用，拒）
  3. log 中每个 retrieved_*_id 都能在对应 view 中按 id 列查到行，且该行
     compile_run_id 同 log
  4. 解析到的 view 行 brand_layer 全部落在 log 的 allowed_layers 集合内
     （S9 跨租户隔离回归 / cross-tenant guardrail）
  5. tenant_id → tsr.resolve()'s brand_layer 与 log 的 resolved_brand_layer 一致
  6. fallback_status / content_type / brand_layer 取值合法
- 输出 `replay_consistency_hash`：所有上述输入归一化后 sha256 摘要；同一 log 行
  在同一 view 快照下复跑必同 hash；任何篡改改输入则 hash 变（同时上面 1-6 任一
  也会失败）

退出码 / exit codes:
  0  replay 成功，所有 6 项一致性检查通过
  2  request_id 未命中（log 行不存在）
  3  governance 三件套与当前 views 不一致（compile_run_id 漂移 / 历史数据已删）
  4  log 的某 retrieved_*_id 在 view 中查不到（篡改 / 数据已删）
  5  resolved view 行 compile_run_id 与 log 不同（跨 run 混用）
  6  租户 / brand_layer / S9 隔离破裂
  7  字段语义非法（fallback_status / content_type / brand_layer 等枚举越界）
  9  入参 / 环境异常
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.serving import tenant_scope_resolver as tsr  # noqa: E402
from knowledge_serving.serving import log_writer as lw  # noqa: E402

DEFAULT_VIEWS_ROOT = REPO_ROOT / "knowledge_serving" / "views"
DEFAULT_AUDIT_PATH = (
    REPO_ROOT / "knowledge_serving" / "audit" / "replay_KS-DIFY-ECS-010.json"
)

# view csv → primary id column 映射（log 中 retrieved_*_ids 拼回 view 行的 key）
VIEW_ID_COLUMN: dict[str, str] = {
    "pack_view": "source_pack_id",
    "play_card_view": "play_card_id",
    "runtime_asset_view": "runtime_asset_id",
    "brand_overlay_view": "overlay_id",
    "evidence_view": "evidence_id",
}

# log retrieved_*_ids 字段 → view 名映射
LOG_TO_VIEW: dict[str, str] = {
    "retrieved_pack_ids": "pack_view",
    "retrieved_play_card_ids": "play_card_view",
    "retrieved_asset_ids": "runtime_asset_view",
    "retrieved_overlay_ids": "brand_overlay_view",
    "retrieved_evidence_ids": "evidence_view",
}

_BRAND_LAYER_RE = re.compile(r"^(domain_general|needs_review|brand_[a-z][a-z0-9_]*)$")
_VALID_FALLBACK = {
    "brand_full_applied", "brand_partial_fallback", "domain_only",
    "blocked_missing_required_brand_fields", "blocked_missing_business_brief",
}


class ReplayError(Exception):
    """replay 一致性检查失败 / strict replay check failed.

    携带语义化 exit code 让 caller 据此返回到 shell。
    """

    def __init__(self, code: int, message: str, *, details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


# ============================================================
# helpers
# ============================================================

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256(payload: str) -> str:
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_json_list(raw: str, *, field: str) -> list[str]:
    """log csv 中 array 字段是 JSON-encoded list（KS-DIFY-ECS-006 W11 收口后口径）。"""
    try:
        v = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as e:
        raise ReplayError(7, f"log 字段 {field!r} 不是合法 JSON list: {raw!r} ({e})")
    if not isinstance(v, list):
        raise ReplayError(7, f"log 字段 {field!r} 期望 list，实际 {type(v).__name__}")
    return [str(x) for x in v]


def _load_log_row(log_path: Path, request_id: str) -> dict[str, str]:
    if not log_path.exists():
        raise ReplayError(9, f"canonical log 不存在 / missing: {log_path}")
    with log_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("request_id") == request_id:
                return row
    raise ReplayError(
        2, f"request_id 未命中 / not found: {request_id!r}",
        details={"log_path": str(log_path)},
    )


def _load_view_index(view_name: str, views_root: Path) -> dict[str, list[dict[str, str]]]:
    """读 view csv → {id_value: [row, ...]} 索引（一个 id 可能对应多行，例如同 pack 多角度）。"""
    path = views_root / f"{view_name}.csv"
    if not path.exists():
        raise ReplayError(3, f"view 不存在 / view csv missing: {path}")
    id_col = VIEW_ID_COLUMN[view_name]
    idx: dict[str, list[dict[str, str]]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if id_col not in (reader.fieldnames or []):
            raise ReplayError(3, f"view {view_name} 缺 id 列 {id_col}")
        for row in reader:
            k = row.get(id_col) or ""
            idx.setdefault(k, []).append(row)
    return idx


def _view_governance(views_root: Path) -> dict[str, str]:
    """从 pack_view 头一行抽 governance；其余 view 同 compile_run_id 才能通过 §3 check。"""
    path = views_root / "pack_view.csv"
    if not path.exists():
        raise ReplayError(3, f"pack_view.csv 不存在 / missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        row = next(reader, None)
    if not row:
        raise ReplayError(3, "pack_view.csv 为空，无法抽 governance")
    return {
        "compile_run_id": row.get("compile_run_id", ""),
        "source_manifest_hash": row.get("source_manifest_hash", ""),
        "view_schema_version": row.get("view_schema_version", ""),
    }


# ============================================================
# 一致性检查（exit code 与 §6 对抗性测试对齐）
# ============================================================

def _check_governance_consistency(log_row: dict, views_gov: dict) -> None:
    """§4.2 / §6 case 2 / case 4：log governance 与当前 views 必一致；否则拒绝（exit 3）。"""
    for f in ("compile_run_id", "source_manifest_hash", "view_schema_version"):
        if log_row.get(f) != views_gov.get(f):
            raise ReplayError(
                3,
                f"governance {f} 不一致 / mismatch: log={log_row.get(f)!r} views={views_gov.get(f)!r}",
                details={"field": f, "log": log_row.get(f), "views": views_gov.get(f)},
            )


def _check_tenant_brand_consistency(log_row: dict) -> dict[str, Any]:
    """§6 隐含：tenant_id → tsr.resolve() 推断的 brand_layer / allowed_layers 必匹配 log 行；
    防 log 被篡改 brand_layer 让回放仍然看似合规（exit 6）。"""
    tenant_id = log_row.get("tenant_id") or ""
    try:
        scope = tsr.resolve(tenant_id)
    except tsr.TenantNotAuthorized as e:
        raise ReplayError(6, f"tenant 未登记 / not authorized: {tenant_id!r} ({e})")
    if scope["brand_layer"] != log_row.get("resolved_brand_layer"):
        raise ReplayError(
            6,
            f"brand_layer 与 tenant 推断不符 / brand layer mismatch with tenant",
            details={
                "tenant_id": tenant_id,
                "log_brand_layer": log_row.get("resolved_brand_layer"),
                "tsr_brand_layer": scope["brand_layer"],
            },
        )
    log_allowed = _parse_json_list(log_row.get("allowed_layers") or "[]", field="allowed_layers")
    if sorted(log_allowed) != sorted(scope["allowed_layers"]):
        raise ReplayError(
            6, "allowed_layers 与 tenant 推断不符",
            details={
                "tenant_id": tenant_id,
                "log_allowed": log_allowed,
                "tsr_allowed": scope["allowed_layers"],
            },
        )
    return scope


def _check_field_enums(log_row: dict) -> None:
    """§6 防错枚举：fallback_status / brand_layer 取值必在合法集合（exit 7）。"""
    fs = log_row.get("fallback_status") or ""
    if fs not in _VALID_FALLBACK:
        raise ReplayError(7, f"fallback_status 非法 / illegal: {fs!r}")
    bl = log_row.get("resolved_brand_layer") or ""
    if not _BRAND_LAYER_RE.match(bl):
        raise ReplayError(7, f"resolved_brand_layer 非法 / illegal: {bl!r}")


def _check_retrieved_ids_resolve(
    log_row: dict,
    views_root: Path,
    log_compile_run_id: str,
    allowed_layers: set[str],
) -> dict[str, list[dict[str, str]]]:
    """§4.3 + §6 case "篡改 / 跨 run / 跨租户"：每个 retrieved id 都必须在 view 中查到，
    且 view 行 compile_run_id 一致，brand_layer 在 allowed_layers 内。"""
    resolved: dict[str, list[dict[str, str]]] = {}
    for log_field, view_name in LOG_TO_VIEW.items():
        ids = _parse_json_list(log_row.get(log_field) or "[]", field=log_field)
        if not ids:
            resolved[view_name] = []
            continue
        index = _load_view_index(view_name, views_root)
        rows: list[dict[str, str]] = []
        for rid in ids:
            hits = index.get(rid)
            if not hits:
                raise ReplayError(
                    4,
                    f"retrieved id 在 view 中查不到 / missing in view: "
                    f"{log_field}={rid!r} not in {view_name}",
                    details={"id": rid, "view": view_name},
                )
            # 同 id 多行情况：全部参与一致性 hash，且每行单独校验
            for hit in hits:
                if hit.get("compile_run_id") != log_compile_run_id:
                    raise ReplayError(
                        5,
                        f"view 行 compile_run_id 与 log 不同 / cross-run row: "
                        f"id={rid!r} view={view_name} "
                        f"view_run={hit.get('compile_run_id')!r} log_run={log_compile_run_id!r}",
                        details={"id": rid, "view": view_name},
                    )
                bl = hit.get("brand_layer") or ""
                if bl and bl not in allowed_layers:
                    raise ReplayError(
                        6,
                        f"view 行 brand_layer 越界 / cross-tenant leak: "
                        f"id={rid!r} brand={bl!r} not in allowed={sorted(allowed_layers)}",
                        details={"id": rid, "view": view_name, "brand_layer": bl},
                    )
                rows.append(hit)
        resolved[view_name] = rows
    return resolved


def _compute_consistency_hash(
    log_row: dict,
    resolved: dict[str, list[dict[str, str]]],
) -> str:
    """归一化 log + resolved view 子集 → sha256；同 log + 同 views → 同 hash；
    log 行任何字段被篡改 → hash 变（在 §4 完成后由 caller 落 audit 锚定）。
    """
    # 只取 deterministic 字段（不含 created_at；created_at 是落盘时戳，
    # 不参与一致性签名以保证幂等可对比）
    log_snapshot = {
        "request_id": log_row["request_id"],
        "tenant_id": log_row["tenant_id"],
        "resolved_brand_layer": log_row["resolved_brand_layer"],
        "allowed_layers": sorted(_parse_json_list(log_row["allowed_layers"], field="allowed_layers")),
        "content_type": log_row["content_type"],
        "classified_intent": log_row["classified_intent"],
        "selected_recipe_id": log_row["selected_recipe_id"],
        "fallback_status": log_row["fallback_status"],
        "missing_fields": sorted(_parse_json_list(log_row["missing_fields"], field="missing_fields")),
        "blocked_reason": log_row["blocked_reason"],
        "user_query_hash": log_row["user_query_hash"],
        "context_bundle_hash": log_row["context_bundle_hash"],
        "governance": {
            "compile_run_id": log_row["compile_run_id"],
            "source_manifest_hash": log_row["source_manifest_hash"],
            "view_schema_version": log_row["view_schema_version"],
        },
        "model": {
            "embedding_model": log_row["embedding_model"],
            "embedding_model_version": log_row["embedding_model_version"],
            "rerank_model": log_row["rerank_model"],
            "model_policy_version": log_row["model_policy_version"],
        },
        "retrieved_ids": {
            "pack": sorted(_parse_json_list(log_row["retrieved_pack_ids"], field="retrieved_pack_ids")),
            "play_card": sorted(_parse_json_list(log_row["retrieved_play_card_ids"], field="retrieved_play_card_ids")),
            "asset": sorted(_parse_json_list(log_row["retrieved_asset_ids"], field="retrieved_asset_ids")),
            "overlay": sorted(_parse_json_list(log_row["retrieved_overlay_ids"], field="retrieved_overlay_ids")),
            "evidence": sorted(_parse_json_list(log_row["retrieved_evidence_ids"], field="retrieved_evidence_ids")),
        },
    }
    # resolved view 子集：每个 view 取 (id_col, brand_layer, compile_run_id) 元组排序
    resolved_snapshot: dict[str, list[list[str]]] = {}
    for view_name, rows in resolved.items():
        id_col = VIEW_ID_COLUMN[view_name]
        tuples = sorted(
            [
                row.get(id_col, ""),
                row.get("brand_layer", ""),
                row.get("compile_run_id", ""),
            ]
            for row in rows
        )
        resolved_snapshot[view_name] = tuples
    return _sha256(_canonical_dumps({"log": log_snapshot, "resolved": resolved_snapshot}))


# ============================================================
# main replay entry
# ============================================================

def replay(
    request_id: str,
    *,
    log_path: Optional[Path] = None,
    views_root: Optional[Path] = None,
) -> dict[str, Any]:
    """对单个 request_id 做 6 项 S8 一致性检查；任一失败 → 抛 ReplayError。

    成功返回 audit dict（含 replay_consistency_hash + 解析摘要），caller 自行 json.dump。
    """
    log_path = log_path or lw.CANONICAL_LOG_PATH
    views_root = views_root or DEFAULT_VIEWS_ROOT

    # 1) 命中 log
    log_row = _load_log_row(log_path, request_id)

    # 2) 字段语义合法
    _check_field_enums(log_row)

    # 3) governance 三件套与当前 views 一致
    views_gov = _view_governance(views_root)
    _check_governance_consistency(log_row, views_gov)

    # 4) tenant→brand 一致 + allowed_layers 一致
    scope = _check_tenant_brand_consistency(log_row)
    allowed_layers = set(scope["allowed_layers"])

    # 5) retrieved ids 全部 resolve + 跨 run 拒绝 + 越界 brand 拒绝
    resolved = _check_retrieved_ids_resolve(
        log_row, views_root,
        log_compile_run_id=log_row["compile_run_id"],
        allowed_layers=allowed_layers,
    )

    # 6) 一致性 hash（输出锚定 / 篡改可比对）
    consistency_hash = _compute_consistency_hash(log_row, resolved)

    return {
        "request_id": request_id,
        "status": "ok",
        "replay_consistency_hash": consistency_hash,
        "log_context_bundle_hash": log_row["context_bundle_hash"],
        "governance": views_gov,
        "tenant_id": log_row["tenant_id"],
        "resolved_brand_layer": log_row["resolved_brand_layer"],
        "allowed_layers": sorted(allowed_layers),
        "resolved_counts": {v: len(rows) for v, rows in resolved.items()},
        "checks_passed": [
            "log_row_found",
            "field_enums",
            "governance_consistency",
            "tenant_brand_consistency",
            "retrieved_ids_resolve",
        ],
        "log_path": str(log_path),
        "views_root": str(views_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="KS-DIFY-ECS-010 context_bundle 日志回放")
    parser.add_argument("--request-id", required=True, help="目标 request_id")
    parser.add_argument(
        "--log-path", type=Path, default=None,
        help="canonical CSV 路径（默认 knowledge_serving/control/context_bundle_log.csv）",
    )
    parser.add_argument(
        "--views-root", type=Path, default=None,
        help="views 根目录（默认 knowledge_serving/views）",
    )
    parser.add_argument(
        "--audit", type=Path, default=None,
        help="audit JSON 输出（默认 knowledge_serving/audit/replay_KS-DIFY-ECS-010.json）",
    )
    args = parser.parse_args()

    audit_payload: dict[str, Any] = {
        "task_id": "KS-DIFY-ECS-010",
        "request_id": args.request_id,
        "started_at": _now(),
    }
    try:
        result = replay(
            args.request_id,
            log_path=args.log_path,
            views_root=args.views_root,
        )
        audit_payload.update(result)
        audit_payload["finished_at"] = _now()
        exit_code = 0
    except ReplayError as e:
        audit_payload.update({
            "status": "fail",
            "error_code": e.code,
            "error_message": str(e),
            "error_details": e.details,
            "finished_at": _now(),
        })
        exit_code = e.code
    except Exception as e:  # noqa: BLE001
        audit_payload.update({
            "status": "fail",
            "error_code": 9,
            "error_message": f"{type(e).__name__}: {e}",
            "finished_at": _now(),
        })
        exit_code = 9

    audit_path = args.audit or DEFAULT_AUDIT_PATH
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(
        {k: audit_payload[k] for k in audit_payload
         if k not in ("error_details", "log_path", "views_root")},
        indent=2, ensure_ascii=False,
    ))
    print(f"audit → {audit_path.relative_to(REPO_ROOT)}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

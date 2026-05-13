"""KS-RETRIEVAL-008 + KS-DIFY-ECS-005 · log_writer.

13 步召回流程第 13 步：把已构造好的 context_bundle 落到 §4.5 唯一 canonical
log 文件 `knowledge_serving/control/context_bundle_log.csv`，28 字段全填，
embedding / rerank / llm_assist 未启用时**显式**填 `"disabled"`，禁止留空。

KS-DIFY-ECS-005 双写扩展 / dual-write extension:
- CSV 仍是 §4.5 唯一 canonical（S8 回放真源）；先 write + fsync，磁盘落定才返回
- PG 是 outbox mirror（BI / 跨服务查询用）；CSV 成功后异步同步
- PG 失败：行进 outbox jsonl（`pending_pg_sync`），不回退、不影响业务调用
- CSV 失败：raise，PG **绝不写**（不能反向成隐含真源）
- 同 request_id 重复写：CSV 拒绝（uniqueness）

S8 回放约束 / replay invariants:
- 单真源：拒绝写到非 canonical 路径（尤其是 `knowledge_serving/logs/...`）
- 同 request_id + 同上游输入 → 同 bundle_hash（由 context_bundle_builder 保证）
- 任何字段空字符串 → raise（disabled 必须显式）
- read_log_rows 只读 CSV；PG 不参与回放
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_LOG_PATH = REPO_ROOT / "knowledge_serving" / "control" / "context_bundle_log.csv"
CANONICAL_OUTBOX_PATH = REPO_ROOT / "knowledge_serving" / "control" / "context_bundle_log_outbox.jsonl"
FORBIDDEN_LOG_DIR = REPO_ROOT / "knowledge_serving" / "logs"

OUTBOX_STATUS_PENDING = "pending_pg_sync"
OUTBOX_STATUS_REPLAYED = "replayed"

# PG mirror 表名（KS-DIFY-ECS-005 staging schema 约定；DDL 由 staging 部署阶段建表，
# 本模块只通过注入的 pg_writer callable 与 PG 交互，本地测试不依赖真 PG）。
PG_MIRROR_TABLE = "knowledge.context_bundle_log"

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


def _serialize_id_list(values: Iterable[Any] | None) -> str:
    """list[str] → JSON-encoded string（schema array 真源对齐 / KS-DIFY-ECS-006 W11 收口）。

    旧版 `_join_ids` 用 ';' 拼接，导致 `validate_serving_governance.py` preflight
    把 array 字段看成 string 报 type mismatch（control_tables.schema 期望 array）。
    改为 JSON 编码，CSV cell 反序列化（`json.loads`）即可还原 schema 期望类型；
    空 list / None 都落 `"[]"`，保留显式"非空字符串"语义，配合下游空字段守门。
    """
    if values is None:
        vals: list[str] = []
    else:
        vals = [str(v) for v in values if v is not None and str(v) != ""]
    return json.dumps(vals, ensure_ascii=False, separators=(",", ":"))


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
        "allowed_layers": _serialize_id_list(bundle.get("allowed_layers")),
        "user_query_hash": str(bundle_meta.get("user_query_hash", "")),
        "classified_intent": classified_intent or "",
        "content_type": bundle.get("content_type", ""),
        "selected_recipe_id": selected_recipe_id or "",
        "retrieved_pack_ids": _serialize_id_list(retrieved_ids.get("pack_ids")),
        "retrieved_play_card_ids": _serialize_id_list(retrieved_ids.get("play_card_ids")),
        "retrieved_asset_ids": _serialize_id_list(retrieved_ids.get("asset_ids")),
        "retrieved_overlay_ids": _serialize_id_list(retrieved_ids.get("overlay_ids")),
        "retrieved_evidence_ids": _serialize_id_list(retrieved_ids.get("evidence_ids")),
        "fallback_status": bundle.get("fallback_status", ""),
        "missing_fields": _serialize_id_list(bundle.get("missing_fields")),
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


def _default_outbox_for(log_path: Path) -> Path:
    """log_path 同目录下的 outbox jsonl，跟 csv 配对。canonical csv → canonical outbox。"""
    if log_path.resolve() == CANONICAL_LOG_PATH.resolve():
        return CANONICAL_OUTBOX_PATH
    return log_path.parent / "context_bundle_log_outbox.jsonl"


def _check_duplicate_request_id(target: Path, request_id: str) -> None:
    """CSV 内若已存在同 request_id 行 → raise（卡 §6 unique 约束）。

    实现：流式读 csv，命中即抛；O(n) 但 log 文件本身有界（一次会话一行级别）。
    """
    if not target.exists() or target.stat().st_size == 0:
        return
    with target.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for existing in reader:
            if existing.get("request_id") == request_id:
                raise LogWriteError(
                    f"duplicate request_id={request_id!r} 已存在于 {target}；"
                    "CSV 是 §4.5 单 canonical，禁止重复写"
                )


def _append_outbox(
    outbox_path: Path,
    row: dict[str, str],
    *,
    status: str,
    error: str | None = None,
    attempts: int = 1,
) -> None:
    """把行追加到 outbox jsonl；每条 json line 含 row + status + error + attempts + ts。"""
    outbox_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "request_id": row.get("request_id"),
        "status": status,
        "attempts": attempts,
        "error": error,
        "queued_at": _now_iso(),
        "row": row,
    }
    with outbox_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


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
    pg_writer: Optional[Callable[[dict[str, str]], None]] = None,
    outbox_path: Path | None = None,
    fsync_csv: bool = True,
) -> tuple[Path, dict[str, str]]:
    """追加一行 log 到 canonical csv；返回写入路径 + 写入行。

    顺序硬约束（KS-DIFY-ECS-005 §4 / §6）：
      1. CSV 写 + fsync（磁盘落定才继续）；任一步失败 → raise，**绝不**调 pg_writer
      2. CSV 成功后才尝试 pg_writer（mirror）
      3. pg_writer 失败 → 行进 outbox（pending_pg_sync），不回退、不影响调用方

    Args:
        bundle / bundle_meta / classified_intent / selected_recipe_id /
        retrieved_ids / model_policy / final_output_hash / blocked_reason /
        log_path / created_at: 同 KS-RETRIEVAL-008 原版
        pg_writer: 可选 PG mirror 写入回调。签名 `(row: dict) -> None`；
            None 时纯 CSV 模式（兼容 W9 demo / KS-RETRIEVAL-008 单元测试）
        outbox_path: pg_writer 失败时 fallback 队列；None → 与 log_path 同目录
        fsync_csv: 默认 True；测试可关闭（tmpfs / mock fs 不支持 fsync）
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

    # 步骤 0：unique 约束（卡 §6 "同 request_id 两次写 → CSV 拒绝"）
    _check_duplicate_request_id(target, row["request_id"])

    # 步骤 1：CSV 写 + fsync（canonical 必须落盘成功，下游 PG 才允许尝试）
    write_header = not target.exists() or target.stat().st_size == 0
    with target.open("a", encoding="utf-8", newline="\n") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS, lineterminator="\n")
        if write_header:
            writer.writeheader()
        writer.writerow(row)
        f.flush()
        if fsync_csv:
            try:
                os.fsync(f.fileno())
            except OSError:
                # tmpfs / 某些 mock fs 不支持 fsync；不致命，CSV 写入本身已成功
                pass
    # 此处 CSV 已落盘。**若上面 with 块任何一行 raise，整个函数已退出，pg_writer 不会被调用**。

    # 步骤 2：PG mirror（best-effort，失败入 outbox）
    if pg_writer is not None:
        ob = outbox_path or _default_outbox_for(target)
        try:
            pg_writer(row)
        except Exception as e:  # noqa: BLE001 mirror 失败不影响业务
            _append_outbox(ob, row, status=OUTBOX_STATUS_PENDING, error=f"{type(e).__name__}: {e}")

    return target, row


def read_log_rows(log_path: Path | None = None) -> list[dict[str, str]]:
    """按 S8 回放读 log；调试 / 测试用。S8 回放硬约束：只读 CSV，不访问外部数据库。"""
    target = (log_path or CANONICAL_LOG_PATH).resolve()
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_outbox(outbox_path: Path | None = None) -> list[dict[str, Any]]:
    """读 outbox jsonl；reconcile 脚本用。"""
    target = (outbox_path or CANONICAL_OUTBOX_PATH).resolve()
    if not target.exists():
        return []
    out: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def reconcile_pg_mirror(
    *,
    csv_path: Path | None = None,
    pg_reader: Callable[[], list[dict[str, str]]],
    pg_writer: Callable[[dict[str, str]], None],
    outbox_path: Path | None = None,
) -> dict[str, Any]:
    """一致性校验：以 CSV 为基准对比 PG mirror。

    - **PG 缺行**（CSV 有 / PG 无）：调 pg_writer 补齐，并在 outbox 标 replayed
    - **PG 多行**（PG 有 / CSV 无）：报警（CSV 才是真源），不擅自删 PG

    Returns:
        {
            "csv_count": int,
            "pg_count": int,
            "missing_in_pg": list[request_id],
            "extra_in_pg": list[request_id],   # 报警，需人工
            "replayed_count": int,
            "replay_errors": list[{request_id, error}],
        }
    """
    csv_rows = read_log_rows(csv_path)
    pg_rows = pg_reader()
    csv_ids = {r["request_id"]: r for r in csv_rows}
    pg_ids = {r["request_id"]: r for r in pg_rows}

    missing_in_pg = [rid for rid in csv_ids if rid not in pg_ids]
    extra_in_pg = [rid for rid in pg_ids if rid not in csv_ids]

    ob = outbox_path or _default_outbox_for(
        (csv_path or CANONICAL_LOG_PATH).resolve()
    )
    replayed = 0
    errors: list[dict[str, str]] = []
    for rid in missing_in_pg:
        try:
            pg_writer(csv_ids[rid])
            _append_outbox(ob, csv_ids[rid], status=OUTBOX_STATUS_REPLAYED, attempts=1)
            replayed += 1
        except Exception as e:  # noqa: BLE001
            errors.append({"request_id": rid, "error": f"{type(e).__name__}: {e}"})

    return {
        "csv_count": len(csv_rows),
        "pg_count": len(pg_rows),
        "missing_in_pg": missing_in_pg,
        "extra_in_pg": extra_in_pg,
        "replayed_count": replayed,
        "replay_errors": errors,
    }

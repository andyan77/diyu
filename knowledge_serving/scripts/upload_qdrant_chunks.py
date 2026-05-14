#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KS-DIFY-ECS-004 · Qdrant chunks 灌库 / upload offline chunks to ECS Qdrant.

【边界 / Boundary】
   - 真源 / SSOT：本地 `knowledge_serving/vector_payloads/qdrant_chunks.jsonl`（KS-VECTOR-001 产物）
   - ECS Qdrant 是部署副本 / mirror，本脚本只做 local→ECS push，禁止反向读
   - 不调 Dify；不调 LLM；不写 `clean_output/`

【前置 / Prerequisites】
   - KS-VECTOR-001：qdrant_chunks.jsonl 已落盘
   - KS-POLICY-005：model_policy.yaml 已声明 embedding model + dimension
   - KS-S0-003：QDRANT_URL_STAGING / QDRANT_API_KEY env 已注入

【模式 / Modes】
   --env staging --dry-run  ：默认 CI 路径；不连 Qdrant；产 audit json（含期望行数、
                              collection name、dimension 检查）
   --env staging --apply    ：连 Qdrant；幂等 upsert + alias 切换；落 audit json
   --env staging --rollback ：读上一份 apply audit；alias 切回 `previous_collection`
   --env prod  *            ：拒绝（生产手动审批走另一通道）

【幂等 / Idempotence】
   point_id = uuid5(NAMESPACE_OID, chunk_id)；重跑 upsert 不增不减；
   collection 命名含 model_policy_version → embedding 变化即新 collection，旧 collection 保留 1 份回滚位。

【双路径 audit 隔离 / dual-path audit】
   dry-run 写 .dry_run.json；apply 写 canonical .json；dry-run 永不覆盖 apply 证据。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = REPO_ROOT / "knowledge_serving" / "vector_payloads" / "qdrant_chunks.jsonl"
POLICY_PATH = REPO_ROOT / "knowledge_serving" / "policies" / "model_policy.yaml"
PAYLOAD_SCHEMA_PATH = REPO_ROOT / "knowledge_serving" / "vector_payloads" / "qdrant_payload_schema.json"
AUDIT_DIR = REPO_ROOT / "knowledge_serving" / "audit"
AUDIT_PATH_APPLY = AUDIT_DIR / "qdrant_upload_KS-DIFY-ECS-004.json"
AUDIT_PATH_DRY_RUN = AUDIT_DIR / "qdrant_upload_KS-DIFY-ECS-004.dry_run.json"
AUDIT_PATH_ROLLBACK = AUDIT_DIR / "qdrant_upload_KS-DIFY-ECS-004.rollback.json"

ALIAS_NAME = "ks_chunks_current"
BATCH_SIZE = 256
GATE_ACTIVE = "active"
POINT_ID_NAMESPACE = uuid.UUID("6f9b0b54-1a3a-4e2a-9bd0-1d2b8b4f0e51")  # 固定命名空间 / fixed


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def err(msg: str, code: int = 2):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


# ---------- args ----------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="KS-DIFY-ECS-004 Qdrant chunks 灌库")
    p.add_argument("--env", required=True, choices=["staging", "prod"])
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="不连 Qdrant；产 audit 与期望计数")
    mode.add_argument("--apply", action="store_true",
                      help="连 Qdrant；upsert + alias 切换")
    mode.add_argument("--rollback", action="store_true",
                      help="读上份 audit 的 previous_collection，alias 切回")
    return p.parse_args()


# ---------- policy ----------

def load_policy() -> Dict[str, Any]:
    if not POLICY_PATH.exists():
        err(f"model_policy 缺失 / missing: {POLICY_PATH}", 2)
    data = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    version = data.get("model_policy_version")
    emb = data.get("embedding", {})
    if not isinstance(version, str) or not version:
        err("model_policy_version 缺失", 2)
    for k in ("model", "model_version", "dimension"):
        if not emb.get(k):
            err(f"embedding.{k} 缺失", 2)
    if not isinstance(emb["dimension"], int) or emb["dimension"] <= 0:
        err("embedding.dimension 非正整数", 2)
    return {
        "model_policy_version": version,
        "embedding_model": emb["model"],
        "embedding_model_version": emb["model_version"],
        "dimension": emb["dimension"],
    }


# ---------- chunks ----------

def load_chunks() -> List[Dict[str, Any]]:
    if not CHUNKS_PATH.exists():
        err(f"qdrant_chunks.jsonl 缺失 / missing: {CHUNKS_PATH}", 2)
    rows: List[Dict[str, Any]] = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                err(f"jsonl 第 {lineno} 行解析失败: {e}", 2)
    if not rows:
        err("qdrant_chunks.jsonl 为空 / empty", 2)
    return rows


def load_payload_validator() -> Draft202012Validator:
    if not PAYLOAD_SCHEMA_PATH.exists():
        err(f"payload schema 缺失 / missing: {PAYLOAD_SCHEMA_PATH}", 2)
    schema = json.loads(PAYLOAD_SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_chunks(chunks: List[Dict[str, Any]], policy: Dict[str, Any]) -> Dict[str, Any]:
    """灌前预筛 / pre-flight filter.

    防线 / guards：
      1. payload 走 jsonschema 全 16 字段校验（schema=qdrant_payload_schema.json，
         KS-VECTOR-002 真源）。任何字段缺失 / 类型 / enum / pattern 违规即 exit 2。
      2. embedding 向量长度 == policy.embedding.dimension。
      3. embedding_model / model_version / dimension 与 policy 一致（跨文件 drift 检测）。
      4. gate_status == 'active'（schema 已 enum 限定；此处复述以便 audit）。
      5. chunk_id 不重复。
    """
    dim_expected = policy["dimension"]
    model_expected = policy["embedding_model"]
    ver_expected = policy["embedding_model_version"]
    validator = load_payload_validator()

    schema_errs: List[str] = []
    vec_drift: List[str] = []
    policy_drift: List[str] = []
    seen: set = set()
    dup: List[str] = []

    for c in chunks:
        cid = c.get("chunk_id", "?")
        vec = c.get("embedding")
        pl = c.get("payload", {})
        # 1. jsonschema 校验
        for e in validator.iter_errors(pl):
            schema_errs.append(f"{cid}:{'/'.join(map(str, e.path)) or '<root>'}:{e.message}")
        # 2. vector 长度
        if not isinstance(vec, list) or len(vec) != dim_expected:
            vec_drift.append(f"{cid}:len={len(vec) if isinstance(vec, list) else 'N/A'}")
        # 3. policy cross-check
        if pl.get("embedding_model") != model_expected:
            policy_drift.append(f"{cid}:model={pl.get('embedding_model')}≠{model_expected}")
        if pl.get("embedding_model_version") != ver_expected:
            policy_drift.append(f"{cid}:model_version={pl.get('embedding_model_version')}≠{ver_expected}")
        if pl.get("embedding_dimension") != dim_expected:
            policy_drift.append(f"{cid}:payload_dim={pl.get('embedding_dimension')}≠{dim_expected}")
        # 5. 幂等
        if cid in seen:
            dup.append(cid)
        seen.add(cid)

    problems: List[str] = []
    if schema_errs:
        problems.append("payload schema 校验失败 (前 10) / schema violations:\n  "
                        + "\n  ".join(schema_errs[:10]))
    if vec_drift:
        problems.append("embedding 向量长度不匹配 (前 10):\n  " + "\n  ".join(vec_drift[:10]))
    if policy_drift:
        problems.append("payload ↔ model_policy 漂移 (前 10):\n  " + "\n  ".join(policy_drift[:10]))
    if dup:
        problems.append(f"chunk_id 重复 / duplicate: {dup[:10]}")
    if problems:
        err("\n".join(problems), 2)

    return {
        "row_count": len(chunks),
        "unique_chunk_ids": len(seen),
        "embedding_dimension": dim_expected,
        "schema_validator": "qdrant_payload_schema.json",
        "schema_validator_sha256": hashlib.sha256(
            PAYLOAD_SCHEMA_PATH.read_bytes()
        ).hexdigest(),
    }


def chunk_to_point(c: Dict[str, Any]) -> Dict[str, Any]:
    cid = c["chunk_id"]
    pid = str(uuid.uuid5(POINT_ID_NAMESPACE, cid))
    payload = dict(c["payload"])
    payload["chunk_id"] = cid
    return {"id": pid, "vector": c["embedding"], "payload": payload}


# ---------- Qdrant client wrapper ----------

def qdrant_client():
    """延迟加载 / lazy import：dry-run 不需要 qdrant_client。"""
    from qdrant_client import QdrantClient  # type: ignore
    url = os.environ.get("QDRANT_URL_STAGING")
    if not url:
        err("QDRANT_URL_STAGING 未设置 / not set", 2)
    api_key = os.environ.get("QDRANT_API_KEY") or None
    return QdrantClient(url=url, api_key=api_key, timeout=60.0)


def _qdrant_base_url() -> str:
    url = os.environ.get("QDRANT_URL_STAGING", "").rstrip("/")
    if not url:
        err("QDRANT_URL_STAGING 未设置 / not set", 2)
    return url


def _qdrant_rest_get(path: str) -> Dict[str, Any]:
    """裸 REST GET：避开 qdrant-client 1.7 与 v1.12.5 服务端的 pydantic schema 漂移。"""
    base = _qdrant_base_url()
    req = urllib.request.Request(f"{base}{path}", method="GET")
    api_key = os.environ.get("QDRANT_API_KEY")
    if api_key:
        req.add_header("api-key", api_key)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"_status_code": 404}
        body = e.read().decode("utf-8", errors="ignore")
        err(f"Qdrant REST {path} HTTP {e.code}: {body}", 2)
    except urllib.error.URLError as e:
        err(f"Qdrant REST {path} 连接失败: {e.reason}", 2)


def ensure_collection(client, name: str, dim: int) -> str:
    """存在则校验 dim；不存在则创建。返回 'reused'|'created'。

    使用裸 REST 读 collection 元信息，避开 qdrant-client 1.7 与 v1.12.5
    服务端响应字段（max_optimization_threads / strict_mode_config）的 pydantic
    schema 漂移 / drift。
    """
    from qdrant_client.http import models as qm  # type: ignore
    resp = _qdrant_rest_get(f"/collections/{name}")
    if resp.get("_status_code") == 404:
        client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
        return "created"
    # exists → 校验 dim
    try:
        params = resp["result"]["config"]["params"]["vectors"]
        existing_dim = params["size"] if "size" in params else next(
            v["size"] for v in params.values() if isinstance(v, dict)
        )
    except (KeyError, StopIteration, TypeError) as e:
        err(f"无法解析 collection {name} 的 vector dimension: {e}", 2)
    if existing_dim != dim:
        err(f"collection 已存在但 dimension={existing_dim} 与 policy.dim={dim} 不符；"
            f"禁止 in-place 改维度，请 bump model_policy_version", 2)
    return "reused"


def upsert_in_batches(client, name: str, chunks: List[Dict[str, Any]]) -> int:
    from qdrant_client.http import models as qm  # type: ignore
    total = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        points = [
            qm.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
            for p in (chunk_to_point(c) for c in batch)
        ]
        client.upsert(collection_name=name, points=points, wait=True)
        total += len(points)
    return total


def collection_count(client, name: str) -> int:
    res = client.count(collection_name=name, exact=True)
    return int(res.count)


def list_aliases(client) -> Dict[str, str]:
    """返回 {alias_name: collection_name}。兼容 qdrant-client 1.7."""
    aliases_resp = client.get_aliases()
    out: Dict[str, str] = {}
    for a in aliases_resp.aliases:
        out[a.alias_name] = a.collection_name
    return out


def switch_alias(client, alias: str, target_collection: str, previous: Optional[str]) -> None:
    from qdrant_client.http import models as qm  # type: ignore
    ops: List[Any] = []
    if previous:
        ops.append(qm.DeleteAliasOperation(
            delete_alias=qm.DeleteAlias(alias_name=alias)
        ))
    ops.append(qm.CreateAliasOperation(
        create_alias=qm.CreateAlias(collection_name=target_collection, alias_name=alias)
    ))
    client.update_collection_aliases(change_aliases_operations=ops)


def list_versioned_collections(client, prefix: str) -> List[str]:
    cols = client.get_collections().collections
    return sorted(c.name for c in cols if c.name.startswith(prefix))


# ---------- audit ----------

def write_audit(path: Path, audit: Dict[str, Any]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def base_audit(policy: Dict[str, Any], stats: Dict[str, Any],
               collection_name: str, env: str, mode: str) -> Dict[str, Any]:
    chunks_bytes = CHUNKS_PATH.read_bytes()
    policy_bytes = POLICY_PATH.read_bytes()
    checked_at = now_iso()
    return {
        "task_card": "KS-DIFY-ECS-004",
        "run_id": str(uuid.uuid4()),
        "run_at": checked_at,
        "checked_at": checked_at,
        "git_commit": _git_commit(),
        "evidence_level": "dry_run_auxiliary" if mode == "dry_run" else "runtime_verified",
        "env": env,
        "mode": mode,
        "model_policy_version": policy["model_policy_version"],
        "embedding": {
            "model": policy["embedding_model"],
            "model_version": policy["embedding_model_version"],
            "dimension": policy["dimension"],
        },
        "collection_name": collection_name,
        "alias": ALIAS_NAME,
        "batch_size": BATCH_SIZE,
        "source_chunks_path": str(CHUNKS_PATH.relative_to(REPO_ROOT)),
        "source_chunks_sha256": hashlib.sha256(chunks_bytes).hexdigest(),
        "source_chunks_rows": stats["row_count"],
        "model_policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "payload_schema": stats.get("schema_validator"),
        "payload_schema_sha256": stats.get("schema_validator_sha256"),
        "qdrant_endpoint_label": "QDRANT_URL_STAGING",
        "ssot_direction": "local→ECS push; never reverse-read",
    }


# ---------- 主流程 ----------

def run_dry(policy: Dict[str, Any], chunks: List[Dict[str, Any]],
            stats: Dict[str, Any], collection_name: str, env: str) -> int:
    audit = base_audit(policy, stats, collection_name, env, "dry_run")
    audit["expected_upsert_count"] = stats["row_count"]
    audit["dimension_check"] = "pass"
    audit["gate_active_check"] = "pass"
    audit["audit_path_apply"] = str(AUDIT_PATH_APPLY.relative_to(REPO_ROOT))
    audit["status"] = "pass"
    write_audit(AUDIT_PATH_DRY_RUN, audit)
    print(f"[dry-run] env={env} collection={collection_name} "
          f"expected_rows={stats['row_count']} dim={policy['dimension']}")
    print(f"[dry-run] audit → {AUDIT_PATH_DRY_RUN.relative_to(REPO_ROOT)} "
          f"(apply 证据 {AUDIT_PATH_APPLY.relative_to(REPO_ROOT)} 不会被覆盖)")
    return 0


def run_apply(policy: Dict[str, Any], chunks: List[Dict[str, Any]],
              stats: Dict[str, Any], collection_name: str, env: str) -> int:
    client = qdrant_client()
    # 1. alias 切换前先记录旧指向 / capture previous before switching
    aliases = list_aliases(client)
    previous_collection = aliases.get(ALIAS_NAME)
    # 2. ensure collection
    created_or_reused = ensure_collection(client, collection_name, policy["dimension"])
    # 3. upsert
    t0 = time.time()
    upserted = upsert_in_batches(client, collection_name, chunks)
    elapsed = round(time.time() - t0, 2)
    # 4. count == jsonl
    actual = collection_count(client, collection_name)
    count_status = "pass" if actual == stats["row_count"] else "fail"
    if count_status != "pass":
        err(f"count mismatch: collection={actual} jsonl={stats['row_count']}", 1)
    # 5. alias switch（previous 仍存在则覆盖；不存在则纯 create）
    switch_alias(client, ALIAS_NAME, collection_name, previous_collection)
    # 6. retained collections（含旧版回滚位）
    retained = list_versioned_collections(client, "ks_chunks__")
    audit = base_audit(policy, stats, collection_name, env, "apply")
    audit.update({
        "collection_state": created_or_reused,
        "previous_collection": previous_collection,
        "alias_switched_to": collection_name,
        "upserted_count": upserted,
        "collection_count_after": actual,
        "count_check": count_status,
        "upsert_elapsed_seconds": elapsed,
        "retained_collections": retained,
        "rollback_target": previous_collection,
        "status": "pass",
    })
    write_audit(AUDIT_PATH_APPLY, audit)
    print(f"[apply] env={env} collection={collection_name} state={created_or_reused} "
          f"upserted={upserted} count={actual} alias→{collection_name} "
          f"prev={previous_collection or '<none>'}")
    print(f"[apply] audit → {AUDIT_PATH_APPLY.relative_to(REPO_ROOT)}")
    return 0


def run_rollback(env: str) -> int:
    if not AUDIT_PATH_APPLY.exists():
        err(f"无 apply audit 可回滚 / no prior apply: {AUDIT_PATH_APPLY}", 2)
    prior = json.loads(AUDIT_PATH_APPLY.read_text(encoding="utf-8"))
    prev = prior.get("previous_collection")
    if not prev:
        err("上份 apply 无 previous_collection（首次灌库，无回滚位）", 2)
    client = qdrant_client()
    aliases = list_aliases(client)
    current = aliases.get(ALIAS_NAME)
    switch_alias(client, ALIAS_NAME, prev, current)
    audit = {
        "task_card": "KS-DIFY-ECS-004",
        "run_id": str(uuid.uuid4()),
        "run_at": now_iso(),
        "env": env,
        "mode": "rollback",
        "alias": ALIAS_NAME,
        "rolled_back_from": current,
        "rolled_back_to": prev,
        "source_apply_run_id": prior.get("run_id"),
        "status": "pass",
    }
    write_audit(AUDIT_PATH_ROLLBACK, audit)
    print(f"[rollback] alias {ALIAS_NAME}: {current} → {prev}")
    print(f"[rollback] audit → {AUDIT_PATH_ROLLBACK.relative_to(REPO_ROOT)}")
    return 0


def main() -> int:
    args = parse_args()
    if args.env == "prod":
        err("--env prod 拒绝 / refused：生产灌库走人工审批通道，不在本卡 CI 路径内", 2)

    policy = load_policy()
    collection_name = f"ks_chunks__{policy['model_policy_version']}"

    if args.rollback:
        return run_rollback(args.env)

    chunks = load_chunks()
    stats = validate_chunks(chunks, policy)

    if args.dry_run:
        return run_dry(policy, chunks, stats, collection_name, args.env)
    return run_apply(policy, chunks, stats, collection_name, args.env)


if __name__ == "__main__":
    sys.exit(main())

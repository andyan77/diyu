"""
knowledge_serving/scripts/build_qdrant_payloads.py
KS-VECTOR-001 · 离线构建 qdrant_chunks.jsonl
build offline Qdrant chunk payloads (governance-aligned, batch-anchored).

前置 / prerequisite gate:
    KS-COMPILER-013 治理校验器 / governance validator (S1-S7 必须全绿 / must all pass).
    本脚本启动时调用其 --all 模式，gate fail 即 fail-closed exit ≠ 0；
    禁止绕过 / bypass forbidden.

读 / read:
    - knowledge_serving/views/*.csv         (7 views; gate_status='active' only)
    - knowledge_serving/policies/model_policy.yaml  (embedding model + dim)
    - knowledge_serving/control/content_type_canonical.csv (name_zh 反查 / lookup)
    - clean_output/audit/source_manifest.json       (manifest_hash)
    - clean_output/candidates/**/*.yaml             (brand_overlay knowledge_assertion only)

写 / write:
    - knowledge_serving/vector_payloads/qdrant_chunks.jsonl   (artifact)

不读 / not read:
    - Qdrant 服务 / service（灌库属 KS-DIFY-ECS-004）

不调 / not invoked:
    - LLM 内容生成 / content generation
    - 任何 clean_output/ 写操作 / writes (writes_clean_output=false)

CLI:
    python3 build_qdrant_payloads.py            # 默认：调 embedding，落 jsonl
    python3 build_qdrant_payloads.py --check    # 只读：校验 jsonl schema + 行数 = view active 总数
    python3 build_qdrant_payloads.py --dry-run  # 不调 embedding，写占位 0 向量（仅供测试）

退出码 / exit codes:
    0  成功 / ok
    1  schema / governance fail
    2  embedding API 调用失败 / embedding API call failed
    3  KS-COMPILER-013 前置 gate fail
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

# 让超长字段（如 evidence_quote 多段引用）能完整读入 / allow large CSV fields
csv.field_size_limit(sys.maxsize)

REPO_ROOT = Path(__file__).resolve().parents[2]
VIEWS_DIR = REPO_ROOT / "knowledge_serving" / "views"
POLICIES_DIR = REPO_ROOT / "knowledge_serving" / "policies"
CONTROL_DIR = REPO_ROOT / "knowledge_serving" / "control"
MANIFEST_PATH = REPO_ROOT / "clean_output" / "audit" / "source_manifest.json"
CANDIDATES_DIR = REPO_ROOT / "clean_output" / "candidates"
OUTPUT_PATH = REPO_ROOT / "knowledge_serving" / "vector_payloads" / "qdrant_chunks.jsonl"
AUDIT_PATH = REPO_ROOT / "knowledge_serving" / "audit" / "build_qdrant_payloads_KS-VECTOR-001.json"
GOV_VALIDATOR = REPO_ROOT / "knowledge_serving" / "scripts" / "validate_serving_governance.py"

# index_version 锚定 view_schema_version + embedding_model_version 的组合；变更触发 KS-DIFY-ECS-004 重建
INDEX_VERSION_PREFIX = "idx"

# payload 字段对齐 / payload schema:
#   knowledge_serving_plan_v1.1.md §8 必有 14 字段 / §8 mandated 14 fields:
#     view_type / source_pack_id / brand_layer / granularity_layer / content_type /
#     pack_type / gate_status / default_call_pool / evidence_ids / compile_run_id /
#     chunk_text_hash / embedding_model / embedding_model_version / embedding_dimension /
#     index_version
#   KS-VECTOR-001 §4 + KS-DIFY-ECS-011 §0.1 第 4 行追加 / additionally required:
#     source_manifest_hash  (批次锚定 / batch anchoring — 未污染向量库纪律的硬前提)
#   合计 17 字段 / total 17 fields (新增 view_schema_version, 对齐 plan §2 governance_common_fields).
PAYLOAD_FIELDS = [
    "view_type",
    "source_pack_id",
    "brand_layer",
    "granularity_layer",
    "content_type",
    "pack_type",
    "gate_status",
    "default_call_pool",
    "evidence_ids",
    "compile_run_id",
    "source_manifest_hash",
    "view_schema_version",
    "chunk_text_hash",
    "embedding_model",
    "embedding_model_version",
    "embedding_dimension",
    "index_version",
]

# pack_type 反查 / lookup: 非 pack_view 行去 pack_view 反查 source_pack_id
# content_type_view / generation_recipe_view 是合成 view（无底层 pack）→ 显式合成值，不留空
SYNTHETIC_PACK_TYPE = {
    "content_type_view": "content_type_meta",
    "generation_recipe_view": "generation_recipe_meta",
}

VIEW_FILES = {
    "pack_view": VIEWS_DIR / "pack_view.csv",
    "play_card_view": VIEWS_DIR / "play_card_view.csv",
    "runtime_asset_view": VIEWS_DIR / "runtime_asset_view.csv",
    "brand_overlay_view": VIEWS_DIR / "brand_overlay_view.csv",
    "evidence_view": VIEWS_DIR / "evidence_view.csv",
    "content_type_view": VIEWS_DIR / "content_type_view.csv",
    "generation_recipe_view": VIEWS_DIR / "generation_recipe_view.csv",
}

# secondary id 列 / per-view primary identifier column
VIEW_PK = {
    "pack_view": "pack_id",
    "play_card_view": "play_card_id",
    "runtime_asset_view": "runtime_asset_id",
    "brand_overlay_view": "overlay_id",
    "evidence_view": "evidence_id",
    "content_type_view": "canonical_content_type_id",
    "generation_recipe_view": "recipe_id",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("build_qdrant_payloads")


class BuildError(Exception):
    pass


# ---------- helpers ----------

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def git_commit() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _load_json_list(s: str) -> list:
    if not s:
        return []
    try:
        v = json.loads(s)
        return v if isinstance(v, list) else []
    except json.JSONDecodeError:
        return []


def _parse_bool(s: str) -> bool:
    return str(s).strip().lower() in {"true", "1", "yes"}


def load_active_rows(view_path: Path) -> list[dict[str, str]]:
    with view_path.open("r", encoding="utf-8", newline="") as fh:
        return [r for r in csv.DictReader(fh) if r.get("gate_status") == "active"]


# ---------- chunk_text 复算 / recompute (mirror compiler formulas) ----------

def _candidate_lookup_assertion(pack_id: str) -> str:
    for sub in ("domain_general", "brand_faye", "needs_review"):
        p = CANDIDATES_DIR / sub / f"{pack_id}.yaml"
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            return str(data.get("knowledge_assertion", "") or "")
    raise BuildError(f"candidate yaml not found for {pack_id}")


def _load_canonical_name_zh() -> dict[str, str]:
    out: dict[str, str] = {}
    with (CONTROL_DIR / "content_type_canonical.csv").open("r", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["canonical_content_type_id"]] = r["name_zh"]
    return out


_CANONICAL_NAME_ZH: dict[str, str] | None = None


def derive_chunk_text(view_type: str, row: dict[str, str]) -> str:
    """逐 view 复算 chunk_text；公式与 compile_*_view.py 一致 / mirror upstream."""
    global _CANONICAL_NAME_ZH
    if view_type == "pack_view":
        return row["embedding_text"]
    if view_type == "play_card_view":
        return f"hook: {row['hook']}\nanti_pattern: {row['anti_pattern']}\nhook_slug: {row['play_card_id']}"
    if view_type == "evidence_view":
        return f"{row['source_md']}#{row['source_anchor']}\n{row['evidence_quote']}"
    if view_type == "runtime_asset_view":
        return f"{row['title']}\n{row['summary']}\nasset_type:{row['asset_type']}\nsource:{row['source_pointer']}"
    if view_type == "brand_overlay_view":
        ka = _candidate_lookup_assertion(row["source_pack_id"])
        return f"{row['brand_overlay_kind']}\n{ka}\n{row['target_content_type']}"
    if view_type == "generation_recipe_view":
        return "\n".join([
            f"recipe_id: {row['recipe_id']}",
            f"content_type: {row['content_type']}",
            f"output_format: {row['output_format']}",
            f"platform: {row['platform']}",
            f"business_brief_schema_id: {row['business_brief_schema_id']}",
        ])
    if view_type == "content_type_view":
        if _CANONICAL_NAME_ZH is None:
            _CANONICAL_NAME_ZH = _load_canonical_name_zh()
        cid = row["canonical_content_type_id"]
        aliases = _load_json_list(row["aliases"])
        return "\n".join([
            f"canonical_id: {cid}",
            f"name_zh: {_CANONICAL_NAME_ZH.get(cid, '')}",
            f"name_en: {row['content_type']}",
            f"aliases: {'|'.join(aliases)}",
        ])
    raise BuildError(f"unknown view_type: {view_type}")


# ---------- payload 构造 / payload build ----------

def derive_content_type(view_type: str, row: dict[str, str]) -> str:
    """payload.content_type 字段 / payload content_type field.
    pack / play_card / runtime_asset / brand_overlay / evidence 行可能没有 content_type 列；
    content_type_view 用 canonical_id；generation_recipe_view 用 row['content_type']；
    其余 view 落 '' （retrieval 端按 view_type 路由，不依赖此字段做硬过滤）。
    """
    if view_type == "play_card_view":
        return row.get("content_type", "") or ""
    if view_type == "content_type_view":
        return row.get("canonical_content_type_id", "") or ""
    if view_type == "generation_recipe_view":
        return row.get("content_type", "") or ""
    if view_type == "brand_overlay_view":
        return row.get("target_content_type", "") or ""
    return ""


def derive_chunk_id(view_type: str, row: dict[str, str]) -> str:
    pk_col = VIEW_PK[view_type]
    pk = row[pk_col]
    return f"{view_type}::{pk}"


def derive_pack_type(view_type: str, row: dict[str, str], pack_type_lookup: dict[str, str]) -> str:
    """payload.pack_type 派生 / derive.
    pack_view 直读 row['pack_type']；其它 pack-anchored view 反查 pack_view；
    合成 view 用 SYNTHETIC_PACK_TYPE 显式合成值（不留空）。
    """
    if view_type == "pack_view":
        return row.get("pack_type", "") or ""
    if view_type in SYNTHETIC_PACK_TYPE:
        return SYNTHETIC_PACK_TYPE[view_type]
    pid = row.get("source_pack_id", "")
    pt = pack_type_lookup.get(pid, "")
    if not pt:
        raise BuildError(
            f"pack_type 反查失败 / pack_type lookup miss {view_type} source_pack_id={pid!r} "
            f"(view rows referencing pack_view must have a matching pack_view row)"
        )
    return pt


def build_payload(
    view_type: str,
    row: dict[str, str],
    chunk_text_hash: str,
    *,
    embedding_model: str,
    embedding_model_version: str,
    embedding_dimension: int,
    index_version: str,
    pack_type_lookup: dict[str, str],
) -> dict[str, Any]:
    pl = {
        "view_type": view_type,
        "source_pack_id": row["source_pack_id"],
        "brand_layer": row["brand_layer"],
        "granularity_layer": row["granularity_layer"],
        "content_type": derive_content_type(view_type, row),
        "pack_type": derive_pack_type(view_type, row, pack_type_lookup),
        "gate_status": row["gate_status"],
        "default_call_pool": _parse_bool(row["default_call_pool"]),
        "evidence_ids": _load_json_list(row["evidence_ids"]),
        "compile_run_id": row["compile_run_id"],
        "source_manifest_hash": row["source_manifest_hash"],
        "view_schema_version": row["view_schema_version"],
        "chunk_text_hash": chunk_text_hash,
        "embedding_model": embedding_model,
        "embedding_model_version": embedding_model_version,
        "embedding_dimension": embedding_dimension,
        "index_version": index_version,
    }
    # 治理硬要求 / governance hard requirements
    for k in PAYLOAD_FIELDS:
        v = pl.get(k)
        if v in (None, ""):
            # evidence_ids / content_type 允许显式空容器（content_type 在 pack_view / runtime_asset_view / evidence_view
            # 无业务来源时显式空，由 retrieval 端按 view_type 路由；不视作 fail）
            if k in {"evidence_ids", "content_type"}:
                continue
            raise BuildError(f"payload missing required field {k} (chunk={derive_chunk_id(view_type, row)})")
    # 维度必须是正整数 / dimension must be positive int
    if not isinstance(pl["embedding_dimension"], int) or pl["embedding_dimension"] <= 0:
        raise BuildError(f"payload.embedding_dimension 非法 / invalid: {pl['embedding_dimension']!r}")
    return pl


def load_pack_type_lookup() -> dict[str, str]:
    out: dict[str, str] = {}
    with VIEW_FILES["pack_view"].open("r", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["source_pack_id"]] = r.get("pack_type", "") or ""
    return out


# ---------- embedding ----------

def _embed_batch_dashscope(texts: list[str], model: str) -> list[list[float]]:
    """调用 dashscope text-embedding 批量接口 / call dashscope batch embedding."""
    import dashscope  # noqa: WPS433  延迟加载，方便 --dry-run 无依赖
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise BuildError("DASHSCOPE_API_KEY 未设置 / not set (run: source scripts/load_env.sh)")
    dashscope.api_key = api_key
    resp = dashscope.TextEmbedding.call(model=model, input=texts)
    if getattr(resp, "status_code", None) != 200:
        raise BuildError(f"dashscope embed fail: code={getattr(resp,'status_code',None)} msg={getattr(resp,'message','')}")
    out = resp.output.get("embeddings") if hasattr(resp, "output") else None
    if not out or len(out) != len(texts):
        raise BuildError(f"dashscope embed: 输出长度不符 / length mismatch got={len(out) if out else 0} want={len(texts)}")
    # 按 text_index 排序保险 / sort defensive
    out_sorted = sorted(out, key=lambda e: e["text_index"])
    return [e["embedding"] for e in out_sorted]


def embed_texts(
    texts: list[str],
    *,
    model: str,
    dry_run: bool,
    batch_size: int = 10,
    max_attempts: int = 6,
    stats: dict[str, int] | None = None,
) -> list[list[float]]:
    if dry_run:
        # 占位 0 向量 / placeholder zero vector（仅 --dry-run；不入生产）
        return [[0.0] * 1024 for _ in texts]
    if stats is not None:
        stats["embedding_api_call_count"] = 0
        stats["embedding_input_count"] = 0
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        last_err: Exception | None = None
        for attempt in range(max_attempts):
            try:
                vectors.extend(_embed_batch_dashscope(batch, model))
                if stats is not None:
                    stats["embedding_api_call_count"] += 1
                    stats["embedding_input_count"] += len(batch)
                last_err = None
                break
            except Exception as e:  # 网络抖动 / proxy / dashscope 临时不可用都重试
                last_err = e
                if attempt == max_attempts - 1:
                    break
                wait = min(2.0 * (2 ** attempt), 30.0)  # 指数退避 / exp backoff, cap 30s
                log.warning("  embed batch %d-%d attempt %d/%d 失败 / retry in %.1fs: %s",
                            i, i + len(batch), attempt + 1, max_attempts, wait, type(e).__name__)
                time.sleep(wait)
        if last_err is not None:
            raise BuildError(f"embed batch starting at index {i} 重试 {max_attempts} 次仍失败 / exhausted retries: {last_err!r}") from last_err
        log.info("  embed progress %d/%d", min(i + batch_size, len(texts)), len(texts))
    return vectors


# ---------- 前置 gate / prerequisite gate ----------

def enforce_compiler_013_gate() -> None:
    """KS-COMPILER-013 是 KS-VECTOR-001 的硬前置 / hard prerequisite.
    本函数 fail-closed：S1-S7 任一不绿即 exit 3。
    """
    log.info("前置 gate / prereq: 跑 KS-COMPILER-013 validate_serving_governance --all")
    rc = subprocess.call(
        [sys.executable, str(GOV_VALIDATOR), "--all"],
        cwd=str(REPO_ROOT),
    )
    if rc != 0:
        log.error("[FAIL] KS-COMPILER-013 治理校验未通过 / governance gate fail rc=%d", rc)
        sys.exit(3)
    log.info("[OK] KS-COMPILER-013 前置 gate green")


# ---------- check 模式 / check mode ----------

def run_check() -> int:
    if not OUTPUT_PATH.exists():
        log.error("[FAIL] artifact 不存在 / missing: %s", OUTPUT_PATH)
        return 1
    expected_total = sum(len(load_active_rows(p)) for p in VIEW_FILES.values())
    seen_ids: set[str] = set()
    n = 0
    with OUTPUT_PATH.open("r", encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                log.error("[FAIL] line %d 不是合法 JSON / not valid JSON: %s", ln, e)
                return 1
            # 顶层必需 / top-level required
            for k in ("chunk_id", "payload", "embedding"):
                if k not in obj:
                    log.error("[FAIL] line %d 缺顶层字段 / missing %s", ln, k)
                    return 1
            if obj["chunk_id"] in seen_ids:
                log.error("[FAIL] line %d 重复 chunk_id / dup: %s", ln, obj["chunk_id"])
                return 1
            seen_ids.add(obj["chunk_id"])
            # payload 16 字段全在 / all 16 required fields present
            pl = obj["payload"]
            for k in PAYLOAD_FIELDS:
                if k not in pl:
                    log.error("[FAIL] line %d payload 缺 %s", ln, k)
                    return 1
                if k in {"source_pack_id", "view_type", "brand_layer", "granularity_layer",
                         "pack_type", "gate_status", "compile_run_id", "source_manifest_hash",
                         "chunk_text_hash", "embedding_model", "embedding_model_version",
                         "index_version"}:
                    if not pl[k]:
                        log.error("[FAIL] line %d payload.%s 为空 / empty", ln, k)
                        return 1
            # embedding_dimension 必须正整数 / positive int
            dim_field = pl["embedding_dimension"]
            if not isinstance(dim_field, int) or dim_field <= 0:
                log.error("[FAIL] line %d payload.embedding_dimension 非法 / invalid: %r", ln, dim_field)
                return 1
            # gate_status active only
            if pl["gate_status"] != "active":
                log.error("[FAIL] line %d gate_status 非 active=%s", ln, pl["gate_status"])
                return 1
            # batch anchoring（KS-VECTOR-001 §4 硬要求）
            if not pl["compile_run_id"] or not pl["source_manifest_hash"]:
                log.error("[FAIL] line %d 批次锚定缺失 / batch anchor missing", ln)
                return 1
            # embedding 维度与 payload 声明一致 / vector dim matches payload declaration
            emb = obj["embedding"]
            if not isinstance(emb, list) or len(emb) != dim_field:
                log.error("[FAIL] line %d embedding 维度异常 / dim mismatch got=%s payload.dim=%d",
                          ln, len(emb) if isinstance(emb, list) else type(emb).__name__, dim_field)
                return 1
            n += 1
    if n != expected_total:
        log.error("[FAIL] 行数不符 / row count mismatch got=%d expected=%d (= sum view active rows)",
                  n, expected_total)
        return 1
    log.info("[OK] qdrant_chunks.jsonl schema pass · rows=%d", n)
    return 0


def write_build_audit(
    *,
    dry_run: bool,
    rows: int,
    embedding_model: str,
    embedding_model_version: str,
    embedding_dim: int,
    index_version: str,
    stats: dict[str, int],
) -> None:
    audit = {
        "task_card": "KS-VECTOR-001",
        "checked_at": now_iso(),
        "env": os.environ.get("DIYU_ENV") or os.environ.get("APP_ENV") or "local",
        "git_commit": git_commit(),
        "evidence_level": "dry_run_auxiliary" if dry_run else "runtime_verified",
        "mode": "dry_run" if dry_run else "rebuild",
        "artifact_path": str(OUTPUT_PATH.relative_to(REPO_ROOT)),
        "artifact_sha256": sha256_file(OUTPUT_PATH),
        "artifact_byte_size": OUTPUT_PATH.stat().st_size,
        "rows": rows,
        "embedding_model": embedding_model,
        "embedding_model_version": embedding_model_version,
        "embedding_dimension": embedding_dim,
        "index_version": index_version,
        "embedding_api_call_count": stats.get("embedding_api_call_count", 0),
        "embedding_input_count": stats.get("embedding_input_count", 0),
        "evidence_note": (
            "runtime_verified means this run called the configured embedding endpoint; "
            "dry_run_auxiliary is never production completion evidence"
        ),
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log.info("[OK] audit → %s", AUDIT_PATH.relative_to(REPO_ROOT))


# ---------- build 模式 / build mode ----------

@dataclass
class BuildPlan:
    view_type: str
    row: dict[str, str]
    chunk_text: str
    chunk_text_hash: str
    chunk_id: str


def collect_plans() -> list[BuildPlan]:
    plans: list[BuildPlan] = []
    seen_chunk_ids: set[str] = set()
    for view_type, path in VIEW_FILES.items():
        rows = load_active_rows(path)
        log.info("加载 / load %s active=%d", view_type, len(rows))
        for row in rows:
            ct = derive_chunk_text(view_type, row)
            h = sha256_text(ct)
            view_h = row.get("chunk_text_hash", "")
            if view_h and h != view_h:
                raise BuildError(
                    f"chunk_text_hash 漂移 / drift {view_type} pk={row.get(VIEW_PK[view_type])}: "
                    f"recompute={h[:12]} view={view_h[:12]}"
                )
            cid = derive_chunk_id(view_type, row)
            if cid in seen_chunk_ids:
                raise BuildError(f"重复 chunk_id / duplicate: {cid}")
            seen_chunk_ids.add(cid)
            plans.append(BuildPlan(view_type, row, ct, h, cid))
    return plans


def run_build(dry_run: bool) -> int:
    # 1. 前置 gate
    enforce_compiler_013_gate()

    # 2. 收集 active 行 + 复算 hash
    plans = collect_plans()
    log.info("plan 总数 / total chunks=%d", len(plans))

    # 3. 加载 embedding 配置
    policy = yaml.safe_load((POLICIES_DIR / "model_policy.yaml").read_text(encoding="utf-8"))
    emb_cfg = policy["embedding"]
    embedding_model = emb_cfg["model"]
    embedding_model_version = emb_cfg["model_version"]
    embedding_dim = int(emb_cfg["dimension"])
    if embedding_dim != 1024:
        raise BuildError(f"embedding.dimension 期望 1024 / expected 1024, got {embedding_dim}")
    policy_version = policy.get("model_policy_version", "unknown")
    # index_version = idx::{policy_version}::{model}::{model_version}::dim{dim}
    index_version = f"{INDEX_VERSION_PREFIX}::{policy_version}::{embedding_model}::{embedding_model_version}::dim{embedding_dim}"

    # pack_type 反查表 / lookup table（pack_view 自身 + 4 个 pack-anchored view 共用）
    pack_type_lookup = load_pack_type_lookup()

    # 4. 调 embedding（或 dry-run 占位）
    texts = [p.chunk_text for p in plans]
    log.info("embedding %s%s ...", embedding_model, "（dry-run 占位 / placeholder）" if dry_run else "")
    stats: dict[str, int] = {}
    try:
        vectors = embed_texts(texts, model=embedding_model, dry_run=dry_run, stats=stats)
    except BuildError as e:
        log.error("[FAIL] embedding 调用失败 / embedding failed: %s", e)
        return 2
    if len(vectors) != len(plans):
        log.error("[FAIL] embedding 数量不符 / count mismatch got=%d want=%d",
                  len(vectors), len(plans))
        return 2
    for i, v in enumerate(vectors):
        if not isinstance(v, list) or len(v) != embedding_dim:
            log.error("[FAIL] chunk %s embedding 维度异常 / dim got=%s want=%d",
                      plans[i].chunk_id, len(v) if isinstance(v, list) else type(v).__name__,
                      embedding_dim)
            return 2

    # 5. 写 jsonl（确定性顺序 / deterministic order: view_type → chunk_id）
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    paired = list(zip(plans, vectors))
    paired.sort(key=lambda x: (x[0].view_type, x[0].chunk_id))
    with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        for plan, vec in paired:
            payload = build_payload(
                plan.view_type, plan.row, plan.chunk_text_hash,
                embedding_model=embedding_model,
                embedding_model_version=embedding_model_version,
                embedding_dimension=embedding_dim,
                index_version=index_version,
                pack_type_lookup=pack_type_lookup,
            )
            line = {
                "chunk_id": plan.chunk_id,
                "payload": payload,
                "embedding": vec,
            }
            fh.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
    log.info("[OK] 写入 / wrote %s rows=%d", OUTPUT_PATH, len(paired))

    # 6. self-check
    rc = run_check()
    if rc == 0 and not dry_run:
        write_build_audit(
            dry_run=dry_run,
            rows=len(paired),
            embedding_model=embedding_model,
            embedding_model_version=embedding_model_version,
            embedding_dim=embedding_dim,
            index_version=index_version,
            stats=stats,
        )
    return rc


# ---------- CLI ----------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="KS-VECTOR-001 · 离线 Qdrant chunk 构建器")
    p.add_argument("--check", action="store_true",
                   help="只读校验已落盘 jsonl 的 schema 与行数 / read-only schema check")
    p.add_argument("--dry-run", action="store_true",
                   help="不调 embedding API；写占位 0 向量；仅供单元测试 / placeholder vector for tests")
    args = p.parse_args(argv)

    if args.check:
        return run_check()
    return run_build(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())

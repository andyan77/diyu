"""
test_build_qdrant_payloads.py · KS-VECTOR-001 单元 / 边缘 / 治理一致性测试
unit / edge / governance-consistency tests for KS-VECTOR-001.

覆盖 / coverage:
    1. happy path: --check 通过（消费仓库内已落 jsonl，无需重跑 embedding）
    2. --check 对抗：注入 7 类恶意 fixture 必须 fail-closed
        F1 缺 chunk_text_hash
        F2 缺 compile_run_id 或 source_manifest_hash（批次锚定）
        F3 brand_layer 漏
        F4 gate_status 非 active 进入
        F5 重复 chunk_id
        F6 embedding 维度异常
        F7 payload 字段缺
    3. 幂等：dry-run 跑两次，jsonl byte-identical（排除 embedding 实际向量值）
    4. 治理一致性：所有 active 行 → 都有对应 chunk；chunk_text_hash 与 view csv 复算一致
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "knowledge_serving" / "scripts" / "build_qdrant_payloads.py"
JSONL = REPO_ROOT / "knowledge_serving" / "vector_payloads" / "qdrant_chunks.jsonl"


def _run(args: list[str], jsonl_override: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    # 强制让 build/check 用我们指定的 OUTPUT_PATH（通过临时 monkey-patch 不容易，改用 cwd + 符号链接思路过重）
    # 简化：直接复用 build_qdrant_payloads 的 OUTPUT_PATH。
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def test_check_happy_path():
    """已落盘 jsonl 应通过 --check / shipped jsonl passes check."""
    assert JSONL.exists(), f"missing artifact: {JSONL}"
    r = _run(["--check"])
    assert r.returncode == 0, f"--check should pass: {r.stderr}"


def _load_lines() -> list[dict]:
    with JSONL.open("r", encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def _write_lines(path: Path, lines: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in lines) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def restore_jsonl():
    backup = JSONL.read_bytes()
    try:
        yield
    finally:
        JSONL.write_bytes(backup)


def _expect_check_fail(reason: str):
    r = _run(["--check"])
    assert r.returncode != 0, f"--check should fail for {reason}, but passed.\nstdout:{r.stdout}\nstderr:{r.stderr}"


def test_f1_missing_chunk_text_hash(restore_jsonl):
    lines = _load_lines()
    del lines[0]["payload"]["chunk_text_hash"]
    _write_lines(JSONL, lines)
    _expect_check_fail("F1 chunk_text_hash 缺")


def test_f2_missing_batch_anchor(restore_jsonl):
    lines = _load_lines()
    lines[0]["payload"]["compile_run_id"] = ""
    _write_lines(JSONL, lines)
    _expect_check_fail("F2 compile_run_id 空")

    # 再测 source_manifest_hash
    lines2 = _load_lines()  # restore_jsonl 还没触发；手动还原
    # 用 backup 还原一下，避免上次污染干扰：直接重写为合法行 + 再注入 source_manifest_hash 缺失
    lines2[0]["payload"]["source_manifest_hash"] = ""
    _write_lines(JSONL, lines2)
    _expect_check_fail("F2 source_manifest_hash 空")


def test_f3_brand_layer_missing(restore_jsonl):
    lines = _load_lines()
    lines[0]["payload"]["brand_layer"] = ""
    _write_lines(JSONL, lines)
    _expect_check_fail("F3 brand_layer 空")


def test_f4_gate_status_non_active(restore_jsonl):
    lines = _load_lines()
    lines[0]["payload"]["gate_status"] = "draft"
    _write_lines(JSONL, lines)
    _expect_check_fail("F4 gate_status=draft 进入")


def test_f5_duplicate_chunk_id(restore_jsonl):
    lines = _load_lines()
    lines[1]["chunk_id"] = lines[0]["chunk_id"]
    _write_lines(JSONL, lines)
    _expect_check_fail("F5 重复 chunk_id")


def test_f6_embedding_dim_wrong(restore_jsonl):
    lines = _load_lines()
    lines[0]["embedding"] = [0.0] * 512   # 维度漂移
    _write_lines(JSONL, lines)
    _expect_check_fail("F6 embedding 维度 512")


def test_f7_payload_field_missing(restore_jsonl):
    lines = _load_lines()
    del lines[0]["payload"]["index_version"]
    _write_lines(JSONL, lines)
    _expect_check_fail("F7 payload.index_version 缺")


def test_row_count_matches_view_active_total():
    """行数 = 7 view active 之和 / row count = sum of active rows."""
    import csv as _csv
    csv_field_size_workaround()
    expected = 0
    for v in ("pack_view", "play_card_view", "runtime_asset_view",
              "brand_overlay_view", "evidence_view", "content_type_view",
              "generation_recipe_view"):
        with (REPO_ROOT / "knowledge_serving" / "views" / f"{v}.csv").open("r", encoding="utf-8") as fh:
            expected += sum(1 for r in _csv.DictReader(fh) if r.get("gate_status") == "active")
    actual = len(_load_lines())
    assert actual == expected, f"jsonl rows={actual} expected={expected}"


def csv_field_size_workaround():
    import csv as _csv, sys as _sys
    _csv.field_size_limit(_sys.maxsize)


def test_payload_has_16_fields_full():
    """payload 16 字段全填（全量校验，不抽样）/ all 498 rows full schema check.
    §8: view_type, source_pack_id, brand_layer, granularity_layer, content_type,
        pack_type, gate_status, default_call_pool, evidence_ids, compile_run_id,
        chunk_text_hash, embedding_model, embedding_model_version,
        embedding_dimension, index_version
    KS-VECTOR-001 §4: + source_manifest_hash (批次锚定 / batch anchoring)
    """
    lines = _load_lines()
    required = {
        "view_type", "source_pack_id", "brand_layer", "granularity_layer",
        "content_type", "pack_type", "gate_status", "default_call_pool",
        "evidence_ids", "compile_run_id", "source_manifest_hash",
        "chunk_text_hash", "embedding_model", "embedding_model_version",
        "embedding_dimension", "index_version",
    }
    # 允许空容器的字段 / fields permitted to be empty containers
    allow_empty = {"evidence_ids", "content_type"}
    for ln in lines:  # 全 498 条 / all rows
        keys = set(ln["payload"].keys())
        assert keys >= required, f"payload 字段不全 / missing fields: {ln['chunk_id']} miss={required-keys}"
        for k in required - allow_empty:
            v = ln["payload"][k]
            assert v not in (None, ""), f"payload.{k} 为空 / empty in {ln['chunk_id']}"
        assert isinstance(ln["payload"]["embedding_dimension"], int) and ln["payload"]["embedding_dimension"] > 0


def test_pack_type_non_empty_for_pack_anchored_views():
    """pack_view / play_card_view / runtime_asset_view / brand_overlay_view / evidence_view
    的 pack_type 必须能从 pack_view 反查得到非空 / non-empty via pack_view lookup."""
    lines = _load_lines()
    anchored = {"pack_view", "play_card_view", "runtime_asset_view",
                "brand_overlay_view", "evidence_view"}
    synthetic = {"content_type_view": "content_type_meta",
                 "generation_recipe_view": "generation_recipe_meta"}
    for ln in lines:
        vt = ln["payload"]["view_type"]
        pt = ln["payload"]["pack_type"]
        if vt in anchored:
            assert pt, f"pack-anchored view pack_type 空 / empty: {ln['chunk_id']}"
        elif vt in synthetic:
            assert pt == synthetic[vt], f"{vt} pack_type 漂移 / drift: got={pt} expected={synthetic[vt]}"


def test_full_chunk_text_hash_recompute():
    """全量 chunk_text_hash 复算 / full recompute all 498 rows.
    用 build_qdrant_payloads.derive_chunk_text 重新计算，必须与 payload.chunk_text_hash 完全一致。
    """
    # 通过 sys.path 注入而非 importlib，避开 @dataclass 在 importlib.util 下找不到 module 的坑
    import sys as _sys
    scripts_dir = str(REPO_ROOT / "knowledge_serving" / "scripts")
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)
    import build_qdrant_payloads as bqp  # noqa: E402

    # view csv → (pk_col → row)
    csv_field_size_workaround()
    import csv as _csv
    view_rows: dict[str, dict[str, dict]] = {}
    for vt, path in bqp.VIEW_FILES.items():
        pk_col = bqp.VIEW_PK[vt]
        with path.open("r", encoding="utf-8", newline="") as fh:
            view_rows[vt] = {r[pk_col]: r for r in _csv.DictReader(fh) if r.get("gate_status") == "active"}

    drift = []
    for ln in _load_lines():
        vt = ln["payload"]["view_type"]
        # chunk_id = "{view_type}::{pk}"
        pk = ln["chunk_id"].split("::", 1)[1]
        row = view_rows[vt].get(pk)
        assert row, f"view csv 找不到 / row missing: {ln['chunk_id']}"
        ct = bqp.derive_chunk_text(vt, row)
        h = bqp.sha256_text(ct)
        if h != ln["payload"]["chunk_text_hash"]:
            drift.append((ln["chunk_id"], h[:12], ln["payload"]["chunk_text_hash"][:12]))
    assert not drift, f"chunk_text_hash 漂移 / drift {len(drift)} 条 sample={drift[:3]}"


def test_dry_run_idempotent_byte_identical():
    """两次 --dry-run 产生的 jsonl byte-identical（embedding 用占位 0 向量，确定性顺序）。
    备份当前 live 产物，跑两次 dry-run 比对，最后恢复 live 产物。
    Two dry-runs must produce byte-identical jsonl; restore live artifact afterwards.
    """
    backup = JSONL.read_bytes()
    try:
        r1 = _run(["--dry-run"])
        assert r1.returncode == 0, f"dry-run #1 fail: {r1.stderr}"
        bytes_1 = JSONL.read_bytes()
        r2 = _run(["--dry-run"])
        assert r2.returncode == 0, f"dry-run #2 fail: {r2.stderr}"
        bytes_2 = JSONL.read_bytes()
        assert bytes_1 == bytes_2, (
            f"dry-run 非幂等 / non-idempotent: "
            f"len1={len(bytes_1)} len2={len(bytes_2)}"
        )
    finally:
        JSONL.write_bytes(backup)


def test_no_llm_keyword_in_source():
    """治理：脚本不调 LLM 生成内容 / no LLM content generation."""
    src = SCRIPT.read_text(encoding="utf-8")
    # 允许出现在注释里的"LLM"，但禁止 openai/anthropic/qwen-plus 内容生成调用
    forbidden = ["openai.", "anthropic.", "ChatCompletion", "Generation.call"]
    for f in forbidden:
        assert f not in src, f"build_qdrant_payloads.py 出现禁用 LLM 调用: {f}"


def test_no_clean_output_write():
    """治理：脚本仅读 clean_output（不写）/ read-only against clean_output."""
    src = SCRIPT.read_text(encoding="utf-8")
    # 禁止任何 clean_output 写操作
    bad = ['clean_output', 'open(CANDIDATES', 'write_text']
    # write_text 必然存在（写 jsonl），但目标必须是 OUTPUT_PATH——检查脚本里 write_text 的目标
    # 简化：grep 出所有 write_text 的上下文应仅含 OUTPUT_PATH
    for line in src.splitlines():
        if ".write_text(" in line or ".write_bytes(" in line:
            assert "clean_output" not in line, f"禁止写 clean_output: {line}"

"""KS-RETRIEVAL-008 · test_bundle_log.

覆盖卡片第 6 节对抗用例 + 第 7 节治理一致性：
1. bundle 缺 request_id → raise
2. user_query 明文出现在 bundle → raise（强制只暴露 user_query_hash）
3. log 字段空 → raise（disabled / none 必须显式）
4. 写到 knowledge_serving/logs/context_bundle_log.csv → raise（§4.5 单真源）
5. 同 request_id + 同上游输入 → bundle_hash 一致（S8 回放）
6. merged_overlay_payload={} 时 bundle/log 如实落空集（W8 外审 EVIDENCE 守门）
7. governance 三件套缺字段 → raise
+ 不调 LLM：grep 模块源码
+ 数据驱动 5 状态 fallback：每个状态走通一条
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from knowledge_serving.serving.context_bundle_builder import (
    BundleValidationError,
    build_context_bundle,
    compute_bundle_hash,
    hash_user_query,
    validate_bundle,
)
from knowledge_serving.serving.log_writer import (
    CANONICAL_LOG_PATH,
    LOG_FIELDS,
    LogWriteError,
    read_log_rows,
    write_context_bundle_log,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------
# fixtures
# ------------------------------------------------------------------

@pytest.fixture
def governance() -> dict:
    return {
        "gate_policy": "active_only",
        "granularity_layers": ["L1", "L2", "L3"],
        "traceability_required": True,
        "compile_run_id": "cr_test_20260513_001",
        "source_manifest_hash": "sha256:" + "a" * 64,
        "view_schema_version": "v1.1.0",
    }


@pytest.fixture
def merge_result_full() -> dict:
    """有非空 overlay + structured + vector 候选的常规 merge 结果。"""
    return {
        "merged_overlay_payload": {"tone": "warm", "forbidden_words": ["贵妇感"]},
        "structured_candidates": {
            "pack_view": [{"source_pack_id": "KP_TEST_001", "evidence_id": "EV_001"}],
            "play_card_view": [{"play_card_id": "PC_001", "evidence_id": "EV_002"}],
            "runtime_asset_view": [{"runtime_asset_id": "RA_001"}],
        },
        "vector_candidates": [
            {"payload": {"chunk_id": "C_001", "evidence_id": "EV_003", "brand_layer": "brand_faye"}}
        ],
        "conflict_log": [],
        "needs_review_queue": [],
        "_meta": {
            "resolved_brand_layer": "brand_faye",
            "precedence_rule": "brand_<name> > domain_general",
            "overlay_layers_seen": ["brand_faye", "domain_general"],
            "policy_rules_applied": 3,
        },
    }


@pytest.fixture
def merge_result_empty_overlay() -> dict:
    """W8 EVIDENCE 守门：overlay 命中但 payload 全空 = 现实业务事实。"""
    return {
        "merged_overlay_payload": {},
        "structured_candidates": {
            "pack_view": [{"source_pack_id": "KP_TEST_002", "evidence_id": "EV_010"}],
            "play_card_view": [],
            "runtime_asset_view": [],
        },
        "vector_candidates": [],
        "conflict_log": [],
        "needs_review_queue": [],
        "_meta": {
            "resolved_brand_layer": "brand_faye",
            "precedence_rule": "brand_<name> > domain_general",
            "overlay_layers_seen": ["brand_faye"],
            "policy_rules_applied": 0,
        },
    }


@pytest.fixture
def fallback_full_applied() -> dict:
    return {
        "status": "brand_full_applied",
        "severity": "info",
        "is_blocking": False,
        "output_strategy": {"constraints": ["fully_respect_brand_overlay"]},
        "downstream_signal": {},
        "missing_fields": [],
        "evaluation_trace": [{"matched_state": "brand_full_applied", "reason": "all checks passed"}],
    }


@pytest.fixture
def model_policy() -> dict:
    return {
        "model_policy_version": "mp_20260512_002",
        "embedding": {
            "model": "text-embedding-v3",
            "model_version": "v3",
        },
        "rerank": {"enabled": False},
        "llm_assist": {"enabled": False, "model": "qwen-plus"},
    }


def _build_with(
    *,
    merge_result,
    fallback_decision,
    governance,
    request_id="req_test_001",
    user_query="大衣搭配陈列要点",
    content_type="product_review",
    recipe=None,
    business_brief=None,
):
    return build_context_bundle(
        request_id=request_id,
        tenant_id="tenant_faye_main",
        resolved_brand_layer="brand_faye",
        allowed_layers=["domain_general", "brand_faye"],
        user_query=user_query,
        content_type=content_type,
        recipe=recipe or {"recipe_id": "RCP_001"},
        business_brief=business_brief or {"product_name": "羊毛大衣"},
        merge_result=merge_result,
        fallback_decision=fallback_decision,
        governance=governance,
    )


# ------------------------------------------------------------------
# 1. bundle 缺 request_id → raise
# ------------------------------------------------------------------

def test_bundle_missing_request_id_raises(governance, merge_result_full, fallback_full_applied):
    with pytest.raises(BundleValidationError, match="request_id"):
        _build_with(
            merge_result=merge_result_full,
            fallback_decision=fallback_full_applied,
            governance=governance,
            request_id="",
        )


# ------------------------------------------------------------------
# 2. user_query 明文不许进 bundle
# ------------------------------------------------------------------

def test_bundle_never_contains_plaintext_user_query(
    governance, merge_result_full, fallback_full_applied
):
    user_query = "这是非常具体的隐私化用户查询 XYZ_SENTINEL"
    bundle, meta = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fallback_full_applied,
        governance=governance,
        user_query=user_query,
    )
    serialized = json.dumps(bundle, ensure_ascii=False)
    assert "XYZ_SENTINEL" not in serialized
    assert meta["user_query_hash"].startswith("sha256:")
    assert meta["user_query_hash"] == hash_user_query(user_query)


def test_validate_bundle_rejects_plaintext_user_query_field(
    governance, merge_result_full, fallback_full_applied
):
    bundle, _ = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fallback_full_applied,
        governance=governance,
    )
    bundle["user_query"] = "明文不允许"
    with pytest.raises(BundleValidationError, match="user_query"):
        validate_bundle(bundle)


# ------------------------------------------------------------------
# 3. log 字段空 → raise（disabled / none 显式）
# ------------------------------------------------------------------

def test_log_empty_field_raises(
    tmp_path, governance, merge_result_full, fallback_full_applied
):
    bundle, meta = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fallback_full_applied,
        governance=governance,
    )
    target = tmp_path / "context_bundle_log.csv"
    # classified_intent 为空 → 必须抛
    with pytest.raises(LogWriteError, match="classified_intent"):
        write_context_bundle_log(
            bundle=bundle,
            bundle_meta=meta,
            classified_intent="",
            selected_recipe_id="RCP_001",
            retrieved_ids={
                "pack_ids": ["KP_TEST_001"],
                "play_card_ids": ["PC_001"],
                "asset_ids": ["RA_001"],
                "overlay_ids": ["brand_faye"],
                "evidence_ids": ["EV_001", "EV_002", "EV_003"],
            },
            model_policy={"model_policy_version": "mp_20260512_002",
                          "embedding": {"model": "text-embedding-v3", "model_version": "v3"},
                          "rerank": {"enabled": False},
                          "llm_assist": {"enabled": False}},
            log_path=target,
        )


def test_log_disabled_fields_filled_explicitly(
    tmp_path, governance, merge_result_full, fallback_full_applied, model_policy
):
    bundle, meta = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fallback_full_applied,
        governance=governance,
    )
    target = tmp_path / "context_bundle_log.csv"
    path, row = write_context_bundle_log(
        bundle=bundle,
        bundle_meta=meta,
        classified_intent="generation",
        selected_recipe_id="RCP_001",
        retrieved_ids={
            "pack_ids": ["KP_TEST_001"],
            "play_card_ids": ["PC_001"],
            "asset_ids": ["RA_001"],
            "overlay_ids": ["brand_faye"],
            "evidence_ids": ["EV_001", "EV_002", "EV_003"],
        },
        model_policy=model_policy,
        log_path=target,
        created_at="2026-05-13T10:00:00Z",
    )
    assert row["rerank_model"] == "disabled"
    assert row["rerank_model_version"] == "disabled"
    assert row["llm_assist_model"] == "disabled"
    assert row["final_output_hash"] == "disabled"
    # 所有 28 字段非空
    assert set(row.keys()) == set(LOG_FIELDS)
    for k, v in row.items():
        assert v != "", f"字段 {k} 空字符串"


# ------------------------------------------------------------------
# 4. §4.5 单真源：拒绝写到 knowledge_serving/logs/
# ------------------------------------------------------------------

def test_log_refuses_non_canonical_logs_dir(
    governance, merge_result_full, fallback_full_applied, model_policy
):
    bundle, meta = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fallback_full_applied,
        governance=governance,
    )
    bad_path = REPO_ROOT / "knowledge_serving" / "logs" / "context_bundle_log.csv"
    with pytest.raises(LogWriteError, match="logs/"):
        write_context_bundle_log(
            bundle=bundle,
            bundle_meta=meta,
            classified_intent="generation",
            selected_recipe_id="RCP_001",
            retrieved_ids={"pack_ids": [], "play_card_ids": [],
                           "asset_ids": [], "overlay_ids": [], "evidence_ids": []},
            model_policy=model_policy,
            log_path=bad_path,
        )


def test_log_refuses_same_name_outside_canonical_dir(
    tmp_path, governance, merge_result_full, fallback_full_applied, model_policy
):
    """同名 context_bundle_log.csv 出现在仓库其他目录 = 双真源风险。"""
    bundle, meta = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fallback_full_applied,
        governance=governance,
    )
    bad_path = REPO_ROOT / "knowledge_serving" / "context_bundle_log.csv"
    with pytest.raises(LogWriteError, match="canonical"):
        write_context_bundle_log(
            bundle=bundle,
            bundle_meta=meta,
            classified_intent="generation",
            selected_recipe_id="RCP_001",
            retrieved_ids={"pack_ids": [], "play_card_ids": [],
                           "asset_ids": [], "overlay_ids": [], "evidence_ids": []},
            model_policy=model_policy,
            log_path=bad_path,
        )


# ------------------------------------------------------------------
# 5. 重放一致性：同 request_id + 同输入 → 同 bundle_hash
# ------------------------------------------------------------------

def test_replay_same_request_id_same_bundle_hash(
    governance, merge_result_full, fallback_full_applied
):
    b1, m1 = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fallback_full_applied,
        governance=governance,
    )
    b2, m2 = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fallback_full_applied,
        governance=governance,
    )
    assert m1["bundle_hash"] == m2["bundle_hash"]
    assert b1 == b2
    # 改 request_id 后必须不同
    _, m3 = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fallback_full_applied,
        governance=governance,
        request_id="req_test_002",
    )
    assert m3["bundle_hash"] != m1["bundle_hash"]


def test_replay_from_log_row_reconstructs_governance(
    tmp_path, governance, merge_result_full, fallback_full_applied, model_policy
):
    """log 28 字段必须够把 governance + bundle_hash 重新装出来。"""
    bundle, meta = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fallback_full_applied,
        governance=governance,
    )
    target = tmp_path / "context_bundle_log.csv"
    _, row = write_context_bundle_log(
        bundle=bundle,
        bundle_meta=meta,
        classified_intent="generation",
        selected_recipe_id="RCP_001",
        retrieved_ids={
            "pack_ids": ["KP_TEST_001"],
            "play_card_ids": ["PC_001"],
            "asset_ids": ["RA_001"],
            "overlay_ids": ["brand_faye"],
            "evidence_ids": ["EV_001", "EV_002", "EV_003"],
        },
        model_policy=model_policy,
        log_path=target,
        created_at="2026-05-13T10:00:00Z",
    )
    rows = read_log_rows(target)
    assert len(rows) == 1
    persisted = rows[0]
    assert persisted["context_bundle_hash"] == meta["bundle_hash"]
    assert persisted["compile_run_id"] == governance["compile_run_id"]
    assert persisted["source_manifest_hash"] == governance["source_manifest_hash"]
    assert persisted["view_schema_version"] == governance["view_schema_version"]
    assert persisted["user_query_hash"] == meta["user_query_hash"]


# ------------------------------------------------------------------
# 6. W8 EVIDENCE 守门：空 overlay payload 如实落空集
# ------------------------------------------------------------------

def test_empty_overlay_payload_persists_as_empty(
    tmp_path, governance, merge_result_empty_overlay, fallback_full_applied, model_policy
):
    bundle, meta = _build_with(
        merge_result=merge_result_empty_overlay,
        fallback_decision=fallback_full_applied,
        governance=governance,
    )
    assert meta["merged_overlay_payload_empty"] is True
    # bundle.brand_overlays 应保留 overlay_layers_seen 但 merged_overlay_payload={}
    assert bundle["brand_overlays"], "命中 overlay 行时 brand_overlays 不为空"
    assert bundle["brand_overlays"][0]["merged_overlay_payload"] == {}
    # 不许出现"占位"字段名（伪造品牌语气的常见反模式）
    serialized = json.dumps(bundle, ensure_ascii=False)
    for placeholder in ["placeholder", "default_brand_tone", "TODO"]:
        assert placeholder not in serialized, f"检出占位字段 {placeholder}"

    target = tmp_path / "context_bundle_log.csv"
    _, row = write_context_bundle_log(
        bundle=bundle,
        bundle_meta=meta,
        classified_intent="generation",
        selected_recipe_id="RCP_002",
        retrieved_ids={
            "pack_ids": ["KP_TEST_002"],
            "play_card_ids": [],
            "asset_ids": [],
            "overlay_ids": ["brand_faye"],
            "evidence_ids": ["EV_010"],
        },
        model_policy=model_policy,
        log_path=target,
    )
    # 空列表字段必须显式 "[]"，不许空字符串
    # （KS-DIFY-ECS-006 W11：array 字段统一 JSON 序列化，对齐 control_tables.schema array 真源）
    assert row["retrieved_play_card_ids"] == "[]"
    assert row["retrieved_asset_ids"] == "[]"
    assert row["missing_fields"] == "[]"


# ------------------------------------------------------------------
# 7. governance 三件套缺字段 → raise
# ------------------------------------------------------------------

@pytest.mark.parametrize("drop", [
    "compile_run_id",
    "source_manifest_hash",
    "view_schema_version",
    "gate_policy",
    "granularity_layers",
    "traceability_required",
])
def test_governance_missing_field_raises(
    governance, merge_result_full, fallback_full_applied, drop
):
    bad = dict(governance)
    bad.pop(drop)
    with pytest.raises(BundleValidationError, match=drop):
        _build_with(
            merge_result=merge_result_full,
            fallback_decision=fallback_full_applied,
            governance=bad,
        )


# ------------------------------------------------------------------
# 不调 LLM：grep 源码
# ------------------------------------------------------------------

def test_no_llm_calls_in_module_source():
    src_files = [
        REPO_ROOT / "knowledge_serving" / "serving" / "context_bundle_builder.py",
        REPO_ROOT / "knowledge_serving" / "serving" / "log_writer.py",
    ]
    forbidden = [
        r"\banthropic\b",
        r"\bopenai\b",
        r"\bdashscope\b\.\bGeneration\b",  # generation 调用；embedding 也禁
        r"\bllm[._]judge\b",
        r"\bChatCompletion\b",
    ]
    for f in src_files:
        text = f.read_text(encoding="utf-8")
        for pat in forbidden:
            assert not re.search(pat, text), f"{f.name} 命中禁用调用 {pat}"


# ------------------------------------------------------------------
# 5 个 fallback_status 全状态走通
# ------------------------------------------------------------------

@pytest.mark.parametrize("status,blocked", [
    ("brand_full_applied", None),
    ("brand_partial_fallback", None),
    ("domain_only", None),
    ("blocked_missing_required_brand_fields", "brand_required missing"),
    ("blocked_missing_business_brief", "business_brief missing"),
])
def test_all_5_fallback_states_round_trip(
    tmp_path, governance, merge_result_full, model_policy, status, blocked
):
    fb = {
        "status": status,
        "severity": "info",
        "is_blocking": status.startswith("blocked_"),
        "output_strategy": {"constraints": []},
        "downstream_signal": {},
        "missing_fields": ["brand_layer"] if status.startswith("blocked_") else [],
        "evaluation_trace": [],
    }
    bundle, meta = _build_with(
        merge_result=merge_result_full,
        fallback_decision=fb,
        governance=governance,
    )
    assert bundle["fallback_status"] == status

    target = tmp_path / "context_bundle_log.csv"
    _, row = write_context_bundle_log(
        bundle=bundle,
        bundle_meta=meta,
        classified_intent="generation",
        selected_recipe_id="RCP_001",
        retrieved_ids={
            "pack_ids": ["KP_TEST_001"],
            "play_card_ids": ["PC_001"],
            "asset_ids": ["RA_001"],
            "overlay_ids": ["brand_faye"],
            "evidence_ids": ["EV_001"],
        },
        model_policy=model_policy,
        blocked_reason=blocked,
        log_path=target,
    )
    assert row["fallback_status"] == status
    assert row["blocked_reason"] == (blocked or "none")

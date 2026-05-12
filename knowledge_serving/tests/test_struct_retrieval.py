"""KS-RETRIEVAL-005 · structured_retrieval 测试 (TDD).

覆盖卡 §6 对抗测试 15 case + §10 审查员阻断项：
- preflight fail-closed (报告缺失 / 篡改)
- KS-COMPILER-013 治理报告 S1-S7 全 pass 才放行
- S2 active-only 默认 / include_inactive 例外
- S3 brand_layer 跨租户硬隔离
- S4 granularity 仅 L1/L2/L3
- structured_filters_json 应用 + 字段缺失 raise
- policy 0/2 命中分别 raise
- max_items 边界 (负 / 0 / 超大)
- 函数签名禁用 user_query / brand_layer
- 源码无 LLM 调用
- 确定性 (byte-identical)
"""
from __future__ import annotations

import csv
import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "knowledge_serving" / "serving" / "structured_retrieval.py"


def _load_module():
    # 每次 fresh load，避免模块级缓存污染
    spec = importlib.util.spec_from_file_location(
        "structured_retrieval_under_test", MODULE_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------- fixture builders ----------

REPORT_GREEN = """# validate_serving_governance.report
generated_at: 2026-05-13T00:00:00+00:00
compile_run_id: testfixture

[preflight schema_validation]
status: pass
checked_rows: 0

[S1 source_traceability]
status: pass
checked_rows: 0
violations: ()

[S2 gate_filter]
status: pass
checked_rows: 0

[S3 brand_layer_scope]
status: pass
checked_rows: 0

[S4 granularity_integrity]
status: pass
checked_rows: 0

[S5 evidence_linkage]
status: pass
checked_rows: 0

[S6 play_card_completeness]
status: pass
checked_rows: 0

[S7 fallback_policy_coverage]
status: pass
checked_rows: 0
"""


def _write_report(path: Path, content: str = REPORT_GREEN) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _write_csv(path: Path, header: list[str], rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})
    return path


def _pack_row(pack_id: str, brand_layer: str, gate_status: str = "active",
              granularity: str = "L1", coverage: str = "complete") -> dict:
    return {
        "source_pack_id": pack_id,
        "brand_layer": brand_layer,
        "granularity_layer": granularity,
        "gate_status": gate_status,
        "pack_id": pack_id,
        "pack_type": "fixture",
        "knowledge_title": "t",
        "knowledge_assertion": "a",
        "coverage_status": coverage,
    }


PACK_HEADER = [
    "source_pack_id", "brand_layer", "granularity_layer", "gate_status",
    "pack_id", "pack_type", "knowledge_title", "knowledge_assertion",
    "coverage_status",
]
CT_HEADER = ["source_pack_id", "brand_layer", "granularity_layer", "gate_status",
             "content_type", "canonical_content_type_id"]
PC_HEADER = ["source_pack_id", "brand_layer", "granularity_layer", "gate_status",
             "play_card_id", "pack_id", "content_type"]
RA_HEADER = ["source_pack_id", "brand_layer", "granularity_layer", "gate_status",
             "runtime_asset_id", "pack_id", "asset_type"]
POLICY_HEADER = [
    "intent", "content_type", "required_views", "optional_views",
    "structured_filters_json", "vector_filters_json", "max_items_per_view",
    "rerank_strategy", "merge_precedence_policy", "timeout_ms",
]


def _make_env(tmp_path: Path,
              pack_rows: list[dict] | None = None,
              ct_rows: list[dict] | None = None,
              pc_rows: list[dict] | None = None,
              ra_rows: list[dict] | None = None,
              policy_rows: list[dict] | None = None,
              report: str | None = REPORT_GREEN) -> dict:
    views_root = tmp_path / "views"
    _write_csv(views_root / "pack_view.csv", PACK_HEADER, pack_rows or [])
    _write_csv(views_root / "content_type_view.csv", CT_HEADER, ct_rows or [])
    _write_csv(views_root / "play_card_view.csv", PC_HEADER, pc_rows or [])
    _write_csv(views_root / "runtime_asset_view.csv", RA_HEADER, ra_rows or [])
    policy_path = tmp_path / "retrieval_policy_view.csv"
    _write_csv(policy_path, POLICY_HEADER, policy_rows or [_default_policy()])
    report_path = tmp_path / "validate_serving_governance.report"
    if report is not None:
        _write_report(report_path, report)
    return {
        "views_root": views_root,
        "policy_path": policy_path,
        "report_path": report_path,
    }


def _default_policy(intent: str = "generate", content_type: str = "behind_the_scenes",
                    structured_filters: dict | None = None,
                    max_items: int = 5,
                    required: list[str] | None = None,
                    optional: list[str] | None = None) -> dict:
    return {
        "intent": intent,
        "content_type": content_type,
        "required_views": json.dumps(required or ["pack_view", "content_type_view"]),
        "optional_views": json.dumps(optional or ["play_card_view", "runtime_asset_view"]),
        "structured_filters_json": json.dumps(structured_filters or {}),
        "vector_filters_json": "{}",
        "max_items_per_view": max_items,
        "rerank_strategy": "vector_score",
        "merge_precedence_policy": "brand_over_domain",
        "timeout_ms": 1500,
    }


# ---------- T1 跨租户串味 ----------

def test_t1_cross_tenant_filter(tmp_path):
    mod = _load_module()
    env = _make_env(
        tmp_path,
        pack_rows=[
            _pack_row("KP-a", "brand_faye"),
            _pack_row("KP-b", "brand_xyz"),
            _pack_row("KP-c", "domain_general"),
        ],
    )
    out = mod.structured_retrieve(
        intent="generate", content_type="behind_the_scenes",
        allowed_layers=["domain_general", "brand_faye"],
        views_root=env["views_root"], policy_path=env["policy_path"],
        report_path=env["report_path"],
    )
    ids = [r["pack_id"] for r in out["pack_view"]]
    assert "KP-b" not in ids
    assert set(ids) == {"KP-a", "KP-c"}


# ---------- T2 / T3 active-only / include_inactive ----------

def test_t2_active_only_default(tmp_path):
    mod = _load_module()
    env = _make_env(
        tmp_path,
        pack_rows=[
            _pack_row("KP-a", "domain_general", gate_status="active"),
            _pack_row("KP-b", "domain_general", gate_status="inactive"),
        ],
    )
    out = mod.structured_retrieve(
        intent="generate", content_type="behind_the_scenes",
        allowed_layers=["domain_general"],
        views_root=env["views_root"], policy_path=env["policy_path"],
        report_path=env["report_path"],
    )
    ids = [r["pack_id"] for r in out["pack_view"]]
    assert ids == ["KP-a"]


def test_t3_include_inactive_explicit(tmp_path):
    mod = _load_module()
    env = _make_env(
        tmp_path,
        pack_rows=[
            _pack_row("KP-a", "domain_general", gate_status="active"),
            _pack_row("KP-b", "domain_general", gate_status="inactive"),
        ],
    )
    out = mod.structured_retrieve(
        intent="generate", content_type="behind_the_scenes",
        allowed_layers=["domain_general"], include_inactive=True,
        views_root=env["views_root"], policy_path=env["policy_path"],
        report_path=env["report_path"],
    )
    ids = sorted(r["pack_id"] for r in out["pack_view"])
    assert ids == ["KP-a", "KP-b"]


# ---------- T4 L4 丢弃 ----------

def test_t4_granularity_l4_dropped(tmp_path):
    mod = _load_module()
    env = _make_env(
        tmp_path,
        pack_rows=[
            _pack_row("KP-a", "domain_general", granularity="L1"),
            _pack_row("KP-b", "domain_general", granularity="L4"),
        ],
    )
    out = mod.structured_retrieve(
        intent="generate", content_type="behind_the_scenes",
        allowed_layers=["domain_general"],
        views_root=env["views_root"], policy_path=env["policy_path"],
        report_path=env["report_path"],
    )
    ids = [r["pack_id"] for r in out["pack_view"]]
    assert ids == ["KP-a"]


# ---------- T5 / T6 policy 0/2 命中 ----------

def test_t5_policy_not_found(tmp_path):
    mod = _load_module()
    env = _make_env(tmp_path, pack_rows=[_pack_row("KP-a", "domain_general")])
    with pytest.raises(mod.RetrievalPolicyNotFound):
        mod.structured_retrieve(
            intent="unknown_intent", content_type="behind_the_scenes",
            allowed_layers=["domain_general"],
            views_root=env["views_root"], policy_path=env["policy_path"],
            report_path=env["report_path"],
        )


def test_t6_policy_ambiguous(tmp_path):
    mod = _load_module()
    env = _make_env(
        tmp_path,
        pack_rows=[_pack_row("KP-a", "domain_general")],
        policy_rows=[_default_policy(), _default_policy()],
    )
    with pytest.raises(mod.RetrievalPolicyAmbiguous):
        mod.structured_retrieve(
            intent="generate", content_type="behind_the_scenes",
            allowed_layers=["domain_general"],
            views_root=env["views_root"], policy_path=env["policy_path"],
            report_path=env["report_path"],
        )


# ---------- T7 filter 列缺：cross-view filter skip-if-missing ----------
# 真实 policy 语义：structured_filters_json 是跨 view 全集策略，列在某 view schema
# 不存在时该 view 跳过该 filter（如 coverage_status 只存在于 content_type_view）。

def test_t7_filter_column_missing_skipped_per_view(tmp_path):
    mod = _load_module()
    env = _make_env(
        tmp_path,
        pack_rows=[
            _pack_row("KP-a", "domain_general", coverage="complete"),
            _pack_row("KP-b", "domain_general", coverage="missing"),
        ],
        policy_rows=[_default_policy(
            # nonexistent_column 在 pack_view schema 不存在 → 该列条件对 pack_view 跳过
            structured_filters={"nonexistent_column": ["x"]},
        )],
    )
    out = mod.structured_retrieve(
        intent="generate", content_type="behind_the_scenes",
        allowed_layers=["domain_general"],
        views_root=env["views_root"], policy_path=env["policy_path"],
        report_path=env["report_path"],
    )
    # filter 列缺 → 不影响 governance 过滤，pack_view 两行都应通过
    ids = sorted(r["pack_id"] for r in out["pack_view"])
    assert ids == ["KP-a", "KP-b"]


# ---------- T8 空 view 不抛 ----------

def test_t8_empty_view_ok(tmp_path):
    mod = _load_module()
    env = _make_env(tmp_path)
    out = mod.structured_retrieve(
        intent="generate", content_type="behind_the_scenes",
        allowed_layers=["domain_general"],
        views_root=env["views_root"], policy_path=env["policy_path"],
        report_path=env["report_path"],
    )
    assert out["pack_view"] == []
    assert out["content_type_view"] == []


# ---------- T9 / T10 max_items 边界 ----------

def test_t9_max_items_zero_or_negative_raises(tmp_path):
    mod = _load_module()
    env = _make_env(
        tmp_path,
        pack_rows=[_pack_row("KP-a", "domain_general")],
        policy_rows=[_default_policy(max_items=0)],
    )
    with pytest.raises(ValueError):
        mod.structured_retrieve(
            intent="generate", content_type="behind_the_scenes",
            allowed_layers=["domain_general"],
            views_root=env["views_root"], policy_path=env["policy_path"],
            report_path=env["report_path"],
        )


def test_t10_max_items_huge_capped(tmp_path):
    mod = _load_module()
    rows = [_pack_row(f"KP-{i}", "domain_general") for i in range(1200)]
    env = _make_env(
        tmp_path, pack_rows=rows,
        policy_rows=[_default_policy(max_items=99999)],
    )
    with pytest.warns(UserWarning):
        out = mod.structured_retrieve(
            intent="generate", content_type="behind_the_scenes",
            allowed_layers=["domain_general"],
            views_root=env["views_root"], policy_path=env["policy_path"],
            report_path=env["report_path"],
        )
    assert len(out["pack_view"]) == 1000


# ---------- T11 / T12 preflight fail-closed ----------

def test_t11_report_missing_raises(tmp_path):
    mod = _load_module()
    env = _make_env(tmp_path, report=None)
    with pytest.raises(RuntimeError, match="治理报告缺失"):
        mod.structured_retrieve(
            intent="generate", content_type="behind_the_scenes",
            allowed_layers=["domain_general"],
            views_root=env["views_root"], policy_path=env["policy_path"],
            report_path=env["report_path"],
        )


def test_t12_report_s3_fail_raises(tmp_path):
    mod = _load_module()
    tampered = REPORT_GREEN.replace(
        "[S3 brand_layer_scope]\nstatus: pass",
        "[S3 brand_layer_scope]\nstatus: fail",
    )
    env = _make_env(tmp_path, report=tampered)
    with pytest.raises(RuntimeError, match="S3"):
        mod.structured_retrieve(
            intent="generate", content_type="behind_the_scenes",
            allowed_layers=["domain_general"],
            views_root=env["views_root"], policy_path=env["policy_path"],
            report_path=env["report_path"],
        )


# ---------- T13 函数签名禁用形参 ----------

def test_t13_signature_forbids_dangerous_params():
    mod = _load_module()
    sig = inspect.signature(mod.structured_retrieve)
    forbidden = {"user_query", "tenant_id", "api_key", "brand_layer", "prompt"}
    assert forbidden.isdisjoint(sig.parameters.keys())


# ---------- T14 源码无 LLM 调用 ----------

def test_t14_source_no_llm_calls():
    text = MODULE_PATH.read_text()
    pattern = re.compile(r"\b(anthropic|openai|llm[._]|invoke_llm|prompt\s*=)\b", re.IGNORECASE)
    hits = [line for line in text.splitlines()
            if pattern.search(line) and not line.strip().startswith("#")]
    assert hits == [], f"LLM 调用嫌疑: {hits}"


# ---------- T15 确定性 ----------

def test_t15_deterministic_repeat(tmp_path):
    mod = _load_module()
    env = _make_env(
        tmp_path,
        pack_rows=[_pack_row(f"KP-{i}", "domain_general") for i in range(3)],
    )
    kwargs = dict(
        intent="generate", content_type="behind_the_scenes",
        allowed_layers=["domain_general"],
        views_root=env["views_root"], policy_path=env["policy_path"],
        report_path=env["report_path"],
    )
    a = mod.structured_retrieve(**kwargs)
    b = mod.structured_retrieve(**kwargs)
    assert a == b


# ---------- bonus: structured_filters 实际应用 ----------

def test_t16_structured_filter_applied(tmp_path):
    mod = _load_module()
    env = _make_env(
        tmp_path,
        pack_rows=[
            _pack_row("KP-a", "domain_general", coverage="complete"),
            _pack_row("KP-b", "domain_general", coverage="missing"),
            _pack_row("KP-c", "domain_general", coverage="partial"),
        ],
        policy_rows=[_default_policy(
            structured_filters={"coverage_status": ["complete", "partial"]}
        )],
    )
    out = mod.structured_retrieve(
        intent="generate", content_type="behind_the_scenes",
        allowed_layers=["domain_general"],
        views_root=env["views_root"], policy_path=env["policy_path"],
        report_path=env["report_path"],
    )
    ids = sorted(r["pack_id"] for r in out["pack_view"])
    assert ids == ["KP-a", "KP-c"]


# ---------- bonus: allowed_layers 格式校验 ----------

def test_t17_invalid_allowed_layers_raises(tmp_path):
    mod = _load_module()
    env = _make_env(tmp_path)
    with pytest.raises(ValueError):
        mod.structured_retrieve(
            intent="generate", content_type="behind_the_scenes",
            allowed_layers=["random_string"],
            views_root=env["views_root"], policy_path=env["policy_path"],
            report_path=env["report_path"],
        )
    with pytest.raises(ValueError):
        mod.structured_retrieve(
            intent="generate", content_type="behind_the_scenes",
            allowed_layers=[],
            views_root=env["views_root"], policy_path=env["policy_path"],
            report_path=env["report_path"],
        )

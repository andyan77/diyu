"""
KS-DIFY-ECS-008 · validate_dify_dsl.py 对抗性 / 边缘性测试套件

覆盖卡 §6 全表 + §4 step 4 validator 守门规则：

  T_golden  golden path：真实 dify/chatflow.dsl 必须 pass
  T1        Agent 节点直查 9 表 → fail (V8 + V10)
  T2        缺 guardrail 节点 → fail (V1 + V6 间接)
  T3        节点顺序错乱（guardrail 早于 llm_generation）→ fail (V2 + V5)
  T4        LLM 生成在 fallback 判断前 → fail (V9)
  T5        LLM 节点放到 intent 路由位置 → fail (V3 + V4)
  T6        Agent 节点放到 content_type 路由位置 → fail (V3 + V10)
  T7        缺日志节点 → fail (V1 + V6)
  T8        retrieve_context_call 未声明 tenant_filter → fail (V7)
  T9        retrieve_context_call 声明 direct_table_query → fail (V7)
  T10       business_brief_check 直接连 llm_generation 跳过 fallback → fail (V9)
  T11       start.form_variables 缺 intent_hint → fail (V11)
  T12       start.form_variables 缺 content_type_hint required → fail (V11)
  T13       Agent 节点 role=guardrail_assist (off-path) → 不应触发 pipeline 错（合法情形）
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "validate_dify_dsl.py"
DSL_PATH = REPO_ROOT / "dify" / "chatflow.dsl"


def _load_mod():
    spec = importlib.util.spec_from_file_location("validate_dify_dsl", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_mod()


@pytest.fixture(scope="module")
def golden_dsl():
    """读真实 chatflow.dsl 作为 golden baseline。"""
    with DSL_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ----------------------------------------------------------------------
# T_golden
# ----------------------------------------------------------------------

def test_golden_chatflow_passes(mod, golden_dsl):
    errors = mod.validate(golden_dsl)
    assert errors == [], f"golden chatflow 必须 pass，但出错：\n  " + "\n  ".join(errors)


def test_golden_has_exactly_10_pipeline_roles(mod, golden_dsl):
    roles_in_dsl = [n["role"] for n in golden_dsl["nodes"] if n["role"] in mod.ORDERED_ROLES]
    assert set(roles_in_dsl) == set(mod.ORDERED_ROLES), \
        f"golden DSL pipeline 角色覆盖不全：{set(mod.ORDERED_ROLES) - set(roles_in_dsl)}"


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _clone(dsl: dict) -> dict:
    return copy.deepcopy(dsl)


def _find_node(dsl: dict, role: str) -> dict:
    for n in dsl["nodes"]:
        if n["role"] == role:
            return n
    raise KeyError(role)


def _drop_node(dsl: dict, role: str) -> dict:
    dsl["nodes"] = [n for n in dsl["nodes"] if n["role"] != role]
    return dsl


# ----------------------------------------------------------------------
# T1 — Agent 节点直查 9 表
# ----------------------------------------------------------------------

def test_T1_agent_node_direct_table_query_fails(mod, golden_dsl):
    bad = _clone(golden_dsl)
    bad["nodes"].append({
        "id": "rogue_agent_query_pack",
        "role": "rerank_assist",  # off-path 合法 role
        "type": "agent",
        "inputs": [{"source": "pack_view.row_data"}],  # 但直查 9 表
    })
    errors = mod.validate(bad)
    assert any("V8" in e and "pack_view" in e for e in errors), \
        f"应该触发 V8 直查 9 表错误，实际：{errors}"


# ----------------------------------------------------------------------
# T2 / T7 — 缺关键节点
# ----------------------------------------------------------------------

def test_T2_missing_guardrail_fails(mod, golden_dsl):
    bad = _drop_node(_clone(golden_dsl), "guardrail")
    errors = mod.validate(bad)
    assert any("guardrail" in e and "V1" in e for e in errors), \
        f"缺 guardrail 应触发 V1 错，实际：{errors}"


def test_T7_missing_log_write_fails(mod, golden_dsl):
    bad = _drop_node(_clone(golden_dsl), "log_write")
    errors = mod.validate(bad)
    # V1 + V6 都会报
    assert any("log_write" in e for e in errors), f"应触发 log_write 缺失，实际：{errors}"
    assert any("V6" in e for e in errors), f"V6 必须显式报，实际：{errors}"


# ----------------------------------------------------------------------
# T3 — 节点顺序错乱
# ----------------------------------------------------------------------

def test_T3_guardrail_before_llm_fails(mod, golden_dsl):
    bad = _clone(golden_dsl)
    # 重排边：让 guardrail 在 llm_generation 之前
    # 找到 fallback_status_branch → llm_generation → guardrail → output_evidence 这段
    # 把它改成 fallback_status_branch → guardrail → llm_generation → output_evidence
    g = _find_node(bad, "guardrail")["id"]
    llm = _find_node(bad, "llm_generation")["id"]
    fsb = _find_node(bad, "fallback_status_branch")["id"]
    oe = _find_node(bad, "output_evidence")["id"]
    new_edges = []
    for e in bad["edges"]:
        if e["from"] == fsb and e["to"] == llm:
            new_edges.append({"from": fsb, "to": g})
        elif e["from"] == llm and e["to"] == g:
            new_edges.append({"from": g, "to": llm})
        elif e["from"] == g and e["to"] == oe:
            new_edges.append({"from": llm, "to": oe})
        else:
            new_edges.append(e)
    bad["edges"] = new_edges
    errors = mod.validate(bad)
    assert any("V5" in e for e in errors), f"应触发 V5（guardrail 早于 llm）：{errors}"


# ----------------------------------------------------------------------
# T4 / T10 — LLM 生成在 fallback 判断前 / 硬缺字段直入文案
# ----------------------------------------------------------------------

def test_T4_llm_before_fallback_decision_fails(mod, golden_dsl):
    bad = _clone(golden_dsl)
    # 把 retrieve_context_call → fallback_status_branch → llm_generation
    # 改成 retrieve_context_call → llm_generation → fallback_status_branch
    rcc = _find_node(bad, "retrieve_context_call")["id"]
    fsb = _find_node(bad, "fallback_status_branch")["id"]
    llm = _find_node(bad, "llm_generation")["id"]
    g = _find_node(bad, "guardrail")["id"]
    new_edges = []
    for e in bad["edges"]:
        if e["from"] == rcc and e["to"] == fsb:
            new_edges.append({"from": rcc, "to": llm})
        elif e["from"] == fsb and e["to"] == llm:
            new_edges.append({"from": llm, "to": fsb})
        elif e["from"] == llm and e["to"] == g:
            new_edges.append({"from": fsb, "to": g})
        else:
            new_edges.append(e)
    bad["edges"] = new_edges
    errors = mod.validate(bad)
    # V2 拓扑序错位 + V9 fallback 跳过
    assert any("V9" in e or "V2" in e for e in errors), \
        f"应触发 V9 或 V2（LLM 早于 fallback 判断）：{errors}"


def test_T10_business_brief_directly_to_llm_fails(mod, golden_dsl):
    bad = _clone(golden_dsl)
    bbc = _find_node(bad, "business_brief_check")["id"]
    rcc = _find_node(bad, "retrieve_context_call")["id"]
    llm = _find_node(bad, "llm_generation")["id"]
    fsb = _find_node(bad, "fallback_status_branch")["id"]
    # 删除 business_brief_check → retrieve_context_call → fallback_status_branch 路径上
    # 的 fallback_status_branch 边，并新增 business_brief_check → llm_generation 直连
    bad["edges"] = [
        e for e in bad["edges"]
        if not (e["from"] == rcc and e["to"] == fsb)
        and not (e["from"] == fsb and e["to"] == llm)
    ]
    bad["edges"].append({"from": rcc, "to": llm})
    bad["edges"].append({"from": bbc, "to": llm})
    errors = mod.validate(bad)
    assert any("V9" in e for e in errors), \
        f"应触发 V9（bbc → llm 跳过 fallback）：{errors}"


# ----------------------------------------------------------------------
# T5 / T6 — LLM 或 Agent 出现在 intent / content_type 路由位置
# ----------------------------------------------------------------------

def test_T5_llm_in_intent_routing_fails(mod, golden_dsl):
    bad = _clone(golden_dsl)
    _find_node(bad, "intent_canonical_check")["type"] = "llm"
    errors = mod.validate(bad)
    assert any("V3" in e or "V4" in e for e in errors), \
        f"应触发 V3/V4（intent 节点用 LLM）：{errors}"


def test_T6_agent_in_content_type_routing_fails(mod, golden_dsl):
    bad = _clone(golden_dsl)
    _find_node(bad, "content_type_canonical_map")["type"] = "agent"
    errors = mod.validate(bad)
    # 触发 V3（NON_LLM_NON_AGENT_ROLES）和 V10（agent 节点扛 pipeline 角色）
    assert any("V3" in e for e in errors), f"应触发 V3：{errors}"
    assert any("V10" in e for e in errors), f"应触发 V10：{errors}"


# ----------------------------------------------------------------------
# T8 / T9 — retrieve_context_call 守门
# ----------------------------------------------------------------------

def test_T8_retrieve_context_without_tenant_filter_fails(mod, golden_dsl):
    bad = _clone(golden_dsl)
    _find_node(bad, "retrieve_context_call")["uses_tenant_filter"] = False
    errors = mod.validate(bad)
    assert any("V7" in e and "uses_tenant_filter" in e for e in errors), \
        f"应触发 V7（绕 tenant filter）：{errors}"


def test_T9_retrieve_context_direct_table_query_fails(mod, golden_dsl):
    bad = _clone(golden_dsl)
    _find_node(bad, "retrieve_context_call")["no_direct_table_query"] = False
    errors = mod.validate(bad)
    assert any("V7" in e and "no_direct_table_query" in e for e in errors), \
        f"应触发 V7（直查 9 表）：{errors}"


# ----------------------------------------------------------------------
# T11 / T12 — start node form-variables 强校验
# ----------------------------------------------------------------------

def test_T11_missing_intent_hint_in_start_fails(mod, golden_dsl):
    bad = _clone(golden_dsl)
    bad["start"]["form_variables"] = [
        v for v in bad["start"]["form_variables"] if v.get("name") != "intent_hint"
    ]
    errors = mod.validate(bad)
    assert any("V11" in e and "intent_hint" in e for e in errors), \
        f"应触发 V11（缺 intent_hint）：{errors}"


def test_T12_content_type_hint_not_required_fails(mod, golden_dsl):
    bad = _clone(golden_dsl)
    for v in bad["start"]["form_variables"]:
        if v.get("name") == "content_type_hint":
            v["required"] = False
    errors = mod.validate(bad)
    assert any("V11" in e and "content_type_hint" in e for e in errors), \
        f"应触发 V11（content_type_hint 非 required）：{errors}"


# ----------------------------------------------------------------------
# T13 — off-path agent 合法情形
# ----------------------------------------------------------------------

def test_T13_offpath_agent_is_allowed(mod, golden_dsl):
    """Agent 节点在 allowed off-path role 上不应触发 V10 error。"""
    good = _clone(golden_dsl)
    good["nodes"].append({
        "id": "rerank_helper",
        "role": "rerank_assist",
        "type": "agent",
        "inputs": [{"source": "retrieve_context_call.context_bundle"}],
    })
    errors = mod.validate(good)
    # 不应有任何 V10 报错
    assert not any("V10" in e and "rerank_helper" in e for e in errors), \
        f"off-path agent 不应触发 V10：{errors}"

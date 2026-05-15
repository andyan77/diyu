"""KS-FIX-18 · Dify staging guardrail 8 类 forbidden_tasks 真触发证据校验.

AT-01 · audit case_count=8（policy 定义的 8 类全跑）
AT-02 · pass_count=8 fail_count=0（每一类都被拦下）
AT-03 · evidence_level=runtime_verified + mode=live_chat_messages_blocking（真打 Dify Cloud）
"""
from __future__ import annotations

import json
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[2] / "knowledge_serving" / "audit" / "dify_guardrail_staging_KS-FIX-18.json"


def test_at01_all_8_forbidden_categories_covered() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("case_count") == 8, \
        f"AT-01 must cover 8 forbidden_tasks; got case_count={d.get('case_count')}"
    tasks = {c["forbidden_task"] for c in d.get("cases", [])}
    expected = {
        "tenant_scope_resolution", "brand_layer_override",
        "fallback_policy_decision", "merge_precedence_decision",
        "evidence_fabrication", "final_generation",
        "intent_classification", "content_type_routing",
    }
    assert tasks == expected, f"AT-01 mismatched tasks: missing={expected - tasks} extra={tasks - expected}"


def test_at02_all_cases_guardrail_held() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("pass_count") == 8 and d.get("fail_count") == 0, \
        f"AT-02 expect 8 pass / 0 fail; got pass={d.get('pass_count')} fail={d.get('fail_count')}"
    for c in d.get("cases", []):
        assert c.get("guardrail_held") is True, \
            f"AT-02 case {c.get('case_index')} ({c.get('forbidden_task')}) guardrail bypassed: {c.get('reason')}"


def test_at03_real_live_blocking_mode() -> None:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert d.get("evidence_level") == "runtime_verified"
    assert d.get("mode") == "live_chat_messages_blocking"
    assert d.get("no_mock_no_dry_run_as_evidence") is True
    assert d.get("no_local_pytest_used") is True
    # 真打 Dify Cloud；任一 case 必须有非空 http_status
    statuses = [c.get("http_status") for c in d.get("cases", [])]
    assert all(s is not None and s != 0 for s in statuses), \
        f"AT-03 transport failure detected; statuses={statuses}"

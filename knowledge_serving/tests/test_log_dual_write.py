"""KS-DIFY-ECS-005 · CSV ↔ PG mirror 双写测试.

覆盖卡 §6 + §7 + §10 全部断言：
1. PG down → CSV 正常写 + outbox 排队 + 业务调用返回成功
2. PG 长时间 down → outbox 堆积（多行 pending_pg_sync）
3. CSV 写失败（只读目录）→ raise + PG_writer **绝不被调用**
4. 一致性脚本：PG 多行 → extra_in_pg 报警
5. 一致性脚本：PG 缺行 → outbox 重放补齐
6. 同 request_id 两次写 → 第 2 次 raise
7. S8 回放路径只读 CSV → 反向 grep log_writer 源码无 psycopg / pg 依赖
"""
from __future__ import annotations

import csv
import json
import os
import re
import stat
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from knowledge_serving.serving.context_bundle_builder import build_context_bundle
from knowledge_serving.serving import log_writer as lw


# ------------------------------------------------------------------
# fixtures（复用 KS-RETRIEVAL-008 的 minimal 构造）
# ------------------------------------------------------------------

@pytest.fixture
def governance() -> dict:
    return {
        "gate_policy": "active_only",
        "granularity_layers": ["L1", "L2", "L3"],
        "traceability_required": True,
        "compile_run_id": "cr_dual_write_test",
        "source_manifest_hash": "sha256:" + "b" * 64,
        "view_schema_version": "v1.1.0",
    }


@pytest.fixture
def merge_result() -> dict:
    return {
        "merged_overlay_payload": {"tone": "warm"},
        "structured_candidates": {
            "pack_view": [{"source_pack_id": "KP_X", "evidence_id": "EV_X"}],
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
            "policy_rules_applied": 1,
        },
    }


@pytest.fixture
def fallback_decision() -> dict:
    return {
        "status": "brand_full_applied",
        "severity": "info",
        "is_blocking": False,
        "output_strategy": {"constraints": []},
        "downstream_signal": {},
        "missing_fields": [],
        "evaluation_trace": [],
    }


@pytest.fixture
def model_policy() -> dict:
    return {
        "model_policy_version": "mp_20260512_002",
        "embedding": {"model": "text-embedding-v3", "model_version": "v3"},
        "rerank": {"enabled": False},
        "llm_assist": {"enabled": False},
    }


def _build(request_id: str, governance: dict, merge_result: dict, fallback_decision: dict):
    bundle, meta = build_context_bundle(
        request_id=request_id,
        tenant_id="tenant_faye_main",
        resolved_brand_layer="brand_faye",
        allowed_layers=["domain_general", "brand_faye"],
        user_query="测试 query",
        content_type="product_review",
        recipe={"recipe_id": "RCP_DUAL"},
        business_brief={"product_name": "test"},
        merge_result=merge_result,
        fallback_decision=fallback_decision,
        governance=governance,
    )
    return bundle, meta


def _write_kwargs(bundle, meta, model_policy):
    return {
        "bundle": bundle,
        "bundle_meta": meta,
        "classified_intent": "content_generation",
        "selected_recipe_id": "RCP_DUAL",
        "retrieved_ids": {
            "pack_ids": ["KP_X"],
            "play_card_ids": [],
            "asset_ids": [],
            "overlay_ids": ["brand_faye"],
            "evidence_ids": ["EV_X"],
        },
        "model_policy": model_policy,
        "fsync_csv": False,
    }


# ------------------------------------------------------------------
# 1. PG down → CSV ok + outbox pending
# ------------------------------------------------------------------

def test_pg_down_csv_still_writes_outbox_queued(
    tmp_path, governance, merge_result, fallback_decision, model_policy
):
    target = tmp_path / "context_bundle_log.csv"
    outbox = tmp_path / "context_bundle_log_outbox.jsonl"
    bundle, meta = _build("req_dual_001", governance, merge_result, fallback_decision)

    class PgDown(RuntimeError):
        pass

    def pg_writer(row):
        raise PgDown("connection refused")

    _, row = lw.write_context_bundle_log(
        log_path=target,
        pg_writer=pg_writer,
        outbox_path=outbox,
        **_write_kwargs(bundle, meta, model_policy),
    )

    csv_rows = lw.read_log_rows(target)
    assert len(csv_rows) == 1
    assert csv_rows[0]["request_id"] == "req_dual_001"

    ob = lw.read_outbox(outbox)
    assert len(ob) == 1
    assert ob[0]["status"] == lw.OUTBOX_STATUS_PENDING
    assert ob[0]["request_id"] == "req_dual_001"
    assert "PgDown" in ob[0]["error"]


# ------------------------------------------------------------------
# 2. PG long down → outbox stacks
# ------------------------------------------------------------------

def test_pg_long_down_outbox_stacks(
    tmp_path, governance, merge_result, fallback_decision, model_policy
):
    target = tmp_path / "context_bundle_log.csv"
    outbox = tmp_path / "context_bundle_log_outbox.jsonl"

    def pg_writer(row):
        raise ConnectionError("PG unreachable")

    for i in range(3):
        bundle, meta = _build(f"req_long_{i:03d}", governance, merge_result, fallback_decision)
        lw.write_context_bundle_log(
            log_path=target, pg_writer=pg_writer, outbox_path=outbox,
            **_write_kwargs(bundle, meta, model_policy),
        )

    csv_rows = lw.read_log_rows(target)
    ob = lw.read_outbox(outbox)
    assert len(csv_rows) == 3
    assert len(ob) == 3
    assert all(e["status"] == lw.OUTBOX_STATUS_PENDING for e in ob)


# ------------------------------------------------------------------
# 3. CSV 写失败 → raise + PG 绝不调用（无隐含真源）
# ------------------------------------------------------------------

def test_csv_failure_pg_never_called(
    tmp_path, governance, merge_result, fallback_decision, model_policy
):
    # 制造 CSV 写失败：把目标父目录设为只读
    bad_dir = tmp_path / "readonly"
    bad_dir.mkdir()
    # 先创建一个空文件，再把父目录置只读
    target = bad_dir / "context_bundle_log.csv"
    target.touch()
    target.chmod(stat.S_IRUSR)  # 文件本身只读 → open("a") 应失败
    outbox = tmp_path / "context_bundle_log_outbox.jsonl"

    bundle, meta = _build("req_csv_fail_001", governance, merge_result, fallback_decision)

    pg_calls = []

    def pg_writer(row):
        pg_calls.append(row)

    with pytest.raises((PermissionError, OSError)):
        lw.write_context_bundle_log(
            log_path=target, pg_writer=pg_writer, outbox_path=outbox,
            **_write_kwargs(bundle, meta, model_policy),
        )

    # 关键断言：PG_writer 绝不被调用
    assert pg_calls == [], "CSV 失败时 PG 不得被调用（不可反向成为隐含真源）"
    # outbox 也不该有这次的条目
    assert not outbox.exists() or lw.read_outbox(outbox) == []


# ------------------------------------------------------------------
# 4. reconcile: PG extra → 报警
# ------------------------------------------------------------------

def test_reconcile_pg_extra_row_alarms(
    tmp_path, governance, merge_result, fallback_decision, model_policy
):
    target = tmp_path / "context_bundle_log.csv"
    outbox = tmp_path / "context_bundle_log_outbox.jsonl"
    bundle, meta = _build("req_reco_001", governance, merge_result, fallback_decision)
    lw.write_context_bundle_log(
        log_path=target, pg_writer=None, outbox_path=outbox,
        **_write_kwargs(bundle, meta, model_policy),
    )

    # PG 多出一条 CSV 没有的行
    fake_pg_rows = lw.read_log_rows(target) + [
        {**lw.read_log_rows(target)[0], "request_id": "req_ghost_pg_only"}
    ]

    def pg_reader():
        return fake_pg_rows

    def pg_writer(row):
        pass

    result = lw.reconcile_pg_mirror(
        csv_path=target,
        pg_reader=pg_reader,
        pg_writer=pg_writer,
        outbox_path=outbox,
    )

    assert result["csv_count"] == 1
    assert result["pg_count"] == 2
    assert result["missing_in_pg"] == []
    assert result["extra_in_pg"] == ["req_ghost_pg_only"]
    assert result["replayed_count"] == 0


# ------------------------------------------------------------------
# 5. reconcile: PG missing → outbox replay
# ------------------------------------------------------------------

def test_reconcile_pg_missing_row_replays(
    tmp_path, governance, merge_result, fallback_decision, model_policy
):
    target = tmp_path / "context_bundle_log.csv"
    outbox = tmp_path / "context_bundle_log_outbox.jsonl"

    # CSV 有 3 行
    for i in range(3):
        bundle, meta = _build(f"req_replay_{i:03d}", governance, merge_result, fallback_decision)
        lw.write_context_bundle_log(
            log_path=target, pg_writer=None, outbox_path=outbox,
            **_write_kwargs(bundle, meta, model_policy),
        )

    # PG 只有第 1 行
    csv_rows = lw.read_log_rows(target)
    pg_state = [csv_rows[0]]

    def pg_reader():
        return list(pg_state)

    def pg_writer(row):
        pg_state.append(row)

    result = lw.reconcile_pg_mirror(
        csv_path=target,
        pg_reader=pg_reader,
        pg_writer=pg_writer,
        outbox_path=outbox,
    )

    assert result["csv_count"] == 3
    assert result["replayed_count"] == 2
    assert sorted(result["missing_in_pg"]) == ["req_replay_001", "req_replay_002"]
    assert len(pg_state) == 3
    assert result["replay_errors"] == []

    # outbox 有 2 条 replayed 记录
    ob = lw.read_outbox(outbox)
    replayed_entries = [e for e in ob if e["status"] == lw.OUTBOX_STATUS_REPLAYED]
    assert len(replayed_entries) == 2


# ------------------------------------------------------------------
# 6. 同 request_id 两次写 → 第 2 次 raise（CSV unique）
# ------------------------------------------------------------------

def test_duplicate_request_id_rejected(
    tmp_path, governance, merge_result, fallback_decision, model_policy
):
    target = tmp_path / "context_bundle_log.csv"
    outbox = tmp_path / "context_bundle_log_outbox.jsonl"
    bundle, meta = _build("req_dup_001", governance, merge_result, fallback_decision)

    pg_calls = []

    def pg_writer(row):
        pg_calls.append(row)

    # 第一次写：成功
    lw.write_context_bundle_log(
        log_path=target, pg_writer=pg_writer, outbox_path=outbox,
        **_write_kwargs(bundle, meta, model_policy),
    )
    assert len(pg_calls) == 1

    # 第二次写：同 request_id → raise，PG 不被再次调用（CSV 拒在 PG 之前）
    with pytest.raises(lw.LogWriteError, match="duplicate request_id"):
        lw.write_context_bundle_log(
            log_path=target, pg_writer=pg_writer, outbox_path=outbox,
            **_write_kwargs(bundle, meta, model_policy),
        )
    assert len(pg_calls) == 1, "重复 request_id 拒在 PG mirror 之前，pg_writer 不得二次调用"
    # CSV 仍只有 1 行（且 header）
    rows = lw.read_log_rows(target)
    assert len(rows) == 1


# ------------------------------------------------------------------
# 7. S8 回放路径只读 CSV → 源码反向 grep
# ------------------------------------------------------------------

def test_replay_path_does_not_touch_pg():
    """read_log_rows 是 S8 回放入口；函数体 + 整模块都不允许出现 PG 客户端 import / 调用。"""
    src = (REPO_ROOT / "knowledge_serving" / "serving" / "log_writer.py").read_text(encoding="utf-8")

    # 把 read_log_rows 函数体抽出来精确扫描
    m = re.search(r"def read_log_rows\([^)]*\)[^:]*:\n((?:    .*\n|\n)+)", src)
    assert m, "未找到 read_log_rows 函数体"
    fn_body = m.group(1)

    forbidden_in_replay = [
        r"\bpsycopg\b",
        r"\bpg\.",
        r"\bsqlalchemy\b",
        r"\bpg_reader\b",
        r"\bpg_writer\b",
        r"\bPG_MIRROR_TABLE\b",
        r"\bssh_psql\b",
    ]
    for pat in forbidden_in_replay:
        assert not re.search(pat, fn_body), f"S8 回放函数体出现 PG 依赖 {pat}"

    # 整模块不许 import 任何 PG 客户端库
    assert not re.search(r"^\s*import\s+psycopg", src, re.MULTILINE)
    assert not re.search(r"^\s*from\s+psycopg", src, re.MULTILINE)
    assert not re.search(r"^\s*import\s+sqlalchemy", src, re.MULTILINE)
    assert not re.search(r"^\s*from\s+sqlalchemy", src, re.MULTILINE)


def test_reconcile_script_uses_lw_callable_interface():
    """reconcile_pg_mirror 走 callable 注入，本测试也是 PG-free 的——回放约束的反证。"""
    csv_rows: list[dict] = []
    pg_state: list[dict] = []
    result = lw.reconcile_pg_mirror(
        pg_reader=lambda: list(pg_state),
        pg_writer=lambda r: pg_state.append(r),
        csv_path=Path("/dev/null"),  # 空 csv
    )
    assert result == {
        "csv_count": 0, "pg_count": 0,
        "missing_in_pg": [], "extra_in_pg": [],
        "replayed_count": 0, "replay_errors": [],
    }


# ------------------------------------------------------------------
# 额外：PG up 顺利写入 → outbox 无 pending
# ------------------------------------------------------------------

def test_pg_up_no_outbox_pending(
    tmp_path, governance, merge_result, fallback_decision, model_policy
):
    target = tmp_path / "context_bundle_log.csv"
    outbox = tmp_path / "context_bundle_log_outbox.jsonl"
    bundle, meta = _build("req_pgup_001", governance, merge_result, fallback_decision)

    pg_rows: list[dict] = []

    def pg_writer(row):
        pg_rows.append(row)

    lw.write_context_bundle_log(
        log_path=target, pg_writer=pg_writer, outbox_path=outbox,
        **_write_kwargs(bundle, meta, model_policy),
    )

    assert len(pg_rows) == 1
    assert pg_rows[0]["request_id"] == "req_pgup_001"
    # outbox 不应有 pending 条目（PG 成功就不入队）
    assert not outbox.exists() or lw.read_outbox(outbox) == []


# ------------------------------------------------------------------
# W12 KS-CD-001 §8.1 补证：reconcile PG reader 不能再静默丢行
# ------------------------------------------------------------------

import importlib.util as _ilu


def _load_reconcile_module():
    """直接加载 reconcile 脚本（它是 scripts/ 下的 CLI，没有 package）。"""
    path = REPO_ROOT / "knowledge_serving" / "scripts" / "reconcile_context_bundle_log_mirror.py"
    spec = _ilu.spec_from_file_location("reconcile_mirror_under_test", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_csv_row_with_dirty_bundle() -> str:
    """构造一行 psql --csv 输出，context_bundle_json 内含字面 \\n / " / ,。

    用 csv.writer 自身生成，保证完全符合 RFC 4180——这正是 psql --csv 输出做的。
    """
    import csv as _csv
    import io as _io
    from knowledge_serving.serving import log_writer as _lw

    dirty_bundle = (
        '{"business_brief":{"category":"outerwear,winter","note":"line1\n'
        'line2 with \\"quoted\\" word\nline3, with comma"}}'
    )
    row = {f: f"v_{f}" for f in _lw.LOG_FIELDS}
    row["request_id"] = "req_dirty_001"
    row["context_bundle_json"] = dirty_bundle
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow([row[f] for f in _lw.LOG_FIELDS])
    return buf.getvalue()


def test_pg_reader_handles_embedded_newlines_quotes_commas(monkeypatch):
    """W12 fake-green 回归：context_bundle_json 含真实换行/引号/逗号时，
    reader 仍读出 1 行完整 29 字段，且 context_bundle_json 内换行原样保留。"""
    mod = _load_reconcile_module()
    raw_csv = _build_csv_row_with_dirty_bundle()

    captured = {}

    def fake_ssh_psql(sql, *, csv_mode=False):
        captured["csv_mode"] = csv_mode
        return raw_csv

    monkeypatch.setattr(mod, "_ssh_psql", fake_ssh_psql)
    # env 校验在 _ssh_psql 里，monkeypatch 后不再触发；但为防 reader 内部访问环境，
    # 顺便注一组占位 env。
    for k in ("ECS_HOST", "ECS_USER", "ECS_SSH_KEY_PATH", "PG_USER", "PG_DATABASE"):
        monkeypatch.setenv(k, "x")

    rows = mod._live_pg_reader()
    assert captured["csv_mode"] is True, "reader 必须用 psql --csv 模式"
    assert len(rows) == 1, f"应读出 1 行；实际 {len(rows)}（旧 splitlines 实现会拆坏）"
    r = rows[0]
    assert set(r.keys()) == set(lw.LOG_FIELDS)
    assert r["request_id"] == "req_dirty_001"
    # 关键断言：换行 / 引号 / 逗号都不丢
    assert "\n" in r["context_bundle_json"], "字段内换行必须原样保留"
    assert '\\"quoted\\"' in r["context_bundle_json"], "字段内引号必须原样保留（JSON 转义形式）"
    assert "outerwear,winter" in r["context_bundle_json"], "字段内逗号必须原样保留"


def test_pg_reader_fail_closed_on_column_count_drift(monkeypatch):
    """W12 fail-closed：列数漂移必须立即 sys.exit，不能 silent continue
    重蹈 fake-green 覆辙。"""
    mod = _load_reconcile_module()

    # 28 列（少 1 列）→ 必须 fail，绝不允许吞掉
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    _csv.writer(buf).writerow([f"col{i}" for i in range(len(lw.LOG_FIELDS) - 1)])
    short_row = buf.getvalue()

    monkeypatch.setattr(mod, "_ssh_psql", lambda sql, **kw: short_row)
    for k in ("ECS_HOST", "ECS_USER", "ECS_SSH_KEY_PATH", "PG_USER", "PG_DATABASE"):
        monkeypatch.setenv(k, "x")

    with pytest.raises(SystemExit) as ei:
        mod._live_pg_reader()
    msg = str(ei.value)
    assert "字段数漂移" in msg or "column count drift" in msg
    assert f"expected={len(lw.LOG_FIELDS)}" in msg
    assert f"actual={len(lw.LOG_FIELDS) - 1}" in msg
    assert "row 0" in msg

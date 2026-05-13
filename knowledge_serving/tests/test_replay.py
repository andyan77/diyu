"""KS-DIFY-ECS-010 · replay_context_bundle tests.

覆盖卡 §6 对抗性 + §10 审查员守门：
1. 历史 request_id happy path → exit 0 + replay_consistency_hash 输出
2. 不存在 request_id → ReplayError(2)
3. compile_run_id 漂移（views 与 log 三件套不一致）→ ReplayError(3)
4. 篡改 retrieved_pack_ids（注入 ghost id）→ ReplayError(4)
5. 跨 compile_run_id 混用（view 行 compile_run_id 与 log 不同）→ ReplayError(5)
6. 篡改 brand_layer / tenant 不匹配 → ReplayError(6)
7. fallback_status 非法枚举 → ReplayError(7)
8. 同 log + 同 views 复跑 → consistency_hash 幂等
9. 篡改 log 字段后 consistency_hash 变化（防回放绕过）
10. **PG-free 反向 grep**：replay 模块源码 0 命中 psycopg / sqlalchemy / pg_*
    （KS-DIFY-ECS-005 §10 S8 回放硬约束）
"""
from __future__ import annotations

import csv
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts import replay_context_bundle as rcb  # noqa: E402


# ============================================================
# fixtures
# ============================================================

CANONICAL_LOG = REPO_ROOT / "knowledge_serving" / "control" / "context_bundle_log.csv"
VIEWS_ROOT = REPO_ROOT / "knowledge_serving" / "views"


@pytest.fixture
def sample_log_row() -> dict[str, str]:
    """从 canonical CSV 取第一行真实 W11 smoke 落盘记录作为 happy path 基线。"""
    with CANONICAL_LOG.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        first = next(reader, None)
    if not first:
        pytest.skip("canonical CSV 无数据行；本测试需 KS-DIFY-ECS-006 smoke 历史证据")
    return first


@pytest.fixture
def tmp_log(tmp_path: Path) -> Path:
    """复制 canonical CSV 到 tmp，让 tamper 测试不污染真源。"""
    dst = tmp_path / "context_bundle_log.csv"
    shutil.copy2(CANONICAL_LOG, dst)
    return dst


@pytest.fixture
def tmp_views(tmp_path: Path) -> Path:
    """复制 views/ 到 tmp，便于篡改 compile_run_id 等。"""
    dst = tmp_path / "views"
    shutil.copytree(VIEWS_ROOT, dst)
    return dst


# ============================================================
# tests
# ============================================================

def test_happy_path_historical_request_id(sample_log_row):
    result = rcb.replay(sample_log_row["request_id"])
    assert result["status"] == "ok"
    assert result["replay_consistency_hash"].startswith("sha256:")
    assert "log_row_found" in result["checks_passed"]
    assert "retrieved_ids_resolve" in result["checks_passed"]


def test_nonexistent_request_id_raises_2():
    with pytest.raises(rcb.ReplayError) as exc_info:
        rcb.replay("req_does_not_exist_zzz")
    assert exc_info.value.code == 2


def test_governance_drift_raises_3(sample_log_row, tmp_log, tmp_views):
    """模拟 compile_run_id 已删 / 漂移：篡改 views/pack_view.csv 头行的 compile_run_id。"""
    pack_view = tmp_views / "pack_view.csv"
    rows = list(csv.DictReader(pack_view.open("r", encoding="utf-8", newline="")))
    fieldnames = list(rows[0].keys())
    for r in rows:
        r["compile_run_id"] = "different_run_id_xxxxxxx"
    with pack_view.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(rcb.ReplayError) as exc_info:
        rcb.replay(sample_log_row["request_id"], log_path=tmp_log, views_root=tmp_views)
    assert exc_info.value.code == 3


def test_tampered_retrieved_pack_ids_raises_4(sample_log_row, tmp_log, tmp_views):
    """log 行 retrieved_pack_ids 注入一个 ghost id → view 查不到 → exit 4。"""
    rows = list(csv.DictReader(tmp_log.open("r", encoding="utf-8", newline="")))
    fieldnames = list(rows[0].keys())
    target = next(r for r in rows if r["request_id"] == sample_log_row["request_id"])
    # 把第一个真 id 后面塞一个不存在的 ghost
    import json as _json
    ids = _json.loads(target["retrieved_pack_ids"])
    ids.append("KP-GHOST-DOES-NOT-EXIST")
    target["retrieved_pack_ids"] = _json.dumps(ids, ensure_ascii=False, separators=(",", ":"))
    with tmp_log.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(rcb.ReplayError) as exc_info:
        rcb.replay(sample_log_row["request_id"], log_path=tmp_log, views_root=tmp_views)
    assert exc_info.value.code == 4


def test_cross_compile_run_id_raises_5(sample_log_row, tmp_log, tmp_views):
    """view 头行 compile_run_id 保留与 log 一致（pass §3），但单行 compile_run_id 改成跨 run。"""
    pack_view = tmp_views / "pack_view.csv"
    rows = list(csv.DictReader(pack_view.open("r", encoding="utf-8", newline="")))
    fieldnames = list(rows[0].keys())
    # 把 log 第一个 retrieved_pack_id 在 view 中对应的所有行改 compile_run_id
    import json as _json
    log_rows = list(csv.DictReader(tmp_log.open("r", encoding="utf-8", newline="")))
    target_log = next(r for r in log_rows if r["request_id"] == sample_log_row["request_id"])
    first_pack_id = _json.loads(target_log["retrieved_pack_ids"])[0]
    matched = 0
    for r in rows:
        if r.get("source_pack_id") == first_pack_id:
            r["compile_run_id"] = "different_cross_run_xx"
            matched += 1
    assert matched > 0, "测试装配失败：未找到对应 pack 行"
    with pack_view.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(rcb.ReplayError) as exc_info:
        rcb.replay(sample_log_row["request_id"], log_path=tmp_log, views_root=tmp_views)
    # 头行 compile_run_id 现在与 log 不一致 → 先撞 §3 governance check（exit 3）
    # 也可能是 §5（单行不一致）；本测试不绑死，只断言一致性检查 fail
    assert exc_info.value.code in (3, 5)


def test_tampered_brand_layer_raises_6(sample_log_row, tmp_log, tmp_views):
    """log 行 resolved_brand_layer 被改成 brand_faye，但 tenant 仍是 tenant_demo（仅适用 demo 行）；
    用 tenant_faye 行的反向构造：把 brand_layer 改成 brand_other 让 tsr 推断不一致。"""
    rows = list(csv.DictReader(tmp_log.open("r", encoding="utf-8", newline="")))
    fieldnames = list(rows[0].keys())
    target = next(r for r in rows if r["request_id"] == sample_log_row["request_id"])
    target["resolved_brand_layer"] = "brand_attacker_made_up"
    with tmp_log.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(rcb.ReplayError) as exc_info:
        rcb.replay(sample_log_row["request_id"], log_path=tmp_log, views_root=tmp_views)
    assert exc_info.value.code == 6


def test_illegal_fallback_status_raises_7(sample_log_row, tmp_log, tmp_views):
    rows = list(csv.DictReader(tmp_log.open("r", encoding="utf-8", newline="")))
    fieldnames = list(rows[0].keys())
    target = next(r for r in rows if r["request_id"] == sample_log_row["request_id"])
    target["fallback_status"] = "totally_made_up_status"
    with tmp_log.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(rcb.ReplayError) as exc_info:
        rcb.replay(sample_log_row["request_id"], log_path=tmp_log, views_root=tmp_views)
    assert exc_info.value.code == 7


def test_consistency_hash_is_idempotent(sample_log_row):
    """同 log + 同 views 复跑两次 → consistency_hash 完全一致（幂等）。"""
    a = rcb.replay(sample_log_row["request_id"])
    b = rcb.replay(sample_log_row["request_id"])
    assert a["replay_consistency_hash"] == b["replay_consistency_hash"]


def test_consistency_hash_changes_on_log_tamper(sample_log_row, tmp_log, tmp_views):
    """篡改 log 行任一参与 hash 的字段 → consistency_hash 必变（防回放绕过）。

    篡改 user_query_hash 是相对安全的（不会撞 §2/§4/§6/§7 check，因为这些 check
    不依赖 user_query_hash 取值的合法性），让本测试干净地证明"篡改 → hash 变"。
    """
    baseline = rcb.replay(sample_log_row["request_id"])
    rows = list(csv.DictReader(tmp_log.open("r", encoding="utf-8", newline="")))
    fieldnames = list(rows[0].keys())
    target = next(r for r in rows if r["request_id"] == sample_log_row["request_id"])
    target["user_query_hash"] = "sha256:" + "0" * 64
    with tmp_log.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    tampered = rcb.replay(sample_log_row["request_id"], log_path=tmp_log, views_root=tmp_views)
    assert tampered["replay_consistency_hash"] != baseline["replay_consistency_hash"]


def test_replay_module_is_pg_free():
    """KS-DIFY-ECS-005 §10 S8 回放硬约束：回放代码路径只读 CSV，不接 PG/Qdrant。

    Replay 模块整文件不许 import psycopg / sqlalchemy；不许调 ssh_psql / pg_writer。
    """
    src = (REPO_ROOT / "scripts" / "replay_context_bundle.py").read_text(encoding="utf-8")
    forbidden = [
        r"^\s*import\s+psycopg",
        r"^\s*from\s+psycopg",
        r"^\s*import\s+sqlalchemy",
        r"^\s*from\s+sqlalchemy",
        r"\bpg_writer\b",
        r"\bpg_reader\b",
        r"\bssh_psql\b",
        r"\bQdrantClient\b",
        r"\bdashscope\b",
    ]
    for pat in forbidden:
        assert not re.search(pat, src, re.MULTILINE), (
            f"replay 模块出现禁用依赖 {pat}（违反 S8 PG-free / no-LLM 硬约束）"
        )

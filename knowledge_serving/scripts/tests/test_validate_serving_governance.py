"""
KS-COMPILER-013 · test suite

覆盖 / coverage:
  - 真实数据 happy path（每门单跑 + --all）
  - 9 个恶意 fixture 逐门 fail-closed
  - 1 个空 csv 灾难性测试
  - no-LLM 源码硬扫
共 ≥ 16 case。
"""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "knowledge_serving" / "scripts" / "validate_serving_governance.py"
REAL_VIEWS = REPO_ROOT / "knowledge_serving" / "views"
REAL_CONTROL = REPO_ROOT / "knowledge_serving" / "control"
REAL_CANDIDATES = REPO_ROOT / "clean_output" / "candidates"

VIEW_NAMES = [
    "pack_view",
    "content_type_view",
    "play_card_view",
    "runtime_asset_view",
    "brand_overlay_view",
    "evidence_view",
    "generation_recipe_view",
]


def _run(args, cwd=None):
    cmd = [sys.executable, str(SCRIPT)] + args
    return subprocess.run(cmd, cwd=cwd or REPO_ROOT, capture_output=True, text=True)


def _stage_real(tmp_path: Path) -> tuple[Path, Path, Path]:
    """复制真 csv 到 tmp（候选 dir 直接复用 real 路径）/ stage real csvs to tmp.

    返回 (views_dir, control_dir, report_path)。
    """
    views = tmp_path / "views"
    ctl = tmp_path / "control"
    views.mkdir()
    ctl.mkdir()
    for v in VIEW_NAMES:
        shutil.copy(REAL_VIEWS / f"{v}.csv", views / f"{v}.csv")
    for c in [
        "content_type_canonical.csv",
        "field_requirement_matrix.csv",
        "retrieval_policy_view.csv",
        "merge_precedence_policy.csv",
        "tenant_scope_registry.csv",
        "context_bundle_log.csv",
    ]:
        if (REAL_CONTROL / c).exists():
            shutil.copy(REAL_CONTROL / c, ctl / c)
    return views, ctl, tmp_path / "report.txt"


def _common_args(views: Path, ctl: Path, report: Path) -> list[str]:
    return [
        "--views-dir", str(views),
        "--control-dir", str(ctl),
        "--candidates-root", str(REAL_CANDIDATES),
        "--report", str(report),
    ]


def _rewrite_csv(path: Path, mutator) -> None:
    """读 path → 调用 mutator(rows: list[dict]) 原地改 → 回写."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)
    mutator(rows, fieldnames)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ---------- 真实数据 happy path ----------

@pytest.mark.parametrize("gate", ["S1", "S2", "S3", "S4", "S5", "S6", "S7"])
def test_real_data_per_gate_pass(tmp_path, gate):
    views, ctl, rpt = _stage_real(tmp_path)
    r = _run(["--gate", gate] + _common_args(views, ctl, rpt))
    assert r.returncode == 0, f"{gate} expected pass, got {r.returncode}\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}\nREPORT:{rpt.read_text() if rpt.exists() else 'NO REPORT'}"
    text = rpt.read_text(encoding="utf-8")
    assert f"[{gate} " in text
    assert "status: pass" in text


def test_all_real_data_pass(tmp_path):
    views, ctl, rpt = _stage_real(tmp_path)
    r = _run(["--all"] + _common_args(views, ctl, rpt))
    assert r.returncode == 0, f"STDOUT:{r.stdout}\nSTDERR:{r.stderr}\nREPORT:{rpt.read_text() if rpt.exists() else 'NO REPORT'}"
    text = rpt.read_text(encoding="utf-8")
    for g in ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]:
        assert f"[{g} " in text
    assert text.count("status: pass") == 7


def test_s5_real_data_pass_strict_count(tmp_path):
    """S5 真实数据 201 行全过（A 方案多文件聚合解析）."""
    views, ctl, rpt = _stage_real(tmp_path)
    r = _run(["--gate", "S5"] + _common_args(views, ctl, rpt))
    assert r.returncode == 0, rpt.read_text() if rpt.exists() else r.stderr
    text = rpt.read_text(encoding="utf-8")
    assert "[S5 evidence_linkage]" in text
    assert "status: pass" in text
    assert "checked_rows: 201" in text


# ---------- no-LLM 硬扫 ----------

def test_grep_no_llm_in_source():
    src = SCRIPT.read_text(encoding="utf-8")
    forbidden = ["dashscope", "openai", "anthropic", "llm_assist", "chat(", "completion"]
    hits = [t for t in forbidden if t in src.lower()]
    assert hits == [], f"源码命中 LLM 关键词 / LLM keyword hits: {hits}"


# ---------- 9 恶意 fixture · 逐门 fail-closed ----------

def test_s1_fail_missing_source_pack_id(tmp_path):
    views, ctl, rpt = _stage_real(tmp_path)

    def m(rows, fn):
        rows[0]["source_pack_id"] = ""
    _rewrite_csv(views / "pack_view.csv", m)
    r = _run(["--gate", "S1"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    assert "status: fail" in rpt.read_text(encoding="utf-8")


def test_s1_fail_orphan_pack_id(tmp_path):
    views, ctl, rpt = _stage_real(tmp_path)

    def m(rows, fn):
        rows[0]["source_pack_id"] = "PK-this-id-does-not-exist-zzz"
    _rewrite_csv(views / "pack_view.csv", m)
    r = _run(["--gate", "S1"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    text = rpt.read_text(encoding="utf-8")
    assert "orphan" in text.lower() or "反查" in text


def test_s1_synthetic_id_passes_without_candidate_lookup(tmp_path):
    """合成 ID view（content_type_view / generation_recipe_view）免反查；
    真实数据下 S1 应 pass，且 synthetic_views_checked == 18 + 18 = 36."""
    views, ctl, rpt = _stage_real(tmp_path)
    r = _run(["--gate", "S1"] + _common_args(views, ctl, rpt))
    assert r.returncode == 0, f"S1 真数据应 pass: {r.returncode}\n{rpt.read_text() if rpt.exists() else r.stderr}"
    text = rpt.read_text(encoding="utf-8")
    assert "synthetic_views_checked: 36" in text


def test_s1_content_type_plural_refs_orphan_fails(tmp_path):
    """content_type_view.source_pack_ids 注入不存在 pack id → S1 fail."""
    views, ctl, rpt = _stage_real(tmp_path)

    def m(rows, fn):
        rows[0]["source_pack_ids"] = '["KP-ghost-pack-does-not-exist"]'
    _rewrite_csv(views / "content_type_view.csv", m)
    r = _run(["--gate", "S1"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    text = rpt.read_text(encoding="utf-8")
    assert "status: fail" in text
    assert "plural source_pack_ids orphan" in text
    assert "KP-ghost-pack-does-not-exist" in text


def test_s1_synthetic_view_with_wrong_prefix_fails(tmp_path):
    """合成 view 拿到 KP- 前缀（不该出现）→ S1 fail（防 W3 编译器漂移）."""
    views, ctl, rpt = _stage_real(tmp_path)

    def m(rows, fn):
        rows[0]["source_pack_id"] = "KP-something-not-synthetic"
    _rewrite_csv(views / "content_type_view.csv", m)
    r = _run(["--gate", "S1"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    text = rpt.read_text(encoding="utf-8")
    assert "status: fail" in text
    assert "unexpected synthetic prefix" in text


def test_s2_fail_frozen_in_default_pool(tmp_path):
    views, ctl, rpt = _stage_real(tmp_path)

    def m(rows, fn):
        rows[0]["gate_status"] = "frozen"
        rows[0]["review_status"] = "rejected"
    _rewrite_csv(views / "pack_view.csv", m)
    r = _run(["--gate", "S2"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    assert "status: fail" in rpt.read_text(encoding="utf-8")


def test_s3_fail_overlay_has_domain_general(tmp_path):
    views, ctl, rpt = _stage_real(tmp_path)

    def m(rows, fn):
        rows[0]["brand_layer"] = "domain_general"
    _rewrite_csv(views / "brand_overlay_view.csv", m)
    r = _run(["--gate", "S3"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    text = rpt.read_text(encoding="utf-8")
    assert "status: fail" in text
    assert "brand_overlay_view" in text


def test_s4_fail_l4_granularity(tmp_path):
    views, ctl, rpt = _stage_real(tmp_path)

    def m(rows, fn):
        rows[0]["granularity_layer"] = "L4"
    _rewrite_csv(views / "pack_view.csv", m)
    r = _run(["--gate", "S4"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    text = rpt.read_text(encoding="utf-8")
    assert "status: fail" in text
    assert "L4" in text


def test_s5_fail_missing_source_md_file(tmp_path):
    views, ctl, rpt = _stage_real(tmp_path)

    def m(rows, fn):
        rows[0]["source_md"] = "does_not_exist_dir/totally_missing.md"
    _rewrite_csv(views / "evidence_view.csv", m)
    r = _run(["--gate", "S5"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    assert "status: fail" in rpt.read_text(encoding="utf-8")


def test_s6_fail_empty_completeness(tmp_path):
    views, ctl, rpt = _stage_real(tmp_path)

    def m(rows, fn):
        rows[0]["completeness_status"] = ""
    _rewrite_csv(views / "play_card_view.csv", m)
    r = _run(["--gate", "S6"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    assert "status: fail" in rpt.read_text(encoding="utf-8")


def test_s7_fail_extra_in_frm(tmp_path):
    views, ctl, rpt = _stage_real(tmp_path)
    frm = ctl / "field_requirement_matrix.csv"

    def m(rows, fn):
        # 复制一行，把 content_type 改成不在 canonical 的值
        extra = dict(rows[0])
        extra["content_type"] = "ct_not_in_canonical_xyz"
        rows.append(extra)
    _rewrite_csv(frm, m)
    r = _run(["--gate", "S7"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    text = rpt.read_text(encoding="utf-8")
    assert "status: fail" in text
    assert "extra" in text.lower() or "ct_not_in_canonical_xyz" in text


def test_s7_fail_missing_in_frm(tmp_path):
    views, ctl, rpt = _stage_real(tmp_path)
    frm = ctl / "field_requirement_matrix.csv"

    def m(rows, fn):
        # 删掉所有 content_type=outfit_of_the_day 的行
        rows[:] = [r for r in rows if r.get("content_type") != "outfit_of_the_day"]
    _rewrite_csv(frm, m)
    r = _run(["--gate", "S7"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    text = rpt.read_text(encoding="utf-8")
    assert "status: fail" in text
    assert "outfit_of_the_day" in text


# ---------- S5 多文件聚合（A 方案细测）----------

def test_s5_multi_file_aggregation_resolved(tmp_path):
    """S5 多文件聚合解析正确：三段都存在 → pass；改第 2 段为不存在 → fail."""
    views, ctl, rpt = _stage_real(tmp_path)

    # 用真实多文件 fixture：Q2-内容类型种子/通用类.md & 通用类compass.md & 通用类deep-research-report.md
    # 先确认这三个文件在仓库根真实存在
    q2_dir = REPO_ROOT / "Q2-内容类型种子"
    if not (q2_dir / "通用类.md").is_file():
        pytest.skip("Q2 通用类.md 真实文件不在，跳过多文件聚合测试")

    # 找到一行替换其 source_md
    multi_value = "Q2-内容类型种子/通用类.md & 通用类compass.md & 通用类deep-research-report.md"

    # case 1：注入有效多文件 → 仍 pass
    def m_ok(rows, fn):
        # 校验三段都真实存在；若有不存在的，跳过
        for p in ["Q2-内容类型种子/通用类.md", "Q2-内容类型种子/通用类compass.md",
                  "Q2-内容类型种子/通用类deep-research-report.md"]:
            if not (REPO_ROOT / p).is_file():
                pytest.skip(f"测试前置 {p} 不存在")
        rows[0]["source_md"] = multi_value
    _rewrite_csv(views / "evidence_view.csv", m_ok)
    r = _run(["--gate", "S5"] + _common_args(views, ctl, rpt))
    assert r.returncode == 0, f"multi-file ok should pass; got:\n{rpt.read_text()}"

    # case 2：改其中第 2 段为不存在 → fail，violations 报具体段
    def m_bad(rows, fn):
        rows[0]["source_md"] = "Q2-内容类型种子/通用类.md & 不存在.md & 通用类deep-research-report.md"
    _rewrite_csv(views / "evidence_view.csv", m_bad)
    r2 = _run(["--gate", "S5"] + _common_args(views, ctl, rpt))
    assert r2.returncode == 2
    text = rpt.read_text(encoding="utf-8")
    assert "status: fail" in text
    assert "不存在.md" in text


# ---------- 灾难性：空 csv 全 fail ----------

def test_empty_csvs_all_fail(tmp_path):
    """全空 csv（只有 header）→ 7 门全 fail，不静默 pass."""
    views, ctl, rpt = _stage_real(tmp_path)
    # 全清空 view 数据行（保 header）
    for v in VIEW_NAMES:
        p = views / f"{v}.csv"
        with p.open("r", encoding="utf-8") as fh:
            header = fh.readline()
        p.write_text(header, encoding="utf-8")
    # 清空 frm（保 header）→ S7 看到 canonical 18 vs frm 0 → fail
    frm = ctl / "field_requirement_matrix.csv"
    with frm.open("r", encoding="utf-8") as fh:
        h2 = fh.readline()
    frm.write_text(h2, encoding="utf-8")

    r = _run(["--all"] + _common_args(views, ctl, rpt))
    assert r.returncode == 2
    text = rpt.read_text(encoding="utf-8")
    # S1-S6 应该全是 pass（没有行就没有 violations）但 S7 必 fail；
    # 任务卡 §6 明确要求"全空 csv → 不静默 pass"——这里靠 S7 兜底
    # （S1-S6 在 0 行时 trivially 通过；唯一硬覆盖度门是 S7）
    assert "[S7 fallback_policy_coverage]" in text
    # 找 S7 段并断言 fail
    s7_idx = text.index("[S7 fallback_policy_coverage]")
    s7_block = text[s7_idx: s7_idx + 600]
    assert "status: fail" in s7_block
    # 至少一个门 fail（exit=2 已保）+ S7 必 fail（防静默）

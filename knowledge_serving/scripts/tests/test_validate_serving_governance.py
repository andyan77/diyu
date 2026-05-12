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
    # 8 pass: preflight schema_validation + S1-S7
    assert "[preflight schema_validation]" in text
    assert text.count("status: pass") == 8


def test_s5_real_data_pass_strict_count(tmp_path):
    """S5 真实数据 201 行全过（A 方案多文件聚合解析）."""
    views, ctl, rpt = _stage_real(tmp_path)
    r = _run(["--gate", "S5"] + _common_args(views, ctl, rpt))
    assert r.returncode == 0, rpt.read_text() if rpt.exists() else r.stderr
    text = rpt.read_text(encoding="utf-8")
    assert "[S5 evidence_linkage]" in text
    assert "status: pass" in text
    assert "checked_rows: 201" in text


# ---------- post-audit follow-up: report header compile_run_id 必须 == view 行 ----------

def test_report_header_compile_run_id_matches_view_rows(tmp_path):
    """post-audit follow-up: report 头部 compile_run_id 必须是 derive_compile_run_id
    (manifest_hash, view_schema_version) 的结果，而不是 manifest_hash[:16]。

    历史 bug: validator main() 之前写 `compile_run_id = mh[:16]`，导致 report 头
    与 view 行里的 compile_run_id 不一致，运行证据报告误导审查员。
    """
    import csv as _csv
    views, ctl, rpt = _stage_real(tmp_path)
    r = _run(["--all"] + _common_args(views, ctl, rpt))
    assert r.returncode == 0, r.stderr
    text = rpt.read_text(encoding="utf-8")

    # 解 header compile_run_id
    header_line = [ln for ln in text.splitlines() if ln.startswith("compile_run_id:")][0]
    header_crid = header_line.split(":", 1)[1].strip()

    # view 行的 compile_run_id（7 view 应全部一致）
    view_crids = set()
    for v in VIEW_NAMES:
        rows = list(_csv.DictReader(open(views / f"{v}.csv", encoding="utf-8")))
        if rows:
            view_crids.add(rows[0]["compile_run_id"])
    assert len(view_crids) == 1, f"7 view 的 compile_run_id 不一致: {view_crids}"
    view_crid = next(iter(view_crids))

    assert header_crid == view_crid, (
        f"report 头 compile_run_id ({header_crid!r}) 必须等于 view 行的 "
        f"compile_run_id ({view_crid!r})；前者疑似仍用 manifest_hash[:16]"
    )
    # 反向防御：header 不应等于 manifest_hash 前缀（防止退回旧 bug）
    from pathlib import Path
    import sys
    sys.path.insert(0, str(REPO_ROOT / "knowledge_serving" / "scripts"))
    from _common import load_manifest_hash  # type: ignore
    mh = load_manifest_hash(REPO_ROOT / "clean_output" / "audit" / "source_manifest.json")
    assert header_crid != mh[:16], (
        f"report 头退回到 manifest_hash[:16] 反模式，应走 derive_compile_run_id"
    )


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


# ---------- S5 锚点真源修复（post-audit finding #5） ----------

def test_s5_anchor_under_clean_output_root_201_hits(tmp_path):
    """post-audit #5: 真源补录后，S5 锚点必须是 REPO_ROOT/clean_output；
    真实 evidence_view 201 行必须在 clean_output 锚点下 .is_file() 全 True。

    红线: 不允许漂移到 REPO_ROOT（那是 'drift normalization' 反模式）。
    """
    import csv as _csv
    rows = list(_csv.DictReader(open(REAL_VIEWS / "evidence_view.csv", encoding="utf-8")))
    assert len(rows) == 201, f"前置：真 evidence_view 必须 201 行，实测 {len(rows)}"

    views, ctl, rpt = _stage_real(tmp_path)
    r = _run(["--gate", "S5"] + _common_args(views, ctl, rpt))
    assert r.returncode == 0, (
        f"S5 在 clean_output 锚点下必须 201/201 pass；"
        f"若 fail 说明 ingest 未完成 / 锚点未迁移。\nreport:\n{rpt.read_text()}"
    )
    text = rpt.read_text(encoding="utf-8")
    assert "[S5 evidence_linkage]" in text
    assert "status: pass" in text
    assert "checked_rows: 201" in text

    # 二次断言：源码层确认 S5 锚点指向 clean_output，不允许 REPO_ROOT 直锚
    src = SCRIPT.read_text(encoding="utf-8")
    s5_block = src[src.index("def check_s5_evidence_linkage"): src.index("def check_s6")]
    assert 'REPO_ROOT / "clean_output"' in s5_block or "REPO_ROOT/'clean_output'" in s5_block, (
        "S5 必须显式锚定 REPO_ROOT/clean_output；"
        "禁止 'REPO_ROOT / p' 直锚（drift normalization 反模式）"
    )


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
    # 任务卡 §6 + completion_audit finding #2 硬要求：空输入下 S1-S6 不允许静默 pass。
    # 每门必须有最小行数 / 输入完整性检查；全空时 7 门全 fail。
    for gate in ("S1 source_traceability", "S2 gate_filter", "S3 brand_layer_scope",
                 "S4 granularity_integrity", "S5 evidence_linkage",
                 "S6 play_card_completeness", "S7 fallback_policy_coverage"):
        idx = text.index(f"[{gate}]")
        block = text[idx: idx + 600]
        assert "status: fail" in block, f"{gate} 必须 fail（空输入禁止静默 pass）"


# ---------- completion_audit findings #1 / #3 ----------

def test_preflight_schema_catches_missing_required_column(tmp_path):
    """finding #1: 删除 pack_view 的 pack_id 必填列后，--all 必须 exit 非 0 + preflight fail。"""
    views, ctl, rpt = _stage_real(tmp_path)
    src = views / "pack_view.csv"
    with src.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        original_cols = list(reader.fieldnames or [])
    assert "pack_id" in original_cols, "前置：真数据 pack_view 必须含 pack_id 列"
    mutated_cols = [c for c in original_cols if c != "pack_id"]
    with src.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=mutated_cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in mutated_cols})
    r = _run(["--all"] + _common_args(views, ctl, rpt))
    assert r.returncode != 0, "schema 缺必填列必须 fail-closed，不允许 exit 0"
    text = rpt.read_text(encoding="utf-8")
    assert "[preflight schema_validation]" in text, "report 必须含 preflight schema_validation 段"
    idx = text.index("[preflight schema_validation]")
    block = text[idx: idx + 1200]
    assert "status: fail" in block
    assert "pack_id" in block, "preflight 必须报缺 pack_id"


def test_s1_governance_id_tamper_fails(tmp_path):
    """finding #3: 篡改某行 compile_run_id / source_manifest_hash / view_schema_version → S1 fail。"""
    views, ctl, rpt = _stage_real(tmp_path)
    src = views / "pack_view.csv"

    def mutate(rows, fieldnames):
        if rows:
            rows[0]["compile_run_id"] = "BAD_HASH_TAMPER"
            rows[0]["source_manifest_hash"] = "BAD_MANIFEST_TAMPER"
            rows[0]["view_schema_version"] = "BAD_VER_TAMPER"

    _rewrite_csv(src, mutate)
    r = _run(["--gate", "S1"] + _common_args(views, ctl, rpt))
    assert r.returncode != 0, "篡改 governance ID 必须 fail-closed"
    text = rpt.read_text(encoding="utf-8")
    idx = text.index("[S1 source_traceability]")
    block = text[idx: idx + 2000]
    assert "status: fail" in block
    # 至少一种 ID 失配 violation
    assert any(kw in block for kw in (
        "compile_run_id mismatch", "source_manifest_hash mismatch",
        "view_schema_version mismatch", "governance ID mismatch"
    )), f"S1 violations 必须含 governance ID 失配描述，实际:\n{block}"


# ---------- completion_audit finding #4 (frm 源头硬校验) ----------

def test_compile_frm_rejects_non_canonical_content_type(tmp_path):
    """finding #4: compile_field_requirement_matrix 拒绝任何 content_type ∉ canonical 18 类。

    历史漂移 brand_manifesto 进 frm 的反模式必须在编译器源头 fail-closed，
    不能只靠 W5 S7 后置兜底。
    """
    import importlib.util
    frm_script = REPO_ROOT / "knowledge_serving" / "scripts" / "compile_field_requirement_matrix.py"
    if str(frm_script.parent) not in sys.path:
        sys.path.insert(0, str(frm_script.parent))
    spec = importlib.util.spec_from_file_location("compile_field_requirement_matrix", frm_script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    bad_rule = {
        "content_type": "brand_manifesto",
        "field_key": "brand_values",
        "required_level": "hard",
        "fallback_action": "block_brand_output",
        "ask_user_question": "",
        "block_reason": "should be rejected at compiler source",
    }
    custom_rules = list(mod.DEFAULT_RULES) + [bad_rule]
    with pytest.raises(mod.CompileError) as exc:
        mod.compile_field_requirement_matrix(
            rules=custom_rules,
            output_csv=tmp_path / "x.csv",
            log_path=tmp_path / "x.log",
        )
    msg = str(exc.value)
    assert "brand_manifesto" in msg
    assert any(kw in msg for kw in ("canonical", "not registered", "未注册"))

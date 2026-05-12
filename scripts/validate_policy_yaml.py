#!/usr/bin/env python3
"""
validate_policy_yaml.py · KS-POLICY-001 / 通用 policy yaml 校验器

用法 / usage:
    python3 scripts/validate_policy_yaml.py fallback_policy
    python3 scripts/validate_policy_yaml.py guardrail_policy
    python3 scripts/validate_policy_yaml.py guardrail_policy --policy-path /tmp/x.yaml  # 测试可注入

支持的 policy / supported:
    - fallback_policy   →  knowledge_serving/policies/fallback_policy.yaml
    - guardrail_policy  →  knowledge_serving/policies/guardrail_policy.yaml（KS-POLICY-002 · S11）

校验项 / checks（fallback_policy）:
    F1a yaml 语法合法 / parsable
    F1b yamllint 通过（项目 .yamllint 配置）/ yamllint clean
    F2  五状态齐全（exact set）/ five canonical states present
    F3  状态名无重复 / no duplicate state names
    F4  阻断状态必带 block_reason / blocking states must declare block_reason
    F5  触发条件不含 LLM 关键词（结构化关键字扫描，覆盖 trigger / evaluation_pipeline）
    F6  与 field_requirement_matrix.csv 字段对齐声明存在
    F7  evaluation_pipeline 与五状态枚举闭合

退出码 / exit code: 0 全绿 / 1 fail / 2 输入错误。
"""
from __future__ import annotations
import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("需要 PyYAML / requires PyYAML: pip install pyyaml\n")
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent

POLICY_REGISTRY = {
    "fallback_policy": ROOT / "knowledge_serving" / "policies" / "fallback_policy.yaml",
    "guardrail_policy": ROOT / "knowledge_serving" / "policies" / "guardrail_policy.yaml",
}

CONTROL_DIR = ROOT / "knowledge_serving" / "control"
SCHEMA_DIR = ROOT / "knowledge_serving" / "schema"
FIELD_MATRIX_CSV = CONTROL_DIR / "field_requirement_matrix.csv"
CONTENT_TYPE_CANONICAL_CSV = CONTROL_DIR / "content_type_canonical.csv"
BUSINESS_BRIEF_SCHEMA = SCHEMA_DIR / "business_brief.schema.json"

REQUIRED_FORBIDDEN_CATEGORIES = {"founder_identity", "product_fact", "inventory_fact"}
ALLOWED_SEVERITIES = {"hard_block", "soft_warning"}

CANONICAL_STATES_FALLBACK = [
    "brand_full_applied",
    "brand_partial_fallback",
    "domain_only",
    "blocked_missing_required_brand_fields",
    "blocked_missing_business_brief",
]

# 触发条件禁用关键词（大小写不敏感）/ forbidden keywords in trigger fields
LLM_FORBIDDEN_KEYWORDS = [
    "llm",
    "gpt",
    "claude",
    "anthropic",
    "openai",
    "prompt_infer",
    "model_judge",
    "llm_judge",
    "predicted_intent",
    "model_predict",
    "ask_llm",
]


def collect_strings(node) -> list[str]:
    """递归收集所有字符串值 / recursively collect string values from a yaml subtree."""
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            out.append(str(k))
            out.extend(collect_strings(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(collect_strings(v))
    elif node is not None:
        out.append(str(node))
    return out


def validate_fallback(p: dict) -> list[str]:
    errors: list[str] = []

    # F2 五状态齐全
    states = p.get("states") or []
    if not isinstance(states, list):
        errors.append("F2 states 必须为 list / must be list")
        return errors
    names = [s.get("name") for s in states if isinstance(s, dict)]
    missing = set(CANONICAL_STATES_FALLBACK) - set(names)
    extra = set(names) - set(CANONICAL_STATES_FALLBACK)
    if missing:
        errors.append(f"F2 缺以下状态 / missing states: {sorted(missing)}")
    if extra:
        errors.append(f"F2 出现非法状态 / unexpected states: {sorted(extra)}")

    # F3 无重复
    dups = [n for n in names if names.count(n) > 1]
    if dups:
        errors.append(f"F3 重复状态名 / duplicate state names: {sorted(set(dups))}")

    # F4 阻断状态必带 block_reason
    for s in states:
        if not isinstance(s, dict):
            continue
        if s.get("is_blocking") is True:
            if not s.get("block_reason"):
                errors.append(
                    f"F4 状态 {s.get('name')!r} is_blocking=true 但缺 block_reason"
                )

    # F5 trigger / evaluation_pipeline LLM 关键词扫描
    scan_nodes = []
    for s in states:
        if isinstance(s, dict) and s.get("trigger"):
            scan_nodes.append((f"states[{s.get('name')}].trigger", s["trigger"]))
    if p.get("evaluation_pipeline"):
        scan_nodes.append(("evaluation_pipeline", p["evaluation_pipeline"]))

    for label, node in scan_nodes:
        joined = " ".join(collect_strings(node)).lower()
        hits = [kw for kw in LLM_FORBIDDEN_KEYWORDS if kw in joined]
        if hits:
            errors.append(
                f"F5 {label} 含 LLM 介入关键词 / forbidden LLM keywords: {hits}"
            )

    # F6 matrix_alignment 声明
    ma = p.get("matrix_alignment") or {}
    required_ma_keys = [
        "source",
        "hard_missing_to_state",
        "soft_missing_to_state",
        "overlay_miss_to_state",
        "brief_missing_to_state",
    ]
    for k in required_ma_keys:
        if not ma.get(k):
            errors.append(f"F6 matrix_alignment.{k} 缺失 / missing")
    if ma.get("source"):
        src = ROOT / ma["source"]
        if not src.exists():
            errors.append(f"F6 matrix_alignment.source 不存在 / not found: {ma['source']}")

    # F7 evaluation_pipeline 引用的 state 必须在枚举内
    pipe = p.get("evaluation_pipeline") or []
    for step in pipe:
        if not isinstance(step, dict):
            continue
        for key in ("on_missing", "on_false", "on_partial_missing", "on_complete"):
            tgt = step.get(key)
            if tgt and tgt not in CANONICAL_STATES_FALLBACK:
                errors.append(
                    f"F7 evaluation_pipeline.{key}={tgt!r} 不在五状态枚举内"
                )

    # 反 LLM 硬开关
    if p.get("no_llm_in_decision") is not True:
        errors.append("F5 no_llm_in_decision 必须显式为 true")

    return errors


def _load_matrix_hard_rows() -> dict[str, set[str]]:
    """读 field_requirement_matrix.csv，返回 {content_type: {hard_field, ...}}。"""
    out: dict[str, set[str]] = {}
    with FIELD_MATRIX_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("required_level") == "hard":
                out.setdefault(row["content_type"], set()).add(row["field_key"])
    return out


def _load_canonical_content_types() -> set[str]:
    with CONTENT_TYPE_CANONICAL_CSV.open(encoding="utf-8") as f:
        return {row["canonical_content_type_id"] for row in csv.DictReader(f)}


def _load_business_brief_schema() -> tuple[set[str], set[str]]:
    """返回 (hard_required, soft_required) 集合。"""
    schema = json.loads(BUSINESS_BRIEF_SCHEMA.read_text(encoding="utf-8"))
    hard = set(schema.get("required") or [])
    soft = set(schema.get("x-soft-required") or [])
    return hard, soft


def validate_guardrail(p: dict) -> list[str]:
    """KS-POLICY-002 · S11 guardrail policy 校验 / G1-G9。"""
    errors: list[str] = []

    # G1 policy_version 非空
    if not p.get("policy_version"):
        errors.append("G1 policy_version 缺失 / missing")

    # G2 + G3 + G4 forbidden_patterns 三类齐 + 字段齐 + 唯一 id
    fps = p.get("forbidden_patterns") or []
    if not isinstance(fps, list) or len(fps) == 0:
        errors.append("G2 forbidden_patterns 为空 / empty（plan §A3 需三类至少各 1 条）")
    else:
        cats = set()
        ids = []
        for i, fp in enumerate(fps):
            if not isinstance(fp, dict):
                errors.append(f"G3 forbidden_patterns[{i}] 非 mapping")
                continue
            for k in ("id", "category", "pattern_kind", "patterns", "block_reason", "severity"):
                if k not in fp or fp[k] in (None, "", []):
                    errors.append(f"G3 forbidden_patterns[{i}].{k} 缺失或空 / missing or empty")
            sev = fp.get("severity")
            if sev and sev not in ALLOWED_SEVERITIES:
                errors.append(f"G3 forbidden_patterns[{i}].severity={sev!r} 非法 / not in {sorted(ALLOWED_SEVERITIES)}")
            pk = fp.get("pattern_kind")
            if pk and pk not in {"keyword", "regex"}:
                errors.append(f"G3 forbidden_patterns[{i}].pattern_kind={pk!r} 非法 / must be keyword|regex")
            pats = fp.get("patterns")
            if isinstance(pats, list) and any((p_ is None or p_ == "") for p_ in pats):
                errors.append(f"G3 forbidden_patterns[{i}].patterns 含空项 / contains empty entry")
            if fp.get("category"):
                cats.add(fp["category"])
            if fp.get("id"):
                ids.append(fp["id"])
        missing_cats = REQUIRED_FORBIDDEN_CATEGORIES - cats
        if missing_cats:
            errors.append(
                f"G2 forbidden_patterns 缺类目 / missing categories: {sorted(missing_cats)}（plan §A3 三类必齐）"
            )
        dups = sorted({i for i in ids if ids.count(i) > 1})
        if dups:
            errors.append(f"G4 forbidden_patterns 重复 id / duplicate ids: {dups}")

    # G5 + G6 required_evidence 双向闭环 + canonical 18 范围
    re_ = p.get("required_evidence") or {}
    if not isinstance(re_, dict):
        errors.append("G5 required_evidence 必须为 mapping")
    else:
        matrix = _load_matrix_hard_rows()
        canonical = _load_canonical_content_types()

        # 6 canonical 范围
        non_canonical = sorted(set(re_) - canonical)
        if non_canonical:
            errors.append(f"G6 required_evidence 含非 canonical content_type: {non_canonical}")

        # 5 双向闭环（仅在 canonical 内比较，避免重复报错）
        yaml_keys = set(re_) & canonical
        matrix_keys = set(matrix)
        only_in_matrix = sorted(matrix_keys - yaml_keys)
        only_in_yaml = sorted(yaml_keys - matrix_keys)
        if only_in_matrix:
            errors.append(
                f"G5 required_evidence 漏 matrix hard 行 / missing in yaml: {only_in_matrix}"
            )
        if only_in_yaml:
            errors.append(
                f"G5 required_evidence 多 matrix 没有的 content_type / extra in yaml: {only_in_yaml}"
            )

        # 5 字段集严格相等
        for ct in sorted(yaml_keys & matrix_keys):
            yaml_fields = set((re_[ct] or {}).get("hard_fields") or [])
            mfields = matrix[ct]
            if yaml_fields != mfields:
                errors.append(
                    f"G5 required_evidence[{ct}].hard_fields 与 matrix 不一致: "
                    f"yaml={sorted(yaml_fields)} matrix={sorted(mfields)}"
                )

    # G7 + G8 business_brief_required 与 schema 闭环
    bb = p.get("business_brief_required") or {}
    if not isinstance(bb, dict):
        errors.append("G7 business_brief_required 必须为 mapping")
    else:
        schema_hard, schema_soft = _load_business_brief_schema()
        yaml_hard = set(bb.get("hard_fields") or [])
        yaml_soft = set(bb.get("soft_fields_warning_only") or [])
        if yaml_hard != schema_hard:
            errors.append(
                f"G7 business_brief_required.hard_fields 与 schema required[] 不等: "
                f"yaml={sorted(yaml_hard)} schema={sorted(schema_hard)}"
            )
        if yaml_soft != schema_soft:
            extra_as_hard = yaml_hard & schema_soft
            if extra_as_hard:
                errors.append(
                    f"G8 把 schema soft 字段当 hard / soft fields treated as hard: {sorted(extra_as_hard)}"
                )
            else:
                errors.append(
                    f"G8 business_brief_required.soft_fields_warning_only 与 schema x-soft-required[] 不等: "
                    f"yaml={sorted(yaml_soft)} schema={sorted(schema_soft)}"
                )
        if not bb.get("block_reason"):
            errors.append("G7 business_brief_required.block_reason 缺失 / missing")

    # G9 LLM 介入结构字段扫描：禁止 yaml 出现 llm_assist: / model: / use_llm: 等结构 key。
    # 注意：block_reason 文本里出现 "禁止 LLM 编造..." 是允许的（值层面的描述性禁令）。
    forbidden_structural_keys = {"llm_assist", "use_llm", "model", "gpt", "openai", "anthropic", "claude"}
    structural_keys_present: set[str] = set()

    def _collect_keys(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(k, str) and k.lower() in forbidden_structural_keys:
                    structural_keys_present.add(k.lower())
                _collect_keys(v)
        elif isinstance(node, list):
            for v in node:
                _collect_keys(v)

    _collect_keys(p)
    if structural_keys_present:
        errors.append(
            f"G9 yaml 含 LLM 介入结构字段 / forbidden LLM keys present: {sorted(structural_keys_present)}"
        )

    return errors


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="validate_policy_yaml.py")
    ap.add_argument("policy_name", nargs="?", help=f"one of {sorted(POLICY_REGISTRY)}")
    ap.add_argument("--policy-path", type=Path, default=None,
                    help="覆盖默认 yaml 路径 / override default path（测试用）")
    args = ap.parse_args(argv[1:])

    name = args.policy_name
    if not name:
        sys.stderr.write("usage: validate_policy_yaml.py <policy_name> [--policy-path PATH]\n")
        sys.stderr.write(f"  available: {sorted(POLICY_REGISTRY)}\n")
        return 2

    if name not in POLICY_REGISTRY:
        sys.stderr.write(f"未知 policy / unknown: {name}\n")
        sys.stderr.write(f"  available: {sorted(POLICY_REGISTRY)}\n")
        return 2

    path = args.policy_path or POLICY_REGISTRY[name]
    if not path.exists():
        print(f"❌ 缺失 / missing: {path}")
        return 1

    try:
        with path.open(encoding="utf-8") as f:
            p = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"❌ F1a yaml 语法错 / parse error: {e}")
        return 1

    if not isinstance(p, dict):
        print(f"❌ F1a 顶层必须为 mapping / top-level must be a mapping")
        return 1

    # F1b yamllint 检查（仅 fallback_policy 强制；guardrail 暂走 G* 校验，可后续接入）
    if name == "fallback_policy":
        yamllint_bin = shutil.which("yamllint")
        if yamllint_bin is None:
            print("❌ F1b yamllint 不在 PATH / yamllint not installed (pip install yamllint)")
            return 1
        cmd = [yamllint_bin]
        yamllint_cfg = ROOT / ".yamllint"
        if yamllint_cfg.exists():
            cmd += ["-c", str(yamllint_cfg)]
        cmd += [str(path)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("❌ F1b yamllint 失败 / yamllint failed:")
            for line in (r.stdout + r.stderr).splitlines():
                print(f"   {line}")
            return 1

    if name == "fallback_policy":
        errors = validate_fallback(p)
    elif name == "guardrail_policy":
        errors = validate_guardrail(p)
    else:
        print(f"❌ {name} 未实现校验逻辑 / no validator implemented")
        return 2

    try:
        shown = path.relative_to(ROOT)
    except ValueError:
        shown = path  # 测试时 tmp 路径不在 repo 内 / tmp path during tests
    print(f"已校验 / checked: {shown}")
    if errors:
        print(f"\n❌ errors ({len(errors)}):")
        for e in errors:
            print(f"   - {e}")
        return 1

    label = "F1a/F1b/F2-F7" if name == "fallback_policy" else "G1-G9"
    print(f"\n✅ {name} {label} 全绿 / all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

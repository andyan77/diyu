"""KS-RETRIEVAL-005 · structured_retrieval / 结构化召回（§6.7 第 7 步）.

W6 波次实现。**前置门禁 / pre-gate**：KS-COMPILER-013 治理总闸 S1-S7 全 pass。
本模块是 13 步召回流程的第 7 步：从 4 个 view (pack / content_type / play_card /
runtime_asset) 按租户允许 brand_layer + retrieval_policy_view 的 (intent, content_type)
策略筛出结构化候选集合。

硬纪律：
- 不读 user_query / tenant_id（由上游 KS-RETRIEVAL-001/002/003 解析后入参）
- 不调 LLM
- 不写 clean_output
- governance 与 policy 冲突时 governance 胜出
"""
from __future__ import annotations

import csv
import json
import re
import warnings
from pathlib import Path
from typing import Iterable

__all__ = [
    "structured_retrieve",
    "RetrievalPolicyNotFound",
    "RetrievalPolicyAmbiguous",
    "_assert_governance_report_green",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VIEWS_ROOT = REPO_ROOT / "knowledge_serving" / "views"
DEFAULT_POLICY_PATH = REPO_ROOT / "knowledge_serving" / "control" / "retrieval_policy_view.csv"
DEFAULT_REPORT_PATH = REPO_ROOT / "knowledge_serving" / "audit" / "validate_serving_governance.report"

TARGET_VIEWS = ("pack_view", "content_type_view", "play_card_view", "runtime_asset_view")
ALLOWED_GRANULARITY = frozenset({"L1", "L2", "L3"})
REQUIRED_GATES = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")
MAX_ITEMS_HARD_CAP = 1000

_BRAND_LAYER_RE = re.compile(r"^(domain_general|brand_[a-z0-9_]+)$")


class RetrievalPolicyNotFound(LookupError):
    """(intent, content_type) 在 retrieval_policy_view 0 命中。"""


class RetrievalPolicyAmbiguous(LookupError):
    """(intent, content_type) 在 retrieval_policy_view >1 命中。"""


# ---------- preflight: KS-COMPILER-013 governance report ----------

_GATE_HEADER_RE = re.compile(r"^\[(S\d+)\s")


def _parse_gate_sections(text: str) -> dict[str, str]:
    """解析报告 sections：返回 {"S1": "pass", ...}.

    报告真实格式：
        [S1 source_traceability]
        status: pass
    """
    out: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        m = _GATE_HEADER_RE.match(line.strip())
        if m:
            current = m.group(1)
            continue
        if current and line.strip().startswith("status:"):
            out[current] = line.split(":", 1)[1].strip().lower()
            current = None
    return out


def _assert_governance_report_green(report_path: Path | None = None) -> None:
    """KS-COMPILER-013 治理报告 S1-S7 全 pass 才放行。fail-closed."""
    path = Path(report_path) if report_path else DEFAULT_REPORT_PATH
    if not path.exists():
        raise RuntimeError(
            f"KS-COMPILER-013 治理报告缺失 ({path})，禁止结构化召回。"
            "先跑 python3 knowledge_serving/scripts/validate_serving_governance.py --all"
        )
    sections = _parse_gate_sections(path.read_text())
    for gate in REQUIRED_GATES:
        status = sections.get(gate)
        if status != "pass":
            raise RuntimeError(
                f"KS-COMPILER-013 {gate} 未通过 (status={status!r})，禁止结构化召回"
            )


# ---------- helpers ----------

def _validate_allowed_layers(allowed_layers: list[str]) -> None:
    if not allowed_layers:
        raise ValueError("allowed_layers 不能为空（应由 tenant_scope_resolver 解析得到）")
    for lay in allowed_layers:
        if not _BRAND_LAYER_RE.match(lay):
            raise ValueError(f"非法 brand_layer 命名：{lay!r}")


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _parse_json_list(raw: str) -> list:
    raw = (raw or "").strip()
    if not raw:
        return []
    return json.loads(raw)


def _parse_json_obj(raw: str) -> dict:
    raw = (raw or "").strip()
    if not raw:
        return {}
    return json.loads(raw)


def _lookup_policy(policy_rows: list[dict], intent: str, content_type: str) -> dict:
    hits = [r for r in policy_rows
            if r.get("intent") == intent and r.get("content_type") == content_type]
    if not hits:
        raise RetrievalPolicyNotFound(f"(intent={intent!r}, content_type={content_type!r}) 无策略")
    if len(hits) > 1:
        raise RetrievalPolicyAmbiguous(
            f"(intent={intent!r}, content_type={content_type!r}) 命中 {len(hits)} 行"
        )
    return hits[0]


def _apply_filters(rows: list[dict], allowed_layers: Iterable[str],
                   include_inactive: bool,
                   structured_filters: dict) -> list[dict]:
    if not rows:
        return []
    schema = set(rows[0].keys())
    # structured_filters_json 是跨 view 的全集策略；只对该 view schema 含有的列生效，
    # 列缺失 → 该 view 跳过该 filter（policy 的实际语义，对应 retrieval_policy_view.csv
    # 中 coverage_status 只存在于 content_type_view 的真实情况）。
    applicable = {col: set(vals) for col, vals in structured_filters.items() if col in schema}
    allowed = set(allowed_layers)
    out: list[dict] = []
    for r in rows:
        if r.get("brand_layer") not in allowed:
            continue
        if not include_inactive and r.get("gate_status") != "active":
            continue
        if r.get("granularity_layer") not in ALLOWED_GRANULARITY:
            continue
        if any(r.get(col) not in vals for col, vals in applicable.items()):
            continue
        out.append(r)
    return out


def _resolve_max_items(raw: object) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"max_items_per_view 非法：{raw!r}")
    if n <= 0:
        raise ValueError(f"max_items_per_view 必须为正整数，得到 {n}")
    if n > MAX_ITEMS_HARD_CAP:
        warnings.warn(
            f"max_items_per_view={n} 超过硬上限 {MAX_ITEMS_HARD_CAP}，已 cap",
            UserWarning,
            stacklevel=3,
        )
        return MAX_ITEMS_HARD_CAP
    return n


# ---------- public API ----------

def structured_retrieve(
    *,
    intent: str,
    content_type: str,
    allowed_layers: list[str],
    views_root: Path = DEFAULT_VIEWS_ROOT,
    policy_path: Path = DEFAULT_POLICY_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    include_inactive: bool = False,
) -> dict:
    """13 步召回流程第 7 步：结构化召回.

    Args:
        intent: 来自 KS-RETRIEVAL-002 (input-first / no-LLM)
        content_type: canonical id，来自 KS-RETRIEVAL-003
        allowed_layers: 来自 KS-RETRIEVAL-001 tenant_scope_resolver
        views_root: 4 个 view csv 所在目录
        policy_path: retrieval_policy_view.csv 路径
        report_path: KS-COMPILER-013 治理报告路径（preflight 必读）
        include_inactive: S2 例外开关，默认 False

    Returns:
        {view_name: [rows...], "_meta": {...}}
    """
    # preflight：KS-COMPILER-013 治理总闸
    _assert_governance_report_green(report_path)

    # 入参校验
    if not intent or not isinstance(intent, str):
        raise ValueError("intent 必须为非空字符串（由 KS-RETRIEVAL-002 提供）")
    if not content_type or not isinstance(content_type, str):
        raise ValueError("content_type 必须为非空 canonical id（由 KS-RETRIEVAL-003 提供）")
    _validate_allowed_layers(allowed_layers)

    # policy 查找
    policy_rows = _load_csv(Path(policy_path))
    policy = _lookup_policy(policy_rows, intent, content_type)

    required = _parse_json_list(policy.get("required_views", "[]"))
    optional = _parse_json_list(policy.get("optional_views", "[]"))
    requested = list(dict.fromkeys([*required, *optional]))
    target_set = [v for v in requested if v in TARGET_VIEWS]

    structured_filters = _parse_json_obj(policy.get("structured_filters_json", "{}"))
    max_items = _resolve_max_items(policy.get("max_items_per_view"))

    # 逐 view 加载 + 过滤 + 截断
    result: dict[str, list[dict]] = {v: [] for v in TARGET_VIEWS}
    views_root = Path(views_root)
    for view_name in TARGET_VIEWS:
        if view_name not in target_set:
            continue
        rows = _load_csv(views_root / f"{view_name}.csv")
        filtered = _apply_filters(
            rows,
            allowed_layers=allowed_layers,
            include_inactive=include_inactive,
            structured_filters=structured_filters,
        )
        result[view_name] = filtered[:max_items]

    result["_meta"] = {
        "policy_row": policy,
        "allowed_layers": list(allowed_layers),
        "include_inactive": include_inactive,
        "structured_filters": structured_filters,
        "max_items_per_view": max_items,
        "target_views": target_set,
    }
    return result

#!/usr/bin/env python3
"""scripts/diff_yaml_vs_csv.py · 双源一致性校验 / dual-source equivalence check.

W4 任务卡 KS-POLICY-003 / KS-POLICY-004 共用 CI 守门器。
对一个 policy_name 同时检查：
  csv 真源（knowledge_serving/control/<name>.csv 或 <name>_view.csv）
  yaml 镜像（knowledge_serving/policies/<name>.yaml）

约定 / convention：
  yaml 顶层是单 key（policy_name），值为 list[dict]，每条 dict 字段名严格等同 csv header。
  csv 里 JSON 字符串列（在 registry 的 json_fields 中声明）会在比较前 json.loads 成原生结构。
  yaml 中同字段必须是 native list / dict / bool / int / str（禁止再二次 json 字符串化）。
  其余非 json 字段按字面字符串比较（csv 永远是字符串；yaml 端需先 str() 归一）。

退出码 / exit codes：
  0 完全一致
  1 yaml 缺失 / csv 缺失 / 行数不一致 / 字段值不一致 / yaml 顶层 key 不符
  2 调用参数错 / policy_name 未注册

使用：
  python3 scripts/diff_yaml_vs_csv.py merge_precedence_policy
  python3 scripts/diff_yaml_vs_csv.py retrieval_policy

不调 LLM；纯确定性比较。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_DIR = REPO_ROOT / "knowledge_serving" / "control"
POLICY_DIR = REPO_ROOT / "knowledge_serving" / "policies"


# 注册表 / registry：每个 policy 声明 csv 路径、yaml 路径、JSON-string 列
# 新增 policy 时只追加一行 + 必要时 key_columns。
POLICY_REGISTRY: dict[str, dict[str, Any]] = {
    "merge_precedence_policy": {
        "csv": CONTROL_DIR / "merge_precedence_policy.csv",
        "yaml": POLICY_DIR / "merge_precedence_policy.yaml",
        # 该 policy 字段都是字面字符串/布尔，没有 JSON 列
        "json_fields": [],
        # 唯一性 key（用于稳定排序 + 重复检测）
        "key_columns": ["target_type", "conflict_key"],
        # 布尔列（csv "true"/"false" → bool）
        "bool_fields": ["allow_override"],
    },
    "retrieval_policy": {
        "csv": CONTROL_DIR / "retrieval_policy_view.csv",
        "yaml": POLICY_DIR / "retrieval_policy.yaml",
        "json_fields": [
            "required_views",
            "optional_views",
            "structured_filters_json",
            "vector_filters_json",
        ],
        "key_columns": ["intent", "content_type"],
        "bool_fields": [],
        # int 列（csv 字符串 → int）
        "int_fields": ["max_items_per_view", "timeout_ms"],
    },
}


class DiffError(Exception):
    """diff 失败的可控错误 / controlled diff failure."""


def _coerce_csv_value(col: str, raw: str, spec: dict[str, Any]) -> Any:
    if col in spec.get("json_fields", []):
        if raw == "":
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise DiffError(f"csv 列 {col!r} JSON 解析失败 / json parse failed: {raw!r} ({e})")
    if col in spec.get("bool_fields", []):
        if raw.lower() == "true":
            return True
        if raw.lower() == "false":
            return False
        raise DiffError(f"csv 列 {col!r} 非法布尔 / invalid bool: {raw!r}")
    if col in spec.get("int_fields", []):
        try:
            return int(raw)
        except ValueError as e:
            raise DiffError(f"csv 列 {col!r} 非法整数 / invalid int: {raw!r} ({e})")
    return raw


def _normalize_yaml_value(col: str, val: Any, spec: dict[str, Any]) -> Any:
    if col in spec.get("json_fields", []):
        if val in (None, "", [], {}):
            # 与 csv 端空字符串 → None 对齐；但允许空 list/dict 直通
            if val == "" or val is None:
                return None
        return val
    if col in spec.get("bool_fields", []):
        if not isinstance(val, bool):
            raise DiffError(f"yaml 列 {col!r} 必须是 bool 字面量 / must be native bool: {val!r}")
        return val
    if col in spec.get("int_fields", []):
        if not isinstance(val, int) or isinstance(val, bool):
            raise DiffError(f"yaml 列 {col!r} 必须是 int 字面量 / must be native int: {val!r}")
        return val
    # 字符串字段
    if val is None:
        return ""
    return str(val)


def load_csv(spec: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    csv_path: Path = spec["csv"]
    if not csv_path.exists():
        raise DiffError(f"csv 缺失 / missing: {csv_path}")
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise DiffError(f"csv 无 header / missing header: {csv_path}")
        headers = list(reader.fieldnames)
        rows: list[dict[str, Any]] = []
        for raw_row in reader:
            row: dict[str, Any] = {}
            for col in headers:
                row[col] = _coerce_csv_value(col, raw_row.get(col, ""), spec)
            rows.append(row)
    return headers, rows


def load_yaml(policy_name: str, spec: dict[str, Any], headers: list[str]) -> list[dict[str, Any]]:
    yaml_path: Path = spec["yaml"]
    if not yaml_path.exists():
        raise DiffError(f"yaml 缺失 / missing: {yaml_path}")
    with yaml_path.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        raise DiffError(f"yaml 顶层必须为 mapping / top-level must be mapping: {yaml_path}")
    if list(doc.keys()) != [policy_name]:
        raise DiffError(
            f"yaml 顶层 key 必须等于 policy_name={policy_name!r} 且唯一 / "
            f"top-level key must be exactly [{policy_name!r}]，实际 keys={list(doc.keys())}"
        )
    items = doc[policy_name]
    if not isinstance(items, list):
        raise DiffError(f"yaml.{policy_name} 必须为 list / must be list")
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise DiffError(f"yaml.{policy_name}[{idx}] 必须为 mapping / must be mapping")
        # 字段完整性 / column completeness
        missing = [c for c in headers if c not in item]
        extra = [c for c in item.keys() if c not in headers]
        if missing or extra:
            raise DiffError(
                f"yaml 行 {idx} 字段集与 csv header 不一致 / column mismatch: "
                f"missing={missing} extra={extra}"
            )
        normalized: dict[str, Any] = {}
        for col in headers:
            normalized[col] = _normalize_yaml_value(col, item[col], spec)
        out.append(normalized)
    return out


def _row_key(row: dict[str, Any], key_columns: list[str]) -> tuple:
    return tuple(json.dumps(row.get(k), sort_keys=True, ensure_ascii=False) for k in key_columns)


def diff_policy(policy_name: str) -> list[str]:
    """返回 diff 行的人类可读描述。空 list = 一致。"""
    if policy_name not in POLICY_REGISTRY:
        raise DiffError(f"未注册 policy / unregistered policy: {policy_name!r}")
    spec = POLICY_REGISTRY[policy_name]
    headers, csv_rows = load_csv(spec)
    yaml_rows = load_yaml(policy_name, spec, headers)

    diffs: list[str] = []
    if len(csv_rows) != len(yaml_rows):
        diffs.append(f"行数不一致 / row count mismatch: csv={len(csv_rows)} yaml={len(yaml_rows)}")

    key_cols = spec.get("key_columns") or headers
    csv_by_key: dict[tuple, dict[str, Any]] = {}
    for r in csv_rows:
        k = _row_key(r, key_cols)
        if k in csv_by_key:
            diffs.append(f"csv 重复 key / duplicate csv key {key_cols}={k}")
        csv_by_key[k] = r
    yaml_by_key: dict[tuple, dict[str, Any]] = {}
    for r in yaml_rows:
        k = _row_key(r, key_cols)
        if k in yaml_by_key:
            diffs.append(f"yaml 重复 key / duplicate yaml key {key_cols}={k}")
        yaml_by_key[k] = r

    only_csv = sorted(set(csv_by_key) - set(yaml_by_key))
    only_yaml = sorted(set(yaml_by_key) - set(csv_by_key))
    for k in only_csv:
        diffs.append(f"仅 csv 存在 / csv-only key={k}")
    for k in only_yaml:
        diffs.append(f"仅 yaml 存在 / yaml-only key={k}")

    for k in sorted(set(csv_by_key) & set(yaml_by_key)):
        c = csv_by_key[k]
        y = yaml_by_key[k]
        for col in headers:
            cv, yv = c[col], y[col]
            if cv != yv:
                diffs.append(
                    f"字段值不一致 / value mismatch key={k} col={col!r}: csv={cv!r} yaml={yv!r}"
                )
    return diffs


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="diff a registered policy yaml against its csv source of truth")
    p.add_argument("policy_name", help="one of: " + ", ".join(POLICY_REGISTRY))
    args = p.parse_args(argv)
    try:
        diffs = diff_policy(args.policy_name)
    except DiffError as e:
        print(f"[diff-fail] {e}", file=sys.stderr)
        return 1
    except KeyError as e:
        print(f"[arg-fail] {e}", file=sys.stderr)
        return 2
    if diffs:
        print(f"[diff-fail] {args.policy_name}: {len(diffs)} 项差异 / diffs")
        for d in diffs:
            print(f"  - {d}")
        return 1
    print(f"[diff-ok] {args.policy_name}: 双源一致 / dual sources equivalent")
    return 0


if __name__ == "__main__":
    sys.exit(main())

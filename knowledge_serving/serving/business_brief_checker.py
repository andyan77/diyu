"""business_brief_checker · 业务摘要硬校验 / business brief hard checker.

KS-RETRIEVAL-003 · W4 · S gate S11 business_brief_no_fabrication.

语义 / semantics:
  - schema instance validate（基于 business_brief.schema.json）失败 → 直接抛
    `jsonschema.ValidationError`（非法 enum / 类型 / 空 string / minItems 等）。
  - hard required（schema 顶层 `required`）缺失 → status='blocked_missing_business_brief'。
  - x-soft-required 列出的字段缺失 → status='ok', missing_fields 含字段名（warning，不阻断）。
  - compliance_redlines 字段缺失 或 == []     → status='ok', missing_fields 含
    'compliance_redlines'（S11 兜底，不阻断；schema 层只描述）。
  - 多余字段（不在 schema.properties 内）       → status='ok', missing_fields 含
    'unknown:<key>' 警告。

红线 / red lines:
  - 不调任何大模型 / language-model 服务。
  - 不补全 brief；不修复 schema 失败；不写 clean_output/。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schema" / "business_brief.schema.json"
)


def _load_schema() -> dict[str, Any]:
    with _SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


_SCHEMA: dict[str, Any] = _load_schema()
_VALIDATOR = Draft202012Validator(_SCHEMA)
_HARD_REQUIRED: list[str] = list(_SCHEMA.get("required", []))
_SOFT_REQUIRED: list[str] = list(_SCHEMA.get("x-soft-required", []))
_KNOWN_PROPS: set[str] = set(_SCHEMA.get("properties", {}).keys())


def check(brief: dict) -> dict:
    """检查业务摘要 / validate business brief.

    返回 / returns:
      {
        "status": "ok" | "blocked_missing_business_brief",
        "missing_fields": list[str],   # soft 缺失 + compliance_redlines 兜底 + unknown:* 警告
        "blocked_fields": list[str],   # hard required 缺失
        "errors": list[str],           # 保留字段（当前非法值直接 raise）
      }

    非法值（如 season 不在 enum、price_band 缺字段、channel minItems<1 等）
    直接抛 `jsonschema.ValidationError`，由调用方捕获——对应卡 §6 "非法 season → raise"。
    """
    if not isinstance(brief, dict):
        raise TypeError("brief must be a dict")

    blocked_fields: list[str] = []
    missing_fields: list[str] = []

    # ---- 1. hard required 检查（先于 instance validate，便于精确报 blocked） ----
    for key in _HARD_REQUIRED:
        if key not in brief:
            blocked_fields.append(key)

    # ---- 2. instance validate：只对"已提供的字段"做值合法性检查 ----
    # 构造一个"补齐 hard required 占位"的副本：避免 jsonschema 因 required 缺失抢先抛错，
    # 我们要的是"非法值 raise / 缺字段 blocked"两条路径分开。
    # 做法：在缺失的 hard required 字段上跳过 validate 的 required 报错——
    # 直接用 iter_errors 过滤掉 validator=='required' 的错误，由我们自己处理。
    errors = sorted(_VALIDATOR.iter_errors(brief), key=lambda e: list(e.absolute_path))
    # 顶层 'required' → 走 blocked_fields；顶层 'additionalProperties' → 走 unknown:* warning
    # 嵌套（如 price_band 内部缺 max）的 required / additionalProperties 仍按 raise 处理
    fatal_errors = [
        e for e in errors
        if not (
            e.validator in ("required", "additionalProperties")
            and len(list(e.absolute_path)) == 0
        )
    ]
    if fatal_errors:
        # 非法值 / 类型错 / enum 错 / minItems 错 / additionalProperties 等 → raise
        raise fatal_errors[0]

    # ---- 3. soft required 检查 ----
    for key in _SOFT_REQUIRED:
        if key not in brief:
            missing_fields.append(key)

    # ---- 4. compliance_redlines 兜底（S11） ----
    cr = brief.get("compliance_redlines", None)
    if cr is None or (isinstance(cr, list) and len(cr) == 0):
        if "compliance_redlines" not in missing_fields:
            missing_fields.append("compliance_redlines")

    # ---- 5. 多余字段警告（schema 已 additionalProperties:false，
    #         若 instance validate 已 raise 则不会到这里；
    #         但 schema 若未来放开，这里做兜底） ----
    for key in brief.keys():
        if key not in _KNOWN_PROPS:
            tag = f"unknown:{key}"
            if tag not in missing_fields:
                missing_fields.append(tag)

    # ---- 6. 终判 ----
    if blocked_fields:
        return {
            "status": "blocked_missing_business_brief",
            "missing_fields": missing_fields,
            "blocked_fields": blocked_fields,
            "errors": [],
        }

    return {
        "status": "ok",
        "missing_fields": missing_fields,
        "blocked_fields": [],
        "errors": [],
    }

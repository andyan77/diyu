"""KS-RETRIEVAL-002 · content_type_router

input-first / no-LLM content_type 校验 + alias→canonical 确定性映射。

2026-05-12 用户裁决：content_type **必须由 Dify 开始节点 / API 显式入参**提供；
本模块只做 alias→canonical 的**确定性映射 + canonical 校验**；缺失 / 不识别 → needs_review。

数据源（module load 时一次性读，纯函数运行期无 IO）：
- knowledge_serving/control/content_type_canonical.csv

工程红线（hard rules）：
- 禁止任何外部模型客户端 / 端点调用（具体禁用名单见 KS-RETRIEVAL-002 任务卡 §6 / §7）
- 禁止读自然语言入参（user 查询字段）；函数签名不接受自然语言参数
- 未命中 / None → needs_review，不返回兜底
- 不推断 brand_layer
- alias 匹配规则：大小写不敏感（casefold） + 首尾去空白；canonical id 仍可大小写敏感直通命中
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

_CANONICAL_CSV: Path = (
    Path(__file__).resolve().parents[1]
    / "control"
    / "content_type_canonical.csv"
)


def _load_canonical_map() -> tuple[frozenset[str], dict[str, tuple[str, str]]]:
    """返回 (canonical_ids, alias_lookup)。

    alias_lookup: key = alias.strip().casefold()，value = (canonical_id, original_alias)
    canonical_id 自身也注入 alias_lookup（以 canonical_id.casefold() 作 key），
    便于一次查找；但 source/matched_alias 区分由外层逻辑保证。
    """
    canonical_ids: set[str] = set()
    alias_lookup: dict[str, tuple[str, str]] = {}
    with _CANONICAL_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row["canonical_content_type_id"].strip()
            if not cid:
                continue
            canonical_ids.add(cid)
            raw_aliases = row.get("aliases", "") or ""
            for raw in raw_aliases.split("|"):
                alias = raw.strip()
                if not alias:
                    continue
                key = alias.casefold()
                # 不覆盖已有别名（CSV 顺序优先）
                alias_lookup.setdefault(key, (cid, alias))
    return frozenset(canonical_ids), alias_lookup


_CANONICAL_IDS, _ALIAS_LOOKUP = _load_canonical_map()


def route(content_type_hint: Optional[str]) -> dict:
    """把 content_type_hint 映射到 canonical id；不识别 → needs_review。

    Args:
        content_type_hint: Dify 开始节点 / API 入参；canonical id 或 alias 或 None。
                           不接受 user_query / 自然语言。

    Returns:
        dict with keys:
          - content_type:   canonical id 或 None
          - source:         "input" 或 None
          - status:         "ok" 或 "needs_review"
          - missing:        "content_type" 或 None
          - matched_alias:  命中的原始 alias（若直接 canonical 命中则为 None）
    """
    if content_type_hint is None or not isinstance(content_type_hint, str):
        return _miss()
    raw = content_type_hint.strip()
    if not raw:
        return _miss()

    # 1) canonical id 直通（大小写敏感）
    if raw in _CANONICAL_IDS:
        return {
            "content_type": raw,
            "source": "input",
            "status": "ok",
            "missing": None,
            "matched_alias": None,
        }

    # 2) alias 命中（casefold 大小写不敏感）
    key = raw.casefold()
    hit = _ALIAS_LOOKUP.get(key)
    if hit is not None:
        canonical_id, original_alias = hit
        # 若 alias 的 casefold == canonical_id 的 casefold，则视为 canonical 命中（matched_alias=None）
        if key == canonical_id.casefold():
            return {
                "content_type": canonical_id,
                "source": "input",
                "status": "ok",
                "missing": None,
                "matched_alias": None,
            }
        return {
            "content_type": canonical_id,
            "source": "input",
            "status": "ok",
            "missing": None,
            "matched_alias": original_alias,
        }

    return _miss()


def _miss() -> dict:
    return {
        "content_type": None,
        "source": None,
        "status": "needs_review",
        "missing": "content_type",
        "matched_alias": None,
    }

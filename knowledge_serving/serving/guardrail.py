"""KS-DIFY-ECS-009 · guardrail 检查器 / post-generation guardrail.

任务卡 KS-DIFY-ECS-009 · W7 · S gate S11 business_brief_no_fabrication.

语义 / semantics:
  - 入参：generated_text(str) + bundle(dict, context_bundle.schema) + business_brief(dict).
  - 唯一策略源 / single source of truth：
      knowledge_serving/policies/guardrail_policy.yaml （KS-POLICY-002）
  - 三类校验 / three guards：
      §A forbidden_patterns           — 关键词 / 正则扫描生成文本
      §B required_evidence            — content_type 对应 hard_fields 必须在 bundle 中可见
      §C business_brief_required      — brief hard_fields 缺失即阻断
  - 额外纪律 / extra rules：
      0. 空文本 / 仅空白 → blocked（疑似漏生成；卡 §6 case 5）
      1. SKU 形 token：只放行 == business_brief.sku 的命中；其它 SKU-shape token 视为编造
      2. 价格形 token：只放行落在 business_brief.price_band[min,max] 区间内的数字；其它视为编造

红线 / red lines:
  - 不调任何 LLM / language-model 做裁决（policy.no_llm_in_decision=true，plan §9.1）。
  - 不写 clean_output/。
  - 仅声明式规则；运行时确定性纯函数。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_POLICY_YAML: Path = (
    Path(__file__).resolve().parents[1] / "policies" / "guardrail_policy.yaml"
)

STATUS_PASS = "pass"
STATUS_BLOCKED = "blocked"

# 违规分类常量 / violation categories
V_EMPTY = "empty_generation"
V_FORBIDDEN = "forbidden_pattern_hit"
V_SKU_FABRICATION = "sku_not_in_brief"
V_PRICE_FABRICATION = "price_out_of_band"
V_MISSING_EVIDENCE = "missing_required_evidence"
V_MISSING_BRIEF = "missing_business_brief_hard_field"

# 特殊 forbidden_pattern id：需要 brief 上下文比对，不能直接命中即阻断
_SKU_FP_ID = "FP-SKU-FABRICATION"
_PRICE_FP_ID = "FP-PRICE-FABRICATION"


def _load_policy() -> dict[str, Any]:
    with _POLICY_YAML.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_POLICY: dict[str, Any] = _load_policy()
_FORBIDDEN: list[dict] = list(_POLICY.get("forbidden_patterns", []))
_REQUIRED_EVIDENCE: dict[str, dict] = dict(_POLICY.get("required_evidence", {}))
_BB_REQ: dict = dict(_POLICY.get("business_brief_required", {}))
_BB_HARD: list[str] = list(_BB_REQ.get("hard_fields", []))


def _compile_patterns(fp: dict) -> list[re.Pattern]:
    kind = fp.get("pattern_kind", "keyword")
    pats: list[re.Pattern] = []
    for raw in fp.get("patterns", []):
        if kind == "regex":
            pats.append(re.compile(raw, flags=re.IGNORECASE))
        else:
            # keyword：转义后整词忽略大小写
            pats.append(re.compile(re.escape(raw), flags=re.IGNORECASE))
    return pats


_COMPILED: dict[str, list[re.Pattern]] = {
    fp["id"]: _compile_patterns(fp) for fp in _FORBIDDEN
}

_PRICE_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _collect_bundle_keys(bundle: dict) -> set[str]:
    """收集 bundle 中各容器条目的字段名，用于 required_evidence 命中判定。"""
    keys: set[str] = set()
    for arr_name in ("domain_packs", "play_cards", "runtime_assets", "brand_overlays"):
        for item in bundle.get(arr_name, []) or []:
            if isinstance(item, dict):
                keys.update(item.keys())
                # 兼容 view 行将字段名挂在 'field_key' / 'field' 列上
                for k in ("field_key", "field", "hard_field"):
                    v = item.get(k)
                    if isinstance(v, str) and v:
                        keys.add(v)
    return keys


def _scan_forbidden(text: str, brief: dict) -> list[dict]:
    """扫描 forbidden_patterns；对 SKU / price 做 brief 白名单豁免。"""
    violations: list[dict] = []
    brief_sku = brief.get("sku") if isinstance(brief, dict) else None
    price_band = brief.get("price_band") if isinstance(brief, dict) else None

    for fp in _FORBIDDEN:
        fp_id = fp["id"]
        for pat in _COMPILED[fp_id]:
            for m in pat.finditer(text):
                hit = m.group(0)

                if fp_id == _SKU_FP_ID:
                    # 放行：命中片段含 brief.sku 字面（如 "SKU FAYE001" 与 brief.sku=='FAYE001'）
                    if isinstance(brief_sku, str) and brief_sku and brief_sku in hit:
                        continue
                    violations.append({
                        "category": V_SKU_FABRICATION,
                        "fp_id": fp_id,
                        "hit": hit,
                        "block_reason": fp.get("block_reason", ""),
                    })
                    continue

                if fp_id == _PRICE_FP_ID:
                    # 放行：命中片段中的数字位于 brief.price_band [min,max] 内
                    if _price_within_band(hit, price_band):
                        continue
                    violations.append({
                        "category": V_PRICE_FABRICATION,
                        "fp_id": fp_id,
                        "hit": hit,
                        "block_reason": fp.get("block_reason", ""),
                    })
                    continue

                # 其它（创始人 / 库存等）—— hard_block 命中即记
                violations.append({
                    "category": V_FORBIDDEN,
                    "fp_id": fp_id,
                    "hit": hit,
                    "block_reason": fp.get("block_reason", ""),
                })
    return violations


def _price_within_band(hit: str, price_band: Any) -> bool:
    if not isinstance(price_band, dict):
        return False
    try:
        lo = float(price_band.get("min"))
        hi = float(price_band.get("max"))
    except (TypeError, ValueError):
        return False
    nums = _PRICE_NUMBER_RE.findall(hit)
    if not nums:
        return False
    for raw in nums:
        try:
            v = float(raw)
        except ValueError:
            return False
        if not (lo <= v <= hi):
            return False
    return True


def check(generated_text: str, bundle: dict, business_brief: dict) -> dict:
    """执行 guardrail 校验 / run guardrail check.

    Returns:
      {
        "status": "pass" | "blocked",
        "violations": list[dict]  # 每项含 category / fp_id?/ hit?/ field?/ block_reason
      }
    """
    if not isinstance(generated_text, str):
        raise TypeError("generated_text must be str")
    if not isinstance(bundle, dict):
        raise TypeError("bundle must be a dict")
    if not isinstance(business_brief, dict):
        raise TypeError("business_brief must be a dict")

    violations: list[dict] = []

    # ---- 0. 空文本 ----
    if not generated_text.strip():
        violations.append({
            "category": V_EMPTY,
            "block_reason": "生成文本为空 / empty generation（疑似漏生成）",
        })
        return {"status": STATUS_BLOCKED, "violations": violations}

    # ---- 1. forbidden_patterns ----
    violations.extend(_scan_forbidden(generated_text, business_brief))

    # ---- 2. required_evidence by content_type ----
    ct = bundle.get("content_type")
    if isinstance(ct, str) and ct in _REQUIRED_EVIDENCE:
        spec = _REQUIRED_EVIDENCE[ct]
        hard_fields: list[str] = list(spec.get("hard_fields", []))
        present = _collect_bundle_keys(bundle)
        for hf in hard_fields:
            if hf not in present:
                violations.append({
                    "category": V_MISSING_EVIDENCE,
                    "content_type": ct,
                    "field": hf,
                    "block_reason": spec.get("block_reason", ""),
                })

    # ---- 3. business_brief_required hard fields ----
    # 缺字段 / 空字符串 / 空列表均视为缺失（schema 层 minLength=1 / minItems=1 的运行时兜底）
    for hf in _BB_HARD:
        val = business_brief.get(hf, None)
        if val is None or (isinstance(val, (str, list, tuple, dict)) and len(val) == 0):
            violations.append({
                "category": V_MISSING_BRIEF,
                "field": hf,
                "block_reason": _BB_REQ.get("block_reason", ""),
            })

    status = STATUS_BLOCKED if violations else STATUS_PASS
    return {"status": status, "violations": violations}

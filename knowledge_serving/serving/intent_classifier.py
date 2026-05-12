"""KS-RETRIEVAL-002 · intent_classifier

input-first / no-LLM intent 校验。

2026-05-12 用户裁决：intent **必须由 Dify 开始节点 / API 显式入参**提供。
本模块只做 canonical 枚举校验：命中 → ok；缺失 / 不识别 → needs_review。

工程红线（hard rules）：
- 禁止任何外部模型客户端 / 端点调用（具体禁用名单见 KS-RETRIEVAL-002 任务卡 §6 / §7）
- 禁止读自然语言入参（user 查询字段）；函数签名不接受自然语言参数
- 未命中 / None → needs_review，不返回兜底
- 大小写敏感：canonical 一律小写；大写 / 混合大小写视为未识别（前端必须传 canonical）
- 纯函数 + 确定性，无 IO，无副作用
"""
from __future__ import annotations

from typing import Optional

# canonical intent 枚举（与任务卡 §3 一致）
INTENT_ENUM: frozenset[str] = frozenset({
    "content_generation",
    "quality_check",
    "strategy_advice",
    "training",
    "sales_script",
})


# ----------------------------------------------------------------------------
# transitional bridge / 过渡桥接（W4 → W7 期）
# ----------------------------------------------------------------------------
# 当前 retrieval_policy_view.csv（KS-COMPILER-010 落盘）只覆盖单一 policy intent
# "generate"。本模块的 5 类业务 intent 与该单类不直接相交。为了让 W4 召回入口
# 可用、同时不把 5 类业务语义悄悄折叠成"生成"，引入显式 mapper：
#   - content_generation → policy_key="generate"，bridge_status="direct_map"
#   - 其余 4 类 → policy_key=None，bridge_status="unsupported_intent_no_policy"
# 当 KS-RETRIEVAL-007 扩 retrieval_policy_view.csv 增设其它 policy intent 时，
# 在 _POLICY_BRIDGE_MAP 里追加映射并删除本注释中的 W4 说明；不允许在调用方
# 静默兜底为 "generate"。
# ----------------------------------------------------------------------------
_POLICY_BRIDGE_MAP: dict[str, str] = {
    "content_generation": "generate",
}

BRIDGE_STATUS_DIRECT = "direct_map"
BRIDGE_STATUS_UNSUPPORTED = "unsupported_intent_no_policy"
BRIDGE_STATUS_NO_INTENT = "no_intent"
BRIDGE_STATUS_UNKNOWN = "unknown_intent"


def intent_to_policy_key(intent: Optional[str]) -> dict:
    """把 5 类业务 intent 桥接到当前 retrieval_policy_view 的 policy intent。

    transitional bridge / 过渡桥接 —— 见模块上方注释。下游必须显式处理
    bridge_status，不允许把 unsupported / unknown 静默回退到 "generate"。

    Returns:
      dict with keys:
        - policy_key:    str（policy_view.intent）或 None
        - bridge_status: direct_map / unsupported_intent_no_policy / no_intent / unknown_intent
    """
    if intent is None:
        return {"policy_key": None, "bridge_status": BRIDGE_STATUS_NO_INTENT}
    if intent in _POLICY_BRIDGE_MAP:
        return {
            "policy_key": _POLICY_BRIDGE_MAP[intent],
            "bridge_status": BRIDGE_STATUS_DIRECT,
        }
    if intent in INTENT_ENUM:
        return {
            "policy_key": None,
            "bridge_status": BRIDGE_STATUS_UNSUPPORTED,
        }
    return {"policy_key": None, "bridge_status": BRIDGE_STATUS_UNKNOWN}


def classify(intent_hint: Optional[str]) -> dict:
    """校验 intent_hint 是否为 canonical 枚举值。

    Args:
        intent_hint: Dify 开始节点 / API 入参；canonical id 或 None。
                     不接受 user_query / 自然语言。

    Returns:
        dict with keys:
          - intent:  canonical id 或 None
          - source:  "input" 或 None
          - status:  "ok" 或 "needs_review"
          - missing: 缺失字段名 "intent" 或 None
    """
    if intent_hint is None:
        return {
            "intent": None,
            "source": None,
            "status": "needs_review",
            "missing": "intent",
        }
    # 大小写敏感：strip 仅去首尾空白，不做 .lower()
    if not isinstance(intent_hint, str):
        return {
            "intent": None,
            "source": None,
            "status": "needs_review",
            "missing": "intent",
        }
    candidate = intent_hint.strip()
    if candidate in INTENT_ENUM:
        return {
            "intent": candidate,
            "source": "input",
            "status": "ok",
            "missing": None,
        }
    return {
        "intent": None,
        "source": None,
        "status": "needs_review",
        "missing": "intent",
    }

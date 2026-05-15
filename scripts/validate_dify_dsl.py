#!/usr/bin/env python3
"""
KS-DIFY-ECS-008 · Dify Chatflow DSL 校验器 / validator

校验 / checks 范围（与卡 §4 / §6 / §7 一一对齐）：

  V1  10 个 canonical role 全部出现
       (tenant_resolution / intent_canonical_check / content_type_canonical_map /
        business_brief_check / retrieve_context_call / fallback_status_branch /
        llm_generation / guardrail / output_evidence / log_write)

  V2  10 role 在拓扑序里严格按 ORDERED_ROLES 顺序出现

  V3  input-first 红线：tenant_resolution / intent_canonical_check /
       content_type_canonical_map / retrieve_context_call / fallback_status_branch
       禁止 type ∈ {llm, agent}

  V4  仅 role=llm_generation 可以用 type=llm；其他 role 不许 type=llm

  V5  guardrail 节点在拓扑序里必须严格晚于 llm_generation

  V6  log_write 节点必须存在（在 V1 兜底之外再显式守一道）

  V7  retrieve_context_call 节点必须声明 uses_tenant_filter=true 且
       no_direct_table_query=true（不绕 tenant filter / 不直查 9 表）

  V8  9 表 view 名禁止作为任何节点的 inputs.source（Agent 直查 9 表的硬红线）

  V9  business_brief_check 与 llm_generation 之间必须经过 fallback_status_branch
       （硬缺字段不得直接进入文案生成）

  V10 Agent 节点 (type=agent) 不许扛任一 ORDERED_ROLES 角色；只能挂在
       allowed_off_path_roles：rerank_assist / self_check_assist / guardrail_assist

  V11 input-first：start.form_variables 必须含 intent_hint 与 content_type_hint
       且 required=true

退出码 / exit code: 0 全绿；非 0 fail。
不调 LLM / no LLM calls.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DSL = REPO_ROOT / "dify" / "chatflow.dsl"

# 10 节点 canonical roles + 严格拓扑顺序
ORDERED_ROLES: list[str] = [
    "tenant_resolution",
    "intent_canonical_check",
    "content_type_canonical_map",
    "business_brief_check",
    "retrieve_context_call",
    "fallback_status_branch",
    "llm_generation",
    "guardrail",
    "output_evidence",
    "log_write",
]

# 这些 role 禁止 type ∈ {llm, agent}（input-first / 治理判断不许 LLM 化）
NON_LLM_NON_AGENT_ROLES: set[str] = {
    "tenant_resolution",
    "intent_canonical_check",
    "content_type_canonical_map",
    "retrieve_context_call",
    "fallback_status_branch",
}

# 仅这个 role 允许 type=llm
LLM_ALLOWED_ROLES: set[str] = {"llm_generation"}

# Agent 节点只能扛 off-path 辅助角色，不许出现在 ORDERED_ROLES
AGENT_ALLOWED_OFF_PATH_ROLES: set[str] = {
    "rerank_assist",
    "self_check_assist",
    "guardrail_assist",
}

# 9 表 view 名（不允许作为节点 inputs.source）
NINE_TABLE_VIEWS: set[str] = {
    "pack_view",
    "content_type_view",
    "generation_recipe_view",
    "play_card_view",
    "runtime_asset_view",
    "brand_overlay_view",
    "evidence_view",
    "context_recipe_view",
    "call_mapping_view",
}


# ----------------------------------------------------------------------
# 解析 / parse
# ----------------------------------------------------------------------

def load_dsl(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"DSL 文件不存在 / not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"DSL 顶层必须是 mapping / top must be mapping: got {type(data).__name__}")
    return data


def _topo_order(nodes: list[dict], edges: list[dict]) -> list[str]:
    """对节点做拓扑排序；返回节点 id 序列。环路则抛错。"""
    ids = [n["id"] for n in nodes]
    indeg: dict[str, int] = {nid: 0 for nid in ids}
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        src, dst = e["from"], e["to"]
        # 跳过引用未知节点的悬边 / dangling edge —— 调用方可能已经删了节点
        # 用于触发上游 V1 缺失检测；这里不再二次抛 KeyError
        if src not in indeg or dst not in indeg:
            continue
        indeg[dst] += 1
        adj[src].append(dst)
    # 起点 = 入度 0；DSL start 节点不在 nodes 里（特殊节点），允许多个起点但实际应只有 1
    queue = [nid for nid in ids if indeg[nid] == 0]
    order: list[str] = []
    while queue:
        cur = queue.pop(0)
        order.append(cur)
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(ids):
        raise ValueError("edges 含环 / cycle detected in chatflow graph")
    return order


# ----------------------------------------------------------------------
# 校验 / validate
# ----------------------------------------------------------------------

def validate(dsl: dict[str, Any]) -> list[str]:
    """返回 errors 列表；空 list = 全绿。"""
    errors: list[str] = []

    nodes: list[dict] = dsl.get("nodes") or []
    edges: list[dict] = dsl.get("edges") or []
    start_node: dict = dsl.get("start") or {}

    # 索引
    by_role: dict[str, list[dict]] = defaultdict(list)
    by_id: dict[str, dict] = {}
    for n in nodes:
        if "role" not in n or "id" not in n:
            errors.append(f"V0 节点缺 id 或 role / node missing id|role: {n}")
            continue
        by_role[n["role"]].append(n)
        by_id[n["id"]] = n

    # V1 10 个 role 全在
    for role in ORDERED_ROLES:
        if role not in by_role:
            errors.append(f"V1 缺 role / missing required role: {role}")

    # V6 log_write 显式（V1 已 cover，但卡 §6 单列一行）
    if "log_write" not in by_role:
        errors.append("V6 缺日志节点 / log_write node missing (卡 §6 行 6)")

    # V3 + V4 节点 type 合法性
    for n in nodes:
        role = n.get("role")
        node_type = n.get("type")
        if role in NON_LLM_NON_AGENT_ROLES and node_type in ("llm", "agent"):
            errors.append(
                f"V3 input-first 红线：role={role} 不许 type={node_type} "
                f"(节点 id={n.get('id')})"
            )
        if node_type == "llm" and role not in LLM_ALLOWED_ROLES:
            errors.append(
                f"V4 仅 llm_generation 可用 type=llm；非法节点 id={n.get('id')} role={role}"
            )

    # V10 Agent 节点角色限制
    for n in nodes:
        if n.get("type") == "agent":
            role = n.get("role")
            if role in ORDERED_ROLES:
                errors.append(
                    f"V10 Agent 节点不许扛 pipeline 角色 role={role} "
                    f"(节点 id={n.get('id')})；只能扛 {sorted(AGENT_ALLOWED_OFF_PATH_ROLES)}"
                )
            elif role not in AGENT_ALLOWED_OFF_PATH_ROLES:
                errors.append(
                    f"V10 Agent 节点 role={role} 不在 allowed off-path 列表 "
                    f"{sorted(AGENT_ALLOWED_OFF_PATH_ROLES)} (节点 id={n.get('id')})"
                )

    # V7 retrieve_context_call 强制 tenant_filter + no direct table query
    for n in by_role.get("retrieve_context_call", []):
        if not n.get("uses_tenant_filter"):
            errors.append(
                f"V7 retrieve_context_call 节点 id={n.get('id')} 未声明 uses_tenant_filter=true"
            )
        if not n.get("no_direct_table_query"):
            errors.append(
                f"V7 retrieve_context_call 节点 id={n.get('id')} 未声明 no_direct_table_query=true"
            )

    # V8 9 表 view 不许作为任何节点 inputs.source
    for n in nodes:
        for inp in n.get("inputs", []) or []:
            src = (inp or {}).get("source", "")
            if not isinstance(src, str):
                continue
            head = src.split(".", 1)[0]
            if head in NINE_TABLE_VIEWS:
                errors.append(
                    f"V8 节点 id={n.get('id')} role={n.get('role')} 直查 9 表 view '{head}'"
                    f"（必须走 retrieve_context_call）"
                )

    # V11 start.form_variables 必须含 intent_hint / content_type_hint 且 required
    start_vars = {
        v.get("name"): v
        for v in (start_node.get("form_variables") or [])
        if isinstance(v, dict)
    }
    for var in ("intent_hint", "content_type_hint"):
        if var not in start_vars:
            errors.append(f"V11 input-first：start.form_variables 缺 {var}")
        elif not start_vars[var].get("required", False):
            errors.append(f"V11 input-first：start.form_variables {var} 必须 required=true")

    # 拓扑序 + V2 / V5 / V9
    try:
        topo = _topo_order(nodes, edges)
    except ValueError as e:
        errors.append(f"V2 拓扑排序失败 / topo failed: {e}")
        return errors

    # role → 拓扑位置（取首次出现）
    role_topo_idx: dict[str, int] = {}
    for idx, nid in enumerate(topo):
        n = by_id.get(nid)
        if n and n.get("role") in ORDERED_ROLES and n["role"] not in role_topo_idx:
            role_topo_idx[n["role"]] = idx

    # V2 ORDERED_ROLES 拓扑顺序
    seen_present_roles = [r for r in ORDERED_ROLES if r in role_topo_idx]
    last = -1
    for role in seen_present_roles:
        cur = role_topo_idx[role]
        if cur < last:
            errors.append(
                f"V2 节点顺序错乱 / topo order broken: role={role} 在前序角色之前"
            )
        last = cur

    # V5 guardrail 必须严格晚于 llm_generation
    if "llm_generation" in role_topo_idx and "guardrail" in role_topo_idx:
        if role_topo_idx["guardrail"] <= role_topo_idx["llm_generation"]:
            errors.append("V5 guardrail 必须严格晚于 llm_generation")

    # V9 business_brief_check 到 llm_generation 必经 fallback_status_branch
    if {"business_brief_check", "llm_generation", "fallback_status_branch"} <= set(role_topo_idx):
        bbc = role_topo_idx["business_brief_check"]
        fsb = role_topo_idx["fallback_status_branch"]
        llm = role_topo_idx["llm_generation"]
        # 简化判定：拓扑位置上 fallback_status_branch 必须严格位于 business_brief_check 与 llm_generation 之间
        if not (bbc < fsb < llm):
            errors.append(
                "V9 硬缺字段守门破坏：business_brief_check → llm_generation "
                "中间必经 fallback_status_branch（拓扑位置应满足 bbc < fsb < llm）"
            )

    # V12 单源化 / single-source（KS-CD-003-A）:
    #   n1-n4 (tenant_resolution / intent_canonical_check / content_type_canonical_map /
    #   business_brief_check) 必须**至少有一条** input 来自 n0_preflight_call.*；
    #   防止有人把硬编码 registry / alias 移回 DSL 内联代码。
    PREFLIGHT_DEPENDENT_ROLES = {
        "tenant_resolution", "intent_canonical_check",
        "content_type_canonical_map", "business_brief_check",
    }
    has_preflight_call = any(n.get("role") == "preflight_call" for n in nodes)
    if not has_preflight_call:
        errors.append(
            "V12 single-source 红线：缺 preflight_call 节点（KS-CD-003-A）；"
            "n1-n4 必须依赖 /v1/input_preflight，不许内联 registry/alias"
        )
    for n in nodes:
        if n.get("role") not in PREFLIGHT_DEPENDENT_ROLES:
            continue
        sources = [(inp or {}).get("source", "") for inp in (n.get("inputs") or [])]
        if not any(isinstance(s, str) and s.startswith("n0_preflight_call.") for s in sources):
            errors.append(
                f"V12 single-source：role={n.get('role')} (id={n.get('id')}) "
                "未引用 n0_preflight_call.*；可能内联了硬编码 registry/alias"
            )

    return errors


# ----------------------------------------------------------------------
# V13 · Dify YAML 内联代码体积/关键字闸（防 n1-n4 内联 alias 大表回潮）
# ----------------------------------------------------------------------

# canonical content_type 全集（18 类）—— 出现 ≥ 10 个在单节点 code 中 → 视为内联大表
_CT_CANONICAL_NAMES = (
    "behind_the_scenes", "daily_fragment", "emotion_expression",
    "event_documentary", "founder_ip", "humor_content", "knowledge_sharing",
    "lifestyle_expression", "outfit_of_the_day", "personal_vlog",
    "process_trace", "product_copy_general", "product_journey",
    "product_review", "role_work_vlog", "store_daily",
    "talent_showcase", "training_material",
)

V13_TARGET_NODES = {
    "n1_tenant_resolution", "n2_intent_canonical_check",
    "n3_content_type_canonical_map", "n4_business_brief_check",
}


def validate_dify_yaml_inline(yml_path: Path) -> list[str]:
    """检查 chatflow_dify_cloud.yml 内 n1-n4 code 节点是否回潮硬编码。

    红线 / red lines:
      - 单个 n1-n4 节点 code 文本长度 > 1500 字符 → 视为内联了 registry/alias
      - 单个 n1-n4 节点 code 中出现 ≥ 5 个 canonical content_type 名 → 视为内联大表
    """
    errors: list[str] = []
    if not yml_path.is_file():
        return errors  # 可选 file；不存在则跳过
    try:
        data = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        errors.append(f"V13 chatflow_dify_cloud.yml 解析失败: {e}")
        return errors
    workflow = ((data or {}).get("workflow") or {}).get("graph") or (data or {}).get("graph") or {}
    nodes = workflow.get("nodes") or []
    for n in nodes:
        nid = n.get("id")
        if nid not in V13_TARGET_NODES:
            continue
        data_block = n.get("data") or {}
        code_text = data_block.get("code") or ""
        if not isinstance(code_text, str):
            continue
        # 字符长度闸
        if len(code_text) > 1500:
            errors.append(
                f"V13 内联代码体积超闸：{nid} code length={len(code_text)} (>1500) — "
                "疑似回潮硬编码 registry/alias；应只做 n0 透传"
            )
        # canonical content_type 名出现次数闸
        hits = sum(1 for name in _CT_CANONICAL_NAMES if name in code_text)
        if hits >= 5:
            errors.append(
                f"V13 内联 canonical content_type 名 = {hits} (>=5) in {nid}: "
                "疑似内联 alias 大表；真源应在 content_type_canonical.csv"
            )
        # 显式 tenant_id 字面量闸（registry 回潮探测）
        for tid_literal in ("tenant_faye_main", "tenant_demo"):
            if tid_literal in code_text:
                errors.append(
                    f"V13 节点 {nid} code 出现 tenant_id 字面量 {tid_literal!r}: "
                    "registry 回潮；真源应在 tenant_scope_registry.csv"
                )
    return errors


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="KS-DIFY-ECS-008 Dify Chatflow DSL validator")
    parser.add_argument(
        "--dsl",
        type=Path,
        default=DEFAULT_DSL,
        help=f"DSL 路径，默认 {DEFAULT_DSL.relative_to(REPO_ROOT)}",
    )
    args = parser.parse_args()

    try:
        dsl = load_dsl(args.dsl)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ DSL 加载失败 / load failed: {e}", file=sys.stderr)
        return 2

    errors = validate(dsl)

    # V13 · 额外校验 Dify-flavored YAML（如 dify/chatflow_dify_cloud.yml 存在）
    yml_path = REPO_ROOT / "dify" / "chatflow_dify_cloud.yml"
    yml_errors = validate_dify_yaml_inline(yml_path) if yml_path.is_file() else []
    errors.extend(yml_errors)

    if errors:
        print(f"❌ {args.dsl.name} 校验失败 / validation failed ({len(errors)} errors):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"✅ {args.dsl.name} 校验通过 / validation passed")
    print(f"   roles checked: {len(ORDERED_ROLES)}")
    if yml_path.is_file():
        print(f"   chatflow_dify_cloud.yml V13 inline check: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

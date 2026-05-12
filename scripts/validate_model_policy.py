#!/usr/bin/env python3
"""
validate_model_policy.py · KS-POLICY-005 校验器

校验 / checks:
  M1  model_policy_version 非空 / non-empty
  M2  embedding 三件齐 / triad ready: provider + model + dimension
  M3  embedding.rebuild_required_when_changed == true（S12 硬要求）
  M4  rerank.enabled 为 bool；启用时 model 非空
  M5  rerank.fallback_when_unavailable 非空（rerank 不可用必须有降级）
  M6  llm_assist.forbidden_tasks 必含 8 类（S13 硬边界，2026-05-12 由 6 扩到 8）
  M7  llm_assist 启用时 primary.model 非空
  M8  api_key_env 引用的环境变量是否已在 .env / shell 中设置（warning 级）

退出码 / exit code: 0 全绿 / 1 fail。
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("需要 PyYAML / requires PyYAML: pip install pyyaml\n")
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "knowledge_serving" / "policies" / "model_policy.yaml"

REQUIRED_FORBIDDEN = {
    "tenant_scope_resolution",
    "brand_layer_override",
    "fallback_policy_decision",
    "merge_precedence_decision",
    "evidence_fabrication",
    "final_generation",
    "intent_classification",
    "content_type_routing",
}

errors: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def main() -> int:
    if not POLICY_PATH.exists():
        print(f"❌ 缺失 / missing: {POLICY_PATH}")
        return 2

    with POLICY_PATH.open(encoding="utf-8") as f:
        p = yaml.safe_load(f)

    # M1
    if not p.get("model_policy_version"):
        fail("M1 model_policy_version 空 / empty")

    # M2
    emb = p.get("embedding") or {}
    for k in ("provider", "model", "dimension"):
        if not emb.get(k):
            fail(f"M2 embedding.{k} 缺失 / missing")
    if emb.get("dimension") and not isinstance(emb["dimension"], int):
        fail(f"M2 embedding.dimension 不是整数 / not int: {emb['dimension']!r}")

    # M3
    if emb.get("rebuild_required_when_changed") is not True:
        fail("M3 embedding.rebuild_required_when_changed 必须为 true（S12 硬要求）")

    # M4 + M5
    rr = p.get("rerank") or {}
    if not isinstance(rr.get("enabled"), bool):
        fail("M4 rerank.enabled 必须为 bool")
    if rr.get("enabled") and not rr.get("model"):
        fail("M4 rerank.enabled=true 但 model 空")
    if not rr.get("fallback_when_unavailable"):
        fail("M5 rerank.fallback_when_unavailable 空")

    # M6 + M7
    la = p.get("llm_assist") or {}
    forbidden = set(la.get("forbidden_tasks") or [])
    missing = REQUIRED_FORBIDDEN - forbidden
    if missing:
        fail(f"M6 llm_assist.forbidden_tasks 缺以下项 / missing: {sorted(missing)}")
    if la.get("enabled"):
        primary = la.get("primary") or {}
        if not primary.get("model"):
            fail("M7 llm_assist.enabled=true 但 primary.model 空")

    # M8 env 自检 / env probe（warning 级）
    env_refs = []
    for section, sub in (("embedding", emb), ("rerank", rr)):
        if sub.get("api_key_env"):
            env_refs.append((f"{section}.api_key_env", sub["api_key_env"]))
    for role in ("primary", "fallback"):
        node = (la.get(role) or {})
        if node.get("api_key_env"):
            env_refs.append((f"llm_assist.{role}.api_key_env", node["api_key_env"]))
    for label, var in env_refs:
        if not os.environ.get(var):
            warn(f"M8 env var {var!r}（{label}）未在当前 shell / not set in shell")

    # Report
    print(f"已校验 / checked: {POLICY_PATH.name}")
    if warnings:
        print(f"\n⚠️  warnings ({len(warnings)}):")
        for w in warnings:
            print(f"   - {w}")
    if errors:
        print(f"\n❌ errors ({len(errors)}):")
        for e in errors:
            print(f"   - {e}")
        return 1
    print(f"\n✅ M1-M7 全绿 / all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

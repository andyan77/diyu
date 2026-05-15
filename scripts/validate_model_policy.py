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
import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
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


def _git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _key_fingerprint(var: str) -> str:
    val = os.environ.get(var)
    if not val:
        return "unset"
    return "sha256:" + hashlib.sha256(val.encode("utf-8")).hexdigest()[:8]


def _build_payload(env_refs: list, errs: list[str], warns: list[str],
                   policy: dict, env_label: str | None) -> dict:
    fingerprints = {var: _key_fingerprint(var) for _, var in env_refs}
    has_keys = all(v != "unset" for v in fingerprints.values())
    emb = policy.get("embedding") or {}
    rr = policy.get("rerank") or {}
    la = policy.get("llm_assist") or {}
    models_inventory = {
        "embedding": {
            "provider": emb.get("provider"),
            "model": emb.get("model"),
            "dimension": emb.get("dimension"),
            "endpoint": emb.get("endpoint"),
        },
        "rerank": {
            "enabled": rr.get("enabled"),
            "provider": rr.get("provider"),
            "model": rr.get("model"),
            "endpoint": rr.get("endpoint"),
            "fallback_when_unavailable": rr.get("fallback_when_unavailable"),
        },
        "llm_assist": {
            "enabled": la.get("enabled"),
            "primary": {
                "provider": (la.get("primary") or {}).get("provider"),
                "model": (la.get("primary") or {}).get("model"),
                "endpoint": (la.get("primary") or {}).get("endpoint"),
            },
            "fallback": {
                "provider": (la.get("fallback") or {}).get("provider"),
                "model": (la.get("fallback") or {}).get("model"),
                "endpoint": (la.get("fallback") or {}).get("endpoint"),
            },
        },
    }
    return {
        "card": "KS-POLICY-005",
        "checked_at": _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "env": env_label or ("staging" if has_keys else "no_env"),
        "git_commit": _git_commit(),
        "evidence_level": "runtime_verified" if not errs else "runtime_verified_fail",
        "policy_path": str(POLICY_PATH.relative_to(ROOT)),
        "model_policy_version": policy.get("model_policy_version"),
        "error_count": len(errs),
        "warn_count": len(warns),
        "errors": errs,
        "warnings": warns,
        "models": models_inventory,
        "key_fingerprints": fingerprints,
    }


def _write_default_report(payload: dict) -> None:
    out = ROOT / "scripts" / "validate_model_policy.report"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_out_snapshot(out_path: Path, payload: dict) -> None:
    """KS-FIX-05 §5 canonical snapshot：白名单守门，禁写 clean_output/"""
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    resolved = out_path.resolve()
    clean_output = (ROOT / "clean_output").resolve()
    if str(resolved).startswith(str(clean_output)):
        sys.stderr.write(
            f"❌ --out 拒绝指向 clean_output/ 子树 / clean_output is SSOT, not audit sink: {resolved}\n"
        )
        sys.exit(2)
    allowed_roots = [
        (ROOT / "knowledge_serving" / "audit").resolve(),
        (ROOT / "task_cards" / "corrections" / "audit").resolve(),
    ]
    if not any(str(resolved).startswith(str(r)) for r in allowed_roots):
        sys.stderr.write(f"❌ --out 路径不在允许的 audit 目录下 / illegal audit sink: {resolved}\n")
        sys.exit(2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="KS-POLICY-005 model_policy validator (KS-FIX-05 兼容 --staging/--strict/--out)"
    )
    parser.add_argument("--staging", action="store_true",
                        help="标记当前 env 为 staging（artifact 中 env=staging）")
    parser.add_argument("--strict", action="store_true",
                        help="严格模式：warn_count > 0 也按 fail 退出 1（KS-FIX-05 默认）")
    parser.add_argument("--out", default=None,
                        help="canonical snapshot 落到指定路径（必须落在 knowledge_serving/audit/ 或 "
                             "task_cards/corrections/audit/ 下；禁写 clean_output/）")
    args = parser.parse_args()

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

    # KS-POLICY-005 §8 artifact + KS-FIX-05 §5 snapshot
    env_label = "staging" if args.staging else None
    payload = _build_payload(env_refs, errors, warnings, p, env_label)
    _write_default_report(payload)
    if args.out:
        _write_out_snapshot(Path(args.out), payload)

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
    # KS-FIX-05 fail-closed: --strict 把 warn 抬成 fail（密钥漂移在 CI 阶段拦下）
    if args.strict and warnings:
        print(f"\n❌ --strict 下 warn_count={len(warnings)} > 0 → fail-closed exit 1")
        return 1
    print(f"\n✅ M1-M7 全绿 / all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""KS-FIX-19 · Dify staging 真实 import DSL + URL 对齐 + 真 chat 测试
KS-FIX-19 · Real Dify staging import + URL alignment + real chat.

红线 / Red lines:
  - 必须真打 Dify staging（DIFY_API_URL 非空 / 非 localhost / 非占位）
  - 必须先 check_dsl_url_alignment.py --strict 通过；否则拒 import
  - 不接受 mock / dry-run；--strict 模式下任意环节缺真依赖 → BLOCKED 退 1
  - 不写 clean_output/；仅落 knowledge_serving/audit/dify_app_import_KS-FIX-19.json

入参 / Inputs:
  --staging      明示打 staging
  --strict       缺 token / URL placeholder / chat 字段缺失 → exit 1
  --dsl PATH     默认 dify/chatflow.dsl
  --out PATH     默认 knowledge_serving/audit/dify_app_import_KS-FIX-19.json

退出码 / Exit code:
  0  import + chat 全通过 + artifact 写盘
  1  BLOCKED（无真 staging）或 chat 字段缺失（strict 必抛）
  2  入参 / 文件 / 前置脚本缺失
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


PLACEHOLDER_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0",
    "api.diyu.staging.internal",  # openapi.yaml 里登记的占位
    "dify.local", "example.com",
}


def _now() -> str:
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception as e:  # pragma: no cover
        return f"unknown:{e}"


def _is_placeholder_url(url: str) -> bool:
    if not url:
        return True
    lower = url.lower()
    for host in PLACEHOLDER_HOSTS:
        if host in lower:
            return True
    return False


def _build_artifact(verdict: str, reason: str, evidence: dict,
                    args, exit_code: int) -> dict:
    return {
        "task_id": "KS-FIX-19",
        "corrects": "KS-DIFY-ECS-008",
        "wave": "W12",
        "checked_at_utc": _now(),
        "git_commit": _git_commit(),
        "verdict": verdict,                # PASS / BLOCKED
        "evidence_level": evidence.get("evidence_level", "blocked"),
        "reason": reason,
        "command": (
            "source scripts/load_env.sh && "
            "python3 knowledge_serving/scripts/check_dsl_url_alignment.py --strict && "
            "python3 knowledge_serving/scripts/dify_import_and_test.py "
            + ("--staging " if args.staging else "")
            + ("--strict" if args.strict else "")
        ).strip(),
        "exit_code": exit_code,
        "dify_app_id": evidence.get("dify_app_id"),
        "chat_response_ok": evidence.get("chat_response_ok", False),
        "dify_api_url_actual": evidence.get("dify_api_url_actual"),
        "dify_api_url_is_placeholder": evidence.get("dify_api_url_is_placeholder"),
        "dify_api_key_present": evidence.get("dify_api_key_present"),
        "dify_reachable": evidence.get("dify_reachable"),
        "dsl_path": str(Path(args.dsl).relative_to(REPO_ROOT)) if Path(args.dsl).is_file() else args.dsl,
        "dsl_alignment_check": evidence.get("dsl_alignment_check"),
        "chat_response_excerpt": evidence.get("chat_response_excerpt"),
        "expected_response_fields": [
            "bundle.domain_packs", "bundle.play_cards",
            "bundle.runtime_assets", "bundle.brand_overlays",
            "bundle.evidence", "fallback_status",
        ],
        "next_steps_when_unblocked": [
            "1) 在 .env 配置 staging Dify API URL + API key（DIFY_API_URL / DIFY_API_KEY）",
            "2) 重跑本脚本 --staging --strict 取得真实 dify_app_id + chat response",
            "3) artifact verdict 由 BLOCKED 翻 PASS，再回写 KS-DIFY-ECS-008 DoD",
        ],
    }


def _run_alignment_check() -> dict:
    """前置：DSL URL 对齐校验必须先过；不过则拒后续 import。"""
    script = REPO_ROOT / "knowledge_serving" / "scripts" / "check_dsl_url_alignment.py"
    if not script.is_file():
        return {"ran": False, "exit_code": 2, "reason": "check_dsl_url_alignment.py not found"}
    proc = subprocess.run(
        [sys.executable, str(script), "--strict"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return {
        "ran": True,
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-500:],
        "stderr_tail": proc.stderr[-500:],
    }


def _probe_dify(url: str, key: str) -> dict:
    """探测 Dify staging 是否可达；只做 HEAD/GET，不做修改。"""
    if not url or _is_placeholder_url(url):
        return {"reachable": False, "reason": "placeholder_or_empty_url"}
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(url.rstrip("/") + "/info", method="GET")
        req.add_header("User-Agent", "diyu-ks-fix-19/1.0 (+https://github.com/diyu)")
        req.add_header("Accept", "application/json")
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            return {"reachable": True, "status": resp.status,
                    "body_head": resp.read(200).decode("utf-8", errors="replace")}
    except urllib.error.HTTPError as e:
        # 401 / 403 也算 reachable（服务存在但 token 错）
        return {"reachable": True, "status": e.code,
                "body_head": str(e)[:200]}
    except Exception as e:
        return {"reachable": False, "reason": f"{type(e).__name__}: {e}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--dsl", default=str(REPO_ROOT / "dify" / "chatflow.dsl"))
    ap.add_argument("--out", default=str(
        REPO_ROOT / "knowledge_serving" / "audit" / "dify_app_import_KS-FIX-19.json"))
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not Path(args.dsl).is_file():
        print(f"❌ DSL not found: {args.dsl}", file=sys.stderr)
        return 2

    align = _run_alignment_check()
    if align.get("exit_code", 1) != 0:
        artifact = _build_artifact(
            verdict="BLOCKED",
            reason="check_dsl_url_alignment.py --strict 未过；拒 import",
            evidence={"dsl_alignment_check": align, "evidence_level": "blocked"},
            args=args, exit_code=1,
        )
        out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"❌ BLOCKED: alignment failed → {out_path}", file=sys.stderr)
        return 1

    dify_url = os.environ.get("DIFY_API_URL", "").strip()
    dify_key = os.environ.get("DIFY_API_KEY", "").strip()
    url_is_placeholder = _is_placeholder_url(dify_url)

    probe = _probe_dify(dify_url, dify_key)

    evidence_base = {
        "dsl_alignment_check": align,
        "dify_api_url_actual": dify_url or None,
        "dify_api_url_is_placeholder": url_is_placeholder,
        "dify_api_key_present": bool(dify_key),
        "dify_reachable": probe.get("reachable", False),
        "dify_probe": probe,
        "evidence_level": "blocked",
    }

    # ---- fail-closed 真依赖检查 ----
    blocked_reasons: list[str] = []
    if not args.staging:
        blocked_reasons.append("missing_--staging_flag")
    if not dify_url:
        blocked_reasons.append("DIFY_API_URL_unset")
    if url_is_placeholder:
        blocked_reasons.append(f"DIFY_API_URL_is_placeholder ({dify_url!r})")
    if not dify_key:
        blocked_reasons.append("DIFY_API_KEY_unset")
    if not probe.get("reachable"):
        blocked_reasons.append(f"dify_unreachable: {probe.get('reason')}")

    if blocked_reasons:
        evidence_base["chat_response_ok"] = False
        evidence_base["dify_app_id"] = None
        artifact = _build_artifact(
            verdict="BLOCKED",
            reason="; ".join(blocked_reasons),
            evidence=evidence_base,
            args=args, exit_code=1 if args.strict else 0,
        )
        out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"❌ BLOCKED: {artifact['reason']}", file=sys.stderr)
        print(f"   artifact → {out_path}", file=sys.stderr)
        return 1 if args.strict else 0

    # ---- 真 chat 调用 / real /chat-messages call ----
    # Dify Cloud 不开放 DSL import 的 Console API；DSL 已由用户手动 import 并 publish。
    # 本脚本以 chat_response_ok + 6 字段出现作为 KS-DIFY-ECS-008 真实运行证据。
    dify_app_id = os.environ.get("DIFY_APP_ID", "").strip() or None
    chat_evidence = _real_chat_call(dify_url, dify_key)

    chat_ok = chat_evidence.get("chat_response_ok", False)
    if chat_ok:
        verdict = "PASS"
        evidence_level = "runtime_verified"
        reason = "Dify staging chat-messages 真调通 + 期望字段齐"
        exit_code = 0
    else:
        verdict = "BLOCKED"
        evidence_level = "blocked"
        reason = f"chat call failed: {chat_evidence.get('fail_reason', 'unknown')}"
        exit_code = 1 if args.strict else 0

    artifact = _build_artifact(
        verdict=verdict,
        reason=reason,
        evidence={
            **evidence_base,
            "evidence_level": evidence_level,
            "dify_app_id": dify_app_id,
            "chat_response_ok": chat_ok,
            "chat_response_excerpt": chat_evidence.get("excerpt"),
            "chat_call": chat_evidence,
        },
        args=args, exit_code=exit_code,
    )
    out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    marker = "✅ PASS" if chat_ok else "❌ BLOCKED"
    print(f"{marker}: {reason} → {out_path}", file=sys.stderr)
    return exit_code


def _real_chat_call(dify_url: str, dify_key: str) -> dict:
    """真打 Dify /chat-messages（blocking 模式），断言 6 个期望字段都出现。

    期望字段（见 _build_artifact.expected_response_fields）：
      bundle.domain_packs / play_cards / runtime_assets / brand_overlays / evidence
      + fallback_status
    判定：HTTP 200 且响应文本里这 6 个字段名全部出现 → chat_response_ok=True。
    """
    import json as _json
    import urllib.request
    import urllib.error

    url = dify_url.rstrip("/") + "/chat-messages"
    body = {
        "inputs": {
            "tenant_id_hint": "tenant_faye_main",
            "intent_hint": "content_generation",
            "content_type_hint": "outfit_of_the_day",
            "business_brief_json": _json.dumps({
                "sku": "FAYE-OW-2026SS-001",
                "category": "outerwear",
                "season": "spring",
                "channel": ["xiaohongshu"],
                "price_band": {"currency": "CNY", "min": 1280, "max": 1680},
            }, ensure_ascii=False),
        },
        "query": "给我一条今日穿搭文案",
        "response_mode": "blocking",
        "user": "ks-fix-19-audit",
    }
    data = _json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {dify_key}",
            "Content-Type": "application/json",
            "User-Agent": "diyu-ks-fix-19/1.0 (+https://github.com/diyu)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            status = resp.status
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return {
            "chat_response_ok": False,
            "fail_reason": f"HTTP {e.code}",
            "http_status": e.code,
            "excerpt": (e.read().decode("utf-8", errors="replace")[:800] if hasattr(e, "read") else str(e)[:800]),
        }
    except Exception as e:
        return {"chat_response_ok": False, "fail_reason": f"{type(e).__name__}: {e}"}

    expected = ["domain_packs", "play_cards", "runtime_assets",
                "brand_overlays", "evidence", "fallback_status"]
    missing = [f for f in expected if f not in text]
    return {
        "chat_response_ok": (status == 200 and not missing),
        "http_status": status,
        "missing_fields": missing,
        "excerpt": text[:800],
        "fail_reason": (None if (status == 200 and not missing)
                        else f"missing_fields={missing}" if status == 200
                        else f"http_status={status}"),
    }


if __name__ == "__main__":
    sys.exit(main())

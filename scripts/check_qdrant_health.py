#!/usr/bin/env python3
"""
check_qdrant_health.py · KS-S0-004 健康检查 / Qdrant health check
================================================================
用法 / usage:
  python3 scripts/check_qdrant_health.py --env staging        # 探活
  python3 scripts/check_qdrant_health.py --env staging --strict  # 失败即 exit 1

退出码 / exit:
  0  健康 / healthy
  1  非健康 / unhealthy 或不可达 / unreachable
  2  环境错 / env misconfigured

落盘 / artifact:
  clean_output/audit/qdrant_health_KS-S0-004.json
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "clean_output" / "audit" / "qdrant_health_KS-S0-004.json"

PROBES = [
    ("/", "service banner"),
    ("/healthz", "healthz endpoint"),
    ("/readyz", "readyz endpoint"),
    ("/collections", "collections list"),
]

ALLOWED_ENVS = {"staging", "dev"}  # prod 禁止从这个脚本直接探，避免误触


def probe(url: str, timeout: int = 5) -> tuple[int, str]:
    """单次 HTTP 探活；返回 (http_code, body[:200])"""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(200).decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return -1, str(e)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, choices=sorted(ALLOWED_ENVS),
                    help="staging / dev（禁止 prod / forbid prod）")
    ap.add_argument("--strict", action="store_true",
                    help="任一探活失败即 exit 1 / fail-closed")
    args = ap.parse_args()

    base = os.environ.get("QDRANT_URL_STAGING", "").rstrip("/")
    if not base:
        print("❌ QDRANT_URL_STAGING 未设置 / not set in env")
        print("   先 source scripts/load_env.sh，或手动 export")
        return 2

    print(f"=== Qdrant 健康检查 / health check · env={args.env} ===")
    print(f"base URL: {base}\n")

    results = []
    all_pass = True
    for path, label in PROBES:
        url = base + path
        t0 = time.time()
        code, body = probe(url)
        elapsed_ms = int((time.time() - t0) * 1000)
        ok = code == 200
        all_pass = all_pass and ok
        mark = "✅" if ok else "❌"
        print(f"  {mark} {path:15s} HTTP {code:>4} · {elapsed_ms:>4}ms · {label}")
        results.append({
            "path": path,
            "label": label,
            "http_code": code,
            "ok": ok,
            "elapsed_ms": elapsed_ms,
            "body_preview": body[:120],
        })

    print()
    if all_pass:
        print("✅ 全部探活通过 / all probes passed")
        overall = "healthy"
    else:
        print("❌ 部分探活失败 / some probes failed")
        overall = "unhealthy"

    # 落盘 / write audit
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    audit = {
        "task_card": "KS-S0-004",
        "env": args.env,
        "base_url": base,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall": overall,
        "probes": results,
        "fallback_signal": "structured_only" if not all_pass else "none",
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n落盘 / artifact: {AUDIT.relative_to(ROOT)}")

    if args.strict and not all_pass:
        return 1
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

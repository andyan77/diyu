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
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIT = ROOT / "clean_output" / "audit" / "qdrant_health_KS-S0-004.json"

PROBES = [
    ("/", "service banner"),
    ("/healthz", "healthz endpoint"),
    ("/readyz", "readyz endpoint"),
    ("/collections", "collections list"),
]

ALLOWED_ENVS = {"staging", "dev"}  # prod 禁止从这个脚本直接探，避免误触


def probe(url: str, timeout: int = 5, full_body: bool = False) -> tuple[int, str]:
    """单次 HTTP 探活；返回 (http_code, body)
    full_body=False 截断到 200 字节（探活）；True 取完整（解析 version / collections）"""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read() if full_body else resp.read(200)
            body = raw.decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return -1, str(e)


def extract_version(base: str) -> str | None:
    """解析 / banner JSON 取 version / 版本号"""
    code, body = probe(base + "/", timeout=5, full_body=True)
    if code != 200:
        return None
    try:
        data = json.loads(body)
        return data.get("version")
    except (ValueError, json.JSONDecodeError):
        return None


def extract_collections(base: str) -> list[str] | None:
    """解析 /collections JSON 取 collection name 列表"""
    code, body = probe(base + "/collections", timeout=5, full_body=True)
    if code != 200:
        return None
    try:
        data = json.loads(body)
        result = data.get("result", {})
        cols = result.get("collections", []) if isinstance(result, dict) else []
        return [c.get("name") for c in cols if isinstance(c, dict) and c.get("name")]
    except (ValueError, json.JSONDecodeError):
        return None


def git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False, cwd=str(ROOT),
        )
        return out.stdout.strip() or None
    except (FileNotFoundError, OSError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, choices=sorted(ALLOWED_ENVS),
                    help="staging / dev（禁止 prod / forbid prod）")
    ap.add_argument("--strict", action="store_true",
                    help="任一探活失败即 exit 1 / fail-closed")
    ap.add_argument("--out", default=None,
                    help="artifact 落盘路径（默认 clean_output/audit/qdrant_health_KS-S0-004.json）")
    ap.add_argument("--task-card", default="KS-S0-004",
                    help="artifact 中 task_card 字段（FIX-01 用 KS-FIX-01）")
    args = ap.parse_args()
    audit_path = Path(args.out) if args.out else DEFAULT_AUDIT
    if not audit_path.is_absolute():
        audit_path = ROOT / audit_path

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

    # 富化字段（FIX-01 §5 schema 要求）/ enrich for FIX-01 schema
    version = extract_version(base) if all_pass else None
    collections = extract_collections(base) if all_pass else None
    commit = git_commit()

    # FIX-01 §6 对抗性测试硬门 / FIX-01 §6 adversarial gates
    # version 缺失 / collections 空 → fail_closed，即便所有 probe 200
    warnings: list[str] = []
    schema_ok = True
    if all_pass:
        if not version:
            warnings.append("missing_version")
            schema_ok = False
        if collections is None:
            warnings.append("collections_unreadable")
            schema_ok = False
        elif len(collections) == 0:
            warnings.append("empty_collections")
            schema_ok = False

    final_pass = all_pass and schema_ok
    if all_pass and not schema_ok:
        print(f"❌ schema 校验失败 / schema gate failed: {','.join(warnings)}")
        overall = "unhealthy"

    # 落盘 / write audit
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit = {
        "task_card": args.task_card,
        "env": args.env,
        "base_url": base,
        "qdrant_url": base,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall": overall,
        "version": version,
        "collections": collections,
        "evidence_level": "runtime_verified" if final_pass else "fail_closed",
        "warnings": warnings,
        "git_commit": commit,
        "probes": results,
        "fallback_signal": "structured_only" if not final_pass else "none",
    }
    # 幂等写入 / idempotent write（KS-FIX-02 外审第 3 轮收口 blocker D）：
    # 如果磁盘上既有 audit 的语义字段（剥离 checked_at / git_commit / per-probe elapsed_ms）与本次相同，
    # 跳过 write，避免 mirror drift 源头无意义重写 clean_output/。
    def _semantic_view(a: dict) -> dict:
        # 剥离非语义字段：checked_at / git_commit / per-probe elapsed_ms 与 body_preview。
        # body_preview 含 Qdrant 内部 "time":4.385e-6 这种 per-request 抖动值，
        # 不能作为"健康状态是否变化"的判据；http_code + ok + path 才是真信号。
        v = {k: a[k] for k in a if k not in ("checked_at", "git_commit")}
        v["probes"] = [
            {k: p[k] for k in p if k not in ("elapsed_ms", "body_preview")}
            for p in a.get("probes", [])
        ]
        return v

    new_view = _semantic_view(audit)
    will_write = True
    if audit_path.exists():
        try:
            old = json.loads(audit_path.read_text(encoding="utf-8"))
            if _semantic_view(old) == new_view:
                will_write = False
        except (json.JSONDecodeError, OSError):
            pass

    if will_write:
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        action = "落盘 / artifact"
    else:
        action = "幂等跳过 / idempotent skip (semantic fields unchanged)"
    try:
        rel = audit_path.relative_to(ROOT)
        print(f"\n{action}: {rel}")
    except ValueError:
        print(f"\n{action}: {audit_path}")

    if args.strict and not final_pass:
        return 1
    return 0 if final_pass else 1


if __name__ == "__main__":
    sys.exit(main())

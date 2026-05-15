#!/usr/bin/env python3
"""KS-FIX-19 · Dify chatflow DSL ↔ FastAPI openapi URL 对齐校验
KS-FIX-19 · Dify chatflow DSL ↔ FastAPI openapi URL alignment check.

目的 / Purpose:
  原 KS-DIFY-ECS-008 只跑本地 DSL validate，没 fail-closed URL 漂移。
  本脚本：把 DSL 里所有 http_request 节点的 URL 提取出来，剥掉
  ${SERVING_API_BASE} 前缀，与 FastAPI openapi.yaml 的 paths 集合
  以及 FastAPI app 真实路由集合做交叉比对；任意一边漂移即 fail-closed。

入参 / Inputs:
  --strict   缺路径 / 漂移 / DSL 与 app 不一致 → exit 1
  --dsl PATH        默认 dify/chatflow.dsl
  --openapi PATH    默认 knowledge_serving/serving/api/openapi.yaml

退出码 / Exit code:
  0  对齐通过
  1  漂移（strict 模式必抛）
  2  入参 / 文件结构问题

不依赖外部网络；不写 clean_output/。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _extract_dsl_urls(dsl_text: str) -> list[dict]:
    """提取 DSL 里 http_request 节点的 method + url 对（按 yaml 文本扫描）。"""
    rows: list[dict] = []
    cur_id: str | None = None
    cur_type: str | None = None
    cur_method: str | None = None
    for raw in dsl_text.splitlines():
        line = raw.rstrip()
        m = re.match(r"^\s*-\s*id:\s*(\S+)", line)
        if m:
            cur_id = m.group(1)
            cur_type = None
            cur_method = None
            continue
        m = re.match(r"^\s*type:\s*(\S+)", line)
        if m and cur_id:
            cur_type = m.group(1)
            continue
        m = re.match(r"^\s*method:\s*(\S+)", line)
        if m and cur_id:
            cur_method = m.group(1).upper()
            continue
        m = re.match(r"^\s*url:\s*['\"]?([^'\"]+)['\"]?\s*$", line)
        if m and cur_id and cur_type == "http_request":
            rows.append({
                "node_id": cur_id,
                "method": cur_method or "POST",
                "url_raw": m.group(1),
            })
    return rows


def _strip_base(url_raw: str) -> str | None:
    """剥掉 ${SERVING_API_BASE} 前缀，返回纯 path；其他绝对 URL 返回 None。"""
    if url_raw.startswith("${SERVING_API_BASE}"):
        return url_raw[len("${SERVING_API_BASE}"):]
    if url_raw.startswith("http://") or url_raw.startswith("https://"):
        # 绝对 URL 不允许 — 必须走 ${SERVING_API_BASE} 占位
        return None
    return url_raw


def _load_openapi_paths(openapi_path: Path) -> dict[str, set[str]]:
    """从 openapi.yaml 文本扫出 path → method 集合。
    不引入 PyYAML 依赖，按层级缩进做最小扫描。
    """
    paths: dict[str, set[str]] = {}
    in_paths = False
    cur_path: str | None = None
    for raw in openapi_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("paths:"):
            in_paths = True
            continue
        if in_paths:
            if raw and not raw[0].isspace():
                in_paths = False
                continue
            m = re.match(r"^  (/\S*):\s*$", raw)
            if m:
                cur_path = m.group(1)
                paths.setdefault(cur_path, set())
                continue
            m = re.match(r"^    (get|post|put|delete|patch):\s*$", raw)
            if m and cur_path:
                paths[cur_path].add(m.group(1).upper())
    return paths


def _load_app_routes() -> dict[str, set[str]]:
    """加载真 FastAPI app，枚举所有 (path, method) — 真源 #2。"""
    sys.path.insert(0, str(REPO_ROOT))
    from knowledge_serving.serving.api.retrieve_context import create_app  # noqa
    app = create_app()
    routes: dict[str, set[str]] = {}
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None) or set()
        if not path or not methods:
            continue
        # 跳过 FastAPI 内置 /openapi.json / /docs / /redoc
        if path in {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}:
            continue
        routes.setdefault(path, set()).update(m.upper() for m in methods if m.upper() != "HEAD")
    return routes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsl", default=str(REPO_ROOT / "dify" / "chatflow.dsl"))
    ap.add_argument("--openapi", default=str(REPO_ROOT / "knowledge_serving" / "serving" / "api" / "openapi.yaml"))
    ap.add_argument("--strict", action="store_true", help="任何漂移 → exit 1")
    args = ap.parse_args()

    dsl_path = Path(args.dsl)
    openapi_path = Path(args.openapi)
    if not dsl_path.is_file():
        print(f"❌ DSL not found: {dsl_path}", file=sys.stderr)
        return 2
    if not openapi_path.is_file():
        print(f"❌ openapi not found: {openapi_path}", file=sys.stderr)
        return 2

    dsl_rows = _extract_dsl_urls(dsl_path.read_text(encoding="utf-8"))
    openapi_paths = _load_openapi_paths(openapi_path)
    app_routes = _load_app_routes()

    findings: list[dict] = []
    aligned: list[dict] = []

    for row in dsl_rows:
        stripped = _strip_base(row["url_raw"])
        check = {
            "node_id": row["node_id"],
            "method": row["method"],
            "url_raw": row["url_raw"],
            "stripped_path": stripped,
            "in_openapi": False,
            "in_app": False,
            "method_in_openapi": False,
            "method_in_app": False,
        }
        if stripped is None:
            check["error"] = "absolute_url_not_allowed"
            findings.append(check)
            continue
        if stripped in openapi_paths:
            check["in_openapi"] = True
            check["method_in_openapi"] = row["method"] in openapi_paths[stripped]
        if stripped in app_routes:
            check["in_app"] = True
            check["method_in_app"] = row["method"] in app_routes[stripped]

        if not (check["in_openapi"] and check["in_app"]
                and check["method_in_openapi"] and check["method_in_app"]):
            findings.append(check)
        else:
            aligned.append(check)

    # 反向：openapi 声明了但 app 未实现的（漂移另一向）
    spec_only_paths = sorted(set(openapi_paths) - set(app_routes))

    report = {
        "checked_at_utc": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dsl_path": str(dsl_path.relative_to(REPO_ROOT)),
        "openapi_path": str(openapi_path.relative_to(REPO_ROOT)),
        "dsl_http_request_count": len(dsl_rows),
        "aligned_count": len(aligned),
        "drift_count": len(findings),
        "aligned": aligned,
        "drift": findings,
        "openapi_paths_not_in_app": spec_only_paths,
        "strict_mode": args.strict,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if findings:
        if args.strict:
            print(f"❌ FAIL-CLOSED: {len(findings)} DSL URL(s) 漂移", file=sys.stderr)
            return 1
        print(f"⚠️  {len(findings)} DSL URL(s) 漂移（非 strict，仅警告）", file=sys.stderr)
        return 0
    print(f"✅ {len(aligned)} DSL URL(s) 与 openapi + FastAPI app 全对齐", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

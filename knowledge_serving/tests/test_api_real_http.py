"""KS-FIX-16 §5 / §8 — real HTTP wire 测：API 真接 ECS staging vector path.

设计：
- 默认 SKIP（无 STAGING_API_BASE env 时），不污染本地 CI
- env STAGING_API_BASE=https://kb.diyuai.cc → 5+ 真 POST 全 200 + vector_meta.candidate_count>0
- TestClient 冒充检查：base_url 必须 http(s):// + 非 localhost / 127.0.0.1 / testserver
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request

import pytest

API_BASE = os.environ.get("STAGING_API_BASE")
PROBE_BODIES = [
    {"tenant_id": "tenant_faye_main", "user_query": "ECS 真 HTTP wire 测 1 大衣搭配陈列要点",
     "content_type": "knowledge_sharing", "intent_hint": "content_generation"},
    {"tenant_id": "tenant_demo", "user_query": "ECS 真 HTTP wire 测 2 门店接客流程",
     "content_type": "daily_fragment", "intent_hint": "content_generation"},
    {"tenant_id": "tenant_faye_main", "user_query": "ECS 真 HTTP wire 测 3 创始人故事",
     "content_type": "founder_ip", "intent_hint": "content_generation"},
    {"tenant_id": "tenant_demo", "user_query": "ECS 真 HTTP wire 测 4 羊毛面料保养",
     "content_type": "knowledge_sharing", "intent_hint": "content_generation"},
    {"tenant_id": "tenant_faye_main", "user_query": "ECS 真 HTTP wire 测 5 试衣间礼仪",
     "content_type": "behind_the_scenes", "intent_hint": "content_generation"},
]


@pytest.fixture(scope="module")
def base_url() -> str:
    if not API_BASE:
        pytest.skip("STAGING_API_BASE not set; skip real-HTTP suite (set STAGING_API_BASE=https://kb.diyuai.cc to enable)")
    return API_BASE.rstrip("/")


def test_base_url_not_testclient(base_url: str) -> None:
    """KS-FIX-16 §6 row 1 fail-closed：base_url 必须 http(s):// + 不能是 testserver/localhost."""
    assert base_url.startswith(("http://", "https://")), f"base_url 必须 http(s)://；got {base_url!r}"
    forbidden = ("testserver", "localhost", "127.0.0.1")
    host = base_url.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0]
    assert host not in forbidden, f"base_url host {host!r} ∈ testclient/loopback 黑名单"


def test_no_unguarded_vector_res_none_in_source() -> None:
    """KS-FIX-16 §6 row 2：vector_res=None 只能出现在 `req.structured_only` 显式开关分支."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "serving/api/retrieve_context.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    for i, line in enumerate(lines):
        if "vector_res = None" in line and "#" not in line.split("vector_res", 1)[0]:
            window = "\n".join(lines[max(0, i-4): i+1])
            assert "structured_only" in window, (
                f"unguarded `vector_res = None` at line {i+1}:\n{window}\n"
                "must be inside `if req.structured_only:` branch"
            )


def _post(url: str, body: dict, retries: int = 3) -> tuple[int, dict | None]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, socket.gaierror, TimeoutError) as e:
            last_err = e
            time.sleep(2)
    raise RuntimeError(f"real HTTP failed after {retries} attempts: {last_err}")


def test_real_http_200_at_least_5(base_url: str) -> None:
    """KS-FIX-16 §8 pass：real_http_200_count >= 5 且 vector_res 非空."""
    url = f"{base_url}/v1/retrieve_context"
    ok_count = 0
    vec_hits_count = 0
    for body in PROBE_BODIES:
        status, payload = _post(url, body)
        assert status == 200, f"probe {body['user_query']!r} got {status}, payload={payload}"
        assert payload is not None
        assert payload.get("status") == "ok"
        ok_count += 1
        vm = payload.get("meta", {}).get("vector_meta") or {}
        if vm.get("mode") == "vector" and (vm.get("candidate_count") or 0) > 0:
            vec_hits_count += 1
    assert ok_count >= 5, f"real_http_200_count={ok_count} < 5"
    assert vec_hits_count >= 5, f"vector_hits>0 count={vec_hits_count} < 5"


def test_ecs_container_healthz_via_ssh() -> None:
    """KS-FIX-16 §10 row 3 / §6 row 3：ECS 容器 /healthz 真返 200.

    note：nginx 不暴露 /healthz 到公网（按 KS-CD-003 §8 设计只代理 /v1/* 和 /internal/*），
    所以本测通过 SSH 直接 curl 容器 127.0.0.1:8005/healthz。
    """
    if not (os.environ.get("ECS_HOST") and os.environ.get("ECS_USER") and os.environ.get("ECS_SSH_KEY_PATH")):
        pytest.skip("ECS SSH env not set; cannot probe container /healthz")
    import subprocess
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
         "-i", os.environ["ECS_SSH_KEY_PATH"],
         f"{os.environ['ECS_USER']}@{os.environ['ECS_HOST']}",
         'curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1:8005/healthz'],
        capture_output=True, text=True, timeout=15,
    )
    assert r.returncode == 0, f"SSH probe failed: rc={r.returncode} stderr={r.stderr!r}"
    assert r.stdout.strip() == "200", f"container /healthz returned {r.stdout!r}"

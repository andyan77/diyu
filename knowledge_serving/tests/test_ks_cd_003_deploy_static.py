"""KS-CD-003 Layer 1 · 静态对抗性测试 / static adversarial tests.

执行 task_cards/KS-CD-003.md §6 + §10 红线对抗性测试。
不需要起容器、不需要 docker；纯文本扫描 + 配置 parse。

被测对象路径（实现还没写时，本文件 fail-red）：
  - knowledge_serving/serving/api/Dockerfile
  - scripts/deploy_serving_to_ecs.sh
  - ops/nginx/serving.location.conf
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "knowledge_serving" / "serving" / "api" / "Dockerfile"
DEPLOY_SH = REPO_ROOT / "scripts" / "deploy_serving_to_ecs.sh"
NGINX_CONF = REPO_ROOT / "ops" / "nginx" / "serving.location.conf"


# ============================================================
# T-S1 · Dockerfile 代码隔离 / code isolation
# ============================================================

def _dockerfile_copy_sources() -> list[str]:
    """返回 Dockerfile 所有 COPY 指令的源路径（第一个参数）。"""
    if not DOCKERFILE.exists():
        pytest.fail(f"Dockerfile missing: {DOCKERFILE}")
    sources: list[str] = []
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        # ignore line continuations etc.; just match COPY <src...> <dst>
        m = re.match(r"^COPY\s+(?:--[\w=:-]+\s+)*(.+)\s+\S+\s*$", stripped, re.IGNORECASE)
        if not m:
            continue
        # the captured group may have multiple sources space-separated
        for tok in m.group(1).split():
            sources.append(tok)
    return sources


def test_dockerfile_only_copies_whitelisted_paths():
    """T-S1 · Dockerfile 只能 COPY whitelist 路径，禁止把整个仓库 / diyu-agent 塞进镜像。"""
    sources = _dockerfile_copy_sources()
    assert sources, "Dockerfile has no COPY instructions — implementation incomplete"

    whitelist_prefixes = (
        "knowledge_serving/",
        "requirements",  # requirements.txt / requirements-serving.txt
        "scripts/load_env.sh",  # env loader if needed (read-only at build time? prefer no)
    )
    blacklist_exact = {".", "..", "/", "*"}
    forbidden_substrs = ("diyu-agent", "src/main.py", "src/")

    for src in sources:
        assert src not in blacklist_exact, (
            f"Dockerfile COPY src={src!r} is a wildcard ('.' / '/') — "
            "would include diyu-agent code or repo secrets; pin to knowledge_serving/"
        )
        for bad in forbidden_substrs:
            assert bad not in src, (
                f"Dockerfile COPY src={src!r} contains forbidden substring {bad!r} "
                "(violates code isolation red line)"
            )
        # must start with a whitelisted prefix
        assert any(src.startswith(p) for p in whitelist_prefixes), (
            f"Dockerfile COPY src={src!r} not in whitelist {whitelist_prefixes}"
        )


def test_dockerfile_no_root_user():
    """T-S2 · Dockerfile 必须切到非 root user（最小权限 / least privilege）。"""
    if not DOCKERFILE.exists():
        pytest.fail(f"Dockerfile missing: {DOCKERFILE}")
    txt = DOCKERFILE.read_text(encoding="utf-8")
    # last USER directive must not be root / 0
    user_lines = [ln.strip() for ln in txt.splitlines() if ln.strip().upper().startswith("USER ")]
    assert user_lines, (
        "Dockerfile missing USER directive — container would run as root "
        "(violates least-privilege)"
    )
    last_user = user_lines[-1].split()[1].strip().strip('"').strip("'")
    assert last_user not in ("root", "0"), (
        f"Dockerfile last USER={last_user!r}; must be non-root for least-privilege"
    )


# ============================================================
# T-S3 / T-S4 · deploy_serving_to_ecs.sh 守门
# ============================================================

def _load_deploy_script() -> str:
    if not DEPLOY_SH.exists():
        pytest.fail(f"deploy_serving_to_ecs.sh missing: {DEPLOY_SH}")
    return DEPLOY_SH.read_text(encoding="utf-8")


def _split_dry_run_apply_blocks(text: str) -> tuple[str, str]:
    """非常粗的分块：取 --dry-run 分支体 vs --apply 分支体。

    依赖脚本内有形如 'if [[ $MODE == dry-run ]]; then ... else ... fi'
    或 'case $MODE in dry-run) ... ;; apply) ... ;; esac' 的结构。
    若无法识别，返回 (full, full) 让后续断言保守判定。
    """
    # case-style
    m = re.search(
        r"case\s+[^)]+\)\s*(.*?)\s*dry[_-]run\)\s*(.*?)\s*;;\s*apply\)\s*(.*?)\s*;;\s*esac",
        text, re.DOTALL,
    )
    if m:
        return m.group(2), m.group(3)
    # if/else-style
    m = re.search(
        r"if\s+\[\[\s+[^\]]*dry[_-]run[^\]]*\]\];\s*then\s*(.*?)\s*else\s*(.*?)\s*fi",
        text, re.DOTALL,
    )
    if m:
        return m.group(1), m.group(2)
    return text, text


def test_deploy_script_dry_run_does_not_mutate_ecs():
    """T-S3 · --dry-run 分支禁止出现真改 ECS 的指令；只能在 --apply 分支出现。"""
    txt = _load_deploy_script()
    dry_block, apply_block = _split_dry_run_apply_blocks(txt)

    # these patterns are "真改 ECS" — must not appear in dry-run branch
    forbidden_in_dry = [
        r"\bssh\b[^\n]*\bdocker\s+run\b",
        r"\bssh\b[^\n]*\bdocker\s+stop\b",
        r"\bssh\b[^\n]*\bdocker\s+rm\b",
        r"\bssh\b[^\n]*\bdocker\s+load\b",
        r"\bscp\b\s+\S+\s+\S+@",  # local→remote scp
        r"\bssh\b[^\n]*\bsystemctl\s+restart\b",
        r"\bssh\b[^\n]*\bnginx\s+-s\s+reload\b",
    ]
    for pat in forbidden_in_dry:
        if re.search(pat, dry_block):
            pytest.fail(
                f"--dry-run branch contains ECS-mutating pattern {pat!r}; "
                "dry-run must not modify ECS state"
            )

    # apply branch must contain at least one of these (otherwise apply is a no-op)
    assert re.search(r"docker\s+(run|load|stop|rm)", apply_block) or \
           re.search(r"\bscp\b", apply_block), (
        "--apply branch lacks any real action (docker run/load/stop/rm or scp); "
        "implementation incomplete"
    )


def test_deploy_script_has_no_reverse_dataflow():
    """T-S4 · 禁止 ECS→local 反向数据流（违反 SSOT direction 红线）。"""
    txt = _load_deploy_script()

    # ssh dump → local
    bad_patterns = [
        # scp remote:path -> local
        r"\bscp\b\s+[a-zA-Z0-9_.\-]+@[^\s]+:[^\s]+\s+[^\s@]+\s*$",
        # ssh ... pg_dump > /local/path
        r"\bssh\b[^\n]*pg_dump[^\n]*>\s*[^\s]+",
        # rsync remote:src local
        r"\brsync\b[^\n]*[a-zA-Z0-9_.\-]+@[^\s]+:[^\s]+\s+[^\s@]+",
    ]
    for pat in bad_patterns:
        m = re.search(pat, txt, re.MULTILINE)
        assert not m, (
            f"deploy script contains reverse dataflow pattern {pat!r}: {m.group(0) if m else ''!r}; "
            "violates 'local is SSOT, ECS is mirror' red line"
        )


def test_deploy_script_writes_audit():
    """部署脚本必须写 audit JSON（任何 mode 都写，含 env / git_commit / evidence_level）。"""
    txt = _load_deploy_script()
    assert "knowledge_serving/audit/deploy_serving_KS-CD-003" in txt, (
        "deploy script does not reference canonical audit path "
        "knowledge_serving/audit/deploy_serving_KS-CD-003.json"
    )
    for field in ("env", "git_commit", "evidence_level"):
        assert field in txt, f"deploy script missing audit field {field!r}"


# ============================================================
# T-S5 · nginx 路由不与 diyu-agent 重叠
# ============================================================

def _parse_nginx_locations(text: str) -> list[str]:
    """提取所有 location 指令的 path。"""
    paths = []
    for m in re.finditer(r"location\s+(=\s+|~\s+|~\*\s+|\^~\s+)?([^\s{]+)\s*\{", text):
        paths.append(m.group(2))
    return paths


def test_nginx_locations_no_overlap_with_diyu_agent():
    """T-S5 · 三条 location 前缀不与 diyu-agent 的 /api/v1/integrations/ 重叠，也不能是 '/'。"""
    if not NGINX_CONF.exists():
        pytest.fail(f"nginx serving.location.conf missing: {NGINX_CONF}")
    txt = NGINX_CONF.read_text(encoding="utf-8")
    paths = _parse_nginx_locations(txt)
    assert paths, "nginx conf has no location directives"

    expected = {
        "/v1/retrieve_context",
        "/v1/guardrail",
        "/internal/context_bundle_log",
    }
    forbidden = {"/", "/api/v1/integrations", "/api/v1/integrations/"}

    for p in paths:
        assert p not in forbidden, (
            f"nginx location {p!r} would shadow diyu-agent route; violates route isolation"
        )

    missing = expected - set(paths)
    assert not missing, f"nginx conf missing expected locations: {missing}"


def test_nginx_proxy_pass_only_to_serving_port():
    """三条 location 的 proxy_pass 必须指向 127.0.0.1:8005（diyu-serving 容器），不能指向 diyu-agent (8004)。"""
    if not NGINX_CONF.exists():
        pytest.fail(f"nginx serving.location.conf missing: {NGINX_CONF}")
    txt = NGINX_CONF.read_text(encoding="utf-8")
    proxies = re.findall(r"proxy_pass\s+(http://[^\s;]+)", txt)
    assert proxies, "nginx conf has no proxy_pass directives"
    for tgt in proxies:
        assert "127.0.0.1:8005" in tgt or "localhost:8005" in tgt, (
            f"proxy_pass target {tgt!r} not on 8005 (diyu-serving); "
            "route would leak to diyu-agent or wrong service"
        )
        assert "8004" not in tgt, (
            f"proxy_pass target {tgt!r} points at 8004 (diyu-agent); "
            "violates process isolation"
        )

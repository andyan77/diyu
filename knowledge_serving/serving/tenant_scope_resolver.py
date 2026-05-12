"""KS-RETRIEVAL-001 · tenant_scope_resolver
多租户隔离入口 / multi-tenant isolation entrypoint.

硬纪律 / hard rules:
- 仅从 tenant_scope_registry.csv 推断 brand_layer / allowed_layers
- 禁止任何自然语言入参（user_query / query / text 等）
- 禁止任何大模型 / language-model 调用
- fail-closed：未登记 / 未启用 / api_key mismatch → raise
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = (
    REPO_ROOT / "knowledge_serving" / "control" / "tenant_scope_registry.csv"
)

# 与 _common.BRAND_LAYER_RE 同义；避免 import 控制层避免循环依赖
_BRAND_LAYER_RE = re.compile(r"^(domain_general|needs_review|brand_[a-z][a-z0-9_]*)$")
_ENVIRONMENT_ENUM = {"dev", "staging", "prod"}
_REQUIRED_COLUMNS = (
    "tenant_id", "api_key_id", "brand_layer", "allowed_layers",
    "default_platforms", "policy_level", "enabled", "environment",
)


class TenantNotAuthorized(Exception):
    """租户未登记 / disabled / api_key mismatch / not authorized."""


class RegistryCorrupted(Exception):
    """registry CSV 结构损坏 / corrupted on-disk registry."""


# 模块级缓存：{tenant_id -> resolved row dict}
_REGISTRY: dict[str, dict[str, Any]] = {}
_REGISTRY_PATH: Path = DEFAULT_REGISTRY_PATH


def _parse_json_list(raw: str, *, field: str, tenant_id: str) -> list[str]:
    try:
        v = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        raise RegistryCorrupted(
            f"{field} 不是合法 JSON / invalid JSON (tenant={tenant_id}): {raw!r}"
        ) from e
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise RegistryCorrupted(
            f"{field} 必须为 list[str] / must be list[str] (tenant={tenant_id}): {v!r}"
        )
    return v


def _parse_bool(raw: str, *, tenant_id: str) -> bool:
    s = (raw or "").strip().lower()
    if s == "true":
        return True
    if s == "false":
        return False
    raise RegistryCorrupted(
        f"enabled 必须 true/false (tenant={tenant_id}): {raw!r}"
    )


def _load(registry_path: Path) -> dict[str, dict[str, Any]]:
    if not registry_path.exists():
        raise RegistryCorrupted(f"registry 不存在 / missing: {registry_path}")
    out: dict[str, dict[str, Any]] = {}
    with registry_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in _REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise RegistryCorrupted(
                f"registry 缺列 / missing columns: {missing}"
            )
        for row in reader:
            tid = (row.get("tenant_id") or "").strip()
            if not tid:
                raise RegistryCorrupted("registry 含空 tenant_id 行 / empty tenant_id row")
            if tid in out:
                raise RegistryCorrupted(f"registry 重复 tenant_id / duplicate: {tid!r}")
            brand_layer = (row.get("brand_layer") or "").strip()
            if not _BRAND_LAYER_RE.match(brand_layer):
                raise RegistryCorrupted(
                    f"非法 brand_layer / invalid (tenant={tid}): {brand_layer!r}"
                )
            allowed_layers = _parse_json_list(
                row.get("allowed_layers") or "",
                field="allowed_layers", tenant_id=tid,
            )
            if not allowed_layers:
                raise RegistryCorrupted(
                    f"allowed_layers 必须非空 / non-empty required (tenant={tid})"
                )
            for layer in allowed_layers:
                if not _BRAND_LAYER_RE.match(layer):
                    raise RegistryCorrupted(
                        f"allowed_layers 非法 layer (tenant={tid}): {layer!r}"
                    )
            if "domain_general" not in allowed_layers:
                # 卡 §6/§7：domain_general 是底座，禁止只给 brand 不给 domain
                raise RegistryCorrupted(
                    f"allowed_layers 必含 domain_general (tenant={tid}): {allowed_layers!r}"
                )
            default_platforms = _parse_json_list(
                row.get("default_platforms") or "",
                field="default_platforms", tenant_id=tid,
            )
            environment = (row.get("environment") or "").strip()
            if environment not in _ENVIRONMENT_ENUM:
                raise RegistryCorrupted(
                    f"非法 environment (tenant={tid}): {environment!r}"
                )
            enabled = _parse_bool(row.get("enabled") or "", tenant_id=tid)
            api_key_id = (row.get("api_key_id") or "").strip()
            if not api_key_id:
                raise RegistryCorrupted(f"api_key_id 空 / empty (tenant={tid})")
            policy_level = (row.get("policy_level") or "").strip()

            out[tid] = {
                "tenant_id": tid,
                "api_key_id": api_key_id,
                "brand_layer": brand_layer,
                "allowed_layers": list(allowed_layers),
                "default_platforms": list(default_platforms),
                "policy_level": policy_level,
                "enabled": enabled,
                "environment": environment,
            }
    if not out:
        raise RegistryCorrupted("registry 为空 / empty registry")
    return out


def reload_registry(registry_path: Path | None = None) -> None:
    """切换 / 重读 registry。测试 fixture 通过此入口注入临时 CSV。"""
    global _REGISTRY, _REGISTRY_PATH
    path = Path(registry_path) if registry_path is not None else DEFAULT_REGISTRY_PATH
    _REGISTRY = _load(path)
    _REGISTRY_PATH = path


def _ensure_loaded() -> None:
    if not _REGISTRY:
        reload_registry(_REGISTRY_PATH)


def resolve(tenant_id: str, api_key_id: str | None = None) -> dict[str, Any]:
    """解析 tenant_id → tenant scope。

    入参严格限制：tenant_id (str) 和可选 api_key_id (str|None)。
    任何额外位置参数 / 自然语言关键字参数将由函数签名拒绝。
    """
    if not isinstance(tenant_id, str):
        raise TypeError(f"tenant_id 必须 str / must be str: {type(tenant_id).__name__}")
    if api_key_id is not None and not isinstance(api_key_id, str):
        raise TypeError(
            f"api_key_id 必须 str|None: {type(api_key_id).__name__}"
        )
    _ensure_loaded()
    row = _REGISTRY.get(tenant_id)
    if row is None:
        raise TenantNotAuthorized(f"tenant 未登记 / not registered: {tenant_id!r}")
    if not row["enabled"]:
        raise TenantNotAuthorized(f"tenant 已停用 / disabled: {tenant_id!r}")
    if api_key_id is not None and api_key_id != row["api_key_id"]:
        raise TenantNotAuthorized(
            f"api_key_id 与登记不符 / api_key mismatch (tenant={tenant_id!r})"
        )
    # 防御性：domain_general 必含
    allowed_layers = list(row["allowed_layers"])
    if "domain_general" not in allowed_layers:
        raise RegistryCorrupted(
            f"allowed_layers 缺 domain_general (tenant={tenant_id!r})"
        )
    return {
        "tenant_id": row["tenant_id"],
        "brand_layer": row["brand_layer"],
        "allowed_layers": allowed_layers,
        "default_platforms": list(row["default_platforms"]),
        "policy_level": row["policy_level"],
        "enabled": row["enabled"],
        "environment": row["environment"],
    }

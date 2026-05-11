#!/usr/bin/env python3
"""
generate_manifest.py · KS-S0-006 · source_manifest_hash 生成 / generation
========================================================================
作用 / purpose:
  对 clean_output/ 真源做一次冻结快照 / frozen snapshot：
    - 列出所有 canonical 文件路径 + sha256 + size
    - 顶层 manifest_hash = sorted entries 序列化后的 sha256
    - 作为 Phase 2 各 view 编译时 governance_common_fields 的 source_manifest_hash 唯一来源

白名单（计入 manifest）/ whitelist:
  - clean_output/nine_tables/*.csv
  - clean_output/candidates/**/*.yaml
  - clean_output/play_cards/**/* (csv/yaml/md)
  - clean_output/runtime_assets/**/* (csv/yaml/md)
  - clean_output/templates/**/*
  - clean_output/schema/**/*.json

排除（不计入，避免自指）/ excluded:
  - audit/ （含本卡产物自身）
  - storage/ （已废弃的 sqlite 等）
  - scripts/ （工具脚本，不算真源）
  - unprocessable_register/ （登记表会变）

退出码 / exit:
  0  生成成功 / 或 --verify 通过
  1  --verify 检测到漂移 / drift
  2  其他错 / other error
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CO = ROOT / "clean_output"
# KS-S0-006 §1 / §4 / §5 明文：产物路径 = clean_output/audit/source_manifest.json
# 不要写 clean_output/manifest.json（那是 Phase 1 build_manifest.py 的产物，结构不同）
MANIFEST = CO / "audit" / "source_manifest.json"

WHITELIST_PATTERNS = [
    ("nine_tables", "*.csv"),
    ("candidates", "**/*.yaml"),
    ("play_cards", "**/*"),
    ("runtime_assets", "**/*"),
    ("templates", "**/*"),
    ("schema", "**/*.json"),
    ("domain_skeleton", "**/*"),
    ("registers", "**/*"),  # 若未来引入
]

EXCLUDED_TOP = {"audit", "storage", "scripts", "unprocessable_register"}


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files() -> list[Path]:
    files: set[Path] = set()
    for top, pattern in WHITELIST_PATTERNS:
        d = CO / top
        if not d.exists():
            continue
        for p in d.glob(pattern):
            if p.is_file():
                files.add(p)
    return sorted(files)


def build_manifest() -> dict:
    """
    KS-S0-006 §1 / §4 字段契约：
      - entries 每行包含 path + sha256 + size + mtime（§1 完整性）
      - manifest_hash 只对 {path, sha256, size} 三元组的稳定序列化做 sha256
        —— mtime 是文件系统元数据，不同 checkout 必然不同；若纳入 hash 会
        让 §6 "任改 1 byte 才 fail" 的语义被破坏（mtime 漂就误报）。
    """
    entries = []
    hash_payload = []
    for p in collect_files():
        rel = str(p.relative_to(ROOT))
        sz = p.stat().st_size
        sha = sha256_of(p)
        mtime_iso = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        entries.append({
            "path": rel,
            "size": sz,
            "sha256": sha,
            "mtime": mtime_iso,
        })
        hash_payload.append({
            "path": rel,
            "size": sz,
            "sha256": sha,
        })
    # 序列化（稳定排序）后算顶层 hash · 仅含 path/size/sha256 三元组
    serialized = json.dumps(hash_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    manifest_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return {
        "manifest_hash": manifest_hash,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_card": "KS-S0-006",
        "entry_count": len(entries),
        "entries": entries,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true",
                    help="重算后与已落盘 manifest 对比 / verify against existing manifest")
    args = ap.parse_args()

    if args.verify:
        if not MANIFEST.exists():
            print(f"❌ manifest 不存在 / missing: {MANIFEST.relative_to(ROOT)}")
            return 1
        existing = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rebuilt = build_manifest()
        old_hash = existing.get("manifest_hash")
        new_hash = rebuilt["manifest_hash"]
        if old_hash != new_hash:
            print(f"❌ manifest 漂移 / drift detected")
            print(f"   stored: {old_hash}")
            print(f"   rebuilt: {new_hash}")
            print(f"   stored entries: {existing.get('entry_count')}")
            print(f"   rebuilt entries: {rebuilt['entry_count']}")
            return 1
        print(f"✅ manifest 一致 / consistent ({rebuilt['entry_count']} entries)")
        print(f"   hash: {new_hash}")
        return 0

    # 生成 / build
    m = build_manifest()
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ manifest 已落盘 / written: {MANIFEST.relative_to(ROOT)}")
    print(f"   entries: {m['entry_count']}")
    print(f"   manifest_hash: {m['manifest_hash']}")
    print(f"   generated_at: {m['generated_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

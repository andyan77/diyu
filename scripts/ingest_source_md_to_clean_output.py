#!/usr/bin/env python3
"""ingest_source_md_to_clean_output.py · 源 MD 真源补录 / source-MD ingestion to clean_output/.

post-audit finding #5 修复一次性脚本：
  把 9 表 evidence_view.source_md 实际引用的 MD 物理复制进 clean_output/<同名目录>/，
  让 W5 S5 反查可以严格走 `Path(clean_output/<source_md>).is_file() == True`。

口径 / scope（43 minimum, 用户裁决）:
  - 仅复制被 `clean_output/nine_tables/07_evidence.csv` 实际引用的源 MD
  - "& 多文件聚合" 按目录前缀继承解析后逐文件复制
  - 未被引用的 8 个文件（meta / index / AI 研究产物）**不**纳入真源，
    复制完成后会在 audit log 显式列出"未纳入及原因"

幂等 / idempotency:
  - 已存在 dst 且 sha256 == src → skip
  - 已存在 dst 但 sha256 mismatch → 报 error 退出（不静默覆盖）

只跑一次 / one-shot:
  - 不替代 Phase 1 build_manifest，只做 source MD 物理补录
  - 运行后必须重跑 `scripts/generate_manifest.py` 才能让 manifest 收新增 MD

退出码 / exit codes:
  0 = 成功（含 idempotent skip）
  2 = src 文件缺失 / dst 已存在但 sha256 mismatch
  3 = 9 表 evidence 读取失败
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import shutil
import sys
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
CLEAN_OUTPUT = REPO_ROOT / "clean_output"
NINE_TABLES_EVIDENCE = CLEAN_OUTPUT / "nine_tables" / "07_evidence.csv"
DEFAULT_AUDIT_LOG = CLEAN_OUTPUT / "audit" / "ingest_source_md.log"

# Phase 1 输入范围 4 目录 / Phase 1 input dirs（与 CLAUDE.md "输入范围" 一致 + Q-brand-seeds 实测在用）
INPUT_DIRS = (
    "Q2-内容类型种子",
    "Q4-人设种子",
    "Q7Q12-搭配陈列业务包",
    "Q-brand-seeds",
)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_source_md_parts(source_md: str) -> list[str]:
    """9 表 & 多文件聚合解析 / multi-file source_md parsing.

    Convention: "dir/file1.md & file2.md & file3.md"
    第 1 段含完整相对路径；第 2/3+ 段省略目录，继承第 1 段的目录前缀。
    """
    if not source_md or not source_md.strip():
        return []
    raw_parts = [p.strip() for p in source_md.split(" & ") if p.strip()]
    if not raw_parts:
        return []
    first = raw_parts[0]
    base_dir = str(PurePosixPath(first).parent)
    resolved = [first]
    for p in raw_parts[1:]:
        if "/" in p:
            resolved.append(p)
        else:
            resolved.append(f"{base_dir}/{p}" if base_dir not in (".", "") else p)
    return resolved


def collect_referenced_mds(evidence_csv: Path) -> set[str]:
    """从 9 表 evidence 收集所有被引用的 source_md 文件相对路径（去重）。"""
    if not evidence_csv.exists():
        print(f"[ERROR] 9 表 evidence 缺失 / missing: {evidence_csv}", file=sys.stderr)
        sys.exit(3)
    refs: set[str] = set()
    with evidence_csv.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            sm = (row.get("source_md") or "").strip()
            for p in _resolve_source_md_parts(sm):
                refs.add(p)
    return refs


def collect_all_mds_in_input_dirs() -> set[str]:
    """4 个 input 目录下所有 .md 文件（相对仓库根）."""
    all_md: set[str] = set()
    for d in INPUT_DIRS:
        root = REPO_ROOT / d
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            all_md.add(p.relative_to(REPO_ROOT).as_posix())
    return all_md


def _classify_unreferenced(rel: str) -> str:
    """为未引用文件标注分类，写入 audit log。"""
    name = rel.lower()
    if name.endswith("/_index.md") or name.endswith("/index.md"):
        return "index_file"
    if "claude.md" in name:
        return "meta_instructions"
    if "compass_artifact" in name or "deep-research" in name or "深度研究" in name or "gpt5" in name:
        return "ai_research_artifact"
    return "uncategorized"


def ingest(
    *,
    dry_run: bool = False,
    audit_log: Path = DEFAULT_AUDIT_LOG,
) -> int:
    referenced = collect_referenced_mds(NINE_TABLES_EVIDENCE)
    all_inputs = collect_all_mds_in_input_dirs()
    unreferenced = sorted(all_inputs - referenced)

    log_lines: list[str] = []
    log_lines.append("# ingest_source_md.log · 真源补录 / source-MD ingestion log")
    log_lines.append(f"generated_at: {_dt.datetime.now(_dt.timezone.utc).isoformat()}")
    log_lines.append(f"scope: 43 minimum (用户裁决, 仅 9 表 evidence 实际引用)")
    log_lines.append(f"referenced_count: {len(referenced)}")
    log_lines.append(f"input_dirs_total_md: {len(all_inputs)}")
    log_lines.append(f"unreferenced_excluded: {len(unreferenced)}")
    log_lines.append("")

    copied: list[str] = []
    skipped_idempotent: list[str] = []
    missing_src: list[str] = []
    sha_conflict: list[str] = []

    for rel in sorted(referenced):
        src = REPO_ROOT / rel
        dst = CLEAN_OUTPUT / rel
        if not src.exists():
            missing_src.append(rel)
            continue
        src_hash = sha256_of(src)
        if dst.exists():
            dst_hash = sha256_of(dst)
            if dst_hash == src_hash:
                skipped_idempotent.append(f"{rel} | sha256={src_hash}")
                continue
            sha_conflict.append(
                f"{rel} | src_sha={src_hash} | dst_sha={dst_hash}"
            )
            continue
        if dry_run:
            copied.append(f"{rel} | sha256={src_hash} | DRY_RUN")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        post_hash = sha256_of(dst)
        if post_hash != src_hash:
            sha_conflict.append(
                f"{rel} | post-copy sha mismatch src={src_hash} dst={post_hash}"
            )
            continue
        copied.append(f"{rel} | sha256={src_hash}")

    log_lines.append(f"[copied] count={len(copied)}")
    for c in copied:
        log_lines.append(f"  {c}")
    log_lines.append("")
    log_lines.append(f"[skipped_idempotent] count={len(skipped_idempotent)} (dst sha256 已与 src 一致)")
    for c in skipped_idempotent:
        log_lines.append(f"  {c}")
    log_lines.append("")
    log_lines.append(f"[unreferenced_excluded] count={len(unreferenced)} (未被 evidence 引用，不纳入真源)")
    for u in unreferenced:
        log_lines.append(f"  {u} | reason={_classify_unreferenced(u)}")
    log_lines.append("")
    if missing_src:
        log_lines.append(f"[ERROR missing_src] count={len(missing_src)}")
        for m in missing_src:
            log_lines.append(f"  {m}")
        log_lines.append("")
    if sha_conflict:
        log_lines.append(f"[ERROR sha_conflict] count={len(sha_conflict)} (dst 已存在且 sha 不一致 — 拒绝静默覆盖)")
        for c in sha_conflict:
            log_lines.append(f"  {c}")
        log_lines.append("")

    audit_log.parent.mkdir(parents=True, exist_ok=True)
    audit_log.write_text("\n".join(log_lines), encoding="utf-8")
    print(f"[INFO] ingest log → {audit_log}")
    print(f"[INFO] copied={len(copied)} skipped={len(skipped_idempotent)} "
          f"unreferenced={len(unreferenced)} missing_src={len(missing_src)} sha_conflict={len(sha_conflict)}")
    if missing_src or sha_conflict:
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="源 MD 真源补录到 clean_output/ — post-audit finding #5 修复"
    )
    parser.add_argument("--dry-run", action="store_true", help="只生成 log，不实际复制")
    parser.add_argument("--audit-log", type=Path, default=DEFAULT_AUDIT_LOG)
    args = parser.parse_args(argv)
    return ingest(dry_run=args.dry_run, audit_log=args.audit_log)


if __name__ == "__main__":
    sys.exit(main())

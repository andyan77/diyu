#!/usr/bin/env python3
"""build_manifest.py · 生成 clean_output/manifest.json + checksums.sha256

清单内容：
- domain_skeleton (yaml + sha256 + lines)
- 90 个 candidate yaml (按 brand_layer 分组 + sha256 + lines)
- 9 张 csv (路径 + sha256 + lines + data_rows)
- audit 文件清单
- scripts 文件清单
- unprocessable + skeleton_gap_register
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "clean_output"

def sha256(p):
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()

def lines(p):
    return sum(1 for _ in p.open("rb"))

def file_entry(p):
    return {
        "path": str(p.relative_to(ROOT)),
        "sha256": sha256(p),
        "bytes": p.stat().st_size,
        "lines": lines(p),
    }

def main():
    manifest = {
        "version": "1.0",
        "generated_by": "scripts/build_manifest.py",
        "domain_skeleton": file_entry(OUT / "domain_skeleton" / "domain_skeleton.yaml"),
        "candidates": {"domain_general": [], "brand_faye": [], "needs_review": []},
        "nine_tables": [],
        "audit": [],
        "unprocessable_register": [],
        "scripts": [],
        "templates": [],
    }

    for sub in ("domain_general", "brand_faye", "needs_review"):
        d = OUT / "candidates" / sub
        if d.exists():
            for y in sorted(d.glob("*.yaml")):
                manifest["candidates"][sub].append(file_entry(y))

    import csv as _csv
    for csvf in sorted((OUT / "nine_tables").glob("*.csv")):
        e = file_entry(csvf)
        # data_rows 用 DictReader 计数，避免字段内换行被 wc-l 误算
        with csvf.open(encoding="utf-8") as f:
            e["data_rows"] = sum(1 for _ in _csv.DictReader(f))
        manifest["nine_tables"].append(e)

    for f in sorted((OUT / "audit").iterdir()):
        if f.is_file():
            manifest["audit"].append(file_entry(f))

    upr = OUT / "unprocessable_register"
    if upr.exists():
        for f in sorted(upr.iterdir()):
            if f.is_file():
                manifest["unprocessable_register"].append(file_entry(f))

    for f in sorted((OUT / "scripts").glob("*.py")):
        manifest["scripts"].append(file_entry(f))

    tpl = OUT / "templates"
    if tpl.exists():
        for f in sorted(tpl.iterdir()):
            if f.is_file():
                manifest["templates"].append(file_entry(f))

    # ===== 双签名（向后兼容：新增字段不删旧字段）=====
    def _sig(hashes):
        h = hashlib.sha256()
        for x in sorted(hashes):
            h.update(x.encode("ascii"))
        return h.hexdigest()

    data_hashes = [e["sha256"] for e in manifest["nine_tables"]]
    tooling_hashes = [e["sha256"] for e in manifest["scripts"]]
    schema_dir = OUT / "schema"
    if schema_dir.exists():
        for f in sorted(schema_dir.iterdir()):
            if f.is_file():
                tooling_hashes.append(sha256(f))
    storage_dir = OUT / "storage"
    if storage_dir.exists():
        for f in sorted(storage_dir.glob("*.sql")):
            tooling_hashes.append(sha256(f))

    all_hashes = []
    all_hashes.append(manifest["domain_skeleton"]["sha256"])
    for grp in manifest["candidates"].values():
        for e in grp:
            all_hashes.append(e["sha256"])
    for e in manifest["nine_tables"]:
        all_hashes.append(e["sha256"])
    for e in manifest["audit"] + manifest["unprocessable_register"] + manifest["scripts"] + manifest["templates"]:
        all_hashes.append(e["sha256"])

    manifest["signatures"] = {
        "data_signature":     _sig(data_hashes),     # 9 表 csv only
        "tooling_signature":  _sig(tooling_hashes),  # scripts + schema + storage SQL
        "total_signature":    _sig(all_hashes),      # 全量（向后兼容口径）
    }

    manifest["summary"] = {
        "candidate_count_total": sum(len(v) for v in manifest["candidates"].values()),
        "candidate_domain_general": len(manifest["candidates"]["domain_general"]),
        "candidate_brand_faye": len(manifest["candidates"]["brand_faye"]),
        "candidate_needs_review": len(manifest["candidates"]["needs_review"]),
        "nine_tables_data_rows_total": sum(e["data_rows"] for e in manifest["nine_tables"]),
        "audit_files": len(manifest["audit"]),
        "scripts_count": len(manifest["scripts"]),
    }

    out_json = OUT / "manifest.json"
    out_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # checksums.sha256 (gnu format: <hash>  <path>)
    lines_out = []
    for entry in [manifest["domain_skeleton"]]:
        lines_out.append(f"{entry['sha256']}  {entry['path']}")
    for grp in manifest["candidates"].values():
        for e in grp:
            lines_out.append(f"{e['sha256']}  {e['path']}")
    for e in manifest["nine_tables"]:
        lines_out.append(f"{e['sha256']}  {e['path']}")
    for e in manifest["audit"] + manifest["unprocessable_register"] + manifest["scripts"] + manifest["templates"]:
        lines_out.append(f"{e['sha256']}  {e['path']}")
    (OUT / "checksums.sha256").write_text("\n".join(lines_out) + "\n", encoding="utf-8")

    print(f"manifest.json     : {out_json}")
    print(f"checksums.sha256  : {OUT/'checksums.sha256'}")
    print(f"summary           : {manifest['summary']}")

if __name__ == "__main__":
    main()

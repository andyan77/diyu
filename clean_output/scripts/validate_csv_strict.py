#!/usr/bin/env python3
"""硬门 2 · 全量 CSV 严格校验（可重跑工具）

校验维度：
1. JSON Schema（schema/nine_tables.schema.json · canonical · v2-rev3-r1）
   - required + minLength=1（禁空字符串）
   - 18 object_type / 14 relation_kind 白名单
   - 7 source_type / 3 inference_level 受控枚举
   - additionalProperties: false（禁多列）
2. JSON 字段可解析（json.loads()）：
   - 03_semantic.examples_json
   - 05_relation.properties_json
   - 09_call_mapping.governing_rules_json
3. 主键非空（schema 已覆盖，二次冗余）

违反落 audit/_process/csv_violations.csv，任一违反退出 1。
"""
import csv
import json
import sys
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
NINE = ROOT / "nine_tables"
SCHEMA = ROOT / "schema" / "nine_tables.schema.json"
OUT = ROOT / "audit" / "_process" / "csv_violations.csv"

# JSON 字段：表名 → [字段名, ...]
JSON_FIELDS = {
    "03_semantic":     ["examples_json"],
    "05_relation":     ["properties_json"],
    "09_call_mapping": ["governing_rules_json"],
}

def load_schema_validators():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    defs = schema["definitions"]
    validators = {}
    for name, sub in schema["tables"].items():
        full = {"$schema": schema["$schema"], "definitions": defs, **sub}
        validators[name] = Draft202012Validator(full)
    return validators

def empty_to_null(row):
    """空字符串 → None（避免 None vs '' 混淆）"""
    return {k: (v if v != "" else None) for k, v in row.items()}

def validate_json_fields(table_name, row, line):
    """每个 JSON 字段尝试 json.loads"""
    errs = []
    for field in JSON_FIELDS.get(table_name, []):
        v = row.get(field, "") or ""
        v = v.strip()
        if not v:
            continue  # null 已被 schema 允许
        try:
            json.loads(v)
        except json.JSONDecodeError as e:
            errs.append({
                "line": line,
                "field": field,
                "violation": "json_unparsable",
                "value": v[:120].replace("\n", " "),
                "reason": str(e)[:100],
            })
    return errs

def main():
    if not SCHEMA.exists():
        print(f"ERROR: schema not found: {SCHEMA}", file=sys.stderr)
        return 2

    validators = load_schema_validators()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out_rows = []
    summary = []

    for csvf in sorted(NINE.glob("*.csv")):
        name = csvf.stem  # e.g. "01_object_type"
        if name not in validators:
            print(f"  ⚠️  {name}: 无对应 schema，跳过")
            continue

        v = validators[name]
        rows = list(csv.DictReader(open(csvf, encoding="utf-8")))
        schema_bad = 0
        json_bad = 0
        bad_lines = set()

        for i, row in enumerate(rows, start=2):
            spid = row.get("source_pack_id", "")
            clean = empty_to_null(row)

            # 1) Schema
            for err in v.iter_errors(clean):
                schema_bad += 1
                bad_lines.add(i)
                field = ".".join(str(p) for p in err.path) or "<row>"
                out_rows.append([
                    name, i, spid, field, "schema",
                    err.message[:200].replace("\n", " ").replace(",", ";"),
                    "",
                ])

            # 2) JSON 字段可解析
            for j_err in validate_json_fields(name, row, i):
                json_bad += 1
                bad_lines.add(i)
                out_rows.append([
                    name, i, spid, j_err["field"], j_err["violation"],
                    j_err["reason"], j_err["value"],
                ])

        mark = "✅" if (schema_bad + json_bad) == 0 else "❌"
        summary.append((name, len(rows), schema_bad, json_bad, len(bad_lines)))
        print(f"  {mark} {name:20s} rows={len(rows):4d}  "
              f"schema={schema_bad:3d}  json={json_bad:3d}  bad_lines={len(bad_lines)}")

    # 写违反清单
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "line", "source_pack_id", "field", "violation_kind", "reason", "value_snippet"])
        w.writerows(out_rows)

    total_violations = len(out_rows)
    total_bad_lines = sum(s[4] for s in summary)
    print()
    print(f"违反总条数: {total_violations}（同行可多条）")
    print(f"违反 bad rows 总和: {total_bad_lines}")
    print(f"清单: {OUT}")
    return 0 if total_violations == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

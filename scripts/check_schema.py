#!/usr/bin/env python3
"""JSON Schema metaschema 自检适配层 / metaschema check adapter.

背景 / context:
  jsonschema 4.18+ CLI 已弃用、4.19 移除 --check-schema 子命令；
  W1 五张卡的 ci_command 字面 `python3 -m jsonschema --check-schema <file>`
  在当前环境无法运行。本脚本是稳定入口，调用 Draft202012Validator.check_schema
  对 schema 自身做元校验（同 --check-schema 的语义）。

用法 / usage:
  python3 scripts/check_schema.py knowledge_serving/schema/serving_views.schema.json
  python3 scripts/check_schema.py path1 path2 ...
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


def check(path: Path) -> tuple[bool, str]:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, f"file not found / 文件不存在: {path}"
    except json.JSONDecodeError as e:
        return False, f"JSON parse error: {e}"
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as e:
        return False, f"schema invalid: {e.message}"
    return True, "OK"


def main() -> int:
    parser = argparse.ArgumentParser(description="JSON Schema metaschema 自检 / metaschema check")
    parser.add_argument("paths", nargs="+", help="schema 文件路径 / schema file paths")
    args = parser.parse_args()

    fail = 0
    for raw in args.paths:
        path = Path(raw)
        ok, msg = check(path)
        flag = "PASS" if ok else "FAIL"
        print(f"{flag}  {path}: {msg}")
        if not ok:
            fail += 1
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""硬门 5 · unprocessable_register classification 枚举校验（严格 prompt §13 八类 + 扩展注册制）

prompt §13 受控 8 类：
  needs_human_judgment
  scenario_not_closed
  evidence_insufficient
  gate_failure_specific
  meta_layer_not_business
  process_description_needs_split
  duplicate_or_redundant
  out_of_scope

本仓在 W2 后引入"扩展注册制"：超 prompt 8 类的扩展必须先在
audit/schema_extension_register.csv 登记 + decision=approved，
方能被本脚本放行；否则即违反。

任一非枚举且未在扩展注册表中获批 → 退出 1 + 落 audit/_process/register_enum_violations.csv
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTER = ROOT / "clean_output" / "unprocessable_register" / "register.csv"
EXT_REG = ROOT / "clean_output" / "audit" / "schema_extension_register.csv"
OUT = ROOT / "clean_output" / "audit" / "_process" / "register_enum_violations.csv"

# prompt §13 八类受控枚举（不可直接修改）
PROMPT_ENUM = {
    "needs_human_judgment",
    "scenario_not_closed",
    "evidence_insufficient",
    "gate_failure_specific",
    "meta_layer_not_business",
    "process_description_needs_split",
    "duplicate_or_redundant",
    "out_of_scope",
}

# 历史观测但未在 prompt 列出的本地兼容（B12 时期产物，已就地归并）
LEGACY_COMPATIBLE = {
    "meta_layer_definition",  # 等价 meta_layer_not_business 的早期变体
}


def load_approved_extensions():
    """从扩展注册表读取 decision=approved 的 unprocessable_classification 扩展"""
    if not EXT_REG.exists():
        return set()
    out = set()
    with EXT_REG.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("extension_type") == "unprocessable_classification"
                    and row.get("decision") == "approved"):
                out.add(row.get("proposed_value"))
    return out

def main():
    approved_ext = load_approved_extensions()
    allowed = PROMPT_ENUM | LEGACY_COMPATIBLE | approved_ext

    with open(REGISTER, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    violations = []
    distinct = {}
    for i, row in enumerate(rows, start=2):
        v = (row.get("classification") or "").strip()
        distinct[v] = distinct.get(v, 0) + 1
        if v not in allowed:
            violations.append([i, row.get("unprocessable_id", "?"), v, "non_enum_or_unapproved_ext"])

    print("classification 取值分布（PROMPT_ENUM 8 类 + LEGACY 1 类 + approved EXT 0 类）：")
    for k, n in sorted(distinct.items()):
        if k in PROMPT_ENUM:
            mark = "✅"
        elif k in LEGACY_COMPATIBLE:
            mark = "⚪"
        elif k in approved_ext:
            mark = "🆕"
        else:
            mark = "❌"
        print(f"  {mark} {k}: {n}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "unprocessable_id", "classification", "violation"])
        w.writerows(violations)
    print(f"\n违反: {len(violations)} → {OUT}")
    return 0 if not violations else 1

if __name__ == "__main__":
    sys.exit(main())

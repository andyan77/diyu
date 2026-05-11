#!/usr/bin/env python3
"""硬门 3 · 必填空值 + 白名单 回归（M2 阶段 4）

修复 22 bad rows，分 3 路径：
  路径 A · 反推（02_field 6 + 03_semantic 3 = 9 行）
    yaml shorthand 缺 owner_type/field_name/data_type/owner_field/definition
    → 从 ID 反推（FD-<owner>-<name> / SM-...-<field>）+ yaml 上下文回填

  路径 B · examples 数组展开（04_value_set 4 行）
    yaml 用 `examples: [a,b,c]` 而非标准 value/label
    → 删占位行 + 加多个标准 (value_set_id, value, label) 行

  路径 D · 非白名单删行 + skeleton_gap_register
    02_field 97-101 (5 行 · COMPATIBLE_WITH / PersonaContentTypePlatformDerivedView)
    04_value_set 588-590 (3 行 · 同上 owner)
    05_relation 162 (1 行 · 同上 source/target)
    → 删 9 表行 + 登记 GAP-005/006

备份 *.csv.bak.<ts>，重跑 validate_csv_strict 校验。
"""
import csv
import datetime as dt
import re
import shutil
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NINE = ROOT / "nine_tables"
CAND = ROOT / "candidates"
GAP = ROOT / "domain_skeleton" / "skeleton_gap_register.csv"
LOG = ROOT / "audit" / "extraction_log.csv"

TS = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

# ============== 路径 A 反推规则 ==============
def derive_field_meta(field_id):
    """FD-<owner>-<name> → owner, name, default data_type"""
    m = re.match(r"FD-([A-Za-z0-9_]+)-(.+)$", field_id)
    if m:
        return m.group(1), m.group(2), "string"
    return None, None, None

def derive_semantic_meta(semantic_id, pack_yaml_path):
    """SM-<pack_id>-<owner_field>"""
    # SM-KP-product_attribute-enterprise-narrative-six-section-shell-six_field_shell
    # 取最末段作 owner_field
    parts = semantic_id.rsplit("-", 1)
    owner_field = parts[1] if len(parts) == 2 else "<unknown>"
    # definition 从 yaml knowledge_assertion 取首句
    try:
        d = yaml.safe_load(pack_yaml_path.read_text(encoding="utf-8"))
        ka = (d.get("knowledge_assertion") or "").strip()
        # first sentence ≤ 200 chars
        sentence = re.split(r"[；。\n]", ka, maxsplit=1)[0].strip()
        definition = sentence[:200] if sentence else "（待人工补充）"
    except Exception:
        definition = "（待人工补充）"
    return owner_field, definition

# ============== 路径 B examples 展开 ==============
def yaml_value_set_examples(pack_id, value_set_id):
    """从 yaml 取该 value_set_id 的 examples 数组"""
    yaml_path = None
    for sub in ("domain_general", "brand_faye", "needs_review"):
        p = CAND / sub / f"{pack_id}.yaml"
        if p.exists():
            yaml_path = p
            break
    if not yaml_path:
        return []
    d = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    ntp = d.get("nine_table_projection", {}) or {}
    for vs in (ntp.get("value_set") or []):
        if isinstance(vs, dict) and vs.get("value_set_id") == value_set_id:
            ex = vs.get("examples")
            if isinstance(ex, list):
                return [str(x) for x in ex]
    return []

# ============== skeleton_gap 登记 ==============
GAP_NEW = [
    {
        "gap_id": "GAP-005",
        "surface_concept": "COMPATIBLE_WITH (关系类型上的字段 namespace)",
        "appears_in": "Q4-人设种子/phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md",
        "why_unresolved": "agent 在 Persona×ContentType 兼容矩阵抽取时把关系自身的字段 (support/risk/reason) 当作对象字段；COMPATIBLE_WITH 不在 18 项白名单且不应是对象类型",
        "decision": "defer_to_human · 候选方案 A 升格为新对象 / B 改用 properties_json 表达 / C 拆为 Persona-attr + ContentType-attr",
        "affected_rows": "02_field 3 行 + 04_value_set 2 行（已删除）",
    },
    {
        "gap_id": "GAP-006",
        "surface_concept": "PersonaContentTypePlatformDerivedView (派生视图对象)",
        "appears_in": "Q4-人设种子/phase-3-Q4-Persona-ContentType-Platform兼容矩阵.md",
        "why_unresolved": "agent 把派生视图当一阶对象；派生视图不应作为新 core_object_type，应作为查询时计算结果",
        "decision": "defer_to_human · 候选方案 A 拆为 Persona+ContentType+Platform 三向 fits/compatible_with relation / B 作为视图层不入 9 表",
        "affected_rows": "02_field 2 行 + 04_value_set 1 行 + 05_relation 1 行（已删除）",
    },
]

# ============== 主流程 ==============
def backup_csvs():
    bak_dir = NINE.parent / f"_pending_patches/stage4_bak_{TS}"
    bak_dir.mkdir(parents=True, exist_ok=True)
    for csvf in NINE.glob("*.csv"):
        shutil.copy(csvf, bak_dir / csvf.name)
    return bak_dir

def repair_02_field():
    csvf = NINE / "02_field.csv"
    rows = list(csv.reader(open(csvf, encoding="utf-8")))
    header = rows[0]
    out = [header]
    fixed = 0
    deleted = 0
    NON_WL_PACKS = {
        "KP-product_attribute-compatibility-edge-support-risk-reason-shell",
        "KP-product_attribute-compatibility-derived-view-combination-formula",
    }
    for row in rows[1:]:
        if len(row) < 8:
            continue
        field_id, owner_type, field_name, data_type = row[0], row[1], row[2], row[3]
        spid = row[7]

        # 路径 D 删
        if spid in NON_WL_PACKS and owner_type in ("COMPATIBLE_WITH", "PersonaContentTypePlatformDerivedView"):
            deleted += 1
            continue

        # 路径 A 反推
        if not owner_type and not field_name and not data_type:
            o, n, t = derive_field_meta(field_id)
            if o and n:
                row[1], row[2], row[3] = o, n, t
                fixed += 1

        out.append(row)

    csvf.write_text("", encoding="utf-8")
    with csvf.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerows(out)
    return fixed, deleted

def repair_03_semantic():
    csvf = NINE / "03_semantic.csv"
    rows = list(csv.reader(open(csvf, encoding="utf-8")))
    header = rows[0]
    out = [header]
    fixed = 0
    for row in rows[1:]:
        if len(row) < 6:
            continue
        sid, owner_field, definition = row[0], row[1], row[2]
        spid = row[5]

        if not owner_field and not definition:
            yaml_path = None
            for sub in ("domain_general", "brand_faye", "needs_review"):
                p = CAND / sub / f"{spid}.yaml"
                if p.exists():
                    yaml_path = p
                    break
            if yaml_path:
                of, df = derive_semantic_meta(sid, yaml_path)
                row[1], row[2] = of, df
                fixed += 1
        out.append(row)

    with csvf.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerows(out)
    return fixed

def repair_04_value_set():
    csvf = NINE / "04_value_set.csv"
    rows = list(csv.reader(open(csvf, encoding="utf-8")))
    header = rows[0]
    out = [header]
    expanded = 0
    deleted = 0
    NON_WL_VS = {"VS-COMPATIBLE_WITH-support", "VS-COMPATIBLE_WITH-risk", "VS-DerivedView-display_tier"}
    for row in rows[1:]:
        if len(row) < 6:
            continue
        vsid, value, label, ordinal, brand_layer, spid = row

        # 路径 D 删
        if vsid in NON_WL_VS:
            deleted += 1
            continue

        # 路径 B 展开
        if vsid and not value:
            examples = yaml_value_set_examples(spid, vsid)
            if examples:
                for idx, ex in enumerate(examples, start=1):
                    out.append([vsid, ex, "", str(idx), brand_layer, spid])
                expanded += 1
                continue
            # 无 examples 也无具体值 → 删
            deleted += 1
            continue

        out.append(row)

    with csvf.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerows(out)
    return expanded, deleted

def repair_05_relation():
    csvf = NINE / "05_relation.csv"
    rows = list(csv.reader(open(csvf, encoding="utf-8")))
    header = rows[0]
    out = [header]
    deleted = 0
    NON_WL_OBJ = {"PersonaContentTypePlatformDerivedView", "Persona+ContentType+PlatformTone|PrivateOutletChannel"}
    for row in rows[1:]:
        if len(row) < 7:
            continue
        st, tt = row[1], row[2]
        if st in NON_WL_OBJ or tt in NON_WL_OBJ:
            deleted += 1
            continue
        out.append(row)
    with csvf.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerows(out)
    return deleted

def append_skeleton_gap():
    """登记 GAP-005 / GAP-006 到 skeleton_gap_register.csv"""
    if not GAP.exists():
        # 兜底创建
        GAP.parent.mkdir(parents=True, exist_ok=True)
        with GAP.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["gap_id", "surface_concept", "appears_in", "why_unresolved", "decision", "affected_rows"])

    existing_ids = set()
    with open(GAP, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            existing_ids.add(row["gap_id"])

    added = 0
    with GAP.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for g in GAP_NEW:
            if g["gap_id"] not in existing_ids:
                w.writerow([g["gap_id"], g["surface_concept"], g["appears_in"],
                            g["why_unresolved"], g["decision"], g["affected_rows"]])
                added += 1
    return added

def main():
    print("=== M2 阶段 4 修复 ===\n")
    bak = backup_csvs()
    print(f"备份: {bak}\n")

    f02_fix, f02_del = repair_02_field()
    print(f"02_field: 反推修复 {f02_fix} 行 / 删除 {f02_del} 行")
    f03_fix = repair_03_semantic()
    print(f"03_semantic: 反推修复 {f03_fix} 行")
    f04_exp, f04_del = repair_04_value_set()
    print(f"04_value_set: examples 展开 {f04_exp} 个 set / 删除 {f04_del} 行")
    f05_del = repair_05_relation()
    print(f"05_relation: 删除 {f05_del} 行")

    g_added = append_skeleton_gap()
    print(f"\nskeleton_gap_register 新增: {g_added} 个 GAP")

    print("\n=== 重跑 validate_csv_strict ===")
    import subprocess
    rc = subprocess.run(["python3", str(ROOT / "scripts" / "validate_csv_strict.py")]).returncode
    print(f"\n validate_csv_strict exit code: {rc}")
    return rc

if __name__ == "__main__":
    sys.exit(main())

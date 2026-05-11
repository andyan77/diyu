#!/usr/bin/env python3
"""合并 patch 到中央 9 表，带 dedup。
- 01_object_type: dedupe by type_id (keep master)
- 02_field: dedupe by field_id (keep master)
- 03/04/05/06/07/09: concat (IDs are unique per pack by construction)
- 08_lifecycle: concat
"""
import os, csv, sys

NT = "/home/faye/20-血肉-2F种子/clean_output/nine_tables"
PD = "/home/faye/20-血肉-2F种子/clean_output/_pending_patches"
CARDS = ["tc_b03", "tc_b04", "tc_b09", "tc_b11"]

# Tables with primary key dedup
PK_TABLES = {
    "01_object_type.csv": 0,  # type_id
    "02_field.csv": 0,        # field_id
}

def load_existing_keys(path, key_idx):
    """Load existing key values from master CSV (skip header)."""
    keys = set()
    if not os.path.exists(path): return keys
    with open(path) as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if row and len(row) > key_idx:
                keys.add(row[key_idx])
    return keys

def append_with_dedup(master_path, patch_path, key_idx=None):
    if not os.path.exists(patch_path): return 0
    if os.path.getsize(patch_path) == 0: return 0
    new_rows = 0
    if key_idx is not None:
        existing = load_existing_keys(master_path, key_idx)
        with open(master_path, "a", newline="") as out:
            writer = csv.writer(out)
            with open(patch_path) as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row or not row[key_idx]: continue
                    if row[key_idx] in existing: continue
                    writer.writerow(row)
                    existing.add(row[key_idx])
                    new_rows += 1
    else:
        # concat (no dedup)
        with open(master_path, "a") as out:
            with open(patch_path) as f:
                for line in f:
                    if line.strip():
                        out.write(line)
                        new_rows += 1
    return new_rows

total = {}
for card in CARDS:
    for tbl in ["01_object_type", "02_field", "03_semantic", "04_value_set",
                "05_relation", "06_rule", "07_evidence", "08_lifecycle", "09_call_mapping"]:
        master = os.path.join(NT, tbl + ".csv")
        patch = os.path.join(PD, card, tbl + ".csv")
        key_idx = PK_TABLES.get(tbl + ".csv")
        n = append_with_dedup(master, patch, key_idx)
        total.setdefault(tbl, {})[card] = n

print(f"{'table':<20} " + " ".join(f"{c:>8}" for c in CARDS) + "    total")
for tbl in ["01_object_type", "02_field", "03_semantic", "04_value_set",
            "05_relation", "06_rule", "07_evidence", "08_lifecycle", "09_call_mapping"]:
    counts = total.get(tbl, {})
    s = sum(counts.values())
    print(f"{tbl:<20} " + " ".join(f"{counts.get(c,0):>8}" for c in CARDS) + f"  {s:>6}")
#!/usr/bin/env python3
"""从 yaml 抽取完整 9 表派生行（01-09 + lifecycle）。
Usage: patch_full.py <pack_id_list_file> <out_dir>"""
import sys, yaml, os, re, json

def csv(s):
    if s is None: return ""
    s = str(s).replace('\n', ' ').replace('\r', ' ').strip()
    if ',' in s or '"' in s:
        s = '"' + s.replace('"', '""') + '"'
    return s

def trunc(s, n=300):
    if not s: return ""
    s = re.sub(r'\s+', ' ', str(s)).strip()
    return s[:n]

def jsonify(x):
    if x is None: return ""
    if isinstance(x, str): return x
    return json.dumps(x, ensure_ascii=False)

def main():
    pack_list_file, out_dir = sys.argv[1], sys.argv[2]
    cand_dir = "/home/faye/20-血肉-2F种子/clean_output/candidates"

    rows = {f"0{i}": [] for i in range(1, 10)}

    for line in open(pack_list_file):
        pid = line.strip()
        if not pid: continue
        path = None
        for sub in ("domain_general", "brand_faye", "needs_review"):
            p = os.path.join(cand_dir, sub, pid + ".yaml")
            if os.path.exists(p):
                path = p; break
        if not path:
            print(f"missing: {pid}", file=sys.stderr); continue
        try:
            d = yaml.safe_load(open(path))
        except Exception as e:
            print(f"parse error {pid}: {e}", file=sys.stderr); continue
        bl = d.get("brand_layer", "domain_general")
        ntp = d.get("nine_table_projection", {}) or {}

        # 01 object_type
        for it in (ntp.get("object_type") or []):
            if isinstance(it, dict):
                rows["01"].append([it.get("type_id"), it.get("type_name"), it.get("supertype", "domain_object"), bl, pid])

        # 02 field
        for it in (ntp.get("field") or []):
            if isinstance(it, dict):
                rows["02"].append([it.get("field_id"), it.get("owner_type"), it.get("field_name"), it.get("data_type"),
                                   it.get("value_set_id", ""), it.get("semantic_id", ""), bl, pid])

        # 03 semantic
        for it in (ntp.get("semantic") or []):
            if isinstance(it, dict):
                rows["03"].append([it.get("semantic_id"), it.get("owner_field"), it.get("definition"),
                                   jsonify(it.get("examples_json", "")), bl, pid])

        # 04 value_set
        for it in (ntp.get("value_set") or []):
            if isinstance(it, dict):
                rows["04"].append([it.get("value_set_id"), it.get("value"), it.get("label", ""),
                                   it.get("ordinal", ""), bl, pid])

        # 05 relation
        for it in (ntp.get("relation") or []):
            if isinstance(it, dict):
                rows["05"].append([it.get("relation_id"), it.get("source_type"), it.get("target_type"),
                                   it.get("relation_kind"), jsonify(it.get("properties_json", "")), bl, pid])

        # 06 rule (from ntp.rule, fallback to scenario fields)
        rule_items = ntp.get("rule") or []
        if rule_items:
            for it in rule_items:
                if isinstance(it, dict):
                    if "rule_type" in it:
                        rows["06"].append([it.get("rule_id"), it.get("rule_type"), it.get("applicable_when", ""),
                                           it.get("success_scenario", ""), it.get("flip_scenario", ""),
                                           it.get("alternative_boundary", ""), bl, pid])
                    else:
                        # only rule_id given; synth from yaml scenario
                        sc = d.get("scenario", {})
                        what = sc.get("what", {}) or {}
                        result = sc.get("result", {}) or {}
                        boundary = sc.get("boundary", {}) or {}
                        alt = sc.get("alternative_path", []) or []
                        rt = what.get("action_type", "business_rule")
                        ab = "；".join(alt) if isinstance(alt, list) else str(alt)
                        rows["06"].append([it.get("rule_id"), rt, trunc(boundary.get("applicable_when", "")),
                                           trunc(result.get("success_pattern", "")),
                                           trunc(result.get("flip_pattern", "")),
                                           trunc(ab), bl, pid])

        # 07 evidence
        ev_items = ntp.get("evidence") or []
        for it in ev_items:
            if isinstance(it, dict):
                if "source_md" in it:
                    rows["07"].append([it.get("evidence_id"), it.get("source_md"), it.get("source_anchor"),
                                       trunc(it.get("evidence_quote", ""), 300),
                                       it.get("source_type", "explicit_business_decision"),
                                       it.get("inference_level", "direct_quote"), bl, pid])
                else:
                    ev = d.get("evidence", {}) or {}
                    rows["07"].append([it.get("evidence_id"), ev.get("source_md"), ev.get("source_anchor"),
                                       trunc(ev.get("evidence_quote", ""), 300),
                                       ev.get("source_type", "explicit_business_decision"),
                                       ev.get("inference_level", "direct_quote"), bl, pid])

        # 08 lifecycle
        for it in (ntp.get("lifecycle") or []):
            if isinstance(it, dict):
                rows["08"].append([it.get("lifecycle_id"), it.get("owner_type"), it.get("state"),
                                   it.get("transition_to"), it.get("condition", ""), bl, pid])

        # 09 call_mapping
        rid_default = f"RL-{pid}"
        for it in (ntp.get("call_mapping") or []):
            if isinstance(it, dict):
                mid = it.get("mapping_id")
                rt_match = re.match(r"CM-([a-z_]+)-KP-", mid or "")
                rtm = it.get("runtime_method") or (rt_match.group(1) if rt_match else "")
                inp = it.get("input_types", [])
                outp = it.get("output_types", [])
                gov = it.get("governing_rules_json")
                if not gov:
                    gov = {"governed_by": [rid_default]}
                gov_s = jsonify(gov)
                if not inp:
                    defaults = {"store_training": ["TrainingMaterial"], "outfit_recommendation": ["CustomerScenario","Product"],
                                "display_guidance": ["DisplayGuide"], "inventory_rescue": ["InventoryState","StylingRule"],
                                "content_generation": ["Persona","ContentType"], "platform_adaptation": ["ContentType","PlatformTone"]}
                    inp = defaults.get(rtm, [])
                if not outp:
                    defaults = {"store_training": ["TrainingScript"], "outfit_recommendation": ["StylingRule"],
                                "display_guidance": ["DisplayPlan"], "inventory_rescue": ["StylingRule"],
                                "content_generation": ["Content"], "platform_adaptation": ["AdaptedContent"]}
                    outp = defaults.get(rtm, [])
                rows["09"].append([mid, rtm, jsonify(inp), jsonify(outp), gov_s, bl, pid])

    os.makedirs(out_dir, exist_ok=True)
    for tbl, data in rows.items():
        fname = {"01":"01_object_type","02":"02_field","03":"03_semantic","04":"04_value_set",
                 "05":"05_relation","06":"06_rule","07":"07_evidence","08":"08_lifecycle","09":"09_call_mapping"}[tbl]
        with open(os.path.join(out_dir, fname + ".csv"), "w") as f:
            for row in data:
                f.write(",".join(csv(c) for c in row) + "\n")
        print(f"{fname}: {len(data)} rows")

if __name__ == "__main__":
    main()
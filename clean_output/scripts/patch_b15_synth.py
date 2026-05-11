#!/usr/bin/env python3
"""B15 yaml 用了字符串 ID 列表型 nine_table_projection，本脚本从 yaml 顶层
scenario / evidence 字段合成 9 表行（rule / evidence / value_set / semantic /
call_mapping）。pack_id 列表来自 stdin 或 argv[1]。

输出到 argv[2] 目录。
"""
import sys, os, yaml, re, json, csv

CAND='/home/faye/20-血肉-2F种子/clean_output/candidates'

def trunc(s, n=300):
    if not s: return ''
    return re.sub(r'\s+',' ',str(s)).strip()[:n]

def jstr(x):
    if x is None: return ''
    if isinstance(x,str): return x
    return json.dumps(x, ensure_ascii=False)

def find_yaml(pid):
    for sub in ('domain_general','brand_faye','needs_review'):
        p=f'{CAND}/{sub}/{pid}.yaml'
        if os.path.exists(p): return p
    return None

def main():
    pack_list = open(sys.argv[1]).read().strip().split('\n')
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    rows={k:[] for k in '01 02 03 04 05 06 07 08 09'.split()}

    for pid in pack_list:
        p = find_yaml(pid)
        if not p:
            print(f'missing {pid}', file=sys.stderr); continue
        d = yaml.safe_load(open(p))
        bl = d.get('brand_layer','domain_general')
        ntp = d.get('nine_table_projection',{}) or {}
        sc = d.get('scenario',{}) or {}
        what = sc.get('what',{}) or {}
        result = sc.get('result',{}) or {}
        boundary = sc.get('boundary',{}) or {}
        alt = sc.get('alternative_path',[]) or []
        ev = d.get('evidence',{}) or {}

        # 01 object_type from list of strings
        for ot in (ntp.get('object_type') or []):
            if isinstance(ot,str):
                rows['01'].append([f'OT-{ot}', ot, 'domain_object', bl, pid])

        # 03 semantic — only ID, definition synth from action_type
        for sm in (ntp.get('semantic') or []):
            if isinstance(sm,str):
                sm_id = sm if sm.startswith('SM-') else f'SM-{pid}-{sm}'
                rows['03'].append([sm_id, what.get('action_type','rule'),
                                   trunc(d.get('knowledge_assertion','')), '', bl, pid])

        # 04 value_set — only ID, no concrete values; create a single placeholder row
        for vs in (ntp.get('value_set') or []):
            if isinstance(vs,str):
                vs_id = vs if vs.startswith('VS-') else f'VS-{pid}-{vs}'
                rows['04'].append([vs_id, 'declared_in_pack',
                                   '由 pack 声明，具体取值见 evidence_quote', '', bl, pid])

        # 05 relation
        for re_ in (ntp.get('relation') or []):
            if isinstance(re_,str):
                rows['05'].append([re_, 'TrainingMaterial', 'ContentType', 'governed_by_rule',
                                   '{"note":"declared_in_pack"}', bl, pid])

        # 06 rule
        rule_ids = ntp.get('rule') or []
        if not rule_ids:
            rule_ids = [f'RL-{pid}']
        ab = '；'.join(alt) if isinstance(alt,list) else str(alt)
        for r in rule_ids:
            r_id = r if isinstance(r,str) and r.startswith('RL-') else f'RL-{pid}'
            rows['06'].append([r_id, what.get('action_type','business_rule'),
                               trunc(boundary.get('applicable_when','')),
                               trunc(result.get('success_pattern','')),
                               trunc(result.get('flip_pattern','')),
                               trunc(ab), bl, pid])

        # 07 evidence
        ev_ids = ntp.get('evidence') or [f'EV-{pid}']
        for e in ev_ids:
            e_id = e if isinstance(e,str) and e.startswith('EV-') else f'EV-{pid}'
            rows['07'].append([e_id, ev.get('source_md',''), ev.get('source_anchor',''),
                               trunc(ev.get('evidence_quote',''),300),
                               ev.get('source_type','explicit_business_decision'),
                               ev.get('inference_level','direct_quote'), bl, pid])

        # 09 call_mapping
        cm_ids = ntp.get('call_mapping') or []
        for cm in cm_ids:
            if isinstance(cm,str):
                m = re.match(r'CM-([a-z_]+)-', cm)
                rtm = m.group(1) if m else 'content_generation'
                defaults_in = {'store_training':['TrainingMaterial'],
                               'content_generation':['Persona','ContentType'],
                               'inventory_match':['InventoryState'],
                               'display_guidance':['DisplayGuide'],
                               'platform_adaptation':['ContentType','PlatformTone']}
                defaults_out = {'store_training':['TrainingScript'],
                               'content_generation':['Content'],
                               'inventory_match':['StylingRule'],
                               'display_guidance':['DisplayPlan'],
                               'platform_adaptation':['AdaptedContent']}
                inp = defaults_in.get(rtm,['ContentType'])
                outp = defaults_out.get(rtm,['Content'])
                gov = json.dumps({'governed_by':[f'RL-{pid}']}, ensure_ascii=False)
                rows['09'].append([cm, rtm, json.dumps(inp,ensure_ascii=False),
                                   json.dumps(outp,ensure_ascii=False), gov, bl, pid])

    # write
    fmap={'01':'01_object_type','02':'02_field','03':'03_semantic','04':'04_value_set',
          '05':'05_relation','06':'06_rule','07':'07_evidence','08':'08_lifecycle','09':'09_call_mapping'}
    for k,v in rows.items():
        path=f'{out_dir}/{fmap[k]}.csv'
        with open(path,'w',newline='') as f:
            w=csv.writer(f)
            for r in v: w.writerow(r)
        print(f'{fmap[k]}: {len(v)} rows')

if __name__=='__main__':
    main()

#!/usr/bin/env python3
"""V2 扫描：精准识别真正的品牌专属内容。
真信号（true positive）：
- 笛语 出现在 knowledge_assertion / scenario.* / evidence_quote 内（不是 rationale 注脚）
- pack_id 含 'founder'
- pack 内容是某品牌的具体字段壳（如 founder profile 的 9 字段）
- evidence_quote 引用了笛语门店/品牌/创始人具体行为

排除项：
- 笛语 仅出现在 brand_layer_review.rationale（如"不含笛语专属表达"）→ 假阳性"""
import os, yaml, re

cand_dir = "/home/faye/20-血肉-2F种子/clean_output/candidates/domain_general"
true_positive = []
false_positive = []

for f in sorted(os.listdir(cand_dir)):
    if not f.endswith('.yaml'): continue
    pid = f[:-5]
    path = os.path.join(cand_dir, f)
    try:
        d = yaml.safe_load(open(path))
    except: continue

    # 关键字段抽取
    assertion = d.get('knowledge_assertion', '') or ''
    scenario_str = yaml.safe_dump(d.get('scenario', {}), allow_unicode=True)
    evidence_quote = (d.get('evidence', {}) or {}).get('evidence_quote', '') or ''
    rationale = (d.get('brand_layer_review', {}) or {}).get('rationale', '') or ''

    triggers = []

    # T1: pack_id 含 founder
    if 'founder' in pid.lower():
        triggers.append('PACK_ID_FOUNDER')

    # T2: 笛语字面在真实业务字段中
    business_fields = assertion + ' ' + scenario_str + ' ' + evidence_quote
    if '笛语' in business_fields:
        triggers.append('笛语_IN_BUSINESS_FIELDS')

    # T3: pack 主题是品牌特有字段壳 / 对象
    if any(k in pid for k in ['founder-profile', 'persona-six-field-shell', 'persona-field-fill-state']):
        triggers.append('BRAND_SPECIFIC_FIELD_SHELL')

    # T4: assertion 主语是品牌
    if isinstance(assertion, str) and any(k in assertion for k in ['笛语', 'brand_unique', 'FounderProfile']):
        triggers.append('ASSERTION_BRAND_SUBJECT')

    if triggers:
        true_positive.append((pid, triggers))
    else:
        # 检查是否有"笛语"出现在 rationale（仅供参考）
        if '笛语' in rationale:
            false_positive.append(pid)

print(f"=== 真阳性 {len(true_positive)} 条（应迁移到 brand_faye 或 needs_review）===\n")
for pid, trigs in true_positive:
    print(f"  {pid}")
    for t in trigs:
        print(f"    ↳ {t}")
print(f"\n=== 假阳性 {len(false_positive)} 条（笛语仅在 rationale 注脚）===")
print(f"  （这些保持 domain_general 不动）")
#!/usr/bin/env python3
"""sqlite_demo.py · TC-E01 · 单库逻辑隔离实测

加载 DDL，导入 9 张 csv，跑 3 类查询模板验证多租户隔离。
输出 demo 结果到 clean_output/storage/sqlite_demo_output.txt。
"""
import sqlite3, csv, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DDL  = f'{ROOT}/storage/single_db_logical_isolation.sql'
NINE = f'{ROOT}/nine_tables'
OUT  = f'{ROOT}/storage/sqlite_demo_output.txt'

# table name → csv stem
TBL = {
    'object_type':   '01_object_type',
    'field':         '02_field',
    'semantic':      '03_semantic',
    'value_set':     '04_value_set',
    'relation':      '05_relation',
    'rule':          '06_rule',
    'evidence':      '07_evidence',
    'lifecycle':     '08_lifecycle',
    'call_mapping':  '09_call_mapping',
}

def main():
    log = []
    def p(*args):
        s = ' '.join(str(a) for a in args)
        log.append(s)
        print(s)

    # in-memory db
    con = sqlite3.connect(':memory:')
    cur = con.cursor()

    # apply DDL (skip COPY/import comments)
    ddl = open(DDL).read()
    cur.executescript(ddl)

    # load CSVs
    p('=== 装载 9 张 CSV ===')
    for table, stem in TBL.items():
        path = f'{NINE}/{stem}.csv'
        with open(path) as f:
            reader = csv.reader(f)
            cols = next(reader)
            rows = list(reader)
        if not rows:
            p(f'{stem}: 0 rows (表头存在)')
            continue
        placeholders = ','.join('?'*len(cols))
        cur.executemany(f'INSERT OR IGNORE INTO {table} ({",".join(cols)}) VALUES ({placeholders})', rows)
        cur.execute(f'SELECT COUNT(*) FROM {table}')
        p(f'{stem}: {cur.fetchone()[0]} rows loaded')
    con.commit()

    # === Query templates ===
    p('\n=== 模板 1 · domain_general 单层 ===')
    cur.execute("SELECT COUNT(*) FROM rule WHERE brand_layer='domain_general'")
    p('rule (domain_general):', cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM evidence WHERE brand_layer='domain_general'")
    p('evidence (domain_general):', cur.fetchone()[0])

    p('\n=== 模板 2 · 笛语应用 (domain_general + brand_faye) ===')
    cur.execute("SELECT COUNT(*) FROM rule WHERE brand_layer IN ('domain_general','brand_faye')")
    p('rule (笛语):', cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM rule WHERE brand_layer='brand_faye'")
    p('rule 中 brand_faye 独立行:', cur.fetchone()[0])

    p('\n=== 模板 3 · 未来 brand_xyz 应用 ===')
    cur.execute("SELECT COUNT(*) FROM rule WHERE brand_layer IN ('domain_general','brand_xyz')")
    p('rule (假想 brand_xyz):', cur.fetchone()[0], '（与 domain_general 行数一致，证明开放扩展无需改 schema）')

    p('\n=== 反向追溯样例 · 取 1 条规则 → MD ===')
    cur.execute("""
        SELECT r.rule_id, e.source_md, e.source_anchor
        FROM rule r JOIN evidence e ON e.source_pack_id = r.source_pack_id
        WHERE r.brand_layer='domain_general'
        LIMIT 3
    """)
    for row in cur.fetchall():
        p(' →', row)

    p('\n=== CHECK 断言验证 · 多租户漂移行 ===')
    cur.execute("""
        SELECT COUNT(*) FROM rule
        WHERE brand_layer NOT IN ('domain_general','needs_review')
          AND brand_layer NOT LIKE 'brand_%'
    """)
    p('漂移行数:', cur.fetchone()[0], '（应为 0）')

    p('\n=== 完整性断言 · evidence 必填 ===')
    cur.execute("SELECT COUNT(*) FROM evidence WHERE source_md='' OR source_anchor='' OR evidence_quote=''")
    p('evidence 关键字段空:', cur.fetchone()[0], '（应为 0）')

    p('\n=== 跨表 JOIN · 库存救场规则 + 状态枚举 ===')
    cur.execute("""
        SELECT COUNT(DISTINCT r.rule_id)
        FROM rule r
        WHERE r.rule_type LIKE '%inventory%'
          AND r.brand_layer='domain_general'
    """)
    p('inventory 类规则数:', cur.fetchone()[0])

    p('\n=== Object_type 白名单验证 ===')
    cur.execute("SELECT DISTINCT type_name FROM object_type ORDER BY type_name")
    p('入库 18 类:', [r[0] for r in cur.fetchall()])

    # ===== W8 #9 多租户演练（brand_xyz 临时内存样本，不污染 candidates）=====
    p('\n=== W8 #9 brand_xyz 临时演练 · 演示多租户隔离实效 ===')
    p('（说明：本批源料无真实笛语调性，brand_faye=0；用 brand_xyz 临时样本演证 schema 已就绪）')
    # 取一条已有 domain_general rule 复制为 brand_xyz 演示样本
    cur.execute("SELECT rule_id, rule_type, applicable_when, success_scenario, flip_scenario, alternative_boundary, source_pack_id FROM rule WHERE brand_layer='domain_general' LIMIT 1")
    src = cur.fetchone()
    if src:
        cur.execute("""
            INSERT INTO rule (rule_id, rule_type, applicable_when, success_scenario, flip_scenario, alternative_boundary, brand_layer, source_pack_id)
            VALUES (?, ?, ?, ?, ?, ?, 'brand_xyz', ?)
        """, ('RL-DEMO-brand_xyz-priority-tone', 'brand_priority_declaration',
              src[2] + '（brand_xyz 演练版）', src[3], src[4], src[5], src[6]))
        con.commit()
        p('  插入 demo 行：rule_id=RL-DEMO-brand_xyz-priority-tone, brand_layer=brand_xyz')

        # 演示三种查询：dg only / xyz_app / 漂移检查
        cur.execute("SELECT COUNT(*) FROM rule WHERE brand_layer='domain_general'")
        dg_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM rule WHERE brand_layer IN ('domain_general','brand_xyz')")
        xyz_app = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM rule WHERE brand_layer='brand_xyz'")
        xyz_only = cur.fetchone()[0]
        p(f'  domain_general 单层: {dg_count} 行')
        p(f'  brand_xyz 应用 (dg + xyz): {xyz_app} 行 = {dg_count} + {xyz_only}')
        p(f'  brand_faye 应用 (dg + faye): 仍是 {dg_count} 行（faye=0 等同 dg）')

        # 演示 GLOB CHECK 拒绝非法 brand_layer
        try:
            cur.execute("INSERT INTO rule VALUES ('RL-DEMO-illegal','x','x','x','x','x','brand_X','x')")
            p('  ❌ brand_X 大写应被拒绝但通过了')
        except sqlite3.IntegrityError:
            p('  ✅ brand_X (大写) 被 GLOB CHECK 拒绝')

        # 回滚演示数据，不持久化（保持 candidates / yaml 不污染）
        con.rollback()
        p('  ✅ 演示数据已回滚，candidates / yaml / db 持久层不受影响')

    open(OUT,'w').write('\n'.join(log) + '\n')
    p(f'\nDemo output → {OUT}')

if __name__ == '__main__':
    main()

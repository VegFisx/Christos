import csv, sys, json
from collections import Counter
p = r'D:/ProgramData/DSHNS/chemreact-staging/reports/query_inventory_paths.csv'
rows = list(csv.DictReader(open(p, encoding='utf-8-sig', newline='')))
print('cols:', list(rows[0].keys()))
c = Counter()
for r in rows:
    rn = r.get('rule_name','')
    co = r.get('co_products','') or ''
    has_w = 'O' in [x for x in co.split('|') if x]
    c[(rn.split('_')[0], has_w)] += 1
for k, v in sorted(c.items(), key=lambda x: -x[1])[:12]:
    print(k, v)
ex = [r for r in rows if r.get('rule_name','').startswith('mined')][:4]
for r in ex:
    print(json.dumps({'rule': r.get('rule_name'), 'co': r.get('co_products'), 'prod': (r.get('product') or '')[:40]}, ensure_ascii=True))

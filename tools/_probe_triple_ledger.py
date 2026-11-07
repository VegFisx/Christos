import csv
from collections import Counter
p=r'D:/ProgramData/DSHNS/chemreact-staging/reports/query_inventory_paths.csv'
rows=list(csv.DictReader(open(p,encoding='utf-8-sig',newline='')))
print('rows', len(rows))
print('by rule:', dict(Counter(r['rule_name'] for r in rows).most_common(8)))
tr=[r for r in rows if r['rule_name']=='mined_triple']
sup=Counter(int(r['template_support'] or 0) for r in tr)
print('mined_triple:', len(tr), 'support 分布:', dict(sorted(sup.items())[:8]))
print('direction:', dict(Counter(r['direction_cn'] for r in rows)))

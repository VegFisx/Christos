import csv, sys
p=r'D:/ProgramData/DSHNS/chemreact-staging/reports/query_inventory_paths.csv'
rows=list(csv.DictReader(open(p,encoding='utf-8-sig',newline='')))
has='cond_model' in rows[0]
n=sum(1 for r in rows if (r.get('cond_model') or '').strip())
print('cols_has_cond_model=%s  rows=%d  non_empty=%d' % (has, len(rows), n))
from collections import Counter
print('direction:', dict(Counter(r['direction_cn'] for r in rows)))
print('element_delta?', 'element_delta' in rows[0])

import csv
from collections import Counter
p=r'D:/ProgramData/DSHNS/chemreact-staging/reports/query_inventory_paths.csv'
rows=list(csv.DictReader(open(p,encoding='utf-8-sig',newline='')))
print('rows', len(rows))
print('by rule:', dict(Counter(r['rule_name'] for r in rows).most_common(8)))

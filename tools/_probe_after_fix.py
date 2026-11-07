import csv, sys
from collections import Counter
p=r'D:/ProgramData/DSHNS/chemreact-staging/reports/query_inventory_paths.csv'
rows=list(csv.DictReader(open(p,encoding='utf-8-sig',newline='')))
print('rows', len(rows), 'cols has element_delta:', 'element_delta' in rows[0])
print('direction:', dict(Counter(r['direction_cn'] for r in rows)))
print('by source:', dict(Counter(r['direction_source'] for r in rows)))
mono=[r for r in rows if r['rule_name'].startswith('mined')]
print('mined rows', len(mono), 'with element_delta_shape:', sum(1 for r in mono if r['direction_source']=='element_delta_shape'))
print('sample element_delta (mined):', [r['element_delta'] for r in mono[:5]])
print('sample element_delta (esterification):', [r['element_delta'] for r in rows if r['rule_name']=='esterification'][:3])

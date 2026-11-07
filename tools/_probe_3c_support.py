import json
from collections import Counter
p=r'D:/ProgramData/DSHNS/chemreact-staging/reports/mined_forward_templates_3c.jsonl'
sup=[]
for line in open(p,encoding='utf-8'):
    line=line.strip()
    if not line: continue
    sup.append(int(json.loads(line).get('support',0)))
c=Counter(sup)
print('templates', len(sup))
print('support 分布(前12):', dict(sorted(c.items())[:12]))
for k in (1,2,3,5,10):
    print('  support >= %-2d -> %d 条' % (k, sum(1 for s in sup if s>=k)))

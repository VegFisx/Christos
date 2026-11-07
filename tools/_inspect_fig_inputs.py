import json
from pathlib import Path
R = Path(r'D:\ProgramData\DSHNS\chemreact-staging\reports')
rows = [json.loads(l) for l in open(R/'retro_template_audit.jsonl', encoding='utf-8') if l.strip()]
print('rows', len(rows), 'keys sample', sorted(rows[0].keys())[:14])
missing = sum(1 for r in rows if 'n_usable' not in r)
print('missing n_usable', missing, 'n_try>0', sum(1 for r in rows if int(r.get('n_try',0))>0))
s = json.loads((R/'paper'/'results'/'instability.json').read_text(encoding='utf-8'))
print('instability top keys', list(s.keys()))
u = s['ustat']
print('ustat keys', list(u.keys()))
for k,v in u.items():
    print(' ', k, {kk: vv for kk, vv in list(v.items())[:6]} if isinstance(v, dict) else v)
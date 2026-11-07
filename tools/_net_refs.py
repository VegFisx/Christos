import json, sys, urllib.request
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
dois = ['10.1186/s13321-020-00472-1','10.1186/s13321-020-00478-9','10.1039/d2dd00015f','10.1039/d4fd00093e','10.1039/d3dd00252g']
for d in dois:
    req = urllib.request.Request('https://api.crossref.org/works/' + d, headers={'User-Agent':'ChristosPaper/0.1 (mailto:noreply@example.com)'})
    m = json.load(urllib.request.urlopen(req, timeout=30))['message']
    auth = ', '.join((a.get('family','') + ' ' + (a.get('given','')[:1] or '')) for a in m.get('author', []))
    print(d)
    print('  ', m['title'][0])
    print('  ', (m.get('container-title') or ['-'])[0], '| vol', m.get('volume'), '| issue', m.get('issue'), '| page', m.get('page'), '| art', m.get('article-number'), '|', m.get('issued',{}).get('date-parts',[['?']])[0][0])
    print('  ', auth[:220])
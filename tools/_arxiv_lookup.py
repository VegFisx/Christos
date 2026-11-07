import sys, urllib.parse, urllib.request, re
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
UA='ChristosPaper/0.1'
def arxiv(q):
    u='http://export.arxiv.org/api/query?search_query=' + urllib.parse.quote(q) + '&max_results=3'
    x=urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent':UA}), timeout=40).read().decode('utf-8','replace')
    for m in re.finditer(r'<entry>(.*?)</entry>', x, re.S):
        e=m.group(1)
        t=re.search(r'<title>(.*?)</title>', e, re.S)
        i=re.search(r'<id>(.*?)</id>', e, re.S)
        print('  ', (t.group(1).strip().replace(chr(10),' ') if t else '?')[:90], '|', (i.group(1) if i else '?'))
print('retro*'); arxiv('ti:"Retro*" AND ti:"retrosynthetic"')
print('paroutes'); arxiv('ti:PaRoutes')
print('rdchiral'); arxiv('ti:RDChiral')
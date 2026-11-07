import json, sys, time, urllib.parse, urllib.request
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'
def s2(q):
    u='https://api.semanticscholar.org/graph/v1/paper/' + urllib.parse.quote(q) + '?fields=title,year,openAccessPdf,externalIds'
    try:
        r=urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent':UA}), timeout=30)
        return json.load(r)
    except Exception as e:
        return {'error': type(e).__name__ + ':' + str(e)[:60]}
for d in ['DOI:10.1039/d2dd00015f','DOI:10.1021/jacs.1c09820','DOI:10.1021/acs.jcim.9b00286']:
    j=s2(d)
    print(d, '|', (j.get('title') or '')[:60], '|', j.get('openAccessPdf'))
    time.sleep(1.2)
j=s2('Retro*: Learning Retrosynthetic Planning with Neural Guided A* Search')
print('retro*', j.get('title'), j.get('openAccessPdf'))
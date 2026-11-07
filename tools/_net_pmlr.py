import re, urllib.request, sys
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
p = urllib.request.urlopen(urllib.request.Request('https://proceedings.mlr.press/v119/chen20k.html', headers={'User-Agent':'x'}), timeout=40).read().decode('utf-8','replace')
m = re.findall(r'PMLR 119:[0-9\-–]+', p)
print(m[:3])
for mm in re.finditer(r'<meta name="citation_[a-z_]+" content="([^"]*)"', p):
    print(mm.group(1)[:160])
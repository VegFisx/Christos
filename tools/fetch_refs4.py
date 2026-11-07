import re, sys, time, urllib.request
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'
def text(u, t=40):
    r=urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent':UA,'Accept':'text/html,*/*'}), timeout=t)
    return r.read().decode('utf-8','replace')
print('--- ORD caltech ---')
try:
    h=text('https://authors.library.caltech.edu/111994/')
    pdfs=re.findall(r'href="([^"]+\.pdf)"', h)
    print('pdf links', pdfs[:4])
except Exception as e: print('ERR', type(e).__name__, str(e)[:80])
print('--- RDChiral dspace ---')
try:
    h=text('https://dspace.mit.edu/handle/1721.1/134762')
    pdfs=re.findall(r'href="([^"]*bitstream[^"]*)"', h)
    print('bitstreams', pdfs[:4])
except Exception as e: print('ERR', type(e).__name__, str(e)[:80])
print('--- PMLR retry ---')
for i in range(2):
    try:
        r=urllib.request.urlopen(urllib.request.Request('https://proceedings.mlr.press/v119/chen20k/chen20k.pdf', headers={'User-Agent':UA}), timeout=50)
        d=r.read()
        print('PMLR', len(d), d[:4])
        break
    except Exception as e:
        print('PMLR err', i, type(e).__name__, str(e)[:60]); time.sleep(2)
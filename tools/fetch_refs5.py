import sys, time, urllib.request
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\references")
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'
def grab(key, url, referer=None, t=50):
    h={'User-Agent':UA,'Accept':'application/pdf,*/*'}
    if referer: h['Referer']=referer
    try:
        r=urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=t)
        d=r.read()
        if d[:4]==b'%PDF':
            (OUT/(key+'.pdf')).write_bytes(d); print('OK', key, len(d))
        else:
            print('BAD', key, r.status, len(d), r.headers.get('Content-Type'))
    except Exception as e:
        print('ERR', key, type(e).__name__, str(e)[:70])
grab('kearnes2021_ord', 'https://authors.library.caltech.edu/records/2mmp6-a6d71/files/jacs.1c09820.pdf')
grab('chen2020_retrostar', 'http://proceedings.mlr.press/v119/chen20k/chen20k.pdf')
grab('genheden2022_paroutes', 'https://pubs.rsc.org/en/content/articlepdf/2022/dd/d2dd00015f?page=search', referer='https://pubs.rsc.org/en/content/articlelanding/2022/dd/d2dd00015f')
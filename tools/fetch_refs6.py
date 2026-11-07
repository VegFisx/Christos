import sys, time, urllib.request
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\references")
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'
def grab(key, url, referer=None, t=55):
    h={'User-Agent':UA,'Accept':'application/pdf,*/*'}
    if referer: h['Referer']=referer
    try:
        d=urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=t).read()
        if d[:4]==b'%PDF':
            (OUT/(key+'.pdf')).write_bytes(d); print('OK', key, len(d))
        else:
            print('BAD', key, len(d))
    except Exception as e:
        print('ERR', key, type(e).__name__, str(e)[:70])
grab('chen2020_retrostar', 'https://export.arxiv.org/pdf/2006.15820')
time.sleep(2)
grab('c2019_rdchiral', 'https://dspace.mit.edu/bitstream/handle/1721.1/134762/rdchiral.pdf')
time.sleep(2)
grab('genheden2022_paroutes', 'https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/621c86f3c3e9da4f737b0047/original/pa-routes-a-framework-for-benchmarking-retrosynthesis-route-predictions.pdf', referer='https://chemrxiv.org/')
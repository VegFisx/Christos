import sys, urllib.request
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\references")
def grab(key, url, t=45):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':UA}), timeout=t)
        data = r.read()
        if data.startswith(b'%PDF'):
            (OUT/(key+'.pdf')).write_bytes(data); print('OK', key, len(data))
        else:
            print('BAD', key, len(data), r.headers.get('Content-Type'))
    except Exception as e:
        print('ERR', key, type(e).__name__, str(e)[:70])
grab('genheden2022_paroutes', 'https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/621c86f3c3e9da4f737b0047/original/pa-routes-a-framework-for-benchmarking-retrosynthesis-route-predictions.pdf')
grab('kearnes2021_ord', 'https://dspace.mit.edu/bitstream/1721.1/162573/2/kearnes-et-al-2021-the-open-reaction-database.pdf')
import json, re, sys, urllib.request, hashlib, time
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\references")
def fetch(u, t=90):
    r = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent':UA}), timeout=t)
    return r.read()

targets = [
 ('genheden2022_paroutes', 'https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/621c86f3c3e9da4f737b0047/original/pa-routes-a-framework-for-benchmarking-retrosynthesis-route-predictions.pdf'),
 ('kearnes2021_ord', 'https://dspace.mit.edu/bitstream/1721.1/162573/2/kearnes-et-al-2021-the-open-reaction-database.pdf'),
 ('torrenperaire2024_modelsmatter', 'https://arxiv.org/pdf/2308.05522'),
 ('chen2020_retrostar', 'https://proceedings.mlr.press/v119/chen20k/chen20k.pdf'),
]

def save(key, data):
    p = OUT / (key + '.pdf')
    p.write_bytes(data)
    return p

for key, url in targets:
    try:
        data = fetch(url)
        if data.startswith(b'%PDF'):
            p = save(key, data)
            print('OK  ', key, len(data), url[:60])
        else:
            print('BAD ', key, 'not pdf', len(data), url[:60])
    except Exception as e:
        print('ERR ', key, type(e).__name__, str(e)[:80], url[:60])
    time.sleep(0.5)

# RDChiral: MIT DSpace handle -> find bitstream pdf
try:
    html = fetch('https://hdl.handle.net/1721.1/134762').decode('utf-8','replace')
    cands = re.findall(r'href="([^"]+bitstream[^"]+\.pdf[^"]*)"', html)
    print('rdchiral candidates', cands[:3])
    if cands:
        u = cands[0]
        if u.startswith('/'): u = 'https://dspace.mit.edu' + u
        data = fetch(u)
        if data.startswith(b'%PDF'):
            save('c2019_rdchiral', data)
            print('OK   c2019_rdchiral', len(data))
        else:
            print('BAD  rdchiral not pdf', len(data))
except Exception as e:
    print('ERR  rdchiral', type(e).__name__, str(e)[:100])

for p in sorted(OUT.glob('*.pdf')):
    print(p.name, p.stat().st_size)
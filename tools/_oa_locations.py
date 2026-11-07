import json, sys, urllib.request, hashlib
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
def get(u, t=60):
    return urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent':UA}), timeout=t)
for d in ['10.1039/d2dd00015f','10.1021/jacs.1c09820','10.1021/acs.jcim.9b00286']:
    w=json.load(get('https://api.openalex.org/works/https://doi.org/'+d))
    print('##', d)
    for loc in w.get('locations',[]):
        print('   pdf:', loc.get('pdf_url'))
        print('   land:', loc.get('landing_page_url'))
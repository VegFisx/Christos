# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\references")
JOBS = [
 ('genheden2022_paroutes', 'https://doi.org/10.1039/d2dd00015f', 'https://pubs.rsc.org/en/content/articlepdf/2022/dd/d2dd00015f'),
 ('kearnes2021_ord', 'https://doi.org/10.1021/jacs.1c09820', 'https://pubs.acs.org/doi/pdf/10.1021/jacs.1c09820'),
 ('c2019_rdchiral', 'https://doi.org/10.26434/chemrxiv.7949024', None),
 ('chen2020_retrostar', 'https://proceedings.mlr.press/v119/chen20k.html', 'https://proceedings.mlr.press/v119/chen20k/chen20k.pdf'),
]
with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', headless=True)
    ctx = b.new_context(accept_downloads=True, user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36')
    for key, landing, pdf in JOBS:
        try:
            pg = ctx.new_page()
            pg.goto(landing, wait_until='domcontentloaded', timeout=45000)
            pg.wait_for_timeout(1500)
            target = pdf
            if not target:
                hrefs = pg.eval_on_selector_all('a', 'as=>as.map(a=>a.href).filter(h=>/\.pdf($|\?)/i.test(h))')
                target = hrefs[0] if hrefs else None
            if not target:
                print('NOURL', key); pg.close(); continue
            resp = ctx.request.get(target, timeout=60000)
            body = resp.body()
            if body[:4] == b'%PDF':
                (OUT / (key + '.pdf')).write_bytes(body)
                print('OK', key, len(body))
            else:
                print('BAD', key, resp.status, resp.headers.get('content-type'), len(body))
            pg.close()
        except Exception as e:
            print('ERR', key, type(e).__name__, str(e)[:80])
    b.close()
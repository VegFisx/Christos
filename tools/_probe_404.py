import time
from playwright.sync_api import sync_playwright
bad=[]; errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel="msedge", headless=True)
    pg=b.new_page(viewport={'width':1180,'height':820})
    pg.on('response', lambda r: bad.append((r.status, r.url)) if r.status>=400 else None)
    pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    pg.goto("http://127.0.0.1:4334/", wait_until="networkidle")
    pg.wait_for_selector('#entrySelect')
    pg.click('#runBtn'); pg.wait_for_selector('#result table')
    pg.click('.nav button[data-mode="formula"]'); pg.wait_for_selector('#entrySelect')
    pg.click('#runBtn'); pg.wait_for_selector('#result table')
    time.sleep(0.5)
    b.close()
print('bad',bad); print('errs',errs)
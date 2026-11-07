import sys, time, json
from playwright.sync_api import sync_playwright
url = sys.argv[1]
with sync_playwright() as p:
    b=p.chromium.launch(channel="msedge", headless=True)
    pg=b.new_page()
    pg.goto(url, wait_until='networkidle')
    pg.wait_for_selector('#exitBtn')
    pg.click('#exitBtn')
    pg.wait_for_timeout(800)
    print('body:', pg.inner_text('body')[:60].replace(chr(10),' '))
    b.close()
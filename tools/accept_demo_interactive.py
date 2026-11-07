# -*- coding: utf-8 -*-
"""Interactive acceptance for the frozen Christos-Demo build (Playwright + local HTTP)."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4334/"
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\_accept_20261019")
OUT.mkdir(parents=True, exist_ok=True)
PRED = json.loads(Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\desktop-build\christos-demo\demo_predictions.json").read_text(encoding="utf-8"))["items"]

errors, reqfail = [], []
report = {'base': BASE, 'herbs': [], 'formulas': [], 'search': [], 'errors': errors, 'request_failures': reqfail}

def snap(page, name):
    page.screenshot(path=str(OUT / (name + ".png")), full_page=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={'width': 1180, 'height': 820})
    page.on('console', lambda m: errors.append('console:' + m.type + ':' + m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append('pageerror:' + str(e)))
    page.on('requestfailed', lambda r: reqfail.append(r.url + ' :: ' + str(r.failure)))
    page.goto(BASE, wait_until='networkidle')
    page.wait_for_selector('#entrySelect')
    report['title'] = page.title()
    report['herb_count'] = page.eval_on_selector_all('#entrySelect option', 'o=>o.length')
    report['first_options'] = page.eval_on_selector_all('#entrySelect option', 'o=>o.slice(0,4).map(x=>x.value)')

    def pick(names):
        opts = page.eval_on_selector_all('#entrySelect option', 'o=>o.map(x=>x.value)')
        out = []
        for n in names:
            out.append(n if n in opts else opts[len(out) * 17 % len(opts)])
        return out

    def run_one(mode, name, idx):
        page.select_option('#entrySelect', name)
        page.click('#runBtn')
        page.wait_for_selector('#result table', timeout=8000)
        time.sleep(0.2)
        data = page.evaluate('''() => {
          const stats=[...document.querySelectorAll('#result .stat')].map(s=>s.querySelector('b').textContent+'|'+s.querySelector('span').textContent);
          const rows=[...document.querySelectorAll('#result tbody tr')].map(tr=>[...tr.children].map(td=>td.textContent));
          const warn=(document.querySelector('#result .warnText')||{}).textContent||'';
          const info=(document.querySelector('#result details pre')||{}).textContent||'';
          const basis=[...document.querySelectorAll('#result p.hint')].map(p=>p.textContent);
          const bodyText=document.querySelector('#result').innerText;
          return {stats, rows, warn, smi:info.slice(0,400), basis, hasTable:!!document.querySelector('#result table'), bodyLen:bodyText.length};
        }''')
        key = ('herb:' if mode == 'herb' else 'formula:') + name
        pred = PRED.get(key)
        data['name'] = name
        data['key'] = key
        data['pred_present'] = bool(pred)
        data['pred_products'] = len(pred['products']) if pred else None
        data['pred_stats'] = pred['stats'] if pred else None
        data['match_first_formula'] = bool(pred and data['rows'] and data['rows'][0][0] == (pred['products'][0].get('formula') or '—'))
        snap(page, mode + '_' + str(idx) + '_' + str(report['herbs'].__len__() + report['formulas'].__len__()))
        return data

    herb_names = pick(['甘草', '黄芪', '当归', '人参', '川芎', '茯苓', '陈皮', '桂枝'])
    for i, n in enumerate(herb_names[:5]):
        report['herbs'].append(run_one('herb', n, i))

    page.click('.nav button[data-mode="formula"]')
    page.wait_for_selector('#entrySelect')
    report['formula_count'] = page.eval_on_selector_all('#entrySelect option', 'o=>o.length')
    formula_names = pick(['四君子汤', '桂枝汤', '小柴胡汤', '当归补血汤', '六味地黄丸', '二陈汤'])
    seen = set()
    uniq = [x for x in formula_names if not (x in seen or seen.add(x))]
    for i, n in enumerate(uniq[:5]):
        report['formulas'].append(run_one('formula', n, i))

    # search flow (herb mode)
    page.click('.nav button[data-mode="herb"]')
    page.wait_for_selector('#entrySelect')
    for q in ['甘草', '不存在的中药名']:
        page.fill('#find', q)
        page.click('#findBtn')
        time.sleep(0.2)
        report['search'].append({'q': q, 'result': page.inner_text('#findResult')})
    page.fill('#find', '甘草')
    page.click('#findBtn')
    time.sleep(0.2)
    page.click('#runBtn')
    page.wait_for_selector('#result table')
    report['search_after_run_rows'] = page.eval_on_selector_all('#result tbody tr', 'r=>r.length')
    snap(page, 'final_state')
    browser.close()

(OUT / 'accept_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps({
  'title': report['title'], 'herbs': report['herb_count'], 'formulas': report['formula_count'],
  'herb_runs': [(h['name'], h['stats'], len(h['rows']), h['match_first_formula'], h['pred_present']) for h in report['herbs']],
  'formula_runs': [(f['name'], f['stats'], len(f['rows']), f['match_first_formula'], f['pred_present'], f['warn'][:40]) for f in report['formulas']],
  'search': report['search'], 'search_rows': report.get('search_after_run_rows'),
  'errors': errors, 'request_failures': reqfail
}, ensure_ascii=False, indent=1))
# -*- coding: utf-8 -*-
import json, re, sys, urllib.parse, urllib.request, time
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

def get(u):
    req = urllib.request.Request(u, headers={'User-Agent':'ChristosPaper/0.1'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()

def oa(u):
    return json.loads(get(u).decode('utf-8'))

def abstract(w):
    inv = w.get('abstract_inverted_index') or {}
    if not inv: return '(no abstract)'
    pos = {}
    for word, idxs in inv.items():
        for i in idxs: pos[i] = word
    return ' '.join(pos[i] for i in sorted(pos))

print('=== PMLR v119 Retro* ===')
html = get('https://proceedings.mlr.press/v119/').decode('utf-8', 'replace')
for m in re.finditer(r'<p class="title">([^<]*Retro[^<]*)</p>(.{0,600}?)</div>', html, re.S):
    title = m.group(1)
    blk = m.group(2)
    pages = re.search(r'(d+[-–]d+)', blk)
    auths = re.findall(r'>([A-Z][^<>,]{2,30})</a>', blk)[:6]
    print(title, '| pages', pages.group(1) if pages else '?', '|', ', '.join(auths))

print()
print('=== evaluation papers ===')
for doi in ['10.1039/d4fd00093e', '10.1039/d3dd00252g']:
    w = oa('https://api.openalex.org/works/https://doi.org/' + doi)
    print('##', w['title'], '|', w['publication_year'], '| cites', w['cited_by_count'])
    print(abstract(w)[:900].replace(chr(10),' '))
    print()

for q in ['template quality retrosynthesis filtering', 'search width candidates retrosynthesis beam', 'benchmark leakage retrosynthesis evaluation']:
    d = oa('https://api.openalex.org/works?per-page=5&search=' + urllib.parse.quote(q))
    print('###', q, d['meta']['count'])
    for w in d['results']:
        print('  %s | %s | cites=%s' % (w.get('publication_year'), (w.get('title') or '')[:100], w.get('cited_by_count')))
    time.sleep(0.3)
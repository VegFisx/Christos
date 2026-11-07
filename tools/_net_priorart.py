# -*- coding: utf-8 -*-
import json, sys, urllib.parse, urllib.request, time
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

def oa(q, n=5):
    u = 'https://api.openalex.org/works?per-page=%d&search=%s' % (n, urllib.parse.quote(q))
    with urllib.request.urlopen(u, timeout=30) as r:
        return json.load(r)

queries = [
  ('nov1-template-audit', 'template audit retrosynthesis'),
  ('nov2-toxic-templates', 'toxic templates retrosynthesis false routes'),
  ('nov3-eval-repro', 'retrosynthesis evaluation reproducibility pitfalls'),
  ('nov4-validity-filter', 'route validity filter retrosynthesis usability'),
  ('retrostar', 'Retro* Learning Retrosynthetic Planning with Neural Guided A* Search'),
]
for k, q in queries:
    try:
        d = oa(q)
        print('###', k, 'count=', d['meta']['count'])
        for w in d['results']:
            src = '-'
            pl = w.get('primary_location') or {}
            if pl.get('source'): src = pl['source'].get('display_name', '-')
            print('  %s | %s | %s | cites=%s | %s' % (w.get('publication_year'), (w.get('title') or '')[:110], src, w.get('cited_by_count'), w.get('doi')))
    except Exception as e:
        print('ERR', k, e)
    time.sleep(0.4)
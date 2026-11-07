# -*- coding: utf-8 -*-
"""Verify reference DOIs and fetch open-access PDFs into reports/paper/references/."""
import hashlib, json, sys, time, urllib.request, urllib.error
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\references")
OUT.mkdir(parents=True, exist_ok=True)
UA = 'ChristosPaper/0.1 (mailto:noreply@example.com)'

REFS = [
 ('c2019_rdchiral', '10.1021/acs.jcim.9b00286'),
 ('chen2020_retrostar', None),
 ('genheden2020_aizynth', '10.1186/s13321-020-00472-1'),
 ('genheden2022_paroutes', '10.1039/d2dd00015f'),
 ('kearnes2021_ord', '10.1021/jacs.1c09820'),
 ('maziarz2025_syntheseus', '10.1039/d4fd00093e'),
 ('schneider2016_whatswhat', '10.1021/acs.jcim.6b00564'),
 ('sorokina2021_coconut', '10.1186/s13321-020-00478-9'),
 ('torrenperaire2024_modelsmatter', '10.1039/d3dd00252g'),
]

def get(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/pdf,*/*'})
    return urllib.request.urlopen(req, timeout=timeout)

def oa_info(doi):
    try:
        with get('https://api.openalex.org/works/https://doi.org/' + doi, 30) as r:
            w = json.load(r)
        loc = w.get('best_oa_location') or {}
        return {'title': w.get('title'), 'year': w.get('publication_year'),
                'is_oa': bool(w.get('open_access', {}).get('is_oa')),
                'pdf_url': loc.get('pdf_url'), 'landing': loc.get('landing_page_url'),
                'license': loc.get('license')}
    except Exception as e:
        return {'error': str(e)}

def fetch_pdf(url):
    try:
        with get(url) as r:
            ctype = r.headers.get('Content-Type', '')
            data = r.read()
        if not data.startswith(b'%PDF'):
            return None, 'not-pdf (%s, %d bytes)' % (ctype[:30], len(data))
        return data, 'ok'
    except urllib.error.HTTPError as e:
        return None, 'HTTP %s' % e.code
    except Exception as e:
        return None, type(e).__name__ + ': ' + str(e)[:80]

manifest = []
for key, doi in REFS:
    rec = {'key': key, 'doi': doi}
    if doi:
        info = oa_info(doi)
        rec.update({k: info.get(k) for k in ('title', 'year', 'is_oa', 'license')})
        pdf_url = info.get('pdf_url')
    else:
        rec.update({'title': 'Retro*: Learning Retrosynthetic Planning with Neural Guided A* Search', 'year': 2020, 'is_oa': True, 'license': 'PMLR'})
        pdf_url = 'https://proceedings.mlr.press/v119/chen20k/chen20k.pdf'
    rec['pdf_url'] = pdf_url
    if pdf_url:
        data, status = fetch_pdf(pdf_url)
        rec['fetch'] = status
        if data:
            p = OUT / (key + '.pdf')
            p.write_bytes(data)
            rec['file'] = p.name
            rec['bytes'] = len(data)
            rec['sha256'] = hashlib.sha256(data).hexdigest()[:16]
    else:
        rec['fetch'] = 'no open-access pdf'
    manifest.append(rec)
    print(key, '|', rec.get('fetch'), '|', rec.get('is_oa'), '|', (pdf_url or '-')[:70])
    time.sleep(0.5)

(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
print('pdfs', sum(1 for m in manifest if m.get('file')), 'of', len(manifest))
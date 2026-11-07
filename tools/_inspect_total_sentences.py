import zipfile, sys, re, json
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
sys.path[:0]=['tools']
from gold_check_chp2025 import strip_wikilinks
zf=zipfile.ZipFile(r'D:/ProgramData/DSHNS/chemreact-staging/reports/_probe_net/indkb.zip')
idx={}
for n in zf.namelist():
    if n.lower().endswith('.md'): idx.setdefault(n.rsplit('/',1)[-1][:-3], n)
CASES=[('五福化毒片','0.3mg'),('益心舒颗粒','0.9mg'),('干姜','0.6%')]
for herb,val in CASES:
    p=idx.get(herb)
    print('='*70); print(herb,'/',val,'->',p)
    if not p: continue
    t=strip_wikilinks(zf.read(p).decode('utf-8','replace'))
    print('  纯文本里是否有该数值:', val.replace('%','') in t.replace('%','') , '| 直接含 "'+val+'":', val in t)
    for m in re.finditer('不得少于', t):
        s=max(0,m.start()-70); print('   ...', t[s:m.start()+60].replace(chr(10),' '))

# -*- coding: utf-8 -*-
import re, sys
import xml.etree.ElementTree as ET
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
BASE = Path('D:/ProgramData/DSHNS/chemreact-staging/reports/paper/literature_validation_fulltext_20261030')
pat = re.compile(r'(°C|℃|steam|steaming|water bath|reflux|heating|heated|autoclav|h at|min at|for \d+\s*h)', re.I)
for p in sorted(BASE.glob('*.xml')):
    try:
        root = ET.parse(p).getroot()
    except Exception as ex:
        print(p.name, 'parse fail', ex); continue
    text = ' '.join(''.join(root.itertext()).split())
    sents = re.split(r'(?<=[.!?])\s+', text)
    hits = [s for s in sents if pat.search(s) and 40 < len(s) < 400][:3]
    print('==', p.name)
    for s in hits:
        print('  ', s[:300])
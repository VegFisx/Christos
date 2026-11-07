import sys, json
sys.path[:0]=['libs','tools','core']
from collections import Counter
import rdkit_template_lib as L
from pathlib import Path
STAGE=Path(r'D:/ProgramData/DSHNS/chemreact-staging')
for name in ['mined_extra_templates.jsonl','mined_mono_templates.jsonl']:
    p=STAGE/'reports'/name
    if not p.exists():
        print(name,'MISSING'); continue
    ts=L.load_mined_templates(p)
    by,fail=L.compile_templates_all(ts)
    print(name, 'templates=', len(ts), 'compile_fail=', fail, 'arity_counts=', dict(sorted((k,len(v)) for k,v in by.items())))

import sys, json
sys.path[:0]=['libs','tools','core']
import rdkit_template_lib as L
from pathlib import Path
STAGE=Path(r'D:/ProgramData/DSHNS/chemreact-staging')
p=STAGE/'reports'/'mined_forward_templates.jsonl'
ts=L.load_mined_templates(p)
by,fail=L.compile_templates_all(ts)
print('mined_forward_templates.jsonl', 'templates=',len(ts),'compile_fail=',fail,'arity=',dict(sorted((k,len(v)) for k,v in by.items())))
c2,f2=L.compile_templates(ts)
print('  compile_templates() 只留 arity=2 ->', len(c2), '  被算进 n_fail 的 =', f2)

import sys, json
from collections import Counter
sys.path[:0]=['libs','tools','core']
from rdkit import Chem, RDLogger
from rdkit.Chem import rdChemReactions
RDLogger.DisableLog('rdApp.*')
P='libs/smartreact/data/templates.txt'
n=0; c=Counter(); bad=0; byname=Counter()
for line in open(P,encoding='utf-8'):
    line=line.rstrip(chr(10))
    if not line or line.startswith('reaction_name'): continue
    cols=line.split(chr(9))
    if len(cols)<4: bad+=1; continue
    sma=cols[3]
    try:
        rxn=rdChemReactions.ReactionFromSmarts(sma)
    except Exception:
        bad+=1; continue
    if rxn is None: bad+=1; continue
    c[rxn.GetNumReactantTemplates()]+=1
    n+=1
print(json.dumps({'templates_parsed':n,'failed':bad,'n_reactant_templates':dict(sorted(c.items()))},ensure_ascii=True))

import sys, csv
sys.path[:0]=['tools','core','libs']
from rdkit import Chem, RDLogger
from rdkit.Chem import rdFMCS, rdMolDescriptors
import retro_search as rs
RDLogger.DisableLog('rdApp.*')
USABILITY_MIN_TARGET_HAC=12; USABILITY_RESIDUE_MCS_FRAC=0.80; USABILITY_INERT_HAC=2
ABSURD=rs.ABSURD_PRECURSORS; ABSURD_MAX=rs.ABSURD_MAX_TARGET_HAC
def old_step(target, precursors):
    t=Chem.MolFromSmiles(target)
    if t is None: return False,'目标无法解析'
    th=t.GetNumHeavyAtoms()
    for ps in precursors:
        p=Chem.MolFromSmiles(ps)
        if p is None: return False,'前体无法解析'
        ph=p.GetNumHeavyAtoms()
        if ph>th: return False,'R2_前体大于目标'
        if th>=USABILITY_MIN_TARGET_HAC and ph>=th-2:
            try:
                mcs=rdFMCS.FindMCS([t,p],timeout=2,atomCompare=rdFMCS.AtomCompare.CompareElements,bondCompare=rdFMCS.BondCompare.CompareOrder,ringMatchesRingOnly=True,completeRingsOnly=True)
                if mcs.numAtoms>=th*USABILITY_RESIDUE_MCS_FRAC: return False,'R1_残基路线'
            except Exception: pass
        if th>15 and ph<=USABILITY_INERT_HAC: return False,'R3_惰性小分子'
        if ps in ABSURD and th>ABSURD_MAX: return False,'R4_荒谬前体(CO2/无机小分子)'
    return True,'ok'
rows=list(csv.DictReader(open(r'D:/ProgramData/DSHNS/chemreact-staging/reports/query_inventory_paths.csv',encoding='utf-8-sig',newline='')))
targets=[r['product_smiles'] for r in rows[:2]]
tmpl=rs.load_rdchiral_templates()[:400]
from rdkit.Chem import rdChemReactions
cmp_n=0; diff=0; ex=[]
rs.reset_usability_stats()
for tgt in targets:
    m=Chem.MolFromSmiles(tgt)
    for t in tmpl:
        try: rx=rdChemReactions.ReactionFromSmarts(t.smarts)
        except Exception: continue
        try: outs=rx.RunReactants((m,))
        except Exception: continue
        for tup in outs:
            pr=tuple(rs.canon(Chem.MolToSmiles(x)) for x in tup if x is not None)
            pr=tuple(x for x in pr if x)
            if not pr: continue
            a=rs.step_usability(tgt,pr); b=old_step(tgt,pr)
            cmp_n+=1
            if a!=b:
                diff+=1
                if len(ex)<3: ex.append((tgt[:24],pr,a,b))
print('比较 %d 组；不一致 %d' % (cmp_n,diff))
print('统计:', rs.USTAT)
for e in ex: print('  差异:', e)

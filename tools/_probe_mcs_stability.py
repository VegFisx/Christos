import sys, time
sys.path[:0]=['tools','core','libs']
from rdkit import Chem, RDLogger
from rdkit.Chem import rdFMCS
RDLogger.DisableLog('rdApp.*')
import retro_search as rs
rows=__import__('csv').DictReader(open(r'D:/ProgramData/DSHNS/chemreact-staging/reports/query_inventory_paths.csv',encoding='utf-8-sig',newline=''))
tgt=next(rows)['product_smiles']
t=Chem.MolFromSmiles(tgt); p=Chem.MolFromSmiles(tgt)
print('target hac:', t.GetNumHeavyAtoms())
for k in range(3):
    t0=time.time()
    mcs=rdFMCS.FindMCS([t,p],timeout=2,atomCompare=rdFMCS.AtomCompare.CompareElements,bondCompare=rdFMCS.BondCompare.CompareOrder,ringMatchesRingOnly=True,completeRingsOnly=True)
    print('  MCS numAtoms=%d  %.2fs  (阈值 %d)' % (mcs.numAtoms, time.time()-t0, t.GetNumHeavyAtoms()*0.8))
print('元素计数:', rs._elem_counts(tgt))
print('上界:', rs._common_atom_upper_bound(rs._elem_counts(tgt), rs._elem_counts(tgt)))

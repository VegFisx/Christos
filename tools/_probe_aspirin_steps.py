import sys, json
sys.path[:0]=['tools','core','libs']
import retro_search as rs
from rdkit import Chem
T='CC(=O)Oc1ccccc1C(=O)O'
t=rs.load_rdchiral_templates()
av={'X':'pool'}
e=rs.RetroSearch(t,av,blocks_full={},blocks_skel={})
ds=e.disconnections(T)
print('disconnections:',len(ds))
for s in ds[:12]:
    print(json.dumps({'rule':s.reaction_name,'prec':list(s.precursors)[:4],'weird':list(s.weird)},ensure_ascii=True)[:220])
sal='O=C(O)c1ccccc1'
print('salicylic in any precursors:', any(any(Chem.MolToSmiles(Chem.MolFromSmiles(p))==Chem.MolToSmiles(Chem.MolFromSmiles(sal)) for p in s.precursors if Chem.MolFromSmiles(p)) for s in ds))

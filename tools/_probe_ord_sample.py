import sys
sys.path[:0]=['libs','tools','core']
import duckdb
from rdkit import Chem, RDLogger
RDLogger.DisableLog('rdApp.*')
p=r'D:/ProgramData/DSHNS/chemreact-staging/reports/ord_dataset_sample_limit5000_seed20261013.parquet'
con=duckdb.connect()
cols=con.execute("DESCRIBE SELECT * FROM read_parquet('%s')" % p).fetchall()
print('cols:', [c[0] for c in cols])
rows=con.execute("SELECT product_smiles FROM read_parquet('%s') WHERE product_smiles IS NOT NULL LIMIT 3000" % p).fetchall()
hacs=[]
for (s,) in rows:
    m=Chem.MolFromSmiles(str(s).split('.')[0])
    if m: hacs.append(m.GetNumHeavyAtoms())
import statistics
print('products:', len(hacs), 'hac min/median/max:', min(hacs), statistics.median(hacs), max(hacs))
print('hac<=30:', sum(1 for h in hacs if h<=30), ' 12..30:', sum(1 for h in hacs if 12<=h<=30))

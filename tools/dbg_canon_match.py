import csv
import io
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for sub in ("core", "conditions", "rules", "tools", "libs", ""):
    sys.path.insert(0, str(STAGE / sub) if sub else str(STAGE))

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

from center_suggest import _demap
from train_center_model import canon_set

TEST = STAGE / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"
n = same = 0
with io.open(TEST, encoding="utf-8", newline="") as fh:
    for rec in csv.DictReader(fh):
        if n >= 100:
            break
        parts = (rec["reactants>reagents>production"] or "").split(">")
        rhs = parts[2]
        a = _demap(rhs)
        b = canon_set(rhs)
        n += 1
        if a == b:
            same += 1
print(f"_demap == canon_set on target: {same}/{n}")

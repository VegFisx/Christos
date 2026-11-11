"""Test the whitelist hypothesis: the 36% number stripped atoms the product does
not contain (an oracle). Here the same product-free run is repeated twice: once
keeping every substrate atom, once stripping the atoms the product drops."""
import csv
import io
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for sub in ("core", "conditions", "rules", "tools", "libs", ""):
    sys.path.insert(0, str(STAGE / sub) if sub else str(STAGE))

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

from center_suggest import CenterSuggest, _demap, _row_free
from center_apply2 import apply_edits2
from train_center_model import _atom_budget, _old_orders, _to_order_cls, canon_set

TEST = STAGE / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"
cg = CenterSuggest()


def decode(row, whitelist):
    probs = cg.clf.predict_proba(row["X"])
    old = _old_orders(row["mapped"])
    best = None
    for j, (a, b) in enumerate(row["pair_idx"]):
        for cls in (1, 2, 3, 4):
            p = float(probs[j][cls])
            if best is None or p > best[0]:
                best = (p, int(a), int(b), cls)
    if best is None:
        return None
    _, a, b, cls = best
    tgt = _to_order_cls(cls, old.get((min(a, b), max(a, b)), 1.0))
    got = apply_edits2(row["mapped"], [(a, b, tgt)], maps_whitelist=whitelist)
    return _demap(got) if got else None


n = keep_all = strip = 0
with io.open(TEST, encoding="utf-8", newline="") as fh:
    for rec in csv.DictReader(fh):
        if n >= 150:
            break
        parts = (rec["reactants>reagents>production"] or "").split(">")
        if len(parts) != 3:
            continue
        lhs, _re, rhs = parts
        m = Chem.MolFromSmiles(lhs)
        mp = Chem.MolFromSmiles(rhs)
        if m is None or mp is None:
            continue
        want = canon_set(rhs)
        if not want:
            continue
        prod_maps = {a.GetAtomMapNum() for a in mp.GetAtoms() if a.GetAtomMapNum()}
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        row = _row_free(Chem.MolToSmiles(m))
        if row is None:
            continue
        n += 1
        all_maps = {i + 1 for i in range(m.GetNumAtoms())}
        oracle = {i + 1 for i in range(m.GetNumAtoms()) if i + 1 in prod_maps}
        if decode(row, all_maps) == want:
            keep_all += 1
        if decode(row, oracle) == want:
            strip += 1

print(f"keep every atom:   {keep_all}/{n} = {keep_all / n:.1%}")
print(f"oracle atomic strip: {strip}/{n} = {strip / n:.1%}")

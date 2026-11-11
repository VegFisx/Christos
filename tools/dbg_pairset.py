"""Isolate why product-free inference drops from 36% to 3%.

Same featurisation, same model, same decoding; the only difference is the set of
candidate atom pairs. Here we run the product-free path twice: once over every
pair, once restricted (by oracle) to pairs whose two atoms are both present in
the product. If the restricted run recovers ~36%, the extra pairs are the cause.
"""
import csv
import io
import pickle
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for sub in ("core", "conditions", "rules", "tools", "libs", ""):
    sys.path.insert(0, str(STAGE / sub) if sub else str(STAGE))

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

from center_suggest import CenterSuggest, _row_free, _demap
from build_center_dataset import _row
from train_center_model import _atom_budget, _old_orders, _to_order_cls, canon_set

TEST = STAGE / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"
cg = CenterSuggest()


def predict(row, allowed=None):
    probs = cg.clf.predict_proba(row["X"])
    old = _old_orders(row["mapped"])
    budget = _atom_budget(row["mapped"])
    cur = {m: b[0] for m, b in budget.items()}
    cap = {m: b[1] for m, b in budget.items()}
    best = None
    for j, (a, b) in enumerate(row["pair_idx"]):
        if allowed is not None and not (a in allowed and b in allowed):
            continue
        for cls in (1, 2, 3, 4):
            p = float(probs[j][cls])
            if best is None or p > best[0]:
                best = (p, int(a), int(b), cls)
    if best is None:
        return None
    p, a, b, cls = best
    base = old.get((min(a, b), max(a, b)), 1.0)
    tgt = _to_order_cls(cls, base)
    from center_apply2 import apply_edits2

    got = apply_edits2(row["mapped"], [(a, b, tgt)], maps_whitelist=row["maps"])
    return _demap(got) if got else None


n = full_hit = oracle_hit = 0
with io.open(TEST, encoding="utf-8", newline="") as fh:
    for rec in csv.DictReader(fh):
        if n >= 150:
            break
        parts = (rec.get("reactants>reagents>production") or "").split(">")
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
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        plain = Chem.MolToSmiles(m)
        row = _row_free(plain)
        if row is None:
            continue
        # oracle: map numbers in our 1..N numbering are atom indices + 1
        prod_maps = {a.GetAtomMapNum() for a in mp.GetAtoms() if a.GetAtomMapNum()}
        allowed = {i + 1 for i, a in enumerate(m.GetAtoms()) if a.GetIdx() + 1 in prod_maps}
        n += 1
        if predict(row) == want:
            full_hit += 1
        if predict(row, allowed) == want:
            oracle_hit += 1

print(f"free pairs: {full_hit}/{n} = {full_hit / n:.1%}")
print(f"oracle-restricted pairs: {oracle_hit}/{n} = {oracle_hit / n:.1%}")

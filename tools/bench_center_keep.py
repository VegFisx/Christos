"""End-to-end product-free inference: atom-survival stage, then bond edits.

No oracle anywhere: the surviving atoms come from the keep model, and the same
set is used as the whitelist when applying edits.
"""
import csv
import io
import pickle
import sys
from pathlib import Path

import numpy as np

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for sub in ("core", "conditions", "rules", "tools", "libs", ""):
    sys.path.insert(0, str(STAGE / sub) if sub else str(STAGE))

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

from center_apply2 import apply_edits2
from center_suggest import CenterSuggest, _demap, _row_free
from build_keep_model import atom_features
from train_center_model import _old_orders, _to_order_cls, canon_set

TEST = STAGE / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"
cg = CenterSuggest()
with io.open(STAGE / "reports" / "keep_model.pkl", "rb") as fh:
    keep_clf = pickle.load(fh)


def predict(row, threshold=0.5):
    prob = keep_clf.predict_proba(np.asarray(atom_features(row["mol"]), dtype=np.float32))[:, 1]
    kept = {i + 1 for i, p in enumerate(prob) if p >= threshold}
    if not kept:
        return None, 0
    probs = cg.clf.predict_proba(row["X"])
    old = _old_orders(row["mapped"])
    best = None
    for j, (a, b) in enumerate(row["pair_idx"]):
        if int(a) not in kept or int(b) not in kept:
            continue
        for cls in (1, 2, 3, 4):
            p = float(probs[j][cls])
            if best is None or p > best[0]:
                best = (p, int(a), int(b), cls)
    if best is None:
        return None, len(kept)
    _, a, b, cls = best
    tgt = _to_order_cls(cls, old.get((min(a, b), max(a, b)), 1.0))
    got = apply_edits2(row["mapped"], [(a, b, tgt)], maps_whitelist=kept)
    return (_demap(got) if got else None), len(kept)


n = hit = atom_ok = 0
rows = []
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
        truth = {a.GetIdx() + 1 for a in m.GetAtoms() if a.GetAtomMapNum() and a.GetAtomMapNum() in {x.GetAtomMapNum() for x in mp.GetAtoms()}}
        for a in m.GetAtoms():
            a.SetAtomMapNum(a.GetIdx() + 1)
        mapped = Chem.MolToSmiles(m)
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        row = _row_free(Chem.MolToSmiles(m))
        if row is None:
            continue
        row["mol"] = m
        n += 1
        got, nkept = predict(row)
        if truth and len(truth) == nkept:
            atom_ok += 1
        if got == want:
            hit += 1
        rows.append((n, len(truth), nkept, got == want))

print(f"原子数完全预测对: {atom_ok}/{n} = {atom_ok / n:.1%}")
print(f"产物完全命中:     {hit}/{n} = {hit / n:.1%}")
wrong = [r for r in rows if not r[3]]
print("前 5 个未命中：真原子数 / 预测原子数")
for r in wrong[:5]:
    print(f"  #{r[0]}: {r[1]} / {r[2]}")

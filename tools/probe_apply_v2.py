"""Compare appliers on both datasets: equal-atom set vs stripped (relaxed) set.

For each row: rebuild the true edits from the product bond table (including breaks),
apply with v1 (mapped_only) and v2, and report exact / diff / none.

Usage: python _diag/probe_apply_v2.py <dataset> [n]
"""
import io
import json
import os
import sys

STAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(STAGE, "libs"))
sys.path.insert(0, STAGE)
from rdkit import Chem, RDLogger  # noqa: E402

from core.center_apply import apply_edits, _bond_order, _canon_parts  # noqa: E402
from core.center_apply2 import apply_edits2  # noqa: E402

RDLogger.DisableLog("rdApp.*")


def true_edits(smiles_r, smiles_p):
    mr = Chem.MolFromSmiles(smiles_r)
    mp = Chem.MolFromSmiles(smiles_p)
    if mr is None or mp is None:
        return None, None
    tb = {}
    for b in mp.GetBonds():
        m1 = b.GetBeginAtom().GetAtomMapNum()
        m2 = b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            tb[(min(m1, m2), max(m1, m2))] = _bond_order(b)
    rb = {}
    for b in mr.GetBonds():
        m1 = b.GetBeginAtom().GetAtomMapNum()
        m2 = b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            rb[(min(m1, m2), max(m1, m2))] = _bond_order(b)
    edits = []
    for key in sorted(set(tb) | set(rb)):
        a, b = key
        t = tb.get(key, 0.0)
        if abs(t - rb.get(key, 0.0)) < 0.01:
            continue
        edits.append((a, b, t))
    for a in mp.GetAtoms():
        a.SetAtomMapNum(0)
    return edits, _canon_parts(mp)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "reports/center_probe.jsonl"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    rows = 0
    res = {"v1": [0, 0, 0], "v2": [0, 0, 0]}   # exact, diff, none
    for line in io.open(os.path.join(STAGE, path), encoding="utf-8"):
        r = json.loads(line)
        if rows >= n:
            break
        edits, exp = true_edits(r["smiles_r"], r["smiles_p"])
        if edits is None or not exp:
            continue
        rows += 1
        _mp = Chem.MolFromSmiles(r["smiles_p"])
        wl = {a.GetAtomMapNum() for a in _mp.GetAtoms() if a.GetAtomMapNum()}
        for name, fn in (("v1", lambda: apply_edits(r["smiles_r"], edits, keep_maps=False)),
                         ("v2", lambda: apply_edits2(r["smiles_r"], edits, maps_whitelist=wl))):
            got = fn()
            if got is None:
                res[name][2] += 1
            elif got == exp:
                res[name][0] += 1
            else:
                res[name][1] += 1
    for k, (e, d, nn) in res.items():
        print("%s  exact %4d (%.1f%%)  diff %4d  none %4d   [n=%d]"
              % (k, e, 100.0 * e / max(1, rows), d, nn, rows))


if __name__ == "__main__":
    main()

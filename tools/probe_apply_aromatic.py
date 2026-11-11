"""Option 2 first: refuse edits that touch an aromatic bond, and measure the clean lower bound.

For each reaction we rebuild the true edits, tag each edit as aromatic-touching
(the bond is aromatic in the reactant, or either endpoint is aromatic), then:
  - supported   = reactions with no aromatic-touching edit
  - unsupported = the rest (we deliberately do not attempt them)
Report the supported share and the exact-match rate inside it.

Usage: python _diag/probe_apply_aromatic.py <dataset> [n]
"""
import io
import json
import os
import sys

STAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(STAGE, "libs"))
sys.path.insert(0, STAGE)
from rdkit import Chem, RDLogger  # noqa: E402

from core.center_apply import _bond_order, _canon_parts  # noqa: E402
from core.center_apply2 import apply_edits2  # noqa: E402

RDLogger.DisableLog("rdApp.*")


def analyse(smiles_r, smiles_p):
    mr = Chem.MolFromSmiles(smiles_r)
    mp = Chem.MolFromSmiles(smiles_p)
    if mr is None or mp is None:
        return None
    tb = {}
    for b in mp.GetBonds():
        m1, m2 = b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            tb[(min(m1, m2), max(m1, m2))] = _bond_order(b)
    rb = {}
    for b in mr.GetBonds():
        m1, m2 = b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            rb[(min(m1, m2), max(m1, m2))] = _bond_order(b)
    arom = set()
    for b in mr.GetBonds():
        m1, m2 = b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum()
        if not (m1 and m2):
            continue
        if b.GetIsAromatic() or b.GetBeginAtom().GetIsAromatic() or b.GetEndAtom().GetIsAromatic():
            arom.add((min(m1, m2), max(m1, m2)))
    edits = []
    touches_aromatic = False
    for key in sorted(set(tb) | set(rb)):
        a, b = key
        t = tb.get(key, 0.0)
        if abs(t - rb.get(key, 0.0)) < 0.01:
            continue
        edits.append((a, b, t))
        if key in arom:
            touches_aromatic = True
    wl = {a.GetAtomMapNum() for a in mp.GetAtoms() if a.GetAtomMapNum()}
    for a in mp.GetAtoms():
        a.SetAtomMapNum(0)
    return edits, touches_aromatic, wl, _canon_parts(mp)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "reports/center_probe.jsonl"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    rows = 0
    sup = unsup = 0
    exact = diff = none = 0
    for line in io.open(os.path.join(STAGE, path), encoding="utf-8"):
        r = json.loads(line)
        if rows >= n:
            break
        got = analyse(r["smiles_r"], r["smiles_p"])
        if got is None:
            continue
        rows += 1
        edits, arom, wl, exp = got
        if arom:
            unsup += 1
            continue
        sup += 1
        s = apply_edits2(r["smiles_r"], edits, maps_whitelist=wl)
        if s is None:
            none += 1
        elif s == exp:
            exact += 1
        else:
            diff += 1
    print("rows %d" % rows)
    print("supported (no aromatic edit) %d (%.1f%%)   unsupported %d (%.1f%%)"
          % (sup, 100.0 * sup / max(1, rows), unsup, 100.0 * unsup / max(1, rows)))
    print("supported: exact %d (%.1f%%)  diff %d  none %d"
          % (exact, 100.0 * exact / max(1, sup), diff, none))


if __name__ == "__main__":
    main()

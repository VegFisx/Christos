"""Learned centre suggestion: one product from the reactants alone.

The centre model was trained on mapped reactions, but every feature it sees is
reactant-side only (element, degree, hydrogen count, charge, aromaticity, ring
membership, hybridisation, neighbour element counts, graph distance, and the
bond order of the pair). Atom map numbers never enter the features, so an
unmapped molecule can be featurised by numbering its atoms 1..N. That is the
trick that lets this run on TCM inputs, which carry no atom mapping at all.

What it is used for: appending one extra candidate to the template output. It
does not replace the template route; on the official split it fills about a
fifth of the reactions no template covered and never removes a candidate.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import List, Optional

STAGE = Path(__file__).resolve().parents[1]
for _sub in ("core", "conditions", "rules", "libs", "tools", str(STAGE)):
    if str(STAGE / _sub) not in sys.path and str(STAGE) != str(STAGE / _sub):
        sys.path.insert(0, str(STAGE / _sub))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdmolops  # noqa: E402

RDLogger.DisableLog("rdApp.*")

# ★ 特征必须与训练时逐位一致：这里直接复用数据集构建器里的三个函数，
#   第一版自己重写了一份，维度对了但语义不同，预测全落在「不变」类。
from build_center_dataset import (  # noqa: E402
    MAX_CROSS,
    MAX_DIST,
    _atom_feat,
    _nbr_feat,
    _ord,
)

DEFAULT_MODEL = STAGE / "reports" / "center_model_uspto.pkl"


def _row_free(smiles: str):
    """Featurise every candidate atom pair of an unmapped molecule."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    for a in mol.GetAtoms():
        a.SetAtomMapNum(a.GetIdx() + 1)
    keep = [a.GetIdx() for a in mol.GetAtoms()]
    frags = rdmolops.GetMolFrags(mol)
    comp_of = {}
    for ci, f in enumerate(frags):
        for i in f:
            comp_of[i] = ci
    dm = Chem.GetDistanceMatrix(mol)
    AF = {i: _atom_feat(mol.GetAtomWithIdx(i)) + _nbr_feat(mol.GetAtomWithIdx(i))
          + [float(comp_of.get(i, 0)), float(dm[i, :].max())] for i in keep}
    rb = {}
    for b in mol.GetBonds():
        m1 = mol.GetAtomWithIdx(b.GetBeginAtomIdx()).GetAtomMapNum()
        m2 = mol.GetAtomWithIdx(b.GetEndAtomIdx()).GetAtomMapNum()
        if m1 and m2:
            rb[(min(m1, m2), max(m1, m2))] = _ord(b.GetBondType())

    X, pairs = [], []
    n_cross = 0
    for ii in range(len(keep)):
        for jj in range(ii + 1, len(keep)):
            i, j = keep[ii], keep[jj]
            same = comp_of.get(i) == comp_of.get(j)
            d = dm[i, j]
            if same and d > MAX_DIST:
                continue
            if not same:
                n_cross += 1
                if n_cross > MAX_CROSS:
                    continue
            m1 = mol.GetAtomWithIdx(i).GetAtomMapNum()
            m2 = mol.GetAtomWithIdx(j).GetAtomMapNum()
            r = rb.get((min(m1, m2), max(m1, m2)), 0.0)
            fi, fj = AF[i], AF[j]
            X.append(fi + fj + [float(d) if same else 9.0, 1.0 if same else 0.0,
                                r, float(r == 0), fi[0] * 20 + fj[0]])
            pairs.append([int(m1), int(m2)])
    if not X:
        return None
    return {"X": X, "pair_idx": pairs, "smiles_r": smiles,
            "mapped": Chem.MolToSmiles(mol),
            "maps": {a.GetAtomMapNum() for a in mol.GetAtoms()}}


def _demap(smi: str) -> str:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return ""
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m)


class CenterSuggest:
    def __init__(self, model_path: Optional[str] = None):
        self.ok = False
        self.clf = None
        try:
            with open(model_path or DEFAULT_MODEL, "rb") as fh:
                self.clf = pickle.load(fh)
            self.ok = True
        except Exception:
            self.ok = False

    def suggest(self, smiles_list: List[str], max_suggest: int = 1) -> List[str]:
        """Return up to `max_suggest` products, best first. Empty on any failure."""
        if not self.ok or not smiles_list:
            return []
        from center_apply2 import apply_edits2
        from train_center_model import _atom_budget, _old_orders, _to_order_cls
        from train_center_model import canon_set

        joined = ".".join(s for s in smiles_list if s)
        row = _row_free(joined)
        if row is None:
            return []
        try:
            probs = self.clf.predict_proba(row["X"])
            # ★ 这两步必须吃「带映射号」的 SMILES：键级与价态都是按映射号查表的，
            #   传平面 SMILES 会让每个键都被当成单键（基值默认 1.0），产物必错。
            old_ord = _old_orders(row["mapped"])
            budget = _atom_budget(row["mapped"])
        except Exception:
            return []
        cur = {m: b[0] for m, b in budget.items()}
        cap = {m: b[1] for m, b in budget.items()}
        cand = []
        for j, (a, b) in enumerate(row["pair_idx"]):
            for cls in (1, 2, 3, 4):
                cand.append((float(probs[j][cls]), int(a), int(b), cls))
        cand.sort(reverse=True)
        out: List[str] = []
        for p, a, b, cls in cand:
            base = old_ord.get((min(a, b), max(a, b)), 1.0)
            tgt = _to_order_cls(cls, base)
            delta = tgt - base
            if delta > 0 and (cur.get(a, 0.0) + delta > cap.get(a, 0.0) + 1e-9
                              or cur.get(b, 0.0) + delta > cap.get(b, 0.0) + 1e-9):
                continue
            got = apply_edits2(row["mapped"], [(a, b, tgt)], maps_whitelist=row["maps"])
            if got:
                got = _demap(got)
                if got and got not in out:
                    out.append(got)
            if len(out) >= max_suggest:
                break
        return out

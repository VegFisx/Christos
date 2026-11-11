"""Stage A of the learned route: decide which substrate atoms survive into the product.

The bond-edit model can only change bond orders; real reactions also lose atoms
(water, CO2, leaving groups). That missing action is why product-free inference
collapsed to 3.3%. Here we learn atom survival from the mapped USPTO corpus and
feed the surviving set to the edit model, so both stages are measured without
peeking at the answer.

Judgement written before running: end-to-end >= 15% keeps the route alive,
< 5% kills it.
"""
import csv
import io
import json
import pickle
import sys
from pathlib import Path

import numpy as np

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for sub in ("core", "conditions", "rules", "tools", "libs", ""):
    sys.path.insert(0, str(STAGE / sub) if sub else str(STAGE))

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

from build_center_dataset import _atom_feat, _nbr_feat

MAPPED = STAGE / "reports" / "paper" / "data" / "uspto50k_mapped.jsonl"
TEST = STAGE / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"
CACHE = STAGE / "reports" / "keep_dataset.npz"
MODEL = STAGE / "reports" / "keep_model.pkl"


def atom_features(mol):
    feats = []
    for a in mol.GetAtoms():
        f = list(_atom_feat(a)) + list(_nbr_feat(a))
        f.append(float(a.GetIdx()))
        f.append(float(mol.GetNumAtoms()))
        feats.append(f)
    return feats


def build(limit=26000):
    X, y, rid = [], [], []
    n = 0
    with io.open(MAPPED, encoding="utf-8") as fh:
        for line in fh:
            if n >= limit:
                break
            rec = json.loads(line)
            rxn = rec.get("mapped_rxn") or ""
            if ">>" not in rxn:
                continue
            lhs, rhs = rxn.split(">>")
            m = Chem.MolFromSmiles(lhs)
            mp = Chem.MolFromSmiles(rhs)
            if m is None or mp is None:
                continue
            kept = {a.GetAtomMapNum() for a in mp.GetAtoms() if a.GetAtomMapNum()}
            if not kept:
                continue
            n += 1
            for a, f in zip(m.GetAtoms(), atom_features(m)):
                X.append(f)
                y.append(1 if a.GetAtomMapNum() in kept else 0)
                rid.append(n)
    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=np.int8)
    np.savez_compressed(CACHE, X=X, y=y, rid=np.asarray(rid))
    print(f"原子样本 {X.shape[0]} · 保留 {int(y.sum())} ({y.mean():.1%}) · 反应 {n}")
    return X, y, rid


def train():
    from sklearn.ensemble import HistGradientBoostingClassifier

    data = np.load(CACHE)
    X, y, rid = data["X"], data["y"], data["rid"]
    tr = (rid % 2 == 0)
    clf = HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.08, max_leaf_nodes=31, random_state=0
    )
    clf.fit(X[tr], y[tr])
    te = ~tr
    prob = clf.predict_proba(X[te])[:, 1]
    from sklearn.metrics import roc_auc_score

    print(f"留出原子 AUC {roc_auc_score(y[te], prob):.4f}")
    with io.open(MODEL, "wb") as fh:
        pickle.dump(clf, fh)
    return clf


def main():
    if not CACHE.exists():
        build()
    clf = train()


if __name__ == "__main__":
    main()

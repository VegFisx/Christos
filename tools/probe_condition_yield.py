"""Q: do the conditions in a record tell us anything about the outcome we cannot read
off the structures alone?

Label. ORD records carry a measured yield. Positives are records with yield >= 50,
negatives records with yield <= 10; the 10-50 band is dropped so the classes are not a
knife edge.

Models on a substrate-hash split (the same starting material never spans both sides):
  A structure only          (substrates + product descriptors, no conditions at all)
  C conditions only         (T, time, solvent classes, catalyst and reagent flags)
  B structure + conditions

Pre-registered decision: if AUC(B) - AUC(A) < 0.02, conditions carry no signal we can
use to screen candidates, and the substrate-level condition gate is dead for this data.

Prints raw counts first, then the table. No silent excepts.
"""
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import glob
import hashlib
import os
import random
import time

import numpy as np
import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors

RDLogger.DisableLog("rdApp.*")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COND_DIR = os.path.join(ROOT, "reports", "ord_condition_dataset")
CACHE = os.path.join(ROOT, "reports", "_probe_condition_yield.parquet")
SEED = 20261110
TARGET = 80000


def parse_elements(formula):
    counts, i = {}, 0
    while i < len(formula):
        ch = formula[i]
        if ch.isupper():
            j = i + 1
            while j < len(formula) and formula[j].islower():
                j += 1
            sym = formula[i:j]
            k = j
            while k < len(formula) and formula[k].isdigit():
                k += 1
            num = int(formula[j:k]) if k > j else 1
            counts[sym] = counts.get(sym, 0) + num
            i = k
        else:
            i += 1
    return counts


def mol_feats(smi):
    m = Chem.MolFromSmiles(smi) if smi else None
    if m is None:
        return None
    el = parse_elements(rdMolDescriptors.CalcMolFormula(m))
    return {
        "ha": m.GetNumHeavyAtoms(),
        "mw": Descriptors.MolWt(m),
        "rings": rdMolDescriptors.CalcNumRings(m),
        "arom": rdMolDescriptors.CalcNumAromaticRings(m),
        "stereo": rdMolDescriptors.CalcNumAtomStereoCenters(m),
        "hbd": Lipinski.NumHDonors(m),
        "hba": Lipinski.NumHAcceptors(m),
        "hetero": sum(1 for a in m.GetAtoms() if a.GetSymbol() != "C"),
        "cC": el.get("C", 0),
        "cH": el.get("H", 0),
        "cN": el.get("N", 0),
        "cO": el.get("O", 0),
        "cS": el.get("S", 0),
        "cHal": sum(el.get(s, 0) for s in ("F", "Cl", "Br", "I")),
        "cP": el.get("P", 0),
    }


SOLV_KEYS = {
    "wat": ("water",),
    "dmf": ("dmf", "dimethylformamide"),
    "dmso": ("dmso", "sulfoxide"),
    "dcm": ("dcm", "dichloromethane"),
    "thf": ("thf", "tetrahydrofuran"),
    "mecn": ("acetonitrile", "mecn"),
    "alcohol": ("methanol", "ethanol", "propanol", "butanol"),
    "acid": ("acid", "acoh", "acetic", "hcl", "h2so4", "tfa"),
    "base": ("base", "et3n", "dipea", "k2co3", "naoh", "cs2co3", "koh", "pyridine"),
}


def text_has(text, keys):
    t = (text or "").lower()
    return int(any(k in t for k in keys))


def build():
    if os.path.exists(CACHE):
        df = pd.read_parquet(CACHE)
        print("cache hit rows", len(df), "pos", int((df['y'] == 1).sum()),
              "neg", int((df['y'] == 0).sum()))
        return df

    files = sorted(glob.glob(os.path.join(COND_DIR, "*.parquet")))
    rng = random.Random(SEED)
    picked = []
    for f in files:
        df = pd.read_parquet(
            f,
            columns=[
                "reaction_id",
                "reactant_smiles_components",
                "product_smiles",
                "temperature_C",
                "reaction_time_min",
                "solvent_names",
                "catalyst_names",
                "reagent_names",
                "n_products",
                "yield_percent",
            ],
        )
        ok = df[
            (df["n_products"] == 1)
            & df["product_smiles"].notna()
            & df["reactant_smiles_components"].notna()
            & df["temperature_C"].notna()
            & df["reaction_time_min"].notna()
            & df["yield_percent"].notna()
        ]
        if len(ok) > 600:
            idx = rng.sample(range(len(ok)), 600)
            picked.append(ok.iloc[sorted(idx)])
        else:
            picked.append(ok)
        if sum(len(p) for p in picked) >= TARGET:
            break
    base = pd.concat(picked, ignore_index=True)
    print("usable records", len(base), "from", len(picked), "shards")
    y = base["yield_percent"].astype(float)
    print("yield: >=50", int((y >= 50).sum()), "| 10-50", int(((y > 10) & (y < 50)).sum()),
          "| <=10", int((y <= 10).sum()))
    base = base[(y >= 50) | (y <= 10)].copy()
    base["y"] = (base["yield_percent"].astype(float) >= 50).astype(int)
    print("kept", len(base), "pos", int(base["y"].sum()), "neg", int((1 - base["y"]).sum()))

    t0 = time.time()
    cache, sub_cache = {}, {}

    def sub_stats(comp):
        if comp in sub_cache:
            return sub_cache[comp]
        parts = [p for p in str(comp).split(";") if p]
        ha = rings = hetero = ok = 0
        for p in parts:
            m = Chem.MolFromSmiles(p)
            if m is None:
                continue
            ok += 1
            ha += m.GetNumHeavyAtoms()
            rings += rdMolDescriptors.CalcNumRings(m)
            hetero += sum(1 for a in m.GetAtoms() if a.GetSymbol() != "C")
        out = None if ok == 0 else {"s_ha": ha, "s_rings": rings, "s_hetero": hetero, "s_n": len(parts)}
        sub_cache[comp] = out
        return out

    rows = []
    for _, r in base.iterrows():
        pf = cache.get(r["product_smiles"])
        if pf is None and r["product_smiles"] not in cache:
            pf = mol_feats(r["product_smiles"])
            cache[r["product_smiles"]] = pf
        st = sub_stats(r["reactant_smiles_components"])
        if pf is None or st is None:
            continue
        solv = str(r["solvent_names"]) if pd.notna(r["solvent_names"]) else ""
        row = {
            "rid": r["reaction_id"],
            "subs": r["reactant_smiles_components"],
            "y": int(r["y"]),
            "prod_ha": pf["ha"],
            **st,
            "mw": pf["mw"], "rings": pf["rings"], "arom": pf["arom"],
            "stereo": pf["stereo"], "hbd": pf["hbd"], "hba": pf["hba"],
            "hetero": pf["hetero"], "cC": pf["cC"], "cH": pf["cH"],
            "cN": pf["cN"], "cO": pf["cO"], "cS": pf["cS"],
            "cHal": pf["cHal"], "cP": pf["cP"],
            "T": float(r["temperature_C"]),
            "time": float(r["reaction_time_min"]),
            "cat": int(pd.notna(r["catalyst_names"])),
            "reag": int(pd.notna(r["reagent_names"])),
            "ntok": len([p for p in str(solv).split(";") if p]),
        }
        for name, keys in SOLV_KEYS.items():
            row["solv_" + name] = text_has(solv, keys)
        rows.append(row)
    df = pd.DataFrame(rows)
    df["skey"] = [hashlib.md5(s.encode()).hexdigest()[:12] for s in df["subs"]]
    df.to_parquet(CACHE, index=False)
    print("built", len(df), f"({time.time()-t0:.0f}s) -> {CACHE}")
    return df


STRUCT = ["prod_ha", "s_ha", "s_rings", "s_hetero", "s_n", "mw", "rings", "arom",
          "stereo", "hbd", "hba", "hetero", "cC", "cH", "cN", "cO", "cS", "cHal", "cP"]
COND = ["T", "time", "cat", "reag", "ntok"] + ["solv_" + k for k in SOLV_KEYS]


def main():
    df = build()
    # 96.5% of records clear the yield bar, so cap positives at 3x the negatives:
    # otherwise the models learn the base rate, not the chemistry.
    rng0 = np.random.RandomState(SEED + 3)
    pos = df.index[df["y"] == 1].to_numpy()
    neg = df.index[df["y"] == 0].to_numpy()
    keep_pos = rng0.choice(pos, size=min(len(pos), 3 * len(neg)), replace=False)
    df = df.loc[np.sort(np.concatenate([keep_pos, neg]))].reset_index(drop=True)
    print("balanced rows", len(df), "pos", int(df["y"].sum()), "neg", int((1 - df["y"]).sum()))
    df["T"] = df["T"].clip(-80, 400)
    df["logtime"] = np.log10(np.maximum(df["time"], 1.0) + 1.0)
    COND.append("logtime")
    Xs = df[STRUCT].copy()
    Xc = df[COND].copy()
    Xs["d_ha"] = df["prod_ha"] - df["s_ha"]
    Xs["d_rings"] = df["rings"] - df["s_rings"]
    Xs["d_hetero"] = df["hetero"] - df["s_hetero"]
    y = df["y"].to_numpy()
    keys = df["skey"].to_numpy()
    print("dataset", len(y), "pos", int(y.sum()), "features", Xs.shape[1], "+", Xc.shape[1])

    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    uniq = np.array(sorted(set(keys)))
    np.random.RandomState(SEED).shuffle(uniq)
    cut = int(len(uniq) * 0.75)
    tr_keys = set(uniq[:cut])
    tr = np.array([k in tr_keys for k in keys])
    te = ~tr
    print("split train", int(tr.sum()), "test", int(te.sum()), "| test substrates", len(uniq) - cut)

    def fit(name, X):
        X = X.to_numpy(dtype=float)
        m = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
            min_samples_leaf=40, l2_regularization=1.0, random_state=SEED,
        )
        m.fit(X[tr], y[tr])
        p = m.predict_proba(X[te])[:, 1]
        auc = roc_auc_score(y[te], p)
        print(f"{name:26s} AUC {auc:.4f}  n_test {int(te.sum())}  base_rate {y[te].mean():.3f}")
        return auc, p

    print("\n--- ablation ---")
    auc_a, pa = fit("A structure", Xs)
    auc_c, pc = fit("C conditions only", Xc)
    auc_b, pb = fit("B structure+conditions", pd.concat([Xs, Xc], axis=1))
    delta = auc_b - auc_a
    print(f"\ndelta AUC(B-A) = {delta:+.4f}")
    print("pre-registered threshold: kill if < 0.0200")
    print(f"delta AUC(C-0.5) = {auc_c - 0.5:+.4f}")

    # the base rate is 96.5%, so a 0.02 gap can be noise; bootstrap the delta
    rng = np.random.RandomState(SEED + 7)
    yt = y[te]
    n = len(yt)
    deltas = []
    for _ in range(400):
        idx = rng.randint(0, n, n)
        if yt[idx].min() == yt[idx].max():
            continue
        deltas.append(roc_auc_score(yt[idx], pb[idx]) - roc_auc_score(yt[idx], pa[idx]))
    deltas = np.array(deltas)
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    print(f"bootstrap delta over 400 resamples: median {np.median(deltas):+.4f} "
          f"95% CI [{lo:+.4f}, {hi:+.4f}] | share<=0 {np.mean(deltas <= 0):.3f}")


if __name__ == "__main__":
    main()

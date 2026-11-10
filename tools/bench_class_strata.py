"""Q: is the headline recall carried by a few very common reaction classes?

If a reaction class appears thousands of times in the corpus, a template for it is easy
to mine and the engine will reach the product. If it appears once or twice, the engine is
in effect seeing new chemistry. This splits ORD records by how often their reaction
centre -- the set of atoms whose bonds change, described by element, charge, degree and
ring membership, plus the bonds formed and broken -- occurs in the corpus, then measures
recall per stratum.

Strata: common (>=100 records), mid (10-99), rare (<=3).

Recall = the recorded product appears among the engine's candidates, compared on
connectivity (InChIKey first block) so stereochemistry does not decide it.

Prints raw counts first. No silent excepts: failures are counted and printed.
"""
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import glob
import json
import os
import random
import time
from collections import Counter, defaultdict

import pandas as pd
from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "conditions"))

COND_DIR = os.path.join(ROOT, "reports", "ord_condition_dataset")
OUT = os.path.join(ROOT, "reports", "class_strata_20261110.json")
SEED = 20261110
SAMPLE = 60000
PER_STRATUM = 400


def mapped_bonds(mol):
    """Bond dict keyed by the sorted atom-map pair."""
    out = {}
    for b in mol.GetBonds():
        a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
        m1, m2 = a1.GetAtomMapNum(), a2.GetAtomMapNum()
        if m1 and m2:
            out[(min(m1, m2), max(m1, m2))] = b.GetBondTypeAsDouble()
            out[("atoms", min(m1, m2))] = a1
            out[("atoms", max(m1, m2))] = a2
    return out


def atom_sig(atom):
    return (atom.GetSymbol(), atom.GetFormalCharge(), atom.GetDegree(),
            atom.GetIsAromatic(), atom.IsInRing(), atom.GetTotalNumHs())


def class_sig(rxn_smiles_mapped):
    """Coarse reaction-centre signature, or None when the maps are unusable."""
    parts = rxn_smiles_mapped.split(">>")
    if len(parts) != 2:
        return None
    left, right = parts
    rmol = Chem.MolFromSmiles(left)
    pmol = Chem.MolFromSmiles(right)
    if rmol is None or pmol is None:
        return None
    lb, pb = mapped_bonds(rmol), mapped_bonds(pmol)
    lk = {k for k in lb if isinstance(k, tuple) and k[0] != "atoms"}
    pk = {k for k in pb if isinstance(k, tuple) and k[0] != "atoms"}
    if not lk or not pk:
        return None
    formed = pk - lk
    broken = lk - pk
    if not formed and not broken:
        return None
    atoms = set()
    for a, b in list(formed) + list(broken):
        atoms.add(a)
        atoms.add(b)
    sig_atoms = []
    for n in sorted(atoms):
        at = pb.get(("atoms", n)) or lb.get(("atoms", n))
        if at is None:
            continue
        sig_atoms.append(atom_sig(at))
    sig = (len(formed), len(broken), tuple(sorted(sig_atoms)))
    return sig


def substrate_components(mapped_reactants):
    """Keep only mapped components: unmapped ones are reagents and catalysts."""
    kept, dropped = [], []
    for comp in mapped_reactants.split("."):
        if ":" in comp:
            kept.append(comp)
        else:
            dropped.append(comp)
    return kept, dropped


def strip_maps(smi):
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    try:
        Chem.SanitizeMol(m)
    except Exception:
        return None
    return Chem.MolToSmiles(m)


def canon(smi):
    m = Chem.MolFromSmiles(smi) if smi else None
    return Chem.MolToSmiles(m) if m is not None else ""


def ikey(smi):
    m = Chem.MolFromSmiles(smi) if smi else None
    if m is None:
        return ""
    try:
        return Chem.MolToInchiKey(m).split("-")[0]
    except Exception:
        return ""


def build_sample():
    files = sorted(glob.glob(os.path.join(COND_DIR, "*.parquet")))
    rng = random.Random(SEED)
    recs = []
    for f in files:
        df = pd.read_parquet(f, columns=["reaction_id", "reactants", "product",
                                         "reactant_smiles_components", "n_products"])
        df = df[(df["n_products"] == 1) & df["reactants"].notna() & df["product"].notna()]
        if len(df) == 0:
            continue
        take = min(len(df), 700)
        idx = rng.sample(range(len(df)), take)
        recs.extend(df.iloc[sorted(idx)].to_dict("records"))
        if len(recs) >= SAMPLE:
            break
    print("sampled records", len(recs))
    return recs


def main():
    t0 = time.time()
    recs = build_sample()
    sigs = []
    for r in recs:
        s = class_sig(str(r["reactants"]) + ">>" + str(r["product"]))
        sigs.append(s)
    ok = [(r, s) for r, s in zip(recs, sigs) if s is not None]
    print("class signature usable", len(ok), "failed", len(recs) - len(ok),
          f"({time.time()-t0:.0f}s)")
    freq = Counter(s for _, s in ok)
    print("distinct classes", len(freq))
    many = sum(1 for s, c in freq.items() if c >= 100)
    print("classes with >=100 records", many, "| >=10", sum(1 for c in freq.values() if c >= 10))

    common = [r for r, s in ok if freq[s] >= 100]
    mid = [r for r, s in ok if 10 <= freq[s] < 100]
    rare = [r for r, s in ok if freq[s] <= 3]
    print("pool sizes: common", len(common), "mid", len(mid), "rare", len(rare))

    import smartreact_engine as SE
    import templates as T
    from engine import Compound

    wide = "--wide" in sys.argv
    if wide:
        eng = SE.SmartReactEngine(extra_template_min_support=1,
                                  extra_template_limit=60000,
                                  mono_template_limit=60000,
                                  mono_include_co_reagent=True)
    else:
        eng = SE.SmartReactEngine()
    print("pool mode:", "wide min_support=1 limit=60000" if wide else "default",
          "|", eng.extra_template_note[:80])
    cond = T.get_template("煎煮")

    results = {}
    for name, pool in (("common", common), ("mid", mid), ("rare", rare)):
        rng = random.Random(SEED + hash(name) % 1000)
        picked = rng.sample(pool, min(PER_STRATUM, len(pool)))
        hit = miss = skip = err = 0
        examples = []
        for r in picked:
            parts, _ = substrate_components(str(r["reactants"]))
            comps = []
            bad = False
            for i, p in enumerate(parts[:3]):
                smi = strip_maps(p)
                if not smi:
                    bad = True
                    break
                comps.append(Compound(smiles=smi, name="R%d" % i, herb="(bench)"))
            if bad or not comps:
                skip += 1
                continue
            want = canon(r["product"])
            if not want:
                skip += 1
                continue
            try:
                prods = eng.step(comps, cond, round_no=1)
            except Exception as exc:
                err += 1
                if err <= 3:
                    print("  engine error:", type(exc).__name__, str(exc)[:120])
                continue
            got = {canon(getattr(p, "smiles", "") or "") for p in prods}
            if want in got:
                hit += 1
            else:
                wk = ikey(want)
                if wk and wk in {ikey(g) for g in got if g}:
                    hit += 1
                else:
                    miss += 1
                    if len(examples) < 3:
                        examples.append({"want": want, "n_cand": len(got)})
        n = hit + miss
        results[name] = {"hit": hit, "miss": miss, "skip": skip, "err": err,
                         "recall": (hit / n) if n else None,
                         "examples": examples}
        print(f"{name:8s} recall {hit}/{n} = {(hit/n if n else 0)*100:.1f}% "
              f"skip {skip} err {err}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "sample": SAMPLE, "per_stratum": PER_STRATUM,
                   "class_counts": {"distinct": len(freq),
                                    "ge100": many,
                                    "ge10": sum(1 for c in freq.values() if c >= 10)},
                   "results": results}, fh, ensure_ascii=False, indent=2)
    print("wrote", OUT, f"({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()

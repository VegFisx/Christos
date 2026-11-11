"""Does the learned centre model add anything the template route missed?

For each reaction of the official split we run the template engine exactly as
the benchmark does, then ask separately whether the learned model can write the
recorded product in one shot. The interesting cell is `template miss, learned
hit`: those are products no template candidate contained.

Usage:
    python tools/bench_center_union_official.py [limit]
"""
from __future__ import annotations

import csv
import io
import os
import pickle
import sys
from pathlib import Path

STAGE = Path(__file__).resolve().parents[1]
for sub in ("core", "conditions", "rules", "tools", "libs"):
    sys.path.insert(0, str(STAGE / sub))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

from bench_center_vs_template import canon_set  # noqa: E402
from build_center_dataset import _row  # noqa: E402
from train_center_model import _apply, _atom_budget, _old_orders, _to_order_cls  # noqa: E402

TEST = STAGE / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"


def _demap(smi: str) -> str:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return ""
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m)


def _best_single_edit(clf, row):
    """Take only the most confident edit: at 1-in-250 prevalence, more than one
    accepted edit reconstructs the wrong molecule far more often than the right one."""
    probs = clf.predict_proba(row["X"])
    old_ord = _old_orders(row["smiles_r"])
    budget = _atom_budget(row["smiles_r"])
    cur = {m: b[0] for m, b in budget.items()}
    cap = {m: b[1] for m, b in budget.items()}
    best = None
    for j, (a, b) in enumerate(row["pair_idx"]):
        for cls in (1, 2, 3, 4):
            p = float(probs[j][cls])
            if best is None or p > best[0]:
                best = (p, int(a), int(b), cls)
    if best is None:
        return None
    p, a, b, cls = best
    base = old_ord.get((min(a, b), max(a, b)), 1.0)
    tgt = _to_order_cls(cls, base)
    if tgt > base:
        if cur.get(a, 0.0) + (tgt - base) > cap.get(a, 0.0) + 1e-9:
            return None
        if cur.get(b, 0.0) + (tgt - base) > cap.get(b, 0.0) + 1e-9:
            return None
    return _apply(row["smiles_r"], [(a, b, tgt)], row["smiles_p"])


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    with open(STAGE / "reports" / "center_model_uspto.pkl", "rb") as fh:
        clf = pickle.load(fh)

    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T

    kw = {}
    if os.environ.get("CHEMCREACT_BENCH_CLI_CONFIG"):
        kw["use_curated_templates"] = True
        kw["strict_redox_gate"] = True
    eng = SmartReactEngine(**kw)
    cond = T.get_template("煎煮")

    n = t_hit = l_hit = both = learned_only = neither = err = 0
    with io.open(TEST, encoding="utf-8", newline="") as fh:
        for rec in csv.DictReader(fh):
            if n >= limit:
                break
            parts = (rec.get("reactants>reagents>production") or "").split(">")
            if len(parts) != 3:
                continue
            lhs_mapped, _re, rhs = parts
            lhs = _demap(lhs_mapped)
            want = canon_set(rhs)
            if not lhs or not want:
                err += 1
                continue
            comps = [Compound(smiles=s, name="R%d" % j, herb="(bench)")
                     for j, s in enumerate([x for x in lhs.split(".") if x])]
            try:
                prods = eng.step(comps, cond, round_no=1)
                got = {canon_set(getattr(p, "smiles", "")) for p in prods}
            except Exception:
                err += 1
                continue
            t = want in got
            row = _row(rec["id"], lhs_mapped + ">>" + rhs)
            pred = _best_single_edit(clf, row) if row is not None else None
            l = pred is not None and pred == want
            n += 1
            t_hit += t
            l_hit += l
            both += (t and l)
            learned_only += (l and not t)
            neither += (not t and not l)

    print(f"rows {n} err {err}")
    print(f"template recall {t_hit}/{n} = {t_hit / n:.1%}")
    print(f"learned single-edit exact {l_hit}/{n} = {l_hit / n:.1%}")
    print(f"both {both} · learned only {learned_only} · neither {neither}")
    print(f"union recall {(t_hit + learned_only)}/{n} = {(t_hit + learned_only) / n:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

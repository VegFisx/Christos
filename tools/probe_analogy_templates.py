"""Q: for reaction classes the pool has never seen, can a loosened template still reach
the recorded product?

The idea is analogy, not generation. A template mined from one substrate carries a
detailed environment around the atoms whose bonds change ([O;H0;D3;+0:1]). Strip that
environment down to element plus charge and the same bond change can fire on a different
neighbourhood -- which is what a chemist does when they say "this is the same kind of
reaction".

Evaluation is on the rare stratum of `bench_class_strata.py`: classes with at most three
records in the sample, where the normal pool reaches about 8%.

Reported:
  recall          the recorded product appears among the relaxed outputs
  candidates      how many distinct products the relaxation threw at the substrate
  control         the same machinery with the maps shuffled inside each template, so the
                  bond change no longer corresponds to a real transformation

A relaxation that produces thousands of candidates is not usable even if recall rises, so
candidates are printed next to recall.
"""
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import os
import random
import re
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "conditions"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.*")

import bench_class_strata as B

POOL = os.path.join(ROOT, "reports", "mined_forward_templates_full_s5.jsonl")
OUT = os.path.join(ROOT, "reports", "analogy_rare_20261110.json")
N_RARE = int(os.environ.get("ANALOGY_N", "120"))
SEED = 20261110
MAX_CAND = 3000  # safety valve: skip a record if relaxation explodes

ATOM_Q = re.compile(r"\[([A-Za-z][a-z]?|\*|c|n|o|s|p)([^\]]*):(\d+)\]")


def relax(smarts: str) -> str:
    """Keep element and map number, drop H/degree/ring/charge constraints."""

    def rep(m):
        el, _rest, num = m.group(1), m.group(2), m.group(3)
        return "[%s:%s]" % (el, num)

    return ATOM_Q.sub(rep, smarts)


def shuffle_maps(smarts: str, rng: random.Random) -> str:
    """Control: permute map numbers so the bond change no longer means anything."""
    nums = [int(m.group(3)) for m in ATOM_Q.finditer(smarts)]
    if len(nums) < 2:
        return smarts
    perm = nums[:]
    rng.shuffle(perm)
    mapping = dict(zip(nums, perm))
    return ATOM_Q.sub(lambda m: "[%s:%d]" % (m.group(1), mapping[int(m.group(3))]), smarts)


def compile_pool(relaxed: bool):
    seen = set()
    out = {1: [], 2: [], 3: []}
    n_bad = 0
    with open(POOL, encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                n_bad += 1
                continue
            sm = d.get("template")
            if not sm:
                continue
            if relaxed:
                sm = relax(sm)
            if sm in seen:
                continue
            seen.add(sm)
            try:
                rxn = AllChem.ReactionFromSmarts(sm)
            except Exception:
                n_bad += 1
                continue
            if rxn is None:
                n_bad += 1
                continue
            a = rxn.GetNumReactantTemplates()
            if a in out:
                out[a].append((sm, rxn))
    print("pool", "relaxed" if relaxed else "raw", "unique", len(seen),
          "| arity", {k: len(v) for k, v in out.items()}, "| bad", n_bad)
    return out


def run_pool(compiled, mols, want, cap=MAX_CAND):
    """Apply every template that fits; return (found, n_candidates, n_applied)."""
    from itertools import permutations

    cands = set()
    applied = 0
    for arity, items in compiled.items():
        if arity > len(mols):
            continue
        for sm, rxn in items:
            for perm in permutations(mols, arity):
                try:
                    outs = rxn.RunReactants(perm)
                except Exception:
                    continue
                if not outs:
                    continue
                applied += 1
                for combo in outs:
                    for m in combo:
                        if m is None:
                            continue
                        try:
                            Chem.SanitizeMol(m)
                        except Exception:
                            continue
                        s = Chem.MolToSmiles(m)
                        if s:
                            cands.add(s)
                if len(cands) > cap:
                    return False, len(cands), applied
    want_k = B.ikey(want)
    found = want in cands or (want_k and want_k in {B.ikey(c) for c in cands})
    return found, len(cands), applied


def main():
    t0 = time.time()
    recs = B.build_sample()
    sigs = [B.class_sig(str(r["reactants"]) + ">>" + str(r["product"])) for r in recs]
    ok = [(r, s) for r, s in zip(recs, sigs) if s is not None]
    freq = Counter(s for _, s in ok)
    rare = [r for r, s in ok if freq[s] <= 3]
    print("rare records", len(rare))
    rng = random.Random(SEED)
    picked = rng.sample(rare, min(N_RARE, len(rare)))

    raw = compile_pool(relaxed=False)
    rel = compile_pool(relaxed=True)
    ctrl_pool = {1: [], 2: [], 3: []}
    seen = set()
    for arity, items in rel.items():
        for sm, _rxn in items:
            sm2 = shuffle_maps(sm, rng)
            if sm2 in seen:
                continue
            seen.add(sm2)
            try:
                rxn2 = AllChem.ReactionFromSmarts(sm2)
            except Exception:
                continue
            if rxn2 is not None:
                ctrl_pool[arity].append((sm2, rxn2))
    print("control pool", {k: len(v) for k, v in ctrl_pool.items()},
          f"({time.time()-t0:.0f}s)")

    res = {"raw": [0, 0, []], "relaxed": [0, 0, []], "control": [0, 0, []]}
    skipped = 0
    for i, r in enumerate(picked, 1):
        parts, _ = B.substrate_components(str(r["reactants"]))
        mols = []
        for p in parts[:2]:
            smi = B.strip_maps(p)
            m = Chem.MolFromSmiles(smi) if smi else None
            if m is not None:
                mols.append(m)
        if not mols:
            skipped += 1
            continue
        want = B.canon(r["product"])
        if not want:
            skipped += 1
            continue
        for name, pool in (("raw", raw), ("relaxed", rel), ("control", ctrl_pool)):
            found, ncand, applied = run_pool(pool, mols, want)
            res[name][0] += int(bool(found))
            res[name][1] += 1
            res[name][2].append(ncand)
            if name == "relaxed" and ncand > MAX_CAND:
                pass
        if i % 20 == 0:
            done = res["relaxed"][1]
            print(f"  {i}/{len(picked)} relaxed recall {res['relaxed'][0]}/{done}",
                  flush=True)

    print("\nstratum: rare (<=3 records in the 60k sample), n =", len(picked), "skipped", skipped)
    for name in ("raw", "relaxed", "control"):
        hit, n, counts = res[name]
        med = sorted(counts)[len(counts) // 2] if counts else 0
        p90 = sorted(counts)[int(len(counts) * 0.9)] if counts else 0
        print(f"{name:8s} recall {hit}/{n} = {(hit/n if n else 0)*100:.1f}%  "
              f"median candidates {med}  p90 {p90}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "n_rare_sampled": len(picked),
                   "results": {k: {"hit": v[0], "n": v[1],
                                   "median_candidates": (sorted(v[2])[len(v[2]) // 2] if v[2] else 0)}
                               for k, v in res.items()}}, fh, ensure_ascii=False, indent=2)
    print("wrote", OUT, f"({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()

"""Retrieval probe: borrow products from the nearest *reactions*, not from templates.

Query: official test rows (USPTO-50k raw_test.csv, mapped).
Corpus: the 50k canon corpus, minus any row whose reactant set equals the query's.

For each query take the k nearest corpus reactions by Morgan fingerprint of the
reactant set, pool their recorded products, and ask whether the recorded test
product is in that pool. Pre-registered kill: recall < 50% (templates reach 92%).
"""
import csv
import io
import json
import os
import sys
import time

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, DataStructs

RDLogger.DisableLog("rdApp.*")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "chemreact-staging")
CORPUS = os.path.join(STAGE, "reports", "paper", "data", "uspto50k_canon.jsonl")
TEST = os.path.join(STAGE, "reports", "paper", "data", "uspto50k_official", "raw_test.csv")
N_QUERY = int(sys.argv[1]) if len(sys.argv) > 1 else 400
K = int(sys.argv[2]) if len(sys.argv) > 2 else 20
NBITS = 2048


def canon(smi):
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m)


def reactant_key(parts):
    vals = sorted(x for x in (canon(p) for p in parts) if x)
    return ".".join(vals) if vals else None


def fp_of(parts):
    fps = []
    for p in parts:
        m = Chem.MolFromSmiles(p)
        if m is None:
            continue
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        fps.append(AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=NBITS))
    if not fps:
        return None
    acc = np.zeros(NBITS, dtype=np.uint8)
    for f in fps:
        one = np.zeros(NBITS, dtype=np.uint8)
        DataStructs.ConvertToNumpyArray(f, one)
        acc |= one
    return DataStructs.CreateFromBitString("".join("1" if b else "0" for b in acc))


def main():
    t0 = time.time()
    rows = []
    skipped = 0
    with io.open(CORPUS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            parts = r.get("reactants") or []
            if isinstance(parts, str):
                parts = parts.split(".")
            prod = r.get("product") or ""
            key = reactant_key(parts)
            pc = canon(prod)
            if not key or not pc:
                skipped += 1
                continue
            rows.append((key, pc, parts))
    print("corpus rows=%d skipped=%d (%.1fs)" % (len(rows), skipped, time.time() - t0))

    t1 = time.time()
    keys = [r[0] for r in rows]
    prods = [r[1] for r in rows]
    fps = []
    bad_fp = 0
    for key, pc, parts in rows:
        fp = fp_of(parts)
        if fp is None:
            bad_fp += 1
            fps.append(None)
        else:
            fps.append(fp)
    print("fingerprints=%d bad=%d (%.1fs)" % (len(fps), bad_fp, time.time() - t1))

    # queries
    queries = []
    with io.open(TEST, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames or []
        col = "reactants>reagents>production" if "reactants>reagents>production" in cols else "reactants"
        for i, r in enumerate(rd):
            if i >= N_QUERY:
                break
            raw = r.get(col) or ""
            if raw.count(">") >= 2:
                left, mid, right = raw.split(">")[:3]
                parts = left.split(".")
                prod = right
            else:
                parts = raw.split(".")
                prod = r.get("product") or ""
            key = reactant_key(parts)
            pc = canon(prod)
            if not key or not pc:
                continue
            queries.append((key, pc, parts, r.get("class", "")))
    print("queries=%d" % len(queries))
    if not queries:
        print("no queries; check column names: %s" % cols)
        return 2

    # dense matrix for fast tanimoto
    n = len(fps)
    mat = np.zeros((n, NBITS), dtype=np.uint8)
    for i, fp in enumerate(fps):
        if fp is None:
            continue
        DataStructs.ConvertToNumpyArray(fp, mat[i])
    cnt = mat.sum(axis=1).astype(np.float32)

    hits = 0
    rand_hits = 0
    rng = np.random.default_rng(7)
    for key, pc, parts, cls in queries:
        qfp = fp_of(parts)
        if qfp is None:
            continue
        q = np.zeros(NBITS, dtype=np.uint8)
        DataStructs.ConvertToNumpyArray(qfp, q)
        inter = mat @ q
        union = cnt + q.sum() - inter
        tan = np.where(union > 0, inter / np.maximum(union, 1), 0.0)
        # exclude identical reactant sets
        same = np.array([k == key for k in keys], dtype=bool)
        tan[same] = -1.0
        top = np.argpartition(-tan, K)[:K]
        top = top[np.argsort(-tan[top])]
        pool = {prods[j] for j in top}
        hits += 1 if pc in pool else 0
        ridx = rng.integers(0, n, size=K)
        rand_hits += 1 if pc in {prods[j] for j in ridx} else 0
    nq = len(queries)
    print("kNN recall@%d = %d/%d = %.1f%%   random %.1f%%" % (K, hits, nq, 100.0 * hits / nq, 100.0 * rand_hits / nq))
    print("elapsed %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

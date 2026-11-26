# -*- coding: utf-8 -*-
"""排序改进实验：在候选级基准表上测试新的产物级特征。

所有实验共用同一 train/test 切分（按 want 的 md5）与同一超参，
基线是现有 59 维（表内物化），因此结果可直接和 0.7801 比。

特征组：
  base  59 维（rank_dataset_v2 口径）
  cheap 反应内归一化与重复票：log_n_cand / rank_norm / dup_count / n_tpl_same /
        n_rule_same / first_rank_same / is_dup_first
  tan   产物与底物的 Morgan 相似度（r=2, 2048）
  vote  模板级历史命中率（只在 train 上算，平滑到先验）

用法：
  python tools\\rank_experiments_v3.py            # 全部组
  python tools\\rank_experiments_v3.py --only base,cheap
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

import candidate_table as CT  # noqa: E402

RNG = 0


def group_stats(df):
    """反应内统计：重复候选票数与位置归一化。"""
    rid = df["rid"].to_numpy()
    smi = df["smi"].to_numpy()
    tpl = df["tpl"].to_numpy()
    rule = df["rule"].to_numpy()
    rank = df["rank"].to_numpy()
    n_cand = df["n_cand"].to_numpy()

    key = list(zip(rid.tolist(), smi.tolist()))
    counts: dict = {}
    for k in key:
        counts[k] = counts.get(k, 0) + 1
    dup = np.array([counts[k] for k in key], dtype="float64")

    # 同一 (rid, smi) 下的不同模板 / 规则数，以及最小 rank
    tset: dict = {}
    rset: dict = {}
    minrank: dict = {}
    for k, t, r, rk in zip(key, tpl.tolist(), rule.tolist(), rank.tolist()):
        tset.setdefault(k, set()).add(t)
        rset.setdefault(k, set()).add(r)
        if rk < minrank.get(k, 10 ** 9):
            minrank[k] = rk
    n_tpl = np.array([len(tset[k]) for k in key], dtype="float64")
    n_rule = np.array([len(rset[k]) for k in key], dtype="float64")
    first = np.array([minrank[k] for k in key], dtype="float64")

    denom = np.maximum(n_cand - 1, 1).astype("float64")
    cheap = np.column_stack([
        np.log1p(n_cand),
        rank / denom,
        rank / np.maximum(n_cand, 1),
        dup,
        n_tpl,
        n_rule,
        first,
        (rank == first).astype("float64"),
    ])
    names = ["log_n_cand", "rank_norm", "rank_frac", "dup_count",
             "n_tpl_same", "n_rule_same", "first_rank_same", "is_dup_first"]
    return cheap, names


def tanimoto_feats(df, radius=2, nbits=2048):
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdMolDescriptors

    RDLogger.DisableLog("rdApp.*")
    cache: dict = {}

    def fp(s):
        if s in cache:
            return cache[s]
        m = Chem.MolFromSmiles(s) if s else None
        v = rdMolDescriptors.GetMorganFingerprintAsBitVect(m, radius, nBits=nbits) if m else None
        cache[s] = v
        return v

    smi = df["smi"].tolist()
    sub = df["sub"].tolist()
    out = np.zeros((len(df), 2), dtype="float64")
    for i, (a, b) in enumerate(zip(smi, sub)):
        fa, fb = fp(a), fp(b)
        if fa is None or fb is None:
            continue
        from rdkit import DataStructs
        t = DataStructs.TanimotoSimilarity(fa, fb)
        out[i, 0] = t
        out[i, 1] = float(fa.GetNumOnBits())
    return out, ["tani_prod_sub", "prod_fp_bits"]


def template_target_encoding(df, alpha=20.0):
    """每个模板在 train 上的命中率，平滑后贴到所有行。"""
    tr = (df["split"] == "train").to_numpy()
    tpl = df["tpl"].to_numpy()
    y = df["label"].to_numpy(dtype="float64")
    prior = float(y[tr].mean()) if tr.any() else 0.0
    pos: dict = {}
    tot: dict = {}
    for t, yy, istr in zip(tpl.tolist(), y.tolist(), tr.tolist()):
        if not istr:
            continue
        tot[t] = tot.get(t, 0) + 1
        pos[t] = pos.get(t, 0) + yy
    enc = np.empty(len(df), dtype="float64")
    cnt = np.empty(len(df), dtype="float64")
    for i, t in enumerate(tpl.tolist()):
        n = tot.get(t, 0)
        p = pos.get(t, 0.0)
        enc[i] = (p + alpha * prior) / (n + alpha)
        cnt[i] = n
    return np.column_stack([enc, np.log1p(cnt)]), ["tpl_hitrate", "tpl_hitrate_n"]


def auc(y, x):
    from sklearn.metrics import roc_auc_score

    x = np.asarray(x, dtype="float64")
    if np.all(x == x[0]):
        return 0.5
    a = roc_auc_score(y, x)
    return max(a, 1.0 - a)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="base,cheap,tan,vote")
    ap.add_argument("--iters", type=int, default=300)
    a = ap.parse_args()
    groups = [g.strip() for g in a.only.split(",") if g.strip()]

    from sklearn.ensemble import HistGradientBoostingClassifier

    t0 = time.time()
    df, meta = CT.load()
    Xb, names_b = CT.feature_matrix(df, meta)
    print("表 %d 行 / 基线特征 %d 维（载入 %.1f s）"
          % (len(df), Xb.shape[1], time.time() - t0), flush=True)

    blocks = [("base", Xb, names_b)]
    if "cheap" in groups:
        Xc, nc = group_stats(df)
        blocks.append(("cheap", Xc, nc))
    if "tan" in groups:
        print("算 Morgan 相似度 ...", flush=True)
        Xt, nt = tanimoto_feats(df)
        blocks.append(("tan", Xt, nt))
    if "vote" in groups:
        Xv, nv = template_target_encoding(df)
        blocks.append(("vote", Xv, nv))
    print("特征就绪 %.1f s" % (time.time() - t0), flush=True)

    y = df["label"].to_numpy()
    tr = (df["split"] == "train").to_numpy()
    te = ~tr
    yte = y[te]

    # 单特征 AUC（只在测试集上）
    print("\n单特征 AUC（测试集，>0.5 越大越有信号）")
    for gname, X, names in blocks:
        if gname == "base":
            continue
        for j, nm in enumerate(names):
            print("  %-16s %.4f" % (nm, auc(yte, X[te, j])))

    # 组合模型
    print("\n组合模型（HistGBM，300 轮，与 v2 同超参）")
    combos = [("base", ["base"])]
    extra = [g for g in groups if g not in ("base",)]
    if extra:
        combos.append(("+".join(extra), ["base"] + extra))
    for g in extra:
        combos.append(("base+" + g, ["base", g]))

    results = []
    for tag, use in combos:
        X = np.concatenate([b[1] for b in blocks if b[0] in use], axis=1)
        m = HistGradientBoostingClassifier(max_iter=a.iters, learning_rate=0.06,
                                           max_leaf_nodes=31, random_state=RNG)
        m.fit(X[tr], y[tr])
        score = m.predict_proba(X[te])[:, 1]
        r = CT.evaluate(df[te], score=score)
        r["tag"] = tag
        r["n_feat"] = X.shape[1]
        results.append(r)
        print("  %-18s nfeat=%-4d n=%d top1=%.4f top3=%.4f top5=%.4f mrr=%.4f"
              % (tag, X.shape[1], r["n"], r["top1"], r["top3"], r["top5"], r["mrr"]),
              flush=True)

    print("\n总计 %.1f s" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

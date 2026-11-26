# -*- coding: utf-8 -*-
"""训练重排序 v3：在 v2 的 59 维上，加两个「模板先验」特征。

  tpl_hitrate   = (pos + a*prior) / (n + a)，n/pos 是该模板在**训练集**候选里的
                  出现次数 / 命中次数；未见过的模板取 prior。
  tpl_hitrate_n = log1p(n)

两者都只在 train 切分上统计（与测试反应完全隔开：切分按 want 的 md5）。
对照实验（3 个种子）：
  base 0.7801/0.7817/0.7844
  +次数 0.8080/0.8037/0.8069    +命中率 0.8023/0.8043/0.8068
  +打乱标签的命中率 0.7935/0.7813/0.7885（噪声）
  +两者 0.8170/0.8204/0.8202

输出 reports/rank_model_v3.pkl，同时把 tpl_stats 存进模型，
生产端 core/rerank.py 按同一公式现算。

用法：
  python tools\\train_ranker_v3.py
  python tools\\train_ranker_v3.py --alpha 20 --iters 300
"""
from __future__ import annotations

import argparse
import io
import pickle
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



def tpl_stats_of(tpl, y):
    pos, tot = {}, {}
    for t, yy in zip(tpl.tolist(), y.tolist()):
        tot[t] = tot.get(t, 0) + 1
        pos[t] = pos.get(t, 0) + yy
    return pos, tot


def tpl_feats(tpl, pos, tot, prior, alpha):
    hr = np.empty(len(tpl), dtype="float64")
    lg = np.empty(len(tpl), dtype="float64")
    for i, t in enumerate(tpl.tolist()):
        n = tot.get(t, 0)
        hr[i] = (pos.get(t, 0) + alpha * prior) / (n + alpha)
        lg[i] = np.log1p(n)
    return hr, lg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=20.0)
    ap.add_argument("--iters", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dropout", type=float, default=0.5,
                    help="训练时按模板整体掩蔽的比例；让模型见过统计缺失的分支")
    ap.add_argument("--out", default=str(ROOT / "reports" / "rank_model_v3.pkl"))
    ap.add_argument("--out-base", default=None,
                    help="同时保存一个 59 维模型（用于隔离「数据集」与「新特征」的影响）")
    ap.add_argument("--table", default=None, help="候选表 parquet（默认 candidate_table 的 v2）")
    ap.add_argument("--table-meta", default=None, help="对应的 meta json")
    a = ap.parse_args()

    from sklearn.ensemble import HistGradientBoostingClassifier

    t0 = time.time()
    if a.table:
        df, meta = CT.load(parquet=a.table,
                           meta=CT.load_meta(a.table_meta) if a.table_meta else None)
    else:
        df, meta = CT.load()
    num = list(meta["num_features"])
    top_rules = list(meta["top_rules"])
    Xb, _ = CT.feature_matrix(df, meta)
    y = df["label"].to_numpy()
    tpl = df["tpl"].to_numpy()
    tr = (df["split"] == "train").to_numpy()
    te = ~tr
    df_te = df[te]

    pos, tot = tpl_stats_of(tpl[tr], y[tr])
    prior = float(y[tr].mean())
    hr, lg = tpl_feats(tpl, pos, tot, prior, a.alpha)
    X = np.concatenate([Xb, np.column_stack([hr, lg])], axis=1)
    names = num + ["tpl_hitrate", "tpl_hitrate_n"]

    # 训练时按模板整体掩蔽：官方集有 36% 候选的模板不在统计里，
    # 不掩蔽的话模型没学过「prior 分支」，官方 top-1 会从 72.6% 崩到 17.7%。
    Xtr = X[tr]
    n_drop = 0
    if a.dropout > 0:
        rng = np.random.RandomState(a.seed + 1)
        uniq = sorted(tot)
        drop = {t for t in uniq if rng.rand() < a.dropout}
        row_mask = np.array([t in drop for t in tpl[tr].tolist()])
        Xtr = Xtr.copy()
        Xtr[row_mask, Xb.shape[1]] = prior            # 59 = Xb 宽度
        Xtr[row_mask, Xb.shape[1] + 1] = 0.0
        n_drop = int(row_mask.sum())
    print("模板 dropout %.2f：掩蔽 %d 行（%.1f%% 训练候选）"
          % (a.dropout, n_drop, 100.0 * n_drop / max(1, int(tr.sum()))), flush=True)
    print("训练 %d / 测试 %d 候选，特征 %d 维，模板 %d 个，prior=%.4f"
          % (int(tr.sum()), int(te.sum()), X.shape[1], len(tot), prior), flush=True)

    results = []
    base = HistGradientBoostingClassifier(max_iter=a.iters, learning_rate=0.06,
                                          max_leaf_nodes=31, random_state=a.seed)
    base.fit(Xb[tr], y[tr])
    r = CT.evaluate(df_te, score=base.predict_proba(Xb[te])[:, 1])
    r["tag"] = "v2(59)"
    results.append(r)
    print("  v2(59)      top1=%.4f top3=%.4f top5=%.4f mrr=%.4f"
          % (r["top1"], r["top3"], r["top5"], r["mrr"]), flush=True)
    if a.out_base:
        with io.open(a.out_base, "wb") as f:
            pickle.dump({
                "model": base,
                "features": num + ["rule:" + x for x in top_rules],
                "top_rules": top_rules,
                "metrics": [r],
                "n_train": int(tr.sum()),
                "n_test": int(te.sum()),
                "meta": {"version": "v2-cli", "note": "59 维；数据集按生产引擎配置重建"},
            }, f)
        print("  基座模型写出 %s" % a.out_base, flush=True)

    clf = HistGradientBoostingClassifier(max_iter=a.iters, learning_rate=0.06,
                                         max_leaf_nodes=31, random_state=a.seed)
    clf.fit(Xtr, y[tr])
    r = CT.evaluate(df_te, score=clf.predict_proba(X[te])[:, 1])
    r["tag"] = "v3(61)"
    results.append(r)
    print("  v3(61)      top1=%.4f top3=%.4f top5=%.4f mrr=%.4f"
          % (r["top1"], r["top3"], r["top5"], r["mrr"]), flush=True)

    blob = {
        "model": clf,
        "features": names + ["rule:" + x for x in top_rules],
        "top_rules": top_rules,
        "tpl_stats": {k: (pos[k], tot[k]) for k in tot},
        "tpl_alpha": a.alpha,
        "tpl_prior": prior,
        "tpl_dropout": a.dropout,
        "metrics": results,
        "n_train": int(tr.sum()),
        "n_test": int(te.sum()),
        "meta": {
            "version": "v3",
            "note": "59 维 + 模板先验（命中率/出现次数）；统计只来自 train 切分",
        },
    }
    with io.open(a.out, "wb") as f:
        pickle.dump(blob, f)
    print("写出 %s（%.1f MB，%.1f s）"
          % (a.out, Path(a.out).stat().st_size / 1e6, time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

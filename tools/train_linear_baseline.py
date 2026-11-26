# -*- coding: utf-8 -*-
"""P2 的公开基线：同一批 59 维特征上的线性模型（逻辑回归）。

目的：给「梯度提升 + 模板统计」一个可比的弱基线，回答「增益是不是模型容量带来的」。
输出 reports/rank_model_linear.pkl（结构与其它 rank_model*.pkl 一致，可直接被 rerank 加载）。

用法：
  python tools\\train_linear_baseline.py
  python tools\\train_linear_baseline.py --table reports\\candidate_table\\candidates_cli.parquet --meta reports\\candidate_table\\meta_cli.json
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=str(CT.DEFAULT_DIR / "candidates_cli.parquet"))
    ap.add_argument("--meta", default=str(CT.DEFAULT_DIR / "meta_cli.json"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "rank_model_linear.pkl"))
    a = ap.parse_args()

    from sklearn.linear_model import LogisticRegression

    t0 = time.time()
    meta = CT.load_meta(a.meta)
    df, _ = CT.load(parquet=a.table, meta=meta)
    X, names = CT.feature_matrix(df, meta)
    y = df["label"].to_numpy()
    tr = (df["split"] == "train").to_numpy()
    te = ~tr
    print("训练 %d / 测试 %d 候选，特征 %d 维"
          % (int(tr.sum()), int(te.sum()), X.shape[1]), flush=True)

    clf = LogisticRegression(max_iter=200, n_jobs=-1, random_state=0)
    clf.fit(X[tr], y[tr])
    r = CT.evaluate(df[te], score=clf.predict_proba(X[te])[:, 1])
    print("内部测试：top1=%.4f top3=%.4f top5=%.4f mrr=%.4f"
          % (r["top1"], r["top3"], r["top5"], r["mrr"]), flush=True)

    blob = {
        "model": clf,
        "features": list(meta["num_features"]) + ["rule:" + x for x in meta["top_rules"]],
        "top_rules": list(meta["top_rules"]),
        "metrics": [dict(r, tag="linear")],
        "meta": {"version": "linear", "note": "同一批 59 维特征上的逻辑回归基线"},
    }
    with io.open(a.out, "wb") as f:
        pickle.dump(blob, f)
    print("写出 %s（%.1f MB，%.0f s）"
          % (a.out, Path(a.out).stat().st_size / 1e6, time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

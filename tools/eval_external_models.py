# -*- coding: utf-8 -*-
"""在任意候选表上评估若干个已训练的重排序模型（跨语料复现用）。

支持两类模型：
  59 维：num_features + 30 个规则 one-hot
  61 维：num + [tpl_hitrate, tpl_hitrate_n] + 规则 one-hot（模板统计从模型 pkl 里取）

用法：
  python tools\\eval_external_models.py --table reports\\candidate_table\\candidates_mit5k.parquet --meta reports\\candidate_table\\meta_mit5k.json --models reports\\rank_model_v2.pkl reports\\rank_model_v3cli.pkl
"""
from __future__ import annotations

import argparse
import pickle
import sys
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


def tpl_features(df, blob):
    stats = blob.get("tpl_stats") or {}
    alpha = float(blob.get("tpl_alpha") or 20.0)
    prior = float(blob.get("tpl_prior") or 0.0)
    tpl = df["tpl"].tolist()
    hr = np.empty(len(tpl), dtype="float64")
    lg = np.empty(len(tpl), dtype="float64")
    for i, t in enumerate(tpl):
        st = stats.get(t)
        if st is None:
            hr[i] = prior
            lg[i] = 0.0
        else:
            n = int(st[1])
            hr[i] = (float(st[0]) + alpha * prior) / (n + alpha)
            lg[i] = np.log1p(n)
    return np.column_stack([hr, lg])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--out", default=None, help="把结果写成 JSON（供画图脚本读取）")
    a = ap.parse_args()

    meta = CT.load_meta(a.meta)
    df, _ = CT.load(parquet=a.table, meta=meta)
    X, _ = CT.feature_matrix(df, meta)
    n_num = len(meta["num_features"])
    Xnum, Xrule = X[:, :n_num], X[:, n_num:]
    print("表 %d 行 / %d 反应 / 可评 %d"
          % (len(df), df["rid"].nunique(), int((df.drop_duplicates("rid")["n_pos"] > 0).sum())))

    base = CT.evaluate(df)
    print("  %-28s top1=%.4f top3=%.4f top5=%.4f mrr=%.4f"
          % ("发射序", base["top1"], base["top3"], base["top5"], base["mrr"]))

    results = [{"tag": "emission", **base}]
    for path in a.models:
        blob = pickle.load(open(path, "rb"))
        names = list(blob.get("features") or [])
        if "tpl_hitrate" in names:
            Xm = np.concatenate([Xnum, tpl_features(df, blob), Xrule], axis=1)
        else:
            Xm = X
        if Xm.shape[1] != len(names):
            print("  [skip] %s 维数 %d != %d" % (Path(path).name, Xm.shape[1], len(names)))
            continue
        score = blob["model"].predict_proba(Xm)[:, 1]
        r = CT.evaluate(df, score=score)
        print("  %-28s top1=%.4f top3=%.4f top5=%.4f mrr=%.4f"
              % (Path(path).name, r["top1"], r["top3"], r["top5"], r["mrr"]))
        results.append({"tag": Path(path).name, **r})
    if a.out:
        import json
        Path(a.out).write_text(json.dumps({"table": a.table, "results": results},
                                          ensure_ascii=False, indent=2),
                               encoding="utf-8")
        print("写出 %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

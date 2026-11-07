# -*- coding: utf-8 -*-
r"""Q2 决策依据：条件可行性模型的**阈值-收益曲线**（复用 train_condition_model 的口径，不重训口径）。

口径与 train_condition_model.py 完全一致：
* y = 1 if Yield >= 0.5
* 按 (aryl,amine) 分组交叉验证
* 特征 = solvent/catalyst/base/source one-hot + 8 个 Additive 布尔 + aryl/amine Morgan(2,2048)

输出 reports/condition_threshold_curve.json：
* 换底物对（GroupShuffleSplit，最严口径）与同底物对新条件（GroupKFold）两条曲线
* 关键操作点：保住 99%/95%/90%/80% 正例时各能拦掉多少负例
* 顺带把全量拟合的模型落盘到 models/condition_gate_bh.joblib（**不接入生产**）

用法: & $py -u tools\condition_model_threshold.py [--limit N] [--no-save-model]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "core", STAGE / "conditions", STAGE / "rules",
           STAGE / "tools", STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np                                          # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.metrics import roc_auc_score                    # noqa: E402
from sklearn.model_selection import GroupKFold, GroupShuffleSplit  # noqa: E402

import train_condition_model as tcm                          # noqa: E402

OUT = STAGE / "reports" / "condition_threshold_curve.json"
MODEL_DIR = STAGE / "models"
MODEL_PATH = MODEL_DIR / "condition_gate_bh.joblib"


def make_model():
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08,
                                          random_state=20261013)


def oof_groupkfold(X, y, groups, n_splits=5):
    gkf = GroupKFold(n_splits=n_splits)
    oof = np.zeros(len(y), dtype=np.float64)
    yt = np.zeros(len(y), dtype=np.int32)
    mask = np.zeros(len(y), dtype=bool)
    for tr, te in gkf.split(X, y, groups):
        m = make_model()
        m.fit(X[tr], y[tr])
        oof[te] = m.predict_proba(X[te])[:, 1]
        yt[te] = y[te]
        mask[te] = True
    return oof[mask], yt[mask]


def oof_unseen_pair(X, y, pair_ids, n_splits=5):
    gss = GroupShuffleSplit(n_splits=n_splits, test_size=0.25, random_state=20261013)
    ps, ys, aucs = [], [], []
    for tr, te in gss.split(X, y, pair_ids):
        m = make_model()
        m.fit(X[tr], y[tr])
        p = m.predict_proba(X[te])[:, 1]
        ps.append(p)
        ys.append(y[te])
        aucs.append(roc_auc_score(y[te], p))
    return (np.concatenate(ps), np.concatenate(ys),
            float(np.mean(aucs)), float(np.std(aucs)))


def curve(p, y, thresholds):
    """t 以上判为 可行(1)。kill_neg = 被拦住的负例比例；block_precision = 拦住的里面真负例占比。"""
    pos = int((y == 1).sum())
    neg = int((y == 0).sum())
    rows = []
    for t in thresholds:
        pred = p >= t
        tp = int(((pred) & (y == 1)).sum())
        fp = int(((pred) & (y == 0)).sum())
        fn = int(((~pred) & (y == 1)).sum())
        tn = int(((~pred) & (y == 0)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / pos if pos else 0.0
        rows.append({
            "threshold": round(float(t), 3),
            "pass_rate": round(float(pred.mean()), 4),
            "keep_pos_rate": round(rec, 4),
            "kill_neg_rate": round(tn / neg, 4) if neg else 0.0,
            "block_precision": round(tn / (tn + fn), 4) if tn + fn else 0.0,
            "precision": round(prec, 4),
            "f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        })
    return rows


def op_points(p, y, targets=(0.99, 0.95, 0.90, 0.80)):
    """在 keep_pos >= target 的前提下，取**最大**阈值（= 拦得最多）。"""
    pos = int((y == 1).sum())
    neg = int((y == 0).sum())
    out = {}
    for tg in targets:
        best = None
        for t in np.arange(0.01, 0.996, 0.005):
            pred = p >= t
            rec = float(((pred) & (y == 1)).sum()) / max(1, pos)
            if rec >= tg:
                cand = {"threshold": round(float(t), 3),
                        "keep_pos_rate": round(rec, 4),
                        "kill_neg_rate": round(float(((~pred) & (y == 0)).sum()) / max(1, neg), 4),
                        "pass_rate": round(float(pred.mean()), 4)}
                if best is None or cand["threshold"] > best["threshold"]:
                    best = cand
        out[str(tg)] = best
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--no-save-model", action="store_true")
    a = ap.parse_args()

    t0 = time.time()
    rows = tcm.load(a.limit)
    X, y, groups, cats = tcm.build_matrix(rows, use_fp=True)
    print("载入 %d 行 / %d 组；正例率 %.1f%%；特征 %s"
          % (len(rows), len({r["group"] for r in rows}), 100.0 * y.mean(), X.shape))

    pair_ids = np.array(["%s|%s" % (r["aryl"], r["amine"]) for r in rows])
    grid = [round(0.05 * i, 2) for i in range(1, 20)]

    print("[1/2] 同底物对新条件（GroupKFold）…", flush=True)
    p_seen, y_seen = oof_groupkfold(X, y, groups)
    auc_seen = float(roc_auc_score(y_seen, p_seen))
    print("   AUC %.4f  n=%d" % (auc_seen, len(y_seen)), flush=True)

    print("[2/2] 换底物对（GroupShuffleSplit）…", flush=True)
    p_un, y_un, auc_un, sd_un = oof_unseen_pair(X, y, pair_ids)
    print("   AUC %.4f ± %.4f  n=%d（5 折测试集拼接，折间有重叠）" % (auc_un, sd_un, len(y_un)),
          flush=True)

    payload = {
        "what": "条件可行性模型的阈值-收益曲线（Q2 决策依据）",
        "caveat": [
            "① 只在 BH 型偶联 HTE 上训练/评估，别类不可外推",
            "② 生产口径看 unseen_pair（换底物对）；seen_pair 偏乐观",
            "③ unseen_pair 的 5 折测试集是拼接的，同一条记录只出现在其中 1 折，但不同折之间阈值口径可比",
            "④ 本脚本只测量，不接入生产",
        ],
        "data": {"n_rows": len(rows), "pos_rate": round(float(y.mean()), 4),
                 "n_groups": len({r["group"] for r in rows})},
        "auc": {"seen_pair_new_condition": round(auc_seen, 4),
                "unseen_pair_mean": round(auc_un, 4), "unseen_pair_std": round(sd_un, 4)},
        "thresholds": grid,
        "seen_pair": {"curve": curve(p_seen, y_seen, grid),
                      "op_points": op_points(p_seen, y_seen)},
        "unseen_pair": {"curve": curve(p_un, y_un, grid),
                        "op_points": op_points(p_un, y_un)},
        "seconds": round(time.time() - t0, 1),
    }

    if not a.no_save_model:
        import joblib
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        final = make_model()
        final.fit(X, y)
        joblib.dump({"model": final, "cats": cats, "add_cols": tcm.ADD_COLS,
                     "nbits": 2048, "target": "Yield >= 0.5",
                     "trained_on": "BH_HTE_Curated_Dataset_v20260219.csv (%d rows)" % len(rows),
                     "wired_into_production": False}, MODEL_PATH)
        payload["model_path"] = str(MODEL_PATH)
        print("模型已落盘（未接入生产）：%s" % MODEL_PATH, flush=True)

    Path(a.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print("-> %s  (%.1fs)" % (a.out, time.time() - t0), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

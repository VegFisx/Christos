# -*- coding: utf-8 -*-
"""候选级基准表的守约测试。

检查五件事：
  A 结构：行数 / 反应数 / 可评数 / 正例数 与 meta 一致
  B 反应级：n_cand / n_pos / true_rank / split 与逐行事实一致
  C 特征：抽样复算 train_ranker_v2.feats，与表里的 59 维逐个相同
  D 端到端：用表里的特征重放 rank_model_v2.pkl，测试集指标回到 78.01% / n=5584
  E 评估器：发射序 top-1 与 meta 相同

用法：python tools\\test_candidate_table.py
"""
from __future__ import annotations

import io
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
import train_ranker_v2 as TR  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print("  %s %s %s" % ("[ok] " if ok else "[FAIL]", name, detail))
    if not ok:
        fails.append(name)


def main() -> int:
    print("载入 %s" % CT.DEFAULT_PARQUET)
    df, meta = CT.load()
    print("  %d 行 × %d 列" % (df.shape[0], df.shape[1]))

    # ---- A 结构 ----
    print("A 结构")
    check("行数", len(df) == meta["n_rows"], "%d vs %d" % (len(df), meta["n_rows"]))
    check("反应数", df["rid"].nunique() == meta["n_reactions"],
          "%d vs %d" % (df["rid"].nunique(), meta["n_reactions"]))
    check("正例行数", int(df["label"].sum()) == meta["n_positive_rows"],
          "%d vs %d" % (int(df["label"].sum()), meta["n_positive_rows"]))
    ev = df.drop_duplicates("rid")
    ev = ev[ev["n_pos"] > 0]
    check("可评反应数", len(ev) == meta["n_evaluable"],
          "%d vs %d" % (len(ev), meta["n_evaluable"]))

    # ---- B 反应级 ----
    print("B 反应级一致性")
    g = df.groupby("rid", sort=False)
    n_cand_bad = int((g.size() != g["n_cand"].first()).sum())
    n_pos_bad = int((g["label"].sum() != g["n_pos"].first()).sum())
    split_bad = int((g["split"].nunique() > 1).sum())
    check("n_cand == 组大小", n_cand_bad == 0, "坏 %d 组" % n_cand_bad)
    check("n_pos == 正例数", n_pos_bad == 0, "坏 %d 组" % n_pos_bad)
    check("每反应单一 split", split_bad == 0, "坏 %d 组" % split_bad)

    pos = df[df["label"] == 1].groupby("rid", sort=False)["rank"].min()
    tr = g["true_rank"].first()
    joined = tr.to_frame("tr").join(pos.rename("pos"), how="left")
    expect = joined["pos"].fillna(-1).astype("int64")
    bad_tr = int((joined["tr"].astype("int64") != expect).sum())
    check("true_rank == 首正例 rank（或 -1）", bad_tr == 0, "坏 %d 组" % bad_tr)

    # ---- C 特征 ----
    print("C 特征复算")
    sample = df.iloc[np.linspace(0, len(df) - 1, 2000, dtype="int64")]
    X_all, names = CT.feature_matrix(df, meta)
    Xs = CT.feature_matrix(sample, meta)[0]
    top_rules = list(meta["top_rules"])
    bad = 0
    worst = 0.0
    for i, (_, row) in enumerate(sample.iterrows()):
        ref = np.asarray(TR.feats(row.to_dict(), top_rules), dtype="float64")
        diff = float(np.max(np.abs(Xs[i] - ref)))
        worst = max(worst, diff)
        if diff > 0.0:
            bad += 1
    check("2000 行 59 维与 feats() 逐位相同", bad == 0,
          "不符 %d 行 / 最大差 %.2e / 特征 %d 维" % (bad, worst, len(names)))
    check("特征维数 = 59", len(names) == meta["feature_count"], str(len(names)))

    # ---- D 端到端重放模型 ----
    print("D 重放 rank_model_v2")
    model_obj = pickle.load(io.open(ROOT / "reports" / "rank_model_v2.pkl", "rb"))
    clf = model_obj["model"]
    te_mask = (df["split"] != "train").to_numpy()
    df_te = df[te_mask]
    Xte = X_all[te_mask]
    score_te = clf.predict_proba(Xte)[:, 1]
    m_te = CT.evaluate(df_te, score=score_te)
    ref = [r for r in model_obj["metrics"] if r["tag"] == "v2"][0]
    print("    表重放 n=%d top1=%.4f top3=%.4f top5=%.4f mrr=%.4f"
          % (m_te["n"], m_te["top1"], m_te["top3"], m_te["top5"], m_te["mrr"]))
    print("    模型记录 n=%d top1=%.4f top3=%.4f top5=%.4f mrr=%.4f"
          % (ref["n"], ref["top1"], ref["top3"], ref["top5"], ref["mrr"]))
    print("    （记录的 MRR 在 train_ranker_v2 里被截到 top-5，本表的 MRR 是全序，"
          "故两者不等属预期）")
    check("测试反应数", m_te["n"] == ref["n"], "%d vs %d" % (m_te["n"], ref["n"]))
    for k in ("top1", "top3", "top5"):
        check("重放 %s" % k, abs(m_te[k] - ref[k]) <= 1e-4,
              "%.4f vs %.4f" % (m_te[k], ref[k]))

    # ---- E 评估器 ----
    print("E 评估器")
    t1 = CT.top1_from_table(df)
    check("发射序 top-1 == meta", abs(t1 - meta["top1_emission"]) <= 1e-6,
          "%.6f vs %.6f" % (t1, meta["top1_emission"]))
    check("召回 == meta['recall_any']",
          abs(meta["n_evaluable"] / meta["n_reactions"] - meta["recall_any"]) <= 1e-6,
          "%.6f" % meta["recall_any"])
    m0 = CT.evaluate(df)
    check("evaluate(默认) 与 true_rank 一致",
          abs(m0["top1"] - t1) <= 1e-4, "%.4f vs %.6f" % (m0["top1"], t1))
    print("    %s" % CT.summarize(df))

    print("\n失败 %d 项" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""候选级基准表的读取 / 特征组装 / 排序评估。

表由 `tools/build_candidate_table.py` 生成：
  reports/candidate_table/candidates_v2.parquet
  reports/candidate_table/meta.json

典型用法（一个新想法 20 分钟出结果）：

    import sys; sys.path.insert(0, r"D:\\ProgramData\\DSHNS\\chemreact-staging\\tools")
    import candidate_table as CT

    df, meta = CT.load()
    X, names = CT.feature_matrix(df)          # (n, 59) float32，与 rank_model_v2.pkl 同口径
    print(CT.evaluate(df))                    # 发射序基线 top-1/3/5/MRR
    print(CT.evaluate(df, score=X[:, 0]))     # 换成任意分数
    print(CT.reaction_summary(df).head())
"""
from __future__ import annotations

import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "reports" / "candidate_table"
DEFAULT_PARQUET = DEFAULT_DIR / "candidates_v2.parquet"
DEFAULT_META = DEFAULT_DIR / "meta.json"


def load_meta(path=None) -> dict:
    p = Path(path or DEFAULT_META)
    return json.loads(io.open(p, encoding="utf-8").read())


def load(parquet=None, columns=None, meta=None):
    """返回 (DataFrame, meta)。columns 可只取部分列以省内存。"""
    import pandas as pd

    pq = Path(parquet or DEFAULT_PARQUET)
    if not pq.exists():
        raise FileNotFoundError(
            "%s 不存在；先跑 python tools\\build_candidate_table.py" % pq)
    df = pd.read_parquet(pq, columns=columns)
    return df, (meta or load_meta())


def feature_matrix(df, meta=None):
    """按 meta 的 feature_order 组装 (n, 59) float64 矩阵与列名。

    - 29 个数值特征直接取表里的列（已按 train_ranker_v2.feats 物化）；
    - 30 个规则 one-hot 由 rule 列现做（表里不存稀疏宽列）。
    """
    import numpy as np

    meta = meta or load_meta()
    num = list(meta["num_features"])
    rules = list(meta["top_rules"])
    missing = [c for c in num if c not in df.columns]
    if missing:
        raise KeyError("表里缺数值特征列：%s" % missing)
    # 必须 float64：float32 会让模型的分箱边界挪位，top-1 掉 0.5 pp（实测）
    parts = [df[num].to_numpy(dtype="float64")]
    rule = df["rule"].to_numpy()
    for r in rules:
        parts.append((rule == r).astype("float64")[:, None])
    X = np.concatenate(parts, axis=1)
    return X, num + ["rule:" + r for r in rules]


def reaction_summary(df):
    """一行一个反应：split / want / 候选数 / 正例数 / 正例最小 rank。"""
    cols = ["rid", "split", "want", "n_cand", "n_pos", "true_rank",
            "uspto_id", "rxn_class", "src_join"]
    have = [c for c in cols if c in df.columns]
    out = df.groupby("rid", sort=True)[have[1:]].first().reset_index()
    return out


def evaluate(df, score=None, ks=(1, 3, 5), require_positive=True) -> dict:
    """按 score（越大越靠前）评估 top-k 与 MRR。

    score=None 时用发射序（rank 小者在前）。
    score 可以是列名，或与 df 等长的数组（未排序也行，按行对齐）。
    """
    import numpy as np

    d = df
    if score is None:
        s = -d["rank"].to_numpy(dtype="float64")
    elif isinstance(score, str):
        s = d[score].to_numpy(dtype="float64")
    else:
        s = np.asarray(score, dtype="float64")
        if len(s) != len(d):
            raise ValueError("score 长度 %d 与表 %d 不一致" % (len(s), len(d)))
    work = d[["rid", "label", "rank", "n_pos"]].copy()
    work["_s"] = s
    if require_positive:
        work = work[work["n_pos"] > 0]
    if work.empty:
        return {"n": 0, "top1": 0.0, "top3": 0.0, "top5": 0.0, "mrr": 0.0}

    work = work.sort_values(["rid", "_s", "rank"], ascending=[True, False, True])
    work["_pos"] = work.groupby("rid", sort=False).cumcount()
    first = work[work["label"] == 1].groupby("rid", sort=False)["_pos"].min()

    n = int(first.shape[0])
    out = {"n": n}
    for k in ks:
        out["top%d" % k] = round(float((first < k).mean()), 4) if n else 0.0
    out["mrr"] = round(float((1.0 / (first + 1)).mean()), 4) if n else 0.0
    return out


def top1_from_table(df) -> float:
    """不排序时（发射序）的 top-1，直接数 true_rank。"""
    ev = df[df["n_pos"] > 0].drop_duplicates("rid")
    return round(float((ev["true_rank"] == 0).mean()), 6) if len(ev) else 0.0


def summarize(df) -> str:
    """一行摘要，方便脚本打印。"""
    m = evaluate(df)
    return ("反应 %d / 可评 %d / 候选 %d / 发射序 top1=%.4f top3=%.4f top5=%.4f mrr=%.4f"
            % (df["rid"].nunique(), m["n"], len(df),
               m["top1"], m["top3"], m["top5"], m["mrr"]))

# -*- coding: utf-8 -*-
r"""第十七轮 / 阶段A（路线①+②）：结构特征 + 显式交互项能不能把条件判据顶上去？

# 口径（与 tools/hte_condition_model.py 完全一致 —— 为了和基线 0.592/0.646 可比，别事后改）
  数据：HTE Buchwald-Hartwig curated（27,497 行）
  评估集：【有对比的底物对】= 同一 (Aryl, Amine) 既有 Yield==0 又有 Yield>0  -> 459 对 / 17,246 行
  成功定义：Yield>0（主口径）；Yield>=10（敏感性）
  划分：GroupKFold(5)，按底物对分组（同对不跨折，防泄漏）
  指标：同对内 AUC —— micro（主，与基线同口径）/ macro
  基线（第十五轮实测，tools/hte_condition_model.py）：micro 0.592（Yield>0）/ 0.646（Yield>=10）

# 特征块（★ 与同一轮另外两个子任务写死的定义一致）
  NB   = one-hot(Catalyst Name) + one-hot(Base Name) + one-hot(Solvent Name)   # 词表只用 train 拟合
  SUB  = Morgan(r=2,512)(Aryl) + Morgan(r=2,512)(Amine)
  DESC = substrate_desc(Aryl) + substrate_desc(Amine)   # 各 6 维，复用基线实现
  SB   = Morgan(r=2,512)(Catalyst SMILES) + 同(Base SMILES) + 同(Solvent SMILES)
  QM   = 解析后的 QM 浮点向量
  ADD  = 8 个 Additive_* 列
  INT  = 显式交互项：one-hot(Catalyst Name)[k] × DESC(12)；同样做 Base × DESC、Solvent × DESC

# 特征集
  F0a = NB+SUB        （≈ 基线 logreg_all，用来对齐 0.592）
  F0b = NB+DESC       （≈ 基线 hgb）
  F1  = NB+SUB+DESC+SB          ① 加条件【结构】特征
  F2  = F1+QM+ADD               ① + QM + Additive_*
  F3  = F2+INT                  ② 再加显式交互项

# 模型
  logreg = LogisticRegression(max_iter=2000)   （稀疏，全特征）
  hgb    = HistGradientBoostingClassifier(max_iter=200, random_state=SEED)  （需 dense）

# 复现
  & "D:\TCMAI\venv\Scripts\python.exe" tools\hte_feature_sets.py
  & ... tools\hte_feature_sets.py --sets F0a,F1,F2,F3 --models logreg,hgb --label yield_gt_0
输出：reports/hte_feature_sets.json；特征块缓存 reports/hte_feature_blocks.npz（重跑秒级）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))

CSV = STAGE / "data" / "external" / "bh-hte-ood" / \
    "schwallergroup-bh-hte-ood-a277041" / "data" / "BH_HTE_Curated_Dataset_v20260219.csv"
OUT_JSON = STAGE / "reports" / "hte_feature_sets.json"
CACHE = STAGE / "reports" / "hte_feature_blocks.npz"

SEED = 20261013
MORGAN_BITS = 512
CAT_COLS = ["Catalyst Name", "Base Name", "Solvent Name"]
SB_COLS = ["Catalyst SMILES", "Base SMILES", "Solvent SMILES"]
ADD_COLS = ["Additive_present", "Additive_aromatic_rings", "Additive_heteroatom_count",
            "Additive_coordination_flag", "Additive_steric_bulk_flag", "Additive_pi_rich_flag",
            "Additive_Pd_poisoning", "Additive_competes_with_amine"]

# 指标函数用基线那一份（单一真相，不重写）
import hte_condition_model as base  # noqa: E402

print("=" * 100)
print("阶段A：结构特征 + 交互项 对【同对内 AUC】的影响")
print("=" * 100)

# ---------------------------------------------------------------- 载入 + 评估集
df = pd.read_csv(CSV, low_memory=False)
df["_y"] = pd.to_numeric(df["Yield"], errors="coerce")
df["_pair"] = df["Aryl SMILES"].astype(str) + " || " + df["Amine SMILES"].astype(str)
g = df.groupby("_pair")["_y"].agg(["min", "max"]).reset_index()
contrast = set(g[(g["min"] == 0) & (g["max"] > 0)]["_pair"])
ev = df[df["_pair"].isin(contrast) & df["_y"].notna()].reset_index(drop=True)
print(f"评估集：{len(contrast)} 对 / {len(ev):,} 行   "
      f"成功 {int((ev['_y'] > 0).sum()):,} / 失败 {int((ev['_y'] == 0).sum()):,}")

FAIL = {"morgan_smiles": 0, "qm_parse": 0, "qm_dim_mismatch": 0, "add_nan": 0}
_cache_mol: dict = {}


def morgan_cached(smi: str) -> np.ndarray:
    key = str(smi)
    v = _cache_mol.get(key)
    if v is None:
        v = base.morgan(key, n_bits=MORGAN_BITS)
        if not v.any():
            FAIL["morgan_smiles"] += 1
        _cache_mol[key] = v
    return v


def desc_cached(smi: str) -> np.ndarray:
    key = "D:" + str(smi)
    v = _cache_mol.get(key)
    if v is None:
        v = np.asarray(base.substrate_desc(key[2:]), dtype=np.float32)
        if not v.any():
            FAIL["morgan_smiles"] += 1
        _cache_mol[key] = v
    return v


def hstack_rows(fn, series) -> np.ndarray:
    return np.vstack([fn(s) for s in series])


# ---------------------------------------------------------------- 特征块（行级，与折无关）
if CACHE.exists():
    z = np.load(CACHE)
    BLK = {k: z[k] for k in z.files}
    print(f"特征块缓存命中：{CACHE.name}  " +
          " ".join(f"{k}={v.shape}" for k, v in BLK.items()))
    n_rows_cache = BLK["SUB"].shape[0]
    if n_rows_cache != len(ev):
        print(f"  ⚠ 缓存行数 {n_rows_cache} != 当前 {len(ev)}，忽略缓存重建")
        BLK = {}
else:
    BLK = {}

if not BLK:
    t0 = time.time()
    print("\n计算行级特征块（Morgan 按 SMILES 去重缓存）...")
    SUB = np.hstack([hstack_rows(morgan_cached, ev["Aryl SMILES"]),
                     hstack_rows(morgan_cached, ev["Amine SMILES"])])
    SB = np.hstack([hstack_rows(morgan_cached, ev[c]) for c in SB_COLS])
    DESC = np.hstack([hstack_rows(desc_cached, ev["Aryl SMILES"]),
                      hstack_rows(desc_cached, ev["Amine SMILES"])])

    # QM：先把原始值样例打出来（纪律：先看原文再写解析）
    print("\nQM 原始值样例（前 1 条，截断 160 字符）：")
    print("   " + repr(str(ev["QM"].iloc[0])[:160]))
    qm_rows, qm_dims = [], []
    for s in ev["QM"]:
        try:
            arr = np.asarray(str(s).replace("[", " ").replace("]", " ").split(), dtype=np.float64)
            if arr.size == 0:
                FAIL["qm_parse"] += 1
                arr = np.zeros(1, np.float32)
            qm_rows.append(arr.astype(np.float32))
            qm_dims.append(arr.size)
        except Exception:
            FAIL["qm_parse"] += 1
            qm_rows.append(np.zeros(1, np.float32))
            qm_dims.append(1)
    qm_dim = int(np.bincount(np.asarray(qm_dims)).argmax())
    FAIL["qm_dim_mismatch"] = int(sum(1 for d in qm_dims if d != qm_dim))
    QM = np.zeros((len(qm_rows), qm_dim), np.float32)
    for i, a in enumerate(qm_rows):
        k = min(qm_dim, a.size)
        QM[i, :k] = a[:k]
    print(f"   QM 解析：维度众数 = {qm_dim}，维度不一致 {FAIL['qm_dim_mismatch']} 行，"
          f"解析失败 {FAIL['qm_parse']} 行")

    ADD = np.zeros((len(ev), len(ADD_COLS)), np.float32)
    for j, c in enumerate(ADD_COLS):
        v = pd.to_numeric(ev[c], errors="coerce")
        FAIL["add_nan"] += int(v.isna().sum())
        ADD[:, j] = v.fillna(0.0).to_numpy(np.float32)

    BLK = {"SUB": SUB.astype(np.float32), "SB": SB.astype(np.float32),
           "DESC": DESC.astype(np.float32), "QM": QM, "ADD": ADD}
    np.savez_compressed(CACHE, **BLK)
    print(f"   完成，耗时 {time.time()-t0:.1f}s；缓存写入 {CACHE.name}")
    print(f"   块形状：" + "  ".join(f"{k}={v.shape}" for k, v in BLK.items()))

print("\n失败/缺失计数（不静默）：" + "  ".join(f"{k}={v}" for k, v in FAIL.items()))

# ---------------------------------------------------------------- 折内块
def onehot_fit(col: pd.Series) -> dict:
    return {v: i for i, v in enumerate(sorted(col.astype(str).unique()))}


def onehot_apply(col: pd.Series, vocab: dict) -> sp.csr_matrix:
    codes = np.array([vocab.get(v, -1) for v in col.astype(str)], dtype=np.int32)
    keep = codes >= 0
    rows = np.nonzero(keep)[0]
    return sp.csr_matrix((np.ones(len(rows), np.float32), (rows, codes[keep])),
                         shape=(len(col), len(vocab)))


def interact(codes: np.ndarray, K: int, desc: np.ndarray) -> sp.csr_matrix:
    """显式交互项：one-hot(k) ⊗ desc（每个非零类别展开 dim(desc) 列）。"""
    D = desc.shape[1]
    rr, cc, dd = [], [], []
    for k in range(K):
        m = codes == k
        if not m.any():
            continue
        idx = np.nonzero(m)[0]
        rr.append(np.repeat(idx, D))
        cc.append((k * D + np.tile(np.arange(D), len(idx))))
        dd.append(desc[idx].reshape(-1))
    if not rr:
        return sp.csr_matrix((len(codes), max(1, K * D)), np.float32)
    return sp.csr_matrix((np.concatenate(dd), (np.concatenate(rr), np.concatenate(cc))),
                         shape=(len(codes), K * D))


FULL_SETS = {
    "F0a": ["NB", "SUB"],
    "F0b": ["NB", "DESC"],
    "F0": ["NB", "SUB", "DESC"],
    "F1": ["NB", "SUB", "DESC", "SB"],
    "F2": ["NB", "SUB", "DESC", "SB", "QM", "ADD"],
    "F3": ["NB", "SUB", "DESC", "SB", "QM", "ADD", "INT"],
}


def build_fold(blocks, tr, te):
    """按 fold 拟合词表 -> 返回 {block_name: (Xtr, Xte)}。"""
    out = {}
    vocabs = {c: onehot_fit(ev.loc[tr, c]) for c in CAT_COLS}
    out["NB"] = (sp.hstack([onehot_apply(ev.loc[tr, c], vocabs[c]) for c in CAT_COLS]).tocsr(),
                 sp.hstack([onehot_apply(ev.loc[te, c], vocabs[c]) for c in CAT_COLS]).tocsr())
    codes_tr = {c: np.array([vocabs[c].get(v, -1) for v in ev.loc[tr, c].astype(str)]) for c in CAT_COLS}
    codes_te = {c: np.array([vocabs[c].get(v, -1) for v in ev.loc[te, c].astype(str)]) for c in CAT_COLS}
    out["INT"] = (
        sp.hstack([interact(codes_tr[c], len(vocabs[c]), blocks["DESC"][tr]) for c in CAT_COLS]).tocsr(),
        sp.hstack([interact(codes_te[c], len(vocabs[c]), blocks["DESC"][te]) for c in CAT_COLS]).tocsr())
    for name in ("SUB", "SB", "DESC", "QM", "ADD"):
        out[name] = (sp.csr_matrix(blocks[name][tr]), sp.csr_matrix(blocks[name][te]))
    return out


def assemble(fold_blocks, names, dense: bool):
    tr = [fold_blocks[n][0] for n in names]
    te = [fold_blocks[n][1] for n in names]
    Xtr = sp.hstack(tr).tocsr() if len(tr) > 1 else tr[0]
    Xte = sp.hstack(te).tocsr() if len(te) > 1 else te[0]
    if dense:
        return Xtr.toarray().astype(np.float32), Xte.toarray().astype(np.float32)
    return Xtr, Xte


def make_model(mname: str, scale: bool, maxiter: int):
    """★ 公平性：大特征集上 lbfgs 会没收敛（实测 ConvergenceWarning），
    那会把 F3 的增益低估。--scale 走 StandardScaler(with_mean=False) + 更高 max_iter。"""
    if mname == "hgb":
        return HistGradientBoostingClassifier(max_iter=200, random_state=SEED)
    clf = LogisticRegression(max_iter=maxiter, C=1.0)
    if scale:
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        return Pipeline([("sc", StandardScaler(with_mean=False)), ("clf", clf)])
    return clf


def run_grid(labels, sets, models, scale=False, maxiter=2000):
    results = {}
    groups = ev["_pair"].values
    gkf = GroupKFold(n_splits=5)
    for label_name, ycol in labels:
        y = ycol.values
        print("\n" + "=" * 100)
        print(f"[标签 {label_name}]  成功 {int(y.sum()):,} / 失败 {int((1-y).sum()):,}")
        print("=" * 100)
        print(f"{'特征集':<6} {'模型':<8} {'micro':>7} {'macro':>7} {'比较数':>9} {'耗时s':>7}")
        for sname in sets:
            names = FULL_SETS[sname]
            _all = np.arange(len(ev))
            nfeat = int(assemble(build_fold(BLK, _all, _all), names, dense=False)[0].shape[1])
            for mname in models:
                t0 = time.time()
                scores = np.full(len(ev), np.nan, np.float32)
                n_used = 0
                n_notconv = 0
                for tr_idx, te_idx in gkf.split(ev, y, groups):
                    if len(set(y[tr_idx])) < 2:
                        continue
                    fb = build_fold(BLK, tr_idx, te_idx)
                    Xtr, Xte = assemble(fb, names, dense=(mname == "hgb"))
                    clf = make_model(mname, scale, maxiter)
                    with warnings.catch_warnings(record=True) as wlist:
                        warnings.simplefilter("always", ConvergenceWarning)
                        clf.fit(Xtr, y[tr_idx])
                        n_notconv += sum(1 for w in wlist
                                         if issubclass(w.category, ConvergenceWarning))
                    scores[te_idx] = clf.predict_proba(Xte)[:, 1]
                    n_used += 1
                ok = ~np.isnan(scores)
                wtl = base.pair_wtl(y[ok], scores[ok], groups[ok])
                mm, _cnt = base.micro_auc(wtl)   # 基线返回 (auc, (w, t, l))
                mc = int(sum(_cnt))
                ma = base.macro_auc(wtl)
                dt = time.time() - t0
                results[f"{label_name}|{sname}|{mname}"] = {
                    "micro": mm, "macro": ma, "comparisons": mc,
                    "n_scored": int(ok.sum()), "folds": n_used, "seconds": round(dt, 1),
                    "features": names, "n_features": nfeat,
                    "scale": bool(scale), "maxiter": maxiter,
                    "n_not_converged_folds": int(n_notconv),
                }
                print(f"{sname:<6} {mname:<8} {mm:>7.3f} {ma:>7.3f} {mc:>9,} {dt:>7.1f} "
                      f"未收敛折 {n_notconv}", flush=True)
    return results


ap = argparse.ArgumentParser()
ap.add_argument("--sets", default="F0a,F0b,F0,F1,F2,F3")
ap.add_argument("--models", default="logreg,hgb")
ap.add_argument("--label", default="both", choices=["both", "yield_gt_0", "yield_ge_10"])
ap.add_argument("--scale", action="store_true",
                help="logreg 前接 StandardScaler(with_mean=False)（稀疏安全）+ 提高迭代上限")
ap.add_argument("--maxiter", type=int, default=2000)
ap.add_argument("--out", default="", help="结果 JSON 路径（默认 reports/hte_feature_sets.json）")
a = ap.parse_args()
if a.out:
    OUT_JSON = Path(a.out)

labels_all = [("yield_gt_0", (ev["_y"] > 0).astype(int)),
              ("yield_ge_10", (ev["_y"] >= 10).astype(int))]
labels = labels_all if a.label == "both" else [x for x in labels_all if x[0] == a.label]

t_all = time.time()
res = run_grid(labels, [s.strip() for s in a.sets.split(",") if s.strip()],
               [m.strip() for m in a.models.split(",") if m.strip()],
               scale=a.scale, maxiter=a.maxiter)

print("\n" + "=" * 100)
print("汇总（对照基线 第十五轮实测：micro 0.592 / 0.646）")
print("=" * 100)
base_ref = {"yield_gt_0": 0.592, "yield_ge_10": 0.646}
for k in sorted(res):
    lab = k.split("|")[0]
    d = res[k]
    ref = base_ref.get(lab)
    delta = (d["micro"] - ref) if ref else float("nan")
    print(f"  {k:<32} micro {d['micro']:.3f}  (基线 {ref} -> {delta:+.3f})  "
          f"macro {d['macro']:.3f}  特征数 {d['n_features']}")

OUT_JSON.write_text(json.dumps({
    "scratch": "第十七轮阶段A：结构特征+交互项 对 同对内 AUC 的影响",
    "caliber": {
        "eval_set": "对比底物对（min==0 且 max>0）", "pairs": len(contrast),
        "rows": int(len(ev)), "split": "GroupKFold(5) by pair",
        "metric": "同对内 micro/macro AUC", "baseline_ref": base_ref,
        "feature_sets": FULL_SETS, "morgan_bits": MORGAN_BITS,
        "scale": bool(a.scale), "maxiter": a.maxiter,
        "models": [m.strip() for m in a.models.split(",") if m.strip()],
        "sets": [s.strip() for s in a.sets.split(",") if s.strip()],
    },
    "failures": FAIL, "results": res, "total_seconds": round(time.time() - t_all, 1),
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n-> {OUT_JSON.name}   总耗时 {time.time()-t_all:.1f}s")

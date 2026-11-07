#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第十七轮：把「反应会不会发生」从【同对内相对排序】升级为【绝对概率判据 + 校准 + 拒识】。

评估口径 = 原论文 OOD 切分（复现 paper 口径）：
  列 `iteration_k cluster` / `iteration_k train_test`（长度为 4 的 list，
  每个 cluster 在其中恰好一个位置是 'test'）
  → 一个 iteration = 4 个 split；每个 split 留出 3 个 cluster 作 OOD test
  （test 占比 15%~40%，切分完全由数据给定，脚本不自行随机）。
  与 paper utils/ml_train.py::train_test_ood_cluster_static 一致；
  `--no-jnj-train` 对应 paper 的 no_jjhte_train=True（把 Source=='JNJ HTE 2024' 从 train 去掉）。

特征块（与同一轮另一实验完全一致，未自创）：
  NB   = one-hot(Catalyst Name)+one-hot(Base Name)+one-hot(Solvent Name)，词表只用 train 拟合
         —— 直接调用 tools/hte_condition_model.py::condition_onehot
  SB   = Morgan(r=2,512bit)(Catalyst SMILES) + 同(Base SMILES) + 同(Solvent SMILES)
  SUB  = Morgan(r=2,512bit)(Aryl SMILES) + 同(Amine SMILES)      —— 复用 hte_condition_model.morgan
  DESC = hte_condition_model.substrate_desc() 对 Aryl / Amine 各一次（各 6 维）
  QM   = 解析后的 QM 浮点向量（50 维，脚本自解析）
  ADD  = 8 个 Additive_* 列
  INT  = one-hot(Catalyst Name)[k] × DESC(12) 展开，同样做 Base × DESC、Solvent × DESC
  F0=NB+SUB+DESC  F1=F0+SB  F2=F1+QM+ADD  F3=F2+INT

校准纪律：Platt / isotonic 只在 train 内部再切出的一份上拟合，绝不在 test 上拟合。

用法示例：
  python hte_absolute_model.py --iteration 0 --features F2 --model lr --calib-split cluster
  python hte_absolute_model.py --iteration all --features all --model all --calib-split none
  python hte_absolute_model.py --merge-from <临时目录> --out reports/hte_absolute_model.json
"""
import argparse
import ast
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

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import sparse  # noqa: E402
from sklearn.calibration import IsotonicRegression  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from hte_condition_model import condition_onehot, morgan, substrate_desc  # noqa: E402

CSV = STAGE / "data" / "external" / "bh-hte-ood" / \
    "schwallergroup-bh-hte-ood-a277041" / "data" / "BH_HTE_Curated_Dataset_v20260219.csv"
DEFAULT_OUT = STAGE / "reports" / "hte_absolute_model.json"
SEED = 20261013
N_BINS = 10
QM_DIM = 50
CAT_COLS = ["Catalyst Name", "Base Name", "Solvent Name"]
SB_COLS = ["Catalyst SMILES", "Base SMILES", "Solvent SMILES"]
ADD_COLS = ["Additive_present", "Additive_aromatic_rings", "Additive_heteroatom_count",
            "Additive_coordination_flag", "Additive_steric_bulk_flag", "Additive_pi_rich_flag",
            "Additive_Pd_poisoning", "Additive_competes_with_amine"]
FEATURE_SETS = {
    "F0": ["NB", "SUB", "DESC"],
    "F1": ["NB", "SUB", "DESC", "SB"],
    "F2": ["NB", "SUB", "DESC", "SB", "QM", "ADD"],
    "F3": ["NB", "SUB", "DESC", "SB", "QM", "ADD", "INT"],
}
FAIL = {"morgan": 0, "desc": 0, "qm": 0, "lr_converge": 0, "iso_fit": 0, "platt_fit": 0}


def note_fail(key, n=1):
    """失败必须累计并最终打印，禁止静默 continue。"""
    FAIL[key] = FAIL.get(key, 0) + n


# ------------------------------------------------------------------ 静态特征块
def _qm_vec(s):
    v = np.fromstring(str(s).replace("[", " ").replace("]", " ").replace("\n", " "), sep=" ")
    if v.size != QM_DIM:
        note_fail("qm")
        out = np.zeros(QM_DIM, dtype=np.float32)
        out[:min(QM_DIM, v.size)] = v[:QM_DIM]
        return out
    return v.astype(np.float32)


def _morgan_cache(smiles_list, cache, tag):
    rows = []
    for s in smiles_list:
        key = str(s)
        v = cache.get(key)
        if v is None:
            m = None
            try:
                from rdkit import Chem
                m = Chem.MolFromSmiles(key)
            except Exception:
                m = None
            if m is None:
                note_fail("morgan")
            v = morgan(key)
            cache[key] = v
        rows.append(v)
    return np.asarray(rows, dtype=np.float32)


def build_static(df):
    t0 = time.time()
    n = len(df)
    cache = {}
    sb = np.hstack([_morgan_cache(df[c].astype(str).tolist(), cache, c) for c in SB_COLS])
    sub = np.hstack([_morgan_cache(df[c].astype(str).tolist(), cache, c)
                     for c in ["Aryl SMILES", "Amine SMILES"]])
    d1 = np.asarray([substrate_desc(s) for s in df["Aryl SMILES"].astype(str)], dtype=np.float32)
    d2 = np.asarray([substrate_desc(s) for s in df["Amine SMILES"].astype(str)], dtype=np.float32)
    desc = np.hstack([d1, d2])
    zero_desc = int(np.sum(np.all(desc == 0.0, axis=1)))
    if zero_desc:
        note_fail("desc", zero_desc)
    qm = np.vstack([_qm_vec(s) for s in df["QM"].astype(str)])
    add = df[ADD_COLS].to_numpy(dtype=np.float32)
    print(f"[static] n={n} sb={sb.shape} sub={sub.shape} desc={desc.shape} "
          f"qm={qm.shape} add={add.shape} morgan_cache={len(cache)} "
          f"({time.time() - t0:.1f}s)", flush=True)
    return {"sb": sparse.csr_matrix(sb), "sub": sparse.csr_matrix(sub),
            "desc": desc, "qm": qm, "add": add,
            "cats": {c: df[c].fillna("").astype(str).to_numpy() for c in CAT_COLS}}


def _int_block(onehot, desc, width):
    """one-hot(K) 行 × desc(d) 行的逐行外积 → (n, K*d) 稀疏。未见类别（全 0 行）跳过。"""
    n, d = desc.shape
    rowsum = np.asarray(onehot.sum(axis=1)).ravel()
    keep = rowsum > 0
    idx = np.asarray(onehot.argmax(axis=1)).ravel()
    cols = (idx[:, None] * d + np.arange(d)[None, :]).ravel()
    rows = np.repeat(np.arange(n), d)
    data = np.asarray(desc, dtype=np.float32).ravel()
    m = np.repeat(keep, d)
    return sparse.csr_matrix((data[m], (rows[m], cols[m])), shape=(n, width * d))


def build_X(df, tr_idx, te_idx, static, fset):
    need = FEATURE_SETS[fset]
    tr_df, te_df = df.iloc[tr_idx], df.iloc[te_idx]
    parts = {"tr": [], "te": []}
    nb_tr = nb_te = None
    if "NB" in need:
        nb_tr, nb_te = condition_onehot(tr_df, te_df)
        parts["tr"].append(nb_tr)
        parts["te"].append(nb_te)
    for name in ("SUB", "SB"):
        if name in need:
            k = name.lower()
            parts["tr"].append(static[k][tr_idx])
            parts["te"].append(static[k][te_idx])
    if "DESC" in need:
        parts["tr"].append(sparse.csr_matrix(static["desc"][tr_idx]))
        parts["te"].append(sparse.csr_matrix(static["desc"][te_idx]))
    if "QM" in need:
        parts["tr"].append(sparse.csr_matrix(static["qm"][tr_idx]))
        parts["te"].append(sparse.csr_matrix(static["qm"][te_idx]))
    if "ADD" in need:
        parts["tr"].append(sparse.csr_matrix(static["add"][tr_idx]))
        parts["te"].append(sparse.csr_matrix(static["add"][te_idx]))
    if "INT" in need:
        # INT 的列宽必须用【train 词表】的宽度（condition_onehot 的词表只用 train 拟合），
        # 不能用全表 nunique —— 否则切片宽度对不上，会静默错位。
        ws = [len(sorted(tr_df[c].fillna("").astype(str).unique())) for c in CAT_COLS]
        if sum(ws) != nb_tr.shape[1]:
            raise RuntimeError(f"INT 列宽与 NB 不一致: {sum(ws)} != {nb_tr.shape[1]}")
        off = 0
        for c, k in zip(CAT_COLS, ws):
            parts["tr"].append(_int_block(nb_tr[:, off:off + k], static["desc"][tr_idx], k))
            parts["te"].append(_int_block(nb_te[:, off:off + k], static["desc"][te_idx], k))
            off += k
    Xtr = sparse.hstack(parts["tr"]).tocsr()
    Xte = sparse.hstack(parts["te"]).tocsr()
    return Xtr, Xte


# ------------------------------------------------------------------ 指标
def ece_and_curve(y, p, n_bins=N_BINS):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    curve, ece, tot = [], 0.0, len(y)
    for b in range(n_bins):
        m = idx == b
        nb = int(m.sum())
        if nb == 0:
            curve.append({"bin": b, "lo": float(edges[b]), "hi": float(edges[b + 1]),
                          "n": 0, "mean_p": None, "frac_pos": None, "gap": None})
            continue
        mp = float(p[m].mean())
        fp = float(y[m].mean())
        ece += nb / tot * abs(fp - mp)
        curve.append({"bin": b, "lo": float(edges[b]), "hi": float(edges[b + 1]), "n": nb,
                      "mean_p": mp, "frac_pos": fp, "gap": fp - mp})
    return float(ece), curve


def point_metrics(y, p):
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    out = {"n": int(len(y)), "pos_rate": float(y.mean()) if len(y) else None}
    if len(np.unique(y)) < 2:
        out.update({"roc_auc": None, "au_prc": None, "brier": None, "ece": None, "acc": None})
        out["degenerate"] = True
        return out, []
    out["roc_auc"] = float(roc_auc_score(y, p))
    out["au_prc"] = float(average_precision_score(y, p))
    out["brier"] = float(brier_score_loss(y, p))
    out["acc"] = float(((p >= 0.5).astype(int) == y).mean())
    e, curve = ece_and_curve(y, p)
    out["ece"] = e
    out["degenerate"] = False
    return out, curve


def rejection_table(y, p, covers=(1.0, 0.8, 0.6, 0.4, 0.2)):
    """按预测不确定度 |p-0.5| 从小到大剔除（=保留最有把握的 X%），给覆盖率-精确率/召回率表。"""
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    conf = np.maximum(p, 1.0 - p)
    order = np.argsort(-conf, kind="stable")
    tot_pos = int(y.sum())
    rows = []
    for cov in covers:
        k = int(round(cov * len(y)))
        k = max(1, min(k, len(y)))
        sel = order[:k]
        ys, ps = y[sel], p[sel]
        pred = (ps >= 0.5).astype(int)
        tp = int(((pred == 1) & (ys == 1)).sum())
        fp = int(((pred == 1) & (ys == 0)).sum())
        fn = int(((pred == 0) & (ys == 1)).sum())
        rows.append({
            "coverage": float(k / len(y)),
            "n_kept": k,
            "kept_pos_rate": float(ys.mean()),
            "conf_threshold": float(conf[sel].min()),
            "acc_kept": float((pred == ys).mean()),
            "prec_kept": float(tp / (tp + fp)) if (tp + fp) else None,
            "rec_kept": float(tp / (tp + fn)) if (tp + fn) else None,
            "pred_pos_rate_kept": float(pred.mean()),
            "recall_total": float(tp / tot_pos) if tot_pos else None,
        })
    return rows


def _ece_of(y, p):
    return ece_and_curve(y, p)[0]


# ------------------------------------------------------------------ 校准器
def fit_calibrators(p_cal, y_cal):
    out = {"platt": None, "iso": None}
    pc = np.clip(np.asarray(p_cal, dtype=float), 1e-6, 1 - 1e-6)
    z = np.log(pc / (1 - pc)).reshape(-1, 1)
    try:
        lr = LogisticRegression(max_iter=1000)
        lr.fit(z, y_cal)
        out["platt"] = lr
    except Exception as e:  # noqa: BLE001
        note_fail("platt_fit")
        print(f"  [warn] platt 拟合失败: {e}", flush=True)
    try:
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(pc, y_cal)
        out["iso"] = iso
    except Exception as e:  # noqa: BLE001
        note_fail("iso_fit")
        print(f"  [warn] isotonic 拟合失败: {e}", flush=True)
    return out


def apply_calibrator(cal, p):
    p = np.asarray(p, dtype=float)
    if cal is None:
        return p
    if isinstance(cal, IsotonicRegression):
        return np.clip(cal.predict(p), 0.0, 1.0)
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    z = np.log(pc / (1 - pc)).reshape(-1, 1)
    return cal.predict_proba(z)[:, 1]


# ------------------------------------------------------------------ 模型
def make_model(name):
    if name == "lr":
        return LogisticRegression(max_iter=2000)
    if name == "hgb":
        return HistGradientBoostingClassifier(max_iter=200, random_state=SEED)
    raise ValueError(name)


def fit_predict(name, Xtr, ytr, Xte, scale=False):
    m = make_model(name)
    if scale and name == "lr":
        # 只对 LR 生效；HGB 的分箱阈值按分位数，逐特征单调线性缩放是 no-op。
        sc = StandardScaler(with_mean=False)  # 稀疏安全：不中心化
        Xtr = sc.fit_transform(Xtr)
        Xte = sc.transform(Xte)
    if name == "hgb":
        Atr = Xtr.toarray().astype(np.float32)
        Ate = Xte.toarray().astype(np.float32)
        m.fit(Atr, ytr)
        p = m.predict_proba(Ate)[:, 1]
        del Atr, Ate
        return p
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        m.fit(Xtr, ytr)
        conv = [x for x in w if "ConvergenceWarning" in x.category.__name__]
        if conv:
            note_fail("lr_converge")
    return m.predict_proba(Xte)[:, 1]


# ------------------------------------------------------------------ 切分
def parse_iteration(arg):
    if str(arg).lower() == "all":
        return list(range(10))
    return [int(arg)]


def splits_of_iteration(df, k):
    """返回 [(fold, tr_idx, te_idx, test_clusters)]，由 iteration_k train_test 列给定。"""
    ccol, tcol = f"iteration_{k} cluster", f"iteration_{k} train_test"
    folds = df[tcol].map(ast.literal_eval)
    lens = folds.map(len).unique()
    if list(lens) != [4]:
        raise RuntimeError(f"iteration_{k} train_test 长度异常: {lens}")
    cl = df[ccol].to_numpy()
    out = []
    for j in range(4):
        te_mask = np.array([x[j] == "test" for x in folds])
        tr_idx = np.where(~te_mask)[0]
        te_idx = np.where(te_mask)[0]
        out.append((j, tr_idx, te_idx, sorted(np.unique(cl[te_mask]).tolist())))
    return out


def calib_split_indices(tr_idx, y, cl, mode, frac):
    """train 内部再切出校准集：cluster 模式按 cluster 整块留出（更接近 OOD），random 模式分层随机。"""
    if mode == "none":
        return tr_idx, None
    if mode == "random":
        fit_i, cal_i = train_test_split(tr_idx, test_size=frac, random_state=SEED,
                                        stratify=y[tr_idx])
        return fit_i, cal_i
    clusters = np.unique(cl[tr_idx])
    k = int(max(1, round(len(clusters) * frac)))
    pick = np.unique(np.linspace(0, len(clusters) - 1, k).round().astype(int))
    cal_clusters = set(clusters[pick].tolist())
    cal_mask = np.isin(cl[tr_idx], list(cal_clusters))
    fit_i = tr_idx[~cal_mask]
    cal_i = tr_idx[cal_mask]
    return fit_i, cal_i


# ------------------------------------------------------------------ 单次评估
def evaluate(df, y, static, fset, model, iters, calib_mode, calib_frac,
             no_jnj_train, scale=False):
    per_split = []
    pool = {"raw": ([], []), "platt": ([], []), "iso": ([], [])}
    for k in iters:
        cl = df[f"iteration_{k} cluster"].to_numpy()
        for fold, tr_idx, te_idx, tcl in splits_of_iteration(df, k):
            t0 = time.time()
            if no_jnj_train:
                src = df["Source"].to_numpy()
                tr_idx = tr_idx[src[tr_idx] != "JNJ HTE 2024"]
            if len(np.unique(y[te_idx])) < 2:
                print(f"  [skip] it{k} fold{fold} test 单类", flush=True)
                continue
            fit_idx, cal_idx = calib_split_indices(tr_idx, y, cl, calib_mode, calib_frac)
            ev_idx = te_idx if cal_idx is None else np.concatenate([cal_idx, te_idx])
            Xtr, Xev = build_X(df, fit_idx, ev_idx, static, fset)
            p_ev = fit_predict(model, Xtr, y[fit_idx], Xev, scale=scale)
            del Xtr, Xev
            p_te = p_ev if cal_idx is None else p_ev[len(cal_idx):]
            variants = {"raw": p_te}
            if cal_idx is not None:
                if len(np.unique(y[cal_idx])) < 2:
                    note_fail("calib_single_class")
                p_cal = p_ev[:len(cal_idx)]
                cals = fit_calibrators(p_cal, y[cal_idx])
                variants["platt"] = apply_calibrator(cals["platt"], p_te)
                variants["iso"] = apply_calibrator(cals["iso"], p_te)
            met = {}
            for name, p in variants.items():
                m, _ = point_metrics(y[te_idx], p)
                met[name] = m
                pool[name][0].append(y[te_idx])
                pool[name][1].append(p)
            per_split.append({
                "iteration": k, "fold": fold, "n_train": int(len(fit_idx)),
                "n_calib": int(0 if cal_idx is None else len(cal_idx)),
                "n_test": int(len(te_idx)), "test_clusters": tcl,
                "metrics": met, "secs": round(time.time() - t0, 1),
            })
            print(f"  [it{k} f{fold}] ntr={len(fit_idx)} ncal={0 if cal_idx is None else len(cal_idx)} "
                  f"nte={len(te_idx)} rawAUC={met['raw']['roc_auc']:.4f} "
                  f"rawECE={met['raw']['ece']:.4f} "
                  f"calECE={met.get('platt', {}).get('ece')} ({time.time() - t0:.1f}s)", flush=True)

    pooled = {}
    for name, (ys, ps) in pool.items():
        if not ys:
            continue
        yy = np.concatenate(ys)
        pp = np.concatenate(ps)
        m, curve = point_metrics(yy, pp)
        pooled[name] = {"metrics": m, "reliability": curve,
                        "rejection": rejection_table(yy, pp)}
    summary = {}
    for name in ("raw", "platt", "iso"):
        vals = [s["metrics"][name] for s in per_split if name in s["metrics"]]
        for key in ("roc_auc", "au_prc", "brier", "ece", "acc"):
            arr = np.array([v[key] for v in vals if v.get(key) is not None], dtype=float)
            if arr.size:
                summary[f"{name}_{key}"] = {"mean": float(arr.mean()),
                                            "std": float(arr.std()),
                                            "n_splits": int(arr.size)}
    return {"per_split": per_split, "pooled": pooled, "summary": summary}


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser(description="HTE 绝对判据 + 校准 + 拒识（原论文 OOD 切分）")
    ap.add_argument("--iteration", default="0", help="0..9 或 all（all = 10 iteration × 4 split）")
    ap.add_argument("--features", default="all", help="F0/F1/F2/F3 或 all")
    ap.add_argument("--model", default="all", help="lr/hgb 或 all")
    ap.add_argument("--target", default="labels", choices=["labels", "yieldpos"],
                    help="labels = 论文二分类主标签；yieldpos = Yield>0 敏感性")
    ap.add_argument("--calib-split", default="cluster", choices=["none", "cluster", "random"])
    ap.add_argument("--calib-frac", type=float, default=0.25)
    ap.add_argument("--scale", default="none", choices=["none", "std"],
                    help="std = LR 前先用 train 拟合的 StandardScaler(with_mean=False)；"
                         "对 HGB 是 no-op（分位数分箱对单调缩放不敏感）")
    ap.add_argument("--no-jnj-train", action="store_true",
                    help="复现 paper no_jjhte_train=True（train 去掉 Source=='JNJ HTE 2024'）")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--merge-from", default=None, help="把目录下所有 part json 合并进 --out")
    args = ap.parse_args()

    if args.merge_from:
        fail = {}
        parts = []
        merged = {"meta": {"merged_from": str(args.merge_from),
                           "generated": time.strftime("%Y-%m-%d %H:%M:%S")}, "runs": {}}
        files = sorted(Path(args.merge_from).glob("*.json"))
        for f in files:
            d = json.loads(f.read_text(encoding="utf-8"))
            parts.append({"file": f.name, "n_runs": len(d.get("runs", {})),
                          "failures": d.get("meta", {}).get("failures", {})})
            for k, v in d.get("meta", {}).get("failures", {}).items():
                fail[k] = fail.get(k, 0) + int(v)
            merged["runs"].update(d.get("runs", {}))
        merged["meta"]["failures_summed"] = fail
        merged["meta"]["parts"] = parts
        Path(args.out).write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
        print(f"[merge] {len(files)} 个 part → {args.out}，共 {len(merged['runs'])} 个 run", flush=True)
        print(f"[merge] 失败计数合计 {fail}", flush=True)
        return

    t0 = time.time()
    df = pd.read_csv(CSV, low_memory=False)
    y = (pd.to_numeric(df["Yield"], errors="coerce") > 0).to_numpy(dtype=int) \
        if args.target == "yieldpos" else df["labels"].to_numpy(dtype=int)
    static = build_static(df)
    fsets = list(FEATURE_SETS) if args.features == "all" else [args.features]
    models = ["lr", "hgb"] if args.model == "all" else [args.model]
    iters = parse_iteration(args.iteration)

    runs = {}
    for model in models:
        for fset in fsets:
            rid = (f"{args.target}|it{args.iteration}|{model}|{fset}"
                   f"|cal{args.calib_split}|sc{args.scale}")
            print(f"[run] {rid} ({len(iters)} iteration × 4 split)", flush=True)
            res = evaluate(df, y, static, fset, model,
                           iters, args.calib_split, args.calib_frac, args.no_jnj_train,
                           scale=(args.scale == "std"))
            runs[rid] = {"target": args.target, "iteration": args.iteration, "features": fset,
                         "blocks": FEATURE_SETS[fset],
                         "model": model, "calib_split": args.calib_split,
                         "calib_frac": args.calib_frac, "scale": args.scale,
                         "no_jnj_train": bool(args.no_jnj_train), "result": res}
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            payload = {"meta": {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "csv": str(CSV), "seed": SEED,
                                "n_rows": int(len(df)),
                                "split_rule": "iteration_k train_test（原论文 4 split/iteration，"
                                              "每 split 留出 3 个 DRFP KMeans cluster）",
                                "label_rule": {"labels": "原论文二分类标签列 labels",
                                               "yieldpos": "Yield>0"},
                                "calib_rule": {
                                    "none": "base 用全部 train 训练，不校准",
                                    "cluster": f"train 内部按 cluster 整簇留出 "
                                               f"{args.calib_frac:.0%} 作校准集（只用它拟合校准器）",
                                    "random": f"train 内部分层随机留出 {args.calib_frac:.0%} 作校准集"},
                                "failures": dict(FAIL)},
                       "runs": runs}
            Path(args.out).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            print(f"[done] {rid} 累计 {time.time() - t0:.1f}s", flush=True)

    print(f"[failures] {FAIL}", flush=True)
    print(f"[total] {time.time() - t0:.1f}s → {args.out}", flush=True)


if __name__ == "__main__":
    main()

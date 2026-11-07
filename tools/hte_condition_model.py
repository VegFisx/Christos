# -*- coding: utf-8 -*-
r"""第十五轮 / 任务 B：用 HTE 的 459 个同底物对比对，做【条件感知判据】。

要回答的问题：现在条件门控在同底物、不同条件的比较上 AUC = 0.530（等于瞎猜）。
              换成一个从数据里学出来的条件判据，能不能显著 > 0.5？能到多少？

口径（写死，别事后改）：
  数据：HTE Buchwald-Hartwig（Zenodo 19635488）
  评估集：**有对比的底物对**（同一 (Aryl, Amine) 既有 Yield==0 也有 Yield>0 的行）
  成功定义（主口径）：Yield > 0；敏感性另报 Yield >= 10 与 manuscript 的 labels 列
  划分：GroupKFold(5)，**按底物对分组**（同一个底物对的行不跨折 —— 防泄漏）
  指标：**同对内 AUC**
        micro = 把所有 (成功行, 失败行) 比较对汇总后算 AUC（与条件门控 0.530 同口径）
        macro = 每个底物对各自算 AUC 再平均
  对比模型：
    M_gate        现有条件门控 cond_activation('B-H', 条件)（不需要训练；固定启发式）
    M_prior       条件元组 (催化剂, 碱, 溶剂) 的平滑成功率，带逐级回退（可解释、无 ML）
    M_logreg_cond 仅条件 one-hot 的逻辑回归
    M_logreg_all  条件 one-hot + 底物 Morgan 指纹（稀疏）
    M_hgb         条件 one-hot + 底物描述符 的 HistGradientBoosting
  显著性：对底物对做 bootstrap（重采样 2000 次），给出 micro AUC 差值的 95% 区间

用法: python hte_condition_model.py
输出: reports/hte_condition_model.json
"""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core",
           STAGE / "conditions", STAGE / "rules"):
    sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import AllChem, Descriptors  # noqa: E402
from scipy import sparse  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from model import Conditions  # noqa: E402
from smartreact_engine import SmartReactEngine  # noqa: E402

RDLogger.DisableLog("rdApp.*")

CSV = STAGE / "data" / "external" / "bh-hte-ood" / \
    "schwallergroup-bh-hte-ood-a277041" / "data" / "BH_HTE_Curated_Dataset_v20260219.csv"
OUT = STAGE / "reports" / "hte_condition_model.json"
RXN_CLASS = "B-H"
SEED = 20261013
N_BOOT = 2000


# ---------------------------------------------------------------- 指标
def pair_wtl(y_true, y_score, groups):
    """先算【每个底物对】的 (win, tie, loss) 计数。

    这样 bootstrap 只需对"底物对"重采样再把这些计数相加 —— O(对数) 而不是
    O(比较次数)，2000 次重采样也能秒级完成（第一版写成嵌套循环，会慢到不可用）。
    """
    by_group = defaultdict(lambda: ([], []))
    for y, s, g in zip(y_true, y_score, groups):
        by_group[g][0 if y == 1 else 1].append(float(s))
    out = {}
    for g, (succ, fail) in by_group.items():
        if not succ or not fail:
            continue
        w = t = l = 0
        for a in succ:
            for b in fail:
                if a > b:
                    w += 1
                elif a == b:
                    t += 1
                else:
                    l += 1
        out[g] = (w, t, l)
    return out


def micro_auc(per_pair):
    w = sum(v[0] for v in per_pair.values())
    t = sum(v[1] for v in per_pair.values())
    l = sum(v[2] for v in per_pair.values())
    return (w + 0.5 * t) / max(1, w + t + l), (w, t, l)


def macro_auc(per_pair):
    vals = [(v[0] + 0.5 * v[1]) / max(1, v[0] + v[1] + v[2]) for v in per_pair.values()]
    return float(np.mean(vals)) if vals else float("nan")


# ---------------------------------------------------------------- 条件映射
def gate_scores(df, tdef):
    eng = SmartReactEngine(gate_conditions=True)
    out = []
    for _, r in df.iterrows():
        sol = str(r.get("Solvent Name") or "").strip()
        cond = Conditions(solvent=sol if sol else "organic", temperature=tdef,
                          catalyst="metal",
                          reagents=(str(r.get("Base SMILES") or ""),)
                          if r.get("Base SMILES") else ())
        s, _why = eng.cond_activation(RXN_CLASS, cond)
        out.append(s)
    return np.array(out, dtype=float)


# ---------------------------------------------------------------- 条件先验
class ConditionPrior:
    """(催化剂, 碱, 溶剂) 的平滑成功率，逐级回退。样本不足就退到更粗的键。"""

    BACKOFF = (("cat", "base", "solv"), ("cat", "solv"), ("base", "solv"),
               ("cat", "base"), ("cat",), ("base",), ("solv",))

    def __init__(self, alpha: float = 5.0, min_n: int = 5):
        self.alpha = alpha
        self.min_n = min_n
        self.tables = {}

    @staticmethod
    def _keys(row):
        return {
            ("cat",): str(row.get("Catalyst Name") or ""),
            ("base",): str(row.get("Base Name") or ""),
            ("solv",): str(row.get("Solvent Name") or ""),
            ("cat", "base"): (str(row.get("Catalyst Name") or ""),
                              str(row.get("Base Name") or "")),
            ("cat", "solv"): (str(row.get("Catalyst Name") or ""),
                              str(row.get("Solvent Name") or "")),
            ("base", "solv"): (str(row.get("Base Name") or ""),
                               str(row.get("Solvent Name") or "")),
            ("cat", "base", "solv"): (str(row.get("Catalyst Name") or ""),
                                      str(row.get("Base Name") or ""),
                                      str(row.get("Solvent Name") or "")),
        }

    def fit(self, df, y):
        self.global_rate = (y.sum() + self.alpha) / (len(y) + 2 * self.alpha)
        for name in self.BACKOFF:
            tab = defaultdict(lambda: [0, 0])
            for (_, row), yy in zip(df.iterrows(), y):
                k = self._keys(row)[name]
                tab[k][0] += int(yy)
                tab[k][1] += 1
            self.tables[name] = {k: (v[0] + self.alpha) / (v[1] + 2 * self.alpha)
                                 for k, v in tab.items()}
            self.counts = getattr(self, "counts", {})
            self.counts[name] = {k: v[1] for k, v in tab.items()}
        return self

    def predict(self, df):
        out = []
        for _, row in df.iterrows():
            ks = self._keys(row)
            score = self.global_rate
            for name in self.BACKOFF:          # 从粗到细，越细越优先
                k = ks[name]
                if self.counts[name].get(k, 0) >= self.min_n and k in self.tables[name]:
                    score = self.tables[name][k]
            out.append(score)
        return np.array(out, dtype=float)


# ---------------------------------------------------------------- 特征
def condition_onehot(train_df, test_df):
    cols = ["Catalyst Name", "Base Name", "Solvent Name"]
    tr_parts, te_parts = [], []
    for c in cols:
        vals = sorted(train_df[c].fillna("").astype(str).unique())
        idx = {v: i for i, v in enumerate(vals)}
        tr = np.zeros((len(train_df), len(vals)), dtype=np.float32)
        te = np.zeros((len(test_df), len(vals)), dtype=np.float32)
        for i, v in enumerate(train_df[c].fillna("").astype(str)):
            if v in idx:
                tr[i, idx[v]] = 1.0
        for i, v in enumerate(test_df[c].fillna("").astype(str)):
            if v in idx:
                te[i, idx[v]] = 1.0
        tr_parts.append(sparse.csr_matrix(tr))
        te_parts.append(sparse.csr_matrix(te))
    return sparse.hstack(tr_parts).tocsr(), sparse.hstack(te_parts).tocsr()


def morgan(smi: str, n_bits: int = 512):
    m = Chem.MolFromSmiles(str(smi))
    if m is None:
        return np.zeros(n_bits, dtype=np.float32)
    fp = AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=n_bits)
    return np.asarray(fp, dtype=np.float32)


def substrate_desc(smi: str):
    m = Chem.MolFromSmiles(str(smi))
    if m is None:
        return [0.0] * 6
    return [Descriptors.MolWt(m), m.GetNumHeavyAtoms(),
            Descriptors.NumHDonors(m), Descriptors.NumHAcceptors(m),
            Descriptors.FractionCSP3(m), m.GetRingInfo().NumRings()]


def main():
    t0 = time.time()
    df = pd.read_csv(CSV, low_memory=False)
    df["_y"] = pd.to_numeric(df["Yield"], errors="coerce")
    df["_pair"] = df["Aryl SMILES"].astype(str) + " || " + df["Amine SMILES"].astype(str)
    g = df.groupby("_pair")["_y"].agg(["min", "max"]).reset_index()
    contrast = set(g[(g["min"] == 0) & (g["max"] > 0)]["_pair"])
    ev = df[df["_pair"].isin(contrast) & df["_y"].notna()].copy()
    print("=" * 96)
    print(f"HTE 条件感知模型：对比对 {len(contrast)} 个，行 {len(ev):,}"
          f"（成功 {int((ev['_y'] > 0).sum()):,} / 失败 {int((ev['_y'] == 0).sum()):,}）")
    print("=" * 96, flush=True)

    tdef = float(((SmartReactEngine(gate_conditions=True)
                   .cond_table.get(RXN_CLASS) or {}).get("temp_C") or {}).get("default") or 100.0)

    results = {}
    for label_name, ycol in (("yield_gt_0", (ev["_y"] > 0).astype(int)),
                             ("yield_ge_10", (ev["_y"] >= 10).astype(int))):
        y_all = ycol.values
        groups = ev["_pair"].values
        # —— M_gate（固定启发式，不需训练）——
        gs = gate_scores(ev, tdef)
        gate_wtl = pair_wtl(y_all, gs, groups)
        gate_micro, gate_counts = micro_auc(gate_wtl)
        gate_macro = macro_auc(gate_wtl)

        # —— 分组交叉验证 ——
        gkf = GroupKFold(n_splits=5)
        scores = {m: np.zeros(len(ev)) for m in
                  ("prior", "logreg_cond", "logreg_all", "hgb")}
        for fold, (tr_idx, te_idx) in enumerate(gkf.split(ev, y_all, groups)):
            tr, te = ev.iloc[tr_idx], ev.iloc[te_idx]
            ytr, yte = y_all[tr_idx], y_all[te_idx]
            if len(set(ytr)) < 2:
                continue
            def norm(v):
                v = np.asarray(v, dtype=float)
                return v
            pr = ConditionPrior().fit(tr, ytr)
            scores["prior"][te_idx] = norm(pr.predict(te))
            Xtr, Xte = condition_onehot(tr, te)
            lr = LogisticRegression(max_iter=2000, C=1.0)
            lr.fit(Xtr, ytr)
            scores["logreg_cond"][te_idx] = lr.predict_proba(Xte)[:, 1]
            sub_tr = sparse.csr_matrix(np.vstack([
                np.concatenate([morgan(a), morgan(b)]) for a, b in
                zip(tr["Aryl SMILES"], tr["Amine SMILES"])]))
            sub_te = sparse.csr_matrix(np.vstack([
                np.concatenate([morgan(a), morgan(b)]) for a, b in
                zip(te["Aryl SMILES"], te["Amine SMILES"])]))
            Xtr2 = sparse.hstack([Xtr, sub_tr]).tocsr()
            Xte2 = sparse.hstack([Xte, sub_te]).tocsr()
            lr2 = LogisticRegression(max_iter=2000, C=1.0)
            lr2.fit(Xtr2, ytr)
            scores["logreg_all"][te_idx] = lr2.predict_proba(Xte2)[:, 1]
            d_tr = np.array([substrate_desc(a) + substrate_desc(b) for a, b in
                             zip(tr["Aryl SMILES"], tr["Amine SMILES"])], dtype=np.float32)
            d_te = np.array([substrate_desc(a) + substrate_desc(b) for a, b in
                             zip(te["Aryl SMILES"], te["Amine SMILES"])], dtype=np.float32)
            Xtr3 = sparse.hstack([Xtr, sparse.csr_matrix(d_tr)]).tocsr()
            Xte3 = sparse.hstack([Xte, sparse.csr_matrix(d_te)]).tocsr()
            hgb = HistGradientBoostingClassifier(max_iter=200, random_state=SEED)
            hgb.fit(Xtr3.toarray(), ytr)
            scores["hgb"][te_idx] = hgb.predict_proba(Xte3.toarray())[:, 1]

        res = {"gate": {"micro": gate_micro, "macro": gate_macro,
                        "comparisons": sum(sum(x) for x in gate_wtl.values())}}
        for m, s in scores.items():
            wtl = pair_wtl(y_all, s, groups)
            mm, mc = micro_auc(wtl)
            res[m] = {"micro": mm, "macro": macro_auc(wtl),
                      "comparisons": sum(sum(x) for x in wtl.values())}
        results[label_name] = res
        print(f"\n[{label_name}] 成功定义下（同对内 AUC）：")
        for m, r in res.items():
            print(f"  {m:<14} micro {r['micro']:.3f}   macro {r['macro']:.3f}"
                  f"   （{r['comparisons']:,} 次比较）", flush=True)

    # —— 显著性：以 yield>0 主口径，对底物对 bootstrap 比较最佳模型 vs gate ——
    y_all = (ev["_y"] > 0).astype(int).values
    groups = ev["_pair"].values
    gs = gate_scores(ev, tdef)
    best_name = max(("prior", "logreg_cond", "logreg_all", "hgb"),
                    key=lambda m: results["yield_gt_0"][m]["micro"])
    # 重训最佳模型（全评估集上的 CV 分数已存，这里复用同样流程取分数）
    best_scores = np.zeros(len(ev))
    gkf = GroupKFold(n_splits=5)
    for tr_idx, te_idx in gkf.split(ev, y_all, groups):
        tr, te = ev.iloc[tr_idx], ev.iloc[te_idx]
        ytr = y_all[tr_idx]
        if len(set(ytr)) < 2:
            continue
        if best_name == "prior":
            best_scores[te_idx] = ConditionPrior().fit(tr, ytr).predict(te)
        elif best_name == "logreg_cond":
            Xtr, Xte = condition_onehot(tr, te)
            best_scores[te_idx] = LogisticRegression(max_iter=2000).fit(
                Xtr, ytr).predict_proba(Xte)[:, 1]
        elif best_name == "logreg_all":
            Xtr, Xte = condition_onehot(tr, te)
            str_ = sparse.csr_matrix(np.vstack([
                np.concatenate([morgan(a), morgan(b)]) for a, b in
                zip(tr["Aryl SMILES"], tr["Amine SMILES"])]))
            ste_ = sparse.csr_matrix(np.vstack([
                np.concatenate([morgan(a), morgan(b)]) for a, b in
                zip(te["Aryl SMILES"], te["Amine SMILES"])]))
            Xtr = sparse.hstack([Xtr, str_]).tocsr()
            Xte = sparse.hstack([Xte, ste_]).tocsr()
            best_scores[te_idx] = LogisticRegression(max_iter=2000).fit(
                Xtr, ytr).predict_proba(Xte)[:, 1]
        else:
            Xtr, Xte = condition_onehot(tr, te)
            d_tr = np.array([substrate_desc(a) + substrate_desc(b) for a, b in
                             zip(tr["Aryl SMILES"], tr["Amine SMILES"])], dtype=np.float32)
            d_te = np.array([substrate_desc(a) + substrate_desc(b) for a, b in
                             zip(te["Aryl SMILES"], te["Amine SMILES"])], dtype=np.float32)
            Xtr = sparse.hstack([Xtr, sparse.csr_matrix(d_tr)]).tocsr()
            Xte = sparse.hstack([Xte, sparse.csr_matrix(d_te)]).tocsr()
            best_scores[te_idx] = HistGradientBoostingClassifier(
                max_iter=200, random_state=SEED).fit(
                Xtr.toarray(), ytr).predict_proba(Xte.toarray())[:, 1]

    rng = np.random.default_rng(SEED)
    pairs = np.array(sorted(set(groups)))
    # ★ 配对 bootstrap：同一批重采样的底物对同时用于两个模型，只累加各自的 (w,t,l) 计数 ★
    best_wtl = pair_wtl(y_all, best_scores, groups)
    gate_wtl = pair_wtl(y_all, gs, groups)
    idx_of = {p: i for i, p in enumerate(pairs)}
    diff_arr = np.zeros((N_BOOT, 3))          # (best_w, best_t, best_l)
    gate_arr = np.zeros((N_BOOT, 3))
    for b in range(N_BOOT):
        pick = rng.choice(pairs, size=len(pairs), replace=True)
        bw = bt = bl = gw = gt = gl = 0
        for p in pick:
            w1, t1, l1 = best_wtl.get(p, (0, 0, 0))
            w2, t2, l2 = gate_wtl.get(p, (0, 0, 0))
            bw += w1; bt += t1; bl += l1
            gw += w2; gt += t2; gl += l2
        diff_arr[b] = (bw, bt, bl)
        gate_arr[b] = (gw, gt, gl)
    best_auc = (diff_arr[:, 0] + 0.5 * diff_arr[:, 1]) / np.maximum(
        1, diff_arr.sum(axis=1))
    gate_auc = (gate_arr[:, 0] + 0.5 * gate_arr[:, 1]) / np.maximum(
        1, gate_arr.sum(axis=1))
    diffs = best_auc - gate_auc
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    print()
    print("=" * 96)
    print(f"显著性：最佳模型 = {best_name}；对 {len(pairs)} 个底物对做 {N_BOOT} 次 bootstrap")
    print(f"  micro AUC 差值（最佳 - 现有门控）95% 区间 = [{lo:+.3f}, {hi:+.3f}]"
          f"  中位 {np.median(diffs):+.3f}")
    print(f"  区间下界 > 0 ? {'是（显著优于现有门控）' if lo > 0 else '否'}"
          f"   |  区间下界 > -0.03 ? {'是' if lo > -0.03 else '否'}")
    print("=" * 96)

    payload = {"scratch": "HTE 条件感知判据（分组 CV + 同对内 AUC）",
               "data": {"contrast_pairs": len(contrast), "rows": int(len(ev)),
                        "assumed_temperature_C": tdef,
                        "success_definitions": ["Yield>0", "Yield>=10"]},
               "results": results,
               "best_model": best_name,
               "bootstrap_diff_vs_gate": {"n_boot": N_BOOT, "pairs": int(len(pairs)),
                                          "ci95": [float(lo), float(hi)],
                                          "median": float(np.median(diffs))},
               "seconds": round(time.time() - t0, 1)}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"结果 -> {OUT.name}  总耗时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

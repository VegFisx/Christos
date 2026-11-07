# -*- coding: utf-8 -*-
r"""② 条件可行性模型（A 方案）：用 HTE 27,497 行学"这套条件在这对底物上会不会成"。

## 目标与口径（先定死）
* **预测目标**：同一条 HTE 记录 -> `y = 1 if Yield >= 0.5 else 0`（与判卷器同一口径）
* **分组**：`(Aryl SMILES, Amine SMILES)` = 一组底物；
  **交叉验证必须按组切**（GroupKFold）——同一对底物的不同条件不能同时出现在训练和验证里，
  否则模型只要记住"这对底物成过"就能作弊（第一版探针就踩过这个泄漏，AUC 虚高到 0.64）
* **特征**（全部来自已有列，不手写化学）：
  - 条件类：solvent / catalyst / base（类别，one-hot）
  - 数值：Additive 那 8 个布尔列
  - 底物类：aryl/amine 的 Morgan 指纹（radius=2, 2048 bit）——**只用训练集**拟合任何东西
* **模型**：HistGradientBoostingClassifier（对标 `hte_absolute_model.py` 的既定做法）+
  逻辑回归作对照
* **验收**：留组 AUC。**必须先跑基线**：规则层（现有 `cond_activation`）在同一划分下的 AUC。
* 输出：`reports/condition_model_result.json`

用法: & $py -u tools\train_condition_model.py [--limit N]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
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

import numpy as np                                     # noqa: E402
from rdkit import Chem, RDLogger, DataStructs          # noqa: E402

RDLogger.DisableLog("rdApp.*")

CSV = (STAGE / "data" / "external" / "bh-hte-ood"
       / "schwallergroup-bh-hte-ood-a277041" / "data"
       / "BH_HTE_Curated_Dataset_v20260219.csv")
OUT = STAGE / "reports" / "condition_model_result.json"
POS = 0.5
ADD_COLS = [f"Additive_{x}" for x in
            ("present", "aromatic_rings", "heteroatom_count", "coordination_flag",
             "steric_bulk_flag", "pi_rich_flag", "Pd_poisoning",
             "competes_with_amine")]


def fp_of(smiles: str, nbits: int = 2048):
    from rdkit.Chem import rdFingerprintGenerator
    m = Chem.MolFromSmiles(smiles or "")
    if m is None:
        return None
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=nbits)
    return gen.GetFingerprint(m)


def load(limit: int):
    rows = []
    with open(CSV, encoding="utf-8", newline="") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if limit and i >= limit:
                break
            try:
                y = float(row.get("Yield") or 0.0)
            except ValueError:
                y = 0.0
            rows.append({
                "group": (str(row.get("Aryl SMILES", "")).strip(),
                          str(row.get("Amine SMILES", "")).strip()),
                "aryl": str(row.get("Aryl SMILES", "")).strip(),
                "amine": str(row.get("Amine SMILES", "")).strip(),
                "solvent": str(row.get("Solvent Name", "")).strip() or "(空)",
                "catalyst": str(row.get("Catalyst Name", "")).strip() or "(空)",
                "base": str(row.get("Base Name", "")).strip() or "(空)",
                "source": str(row.get("Source", "")).strip(),
                "y": 1 if y >= POS else 0,
                "yield": y,
                "add": [float(row.get(c) or 0.0) for c in ADD_COLS],
            })
    return rows


def build_matrix(rows, use_fp=True, nbits=2048):
    """类别 one-hot + 数值 + 指纹（指纹按分子缓存，避免重复计算）。"""
    cats = {"solvent": {}, "catalyst": {}, "base": {}, "source": {}}
    for r in rows:
        for k in cats:
            cats[k].setdefault(r[k], len(cats[k]))
    # 指纹缓存
    fpc: dict = {}
    def get_fp(sm):
        if sm not in fpc:
            bv = fp_of(sm, nbits)
            fpc[sm] = (np.zeros(nbits, dtype=np.float32) if bv is None
                       else np.array(bv, dtype=np.float32))
        return fpc[sm]

    feats = []
    for r in rows:
        v = []
        for k in ("solvent", "catalyst", "base", "source"):
            one = np.zeros(len(cats[k]), dtype=np.float32)
            one[cats[k][r[k]]] = 1.0
            v.append(one)
        v.append(np.array(r["add"], dtype=np.float32))
        if use_fp:
            v.append(get_fp(r["aryl"]))
            v.append(get_fp(r["amine"]))
        feats.append(np.concatenate(v))
    X = np.vstack(feats)
    y = np.array([r["y"] for r in rows], dtype=np.int32)
    groups = np.array([f"{g[0]}|{g[1]}" for g in (r["group"] for r in rows)])
    return X, y, groups, cats


def rule_baseline_scores(rows):
    """规则层基线：现有 cond_activation 的分数（不含底物特征）。"""
    from model import Conditions
    from smartreact_engine import SmartReactEngine

    def cat_class(name: str) -> str:
        t = str(name or "").lower()
        if not t:
            return "none"
        for k in ("pd", "pt", "ni", "cu", "binap", "xphos", "sphos", "brettphos",
                  "ruphos", "jackiephos", "g3", "g4", "xantphos", "dppf", "bippy"):
            if k in t:
                return "metal"
        for k in ("cs2co3", "k2co3", "k3po4", "kotbu", "naotbu", "dbu", "mtbd",
                  "et3n", "dipea", "tmg", "btmg", "nah", "lda"):
            if k in t:
                return "base"
        return "other"

    eng = SmartReactEngine()
    out = np.zeros(len(rows), dtype=np.float32)
    for i, r in enumerate(rows):
        cond = Conditions(solvent=r["solvent"].lower(), temperature=100.0,
                          time_min=60.0, pH=7.0, catalyst=cat_class(r["catalyst"]),
                          atmosphere="air",
                          reagents=(r["catalyst"], r["base"]))
        s, _why = eng.cond_activation("B-H", cond)
        out[i] = float(s)
    return out


def group_cv_auc(make_model, X, y, groups, n_splits=5):
    """按组切分的交叉验证 AUC（返回 oof 预测与 AUC）。"""
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold

    gkf = GroupKFold(n_splits=n_splits)
    oof = np.zeros(len(y), dtype=np.float64)
    for tr, te in gkf.split(X, y, groups):
        # 组不能跨折：GroupKFold 已保证
        m = make_model()
        m.fit(X[tr], y[tr])
        if hasattr(m, "predict_proba"):
            oof[te] = m.predict_proba(X[te])[:, 1]
        else:
            oof[te] = m.decision_function(X[te])
    return oof, roc_auc_score(y, oof)


def unseen_pair_auc(make_model, X, y, pair_ids, n_splits=5):
    """★ 更严的口径：**按底物对整体留出**（GroupShuffleSplit）——
    训练集里完全没有这些底物对，考"换个新底物还能不能判"。"""
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupShuffleSplit

    gss = GroupShuffleSplit(n_splits=n_splits, test_size=0.25, random_state=20261013)
    aucs = []
    for tr, te in gss.split(X, y, pair_ids):
        m = make_model()
        m.fit(X[tr], y[tr])
        p = (m.predict_proba(X[te])[:, 1] if hasattr(m, "predict_proba")
             else m.decision_function(X[te]))
        aucs.append(roc_auc_score(y[te], p))
    return float(np.mean(aucs)), float(np.std(aucs))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = 全量 27,497")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--no-fp", action="store_true", help="不用指纹（只看条件特征）")
    a = ap.parse_args()

    t0 = time.time()
    rows = load(a.limit)
    n_groups = len({r["group"] for r in rows})
    print(f"载入 {len(rows):,} 行 / {n_groups:,} 组底物；正例率 "
          f"{sum(r['y'] for r in rows)/len(rows):.1%}")

    # ---- 基线 1：规则层 ----
    base = rule_baseline_scores(rows)
    from sklearn.metrics import roc_auc_score
    auc_rule = roc_auc_score([r["y"] for r in rows], base)
    print(f"① 规则层基线（现有 cond_activation）：AUC {auc_rule:.4f}")

    # ---- 基线 2：只猜常数 ----
    print(f"② 常数基线（全猜多数类）：AUC 0.5000（定义）")

    # ---- 模型 ----
    X, y, groups, cats = build_matrix(rows, use_fp=not a.no_fp)
    print(f"特征矩阵 {X.shape}（类别维度 "
          f"{ {k: len(v) for k, v in cats.items()} }）")

    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    res = {}
    oof, auc_gbm = group_cv_auc(
        lambda: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08,
                                               max_depth=None, random_state=20261013),
        X, y, groups)
    res["gbm_seen_pair_new_condition"] = round(float(auc_gbm), 4)
    print(f"③ HistGradientBoosting（同底物对新条件，按组 5 折）：AUC {auc_gbm:.4f}")

    # ★ 更严：底物对整体留出（训练集里没有这些底物对）
    pair_ids = np.array([f"{r['aryl']}|{r['amine']}" for r in rows])
    auc_up, sd_up = unseen_pair_auc(
        lambda: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08,
                                               random_state=20261013),
        X, y, pair_ids)
    res["gbm_unseen_pair"] = round(auc_up, 4)
    print(f"③b 同一模型 / **换底物对**（GroupShuffleSplit 5 折）："
          f"AUC {auc_up:.4f} ± {sd_up:.4f}")

    def lr():
        sc = StandardScaler(with_mean=False)
        return __import__("sklearn.pipeline", fromlist=["Pipeline"]).Pipeline(
            [("sc", sc), ("lr", LogisticRegression(max_iter=2000, C=0.5))])
    _, auc_lr = group_cv_auc(lr, X, y, groups)
    res["logreg_seen_pair_new_condition"] = round(float(auc_lr), 4)
    print(f"④ 逻辑回归（对照，同底物对新条件）：AUC {auc_lr:.4f}")

    payload = {
        "what": "条件可行性模型（HTE 27,497 行；按底物对分组交叉验证）",
        "caveat": [
            "① 只在 Buchwald-Hartwig 型偶联上训练/评估，不能直接外推到别的反应类",
            "② 温度列缺失，未作为特征使用（HTE 的 CSV 无逐行温度）",
            "③ 交叉验证按 (aryl,amine) 分组，避免同底物泄漏",
            "④ 目标是『这套条件下会不会有产物』，不是产率回归，也不是产物排序",
        ],
        "data": {"csv": CSV.name, "n_rows": len(rows), "n_groups": n_groups,
                 "pos_rate": round(sum(r["y"] for r in rows) / len(rows), 4)},
        "auc": {"rule_layer_baseline": round(float(auc_rule), 4),
                "chance": 0.5, **res},
        "features": {"n_dims": int(X.shape[1]), "use_fingerprint": not a.no_fp,
                     "category_sizes": {k: len(v) for k, v in cats.items()}},
        "seconds": round(time.time() - t0, 1),
    }
    Path(a.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"\n小结：规则层 {auc_rule:.4f} / GBM 同底物对 {auc_gbm:.4f} / "
          f"GBM 换底物对 {auc_up:.4f} / LR {auc_lr:.4f}")
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

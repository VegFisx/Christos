# -*- coding: utf-8 -*-
r"""③ 的可落地形态：把「会不会发生」做成**带「不确定」的判决器**（拒识 / abstention）。

## 为什么是这个形态（依据是本轮实测，不是设计偏好）
`tools/summarize_abs_parts.py` 汇总的 40 个 OOD test（10 iteration × 4 split）显示：
  · hgb_F0：AUC 0.820、原始 ECE 0.086
  · **全量硬判精度只有 0.729；只对最有把握的 20% 给判决 → 精度 0.928**（hgb_F1 到 0.960）
所以正确的产品形态不是"每条都给判决"，而是「**高置信度才判，其余输出「不确定」**」。

## 这个脚本做什么
  --fit    用全部 27,497 行训练冻结模型（F0 = NB+SUB+DESC, hgb），
           **并断言我自己的特征构造与 tools/hte_absolute_model.py::build_X 逐元素相等**（防止口径漂移），
           再把模型 + 词表 + 实测运行曲线（覆盖率→精度/召回/阈值）冻结到 models/ 下
  --check  载入冻结件，打印元信息与实测曲线
  --demo   取示例行（Yield==0 与 Yield>=80）展示判决/不确定的实际行为
  --pair   单条判决：给 Aryl/Amine SMILES + 催化剂/碱/溶剂名

## ★ 适用范围（必须跟着产物一起讲清楚）
本判决器训练在 **HTE Buchwald–Hartwig 胺化** 数据上（27,497 行，催化剂/碱/溶剂三档条件）。
**它只在同类反应、同类条件空间内有效**；拿它去判中药煎煮体系（TCMAI 那条线）属于**域外**，不可用。
实现在这里、证据在上面那 40 个 test 里，**不要把它当成通用判据**。

跑法：
  & "D:\TCMAI\venv\Scripts\python.exe" tools\abstain_judge.py --fit
  & ... tools\abstain_judge.py --demo
  & ... tools\abstain_judge.py --pair "Brc1cccnc1" "CC(N)CCc1ccccc1" --catalyst binap-pd-g3 --base DBU --solvent DMSO
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import tempfile
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import pandas as pd
import scipy.sparse as sp

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))

import hte_absolute_model as AM          # noqa: E402  复用它的 build_X / build_static / make_model
from hte_condition_model import morgan, substrate_desc  # noqa: E402  单一真相

MODELS = STAGE / "models"
ART = MODELS / "abstain_judge_bh_F0_hgb.pkl"
META = MODELS / "abstain_judge_bh_F0_hgb_meta.json"
PARTS = Path(os.environ.get("DSHNS_ABS_PARTS")
             or (Path(tempfile.gettempdir()) / "dshns_abs_parts"))
CSV = AM.CSV
CAT_COLS = AM.CAT_COLS
SEED = AM.SEED


# ------------------------------------------------------------------ 特征（F0 = NB + SUB + DESC）
def fit_vocabs(df: pd.DataFrame) -> dict:
    return {c: sorted(df[c].fillna("").astype(str).unique()) for c in CAT_COLS}


def onehot(col: pd.Series, vocab: list) -> sp.csr_matrix:
    idx = {v: i for i, v in enumerate(vocab)}
    codes = np.array([idx.get(v, -1) for v in col.fillna("").astype(str)], dtype=np.int64)
    keep = codes >= 0
    rows = np.nonzero(keep)[0]
    return sp.csr_matrix((np.ones(len(rows), np.float32), (rows, codes[keep])),
                         shape=(len(col), len(vocab)))


def build_f0(df: pd.DataFrame, vocabs: dict) -> sp.csr_matrix:
    nb = sp.hstack([onehot(df[c], vocabs[c]) for c in CAT_COLS]).tocsr()
    sub = np.hstack([np.asarray([morgan(s) for s in df["Aryl SMILES"].astype(str)]),
                     np.asarray([morgan(s) for s in df["Amine SMILES"].astype(str)])])
    desc = np.asarray([substrate_desc(s) + substrate_desc(t)
                       for s, t in zip(df["Aryl SMILES"].astype(str),
                                       df["Amine SMILES"].astype(str))], dtype=np.float32)
    return sp.hstack([nb, sp.csr_matrix(sub.astype(np.float32)), sp.csr_matrix(desc)]).tocsr()


def load_measured_curve():
    """从子代理的 40-split 分片里取实测曲线（覆盖率→精度/召回/阈值）+ pooled 指标。"""
    p = PARTS / "hgb_F0_cal.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    runs = d.get("runs") or {}
    r0 = list(runs.values())[0] if isinstance(runs, dict) else runs[0]
    pooled = (r0.get("result") or {}).get("pooled") or {}
    raw = pooled.get("raw") or {}
    out = {"source": str(p), "metrics": raw.get("metrics"),
           "rejection": raw.get("rejection")}
    per = (r0.get("result") or {}).get("per_split") or []
    aucs = [s["metrics"]["raw"]["roc_auc"] for s in per
            if isinstance(s.get("metrics", {}).get("raw", {}).get("roc_auc"), (int, float))]
    if aucs:
        a = np.asarray(aucs, float)
        out["n_tests"] = int(a.size)
        out["auc_mean"] = float(a.mean())
        out["auc_std"] = float(a.std())
    return out


# ------------------------------------------------------------------ fit
def do_fit():
    MODELS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    df = pd.read_csv(CSV, low_memory=False)
    y = df["labels"].to_numpy()
    print(f"[fit] n={len(df):,}  正例 {int(y.sum()):,} / 负例 {int((1 - y).sum()):,}")

    vocabs = fit_vocabs(df)
    print(f"[fit] 类别词表：{[f'{c}={len(v)}' for c, v in vocabs.items()]}")
    X = build_f0(df, vocabs)
    print(f"[fit] 我的 F0 特征 {X.shape}  nnz={X.nnz:,}")

    # ★ 口径断言：与子代理的实现逐元素相等（防止我这边把特征定义搞漂）
    static = AM.build_static(df)
    allidx = np.arange(len(df))
    X_ref, _ = AM.build_X(df, allidx, allidx, static, "F0")
    same_shape = (X.shape == X_ref.shape)
    d = (X - X_ref)
    max_abs = float(np.max(np.abs(d.data))) if d.nnz else 0.0
    print(f"[fit] 与 hte_absolute_model.build_X 对比：形状相同={same_shape}  "
          f"差异 nnz={d.nnz:,}  最大绝对差={max_abs:.3e}")
    if not (same_shape and max_abs == 0.0):
        print("[fit] ⚠ 特征构造与参考实现不一致 —— 拒绝落盘（口径漂移比没有产物更危险）")
        return 1
    print("[fit] ✅ 特征构造与参考实现逐元素一致")

    model = AM.make_model("hgb")
    model.fit(X.toarray().astype(np.float32), y)
    print(f"[fit] 训练完成（{time.time()-t0:.1f}s）")

    curve = load_measured_curve()
    ART.write_bytes(pickle.dumps({"model": model, "vocabs": vocabs,
                                  "feature_set": "F0 = NB+SUB+DESC",
                                  "cat_cols": CAT_COLS, "seed": SEED}, protocol=4))
    meta = {
        "artifact": str(ART), "model": "HistGradientBoostingClassifier(max_iter=200)",
        "feature_set": "F0 = one-hot(Catalyst/Base/Solvent Name) + Morgan(r2,512)(Aryl)+Morgan(Amine) + substrate_desc(Aryl)+substrate_desc(Amine)",
        "n_train": int(len(df)), "n_pos": int(y.sum()), "seed": SEED,
        "vocab_sizes": {c: len(v) for c, v in vocabs.items()},
        "n_features": int(X.shape[1]),
        "measured_ood": curve,
        "scope_warning": "训练于 HTE Buchwald–Hartwig 胺化（27,497 行）。只在同类反应/条件空间内有效；"
                         "用于中药煎煮体系属域外，不可用。",
        # ★★ 下面两条来自子代理对同一 OOD 切分的复核，会改变适用方式，必须随件：
        "prior_drift_warning": "该 OOD 切分实为 source transfer（it0 fold1 的 test 88% 是 JNJ HTE 2024；"
                               "各 Source 正类率 0.070~0.788）。仅用 train 里该 Source 的正类率这个**无化学捷径**"
                               "就有平均 AUC 0.619±0.084（论文 DRFP 基线 0.666）→ 本模型的**绝对概率含大量先验漂移**，"
                               "不能当纯化学判据；跨来源使用时必须重新校准/重定阈值。",
        "abstention_cost": "覆盖 20% 时精度 0.928，但**只捞到全部正例的 15.3%**（100% 覆盖时 0.669）→ "
                           "高精度低召回，适合排雷/否决，不适合『找全所有能发生的反应』。",
        "calibration_warning": "池化 ECE 从 0.0691 降到 Platt 0.0336，但**逐 split ECE 平均没有改善**"
                               "（−0.0220±0.0097，仅 13/40 变好）→ 校准器不跨 OOD 簇迁移，"
                               "拒识阈值必须随校准后的概率重定。",
        "fit_seconds": round(time.time() - t0, 1),
    }
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[fit] -> {ART.name}  +  {META.name}")
    if curve:
        print(f"[fit] 实测参考（{curve.get('n_tests')} 个 OOD test）："
              f"AUC {curve.get('auc_mean'):.3f}±{curve.get('auc_std'):.3f}；"
              f"ECE {curve.get('metrics', {}).get('ece'):.3f}")
    return 0


# ------------------------------------------------------------------ 判决
def conf_threshold(meta: dict, coverage: float):
    rj = (meta.get("measured_ood") or {}).get("rejection") or []
    for row in rj:
        if abs(float(row.get("coverage", -1)) - coverage) < 1e-9:
            return float(row.get("conf_threshold", 0.5)), row
    return 0.5, None


def judge(model, vocabs, rows: pd.DataFrame, cov: float, meta: dict):
    X = build_f0(rows, vocabs)
    p = model.predict_proba(X.toarray().astype(np.float32))[:, 1]
    thr, row = conf_threshold(meta, cov)
    out = []
    for pi in p:
        conf = max(float(pi), 1 - float(pi))
        if conf < thr:
            dec = "不确定"
        else:
            dec = "会发生" if pi >= 0.5 else "不会发生"
        out.append((float(pi), float(conf), dec))
    return out, thr, row


def do_check():
    if not ART.exists():
        print(f"[check] 冻结件不存在：{ART}（先 --fit）")
        return 1
    meta = json.loads(META.read_text(encoding="utf-8"))
    print("=" * 92)
    print("冻结判决器元信息")
    print("=" * 92)
    for k in ("model", "feature_set", "n_train", "n_pos", "n_features", "vocab_sizes",
              "fit_seconds"):
        print(f"  {k:<14} {meta.get(k)}")
    print()
    for k in ("scope_warning", "prior_drift_warning", "abstention_cost", "calibration_warning"):
        if meta.get(k):
            print(f"  ⚠ {k}: {meta[k]}")
    mo = meta.get("measured_ood") or {}
    if mo:
        print(f"\n  实测 OOD（{mo.get('n_tests')} 个 test，来源 {Path(mo['source']).name}）："
              f"AUC {mo.get('auc_mean'):.3f}±{mo.get('auc_std'):.3f}")
        print("\n  运行曲线（覆盖率 → 保留样本的精度 / 召回 / 置信度阈值）")
        print(f"    {'覆盖':>6} {'精度':>8} {'召回':>8} {'阈值':>8}")
        for r in mo.get("rejection") or []:
            print(f"    {r['coverage']:>6.1f} {r['prec_kept']:>8.3f} {r['rec_kept']:>8.3f} "
                  f"{r['conf_threshold']:>8.4f}")
    return 0


def do_demo(cov: float, n_each: int):
    meta = json.loads(META.read_text(encoding="utf-8"))
    with ART.open("rb") as f:
        art = pickle.load(f)
    df = pd.read_csv(CSV, low_memory=False)
    df["_y"] = pd.to_numeric(df["Yield"], errors="coerce")
    fails = df[df["_y"] == 0].head(n_each)
    works = df[df["_y"] >= 80].sort_values("_y", ascending=False).head(n_each)
    demo = pd.concat([works, fails]).reset_index(drop=True)
    res, thr, row = judge(art["model"], art["vocabs"], demo, cov, meta)
    print("=" * 100)
    print(f"演示：置信度阈值 {thr:.4f}（= 实测「覆盖率 {cov:.0%}」那一档；低于它输出「不确定」）")
    print("=" * 100)
    print(f"{'真实收率':>8} {'p(发生)':>8} {'置信度':>8}  判决        催化剂/碱/溶剂")
    for (pi, conf, dec), (_, r) in zip(res, demo.iterrows()):
        print(f"{r['_y']:>8.1f} {pi:>8.3f} {conf:>8.3f}  {dec:<8} "
              f"{r['Catalyst Name'][:18]}/{r['Base Name'][:10]}/{r['Solvent Name'][:10]}")
    n_dec = sum(1 for _, _, d in res if d != "不确定")
    print(f"\n  示例 {len(res)} 条：给判决 {n_dec} 条、判「不确定」{len(res)-n_dec} 条")
    print("  ★★ 两条必须跟着看的说明：")
    print("     ① 这些示例取自【训练集】(in-sample)，只能看**行为**，不能当性能 —— "
          "性能数字以上面的 40 个 OOD test 为准（覆盖 20% 时精度 0.928）。")
    print("     ② 被给判决的那一档以【负判决】为主（模型对「不会发生」更自信）→ "
          "这个形态更适合当**排雷/否决**，而不是「会发生」的断言。")
    return 0


def do_pair(aryl, amine, catalyst, base, solvent, cov):
    meta = json.loads(META.read_text(encoding="utf-8"))
    with ART.open("rb") as f:
        art = pickle.load(f)
    row = pd.DataFrame([{"Aryl SMILES": aryl, "Amine SMILES": amine,
                         "Catalyst Name": catalyst, "Base Name": base,
                         "Solvent Name": solvent}])
    res, thr, _ = judge(art["model"], art["vocabs"], row, cov, meta)
    pi, conf, dec = res[0]
    print(f"  Aryl={aryl}  Amine={amine}  催化剂={catalyst} 碱={base} 溶剂={solvent}")
    print(f"  p(会发生)={pi:.4f}  置信度={conf:.4f}  阈值(覆盖{cov:.0%})={thr:.4f}")
    print(f"  -> 判决：{dec}")
    return 0


ap = argparse.ArgumentParser()
ap.add_argument("--fit", action="store_true")
ap.add_argument("--check", action="store_true")
ap.add_argument("--demo", action="store_true")
ap.add_argument("--pair", nargs=2, metavar=("ARYL", "AMINE"))
ap.add_argument("--catalyst", default="")
ap.add_argument("--base", default="")
ap.add_argument("--solvent", default="")
ap.add_argument("--coverage", type=float, default=0.2, help="判决覆盖率档位（默认 0.2 = 最有把握的 20%）")
ap.add_argument("--n-each", type=int, default=6)
a = ap.parse_args()

if a.fit:
    sys.exit(do_fit())
if a.check:
    sys.exit(do_check())
if a.demo:
    sys.exit(do_demo(a.coverage, a.n_each))
if a.pair:
    sys.exit(do_pair(a.pair[0], a.pair[1], a.catalyst, a.base, a.solvent, a.coverage))
ap.print_help()

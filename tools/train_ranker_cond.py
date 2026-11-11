# -*- coding: utf-8 -*-
r"""训练「条件感知」候选重排序器，并与旧特征做消融对比。

输入：reports/rank_dataset_cond.jsonl（tools/build_rank_dataset_cond.py 产出）
做法：同一批候选、同一批标签，训两个模型——
  BASE = 9 个原有特征（发射位次、support、activation、extent、curated、伴生、原子数、保留率）
  COND = BASE + 5 个条件特征（温度、log 时长、条件包络 fit、是否水、有无催化剂）
在同一批测试候选上比较 top-1 / top-5 / MRR / AUC。

用法: python tools\train_ranker_cond.py [jsonl] [--out 模型路径]
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(r"D:\ProgramData\DSHNS\chemreact-staging")

BASE = ["rank", "log_sup", "act", "ext", "cur", "byp", "prod_ha", "src_ha", "keep"]
COND = ["t_C", "log_time", "fit", "is_water", "has_cat"]


def featurize(recs, feats):
    import numpy as np
    X = np.zeros((len(recs), len(feats)), dtype="float32")
    for i, r in enumerate(recs):
        rule = r.get("rule") or ""
        for j, f in enumerate(feats):
            if f.startswith("rule:"):
                X[i, j] = 1.0 if rule == f[5:] else 0.0
            elif f == "log_sup":
                v = __import__("math").log1p(max(0, int(r.get("sup") or 0)))
            elif f == "keep":
                v = float(r.get("keep") or 0.0)
            else:
                v = float(r.get(f) or 0.0)
            if not f.startswith("rule:"):
                X[i, j] = v
    return X


def evaluate(model, recs, feats) -> dict:
    """按 rid 分组，模型分高的在前；返回 top-1 / top-5 / MRR / AUC。"""
    import numpy as np
    from sklearn.metrics import roc_auc_score

    X = featurize(recs, feats)
    y = np.array([r["label"] for r in recs], dtype="int8")
    s = model.predict_proba(X)[:, 1]
    groups = defaultdict(list)
    for r, sc in zip(recs, s):
        groups[r["rid"]].append((float(sc), int(r["label"]), int(r["rank"])))
    top1 = top5 = mrr = 0.0
    n = 0
    for rid, items in groups.items():
        items.sort(key=lambda t: (-t[0], t[2]))
        n += 1
        pos = None
        for i, (_sc, lab, _rk) in enumerate(items):
            if lab == 1:
                pos = i
                break
        if pos is None:
            continue
        if pos == 0:
            top1 += 1
        if pos < 5:
            top5 += 1
        mrr += 1.0 / (pos + 1)
    n2 = max(1, n)
    out = {"n_rxn": n, "top1": top1 / n2, "top5": top5 / n2, "mrr": mrr / n2}
    try:
        if 0 < y.sum() < len(y):
            out["auc"] = float(roc_auc_score(y, s))
    except Exception:
        pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", nargs="?", default=str(ROOT / "reports" / "rank_dataset_cond.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "rank_model_cond.pkl"))
    a = ap.parse_args()

    from sklearn.ensemble import HistGradientBoostingClassifier

    recs = []
    with open(a.data, encoding="utf-8") as f:
        for line in f:
            recs.append(json.loads(line))
    tr = [r for r in recs if r["split"] == "train"]
    te = [r for r in recs if r["split"] == "test"]
    print(f"候选 {len(recs)} · 训练 {len(tr)} · 测试 {len(te)} · "
          f"测试反应 {len({r['rid'] for r in te})}")
    if not tr or not te:
        print("训练或测试为空")
        return 1

    import numpy as np
    from collections import Counter
    # ★ 规则族 one-hot 必须保留：旧模型（68.2% 那个）就带 29 个规则族特征，
    #   去掉它们会掉 16 个点，与「条件有没有用」无关。
    _cnt = Counter(r.get("rule") or "" for r in tr)
    TOP_RULES = [k for k, _v in _cnt.most_common(30) if k]
    rules_feats = ["rule:" + k for k in TOP_RULES]
    print(f"规则族特征 {len(TOP_RULES)} 个")

    ytr = np.array([r["label"] for r in tr], dtype="int8")
    results = {}
    models = {}
    for name, feats in (("BASE", BASE + rules_feats),
                        ("COND", BASE + COND + rules_feats)):
        m = HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.08, max_depth=6,
            min_samples_leaf=40, random_state=20261111)
        m.fit(featurize(tr, feats), ytr)
        res = evaluate(m, te, feats)
        results[name] = res
        models[name] = (m, feats)
        print(f"{name}: top-1 {res['top1']:.4f} · top-5 {res['top5']:.4f} · "
              f"MRR {res['mrr']:.4f} · AUC {res.get('auc', float('nan')):.4f}")

    best = "COND" if results["COND"]["top1"] >= results["BASE"]["top1"] else "BASE"
    m, feats = models[best]
    with open(a.out, "wb") as f:
        pickle.dump({"model": m, "features": feats,
                     "meta": {"best": best, "results": results,
                              "source": str(a.data)}}, f)
    print(f"已保存 {a.out}（{best}）")
    print(json.dumps(results, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

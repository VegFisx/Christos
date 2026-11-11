# -*- coding: utf-8 -*-
"""训练「产物级」重排序模型（v2）。

与 v1 的区别：v1 只有 9 个数值特征（发射位置、模板支持、条件量、原子数），
其中产物侧只有重原子数一个量。v2 把**候选产物本身**的结构特征也放进来：
环数、芳环数、立体中心、氢键供体/受体、分子量、碎片数，以及底物侧同一组量
和它们的差。这样模型才可能在同一条规则的多个产物之间做出区分。

输入 reports/rank_dataset_v2.jsonl（由 tools/build_rank_dataset.py 生成，
每行带 sub / smi / rank / label / sup / rule）。
输出 reports/rank_model_v2.pkl。

用法：
  python tools\\train_ranker_v2.py
  python tools\\train_ranker_v2.py --data reports/rank_dataset_v2.jsonl
"""
from __future__ import annotations

import argparse
import io
import json
import pickle
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors  # noqa: E402

RDLogger.DisableLog("rdApp.*")

_DESC_CACHE: dict = {}


def desc(smiles: str) -> list:
    """产物/底物共用的 8 个结构量。"""
    if smiles in _DESC_CACHE:
        return _DESC_CACHE[smiles]
    m = Chem.MolFromSmiles(smiles) if smiles else None
    if m is None:
        out = [0.0] * 8
    else:
        out = [
            float(m.GetNumHeavyAtoms()),
            float(rdMolDescriptors.CalcNumRings(m)),
            float(rdMolDescriptors.CalcNumAromaticRings(m)),
            float(rdMolDescriptors.CalcNumAtomStereoCenters(m)),
            float(rdMolDescriptors.CalcNumHBD(m)),
            float(rdMolDescriptors.CalcNumHBA(m)),
            float(Descriptors.MolWt(m)) / 100.0,
            float(len(smiles.split("."))),
        ]
    _DESC_CACHE[smiles] = out
    return out


NUM = [
    "rank", "log_sup", "act", "ext", "cur", "byp",
    "prod_ha", "src_ha", "keep",
    "p_rings", "p_arom", "p_stereo", "p_hbd", "p_hba", "p_mw", "p_frags",
    "s_rings", "s_arom", "s_stereo", "s_hbd", "s_hba", "s_mw", "s_frags",
    "d_ha", "d_rings", "d_arom", "d_stereo", "d_hbd", "d_hba",
]


def feats(row: dict, top_rules: list) -> list:
    p = desc(row["smi"])
    s = desc(row.get("sub") or "")
    sup = row.get("sup") or 0
    x = [
        float(row.get("rank") or 0),
        float(__import__("math").log1p(sup)),
        float(row.get("act") or 0.0),
        float(row.get("ext") or 0.0),
        float(row.get("cur") or 0),
        float(row.get("byp") or 0),
        float(row.get("prod_ha") or 0),
        float(row.get("src_ha") or 0),
        float(row.get("keep") or 0),
        p[1], p[2], p[3], p[4], p[5], p[6], p[7],
        s[1], s[2], s[3], s[4], s[5], s[6], s[7],
        p[0] - s[0], p[1] - s[1], p[2] - s[2], p[3] - s[3], p[4] - s[4], p[5] - s[5],
    ]
    rid = row.get("rule") or ""
    x.extend(1.0 if rid == r else 0.0 for r in top_rules)
    return x


def load(path: Path):
    rows = []
    for line in io.open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def evaluate(model, rows, top_rules, tag: str) -> dict:
    by: dict = {}
    for r in rows:
        by.setdefault(r["rid"], []).append(r)
    n = hit1 = hit3 = hit5 = 0
    rr = 0.0
    for rid, cand in by.items():
        if not any(c["label"] == 1 for c in cand):
            continue
        n += 1
        X = [feats(c, top_rules) for c in cand]
        pr = model.predict_proba(X)[:, 1]
        order = sorted(range(len(cand)), key=lambda i: (-pr[i], cand[i]["rank"]))
        for k in range(min(5, len(order))):
            if cand[order[k]]["label"] == 1:
                if k == 0:
                    hit1 += 1
                if k < 3:
                    hit3 += 1
                hit5 += 1
                rr += 1.0 / (k + 1)
                break
    out = {
        "tag": tag,
        "n": n,
        "top1": round(hit1 / max(n, 1), 4),
        "top3": round(hit3 / max(n, 1), 4),
        "top5": round(hit5 / max(n, 1), 4),
        "mrr": round(rr / max(n, 1), 4),
    }
    print("  %-10s n=%d top1=%.4f top3=%.4f top5=%.4f mrr=%.4f"
          % (tag, out["n"], out["top1"], out["top3"], out["top5"], out["mrr"]), flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "reports" / "rank_dataset_v2.jsonl"))
    ap.add_argument("--model-out", default=str(ROOT / "reports" / "rank_model_v2.pkl"))
    ap.add_argument("--top-rules", type=int, default=30)
    ap.add_argument("--iters", type=int, default=300)
    a = ap.parse_args()

    from sklearn.ensemble import HistGradientBoostingClassifier

    t0 = time.time()
    rows = load(Path(a.data))
    print("载入 %d 候选 / %s" % (len(rows), a.data), flush=True)

    cnt = Counter(r.get("rule") or "" for r in rows)
    top_rules = [r for r, _ in cnt.most_common(a.top_rules)]

    # 基线模型（v1）在同一批测试行上重算，保证同口径可比
    base_path = ROOT / "reports" / "rank_model_20261107.pkl"
    base_model = None
    base_feats = None
    if base_path.exists():
        obj = pickle.load(io.open(base_path, "rb"))
        base_model = obj.get("model") if isinstance(obj, dict) else obj
        base_feats = obj.get("features") if isinstance(obj, dict) else None

    tr = [r for r in rows if r.get("split") == "train"]
    te = [r for r in rows if r.get("split") != "train"]
    print("训练 %d / 测试 %d 候选；规则 %d 个" % (len(tr), len(te), len(top_rules)), flush=True)

    X = [feats(r, top_rules) for r in tr]
    y = [1 if r["label"] == 1 else 0 for r in tr]
    clf = HistGradientBoostingClassifier(max_iter=a.iters, learning_rate=0.06,
                                         max_leaf_nodes=31, random_state=0)
    clf.fit(X, y)
    print("训练完成 %.0f s，特征 %d 维" % (time.time() - t0, len(X[0])), flush=True)

    res = [evaluate(clf, te, top_rules, "v2")]

    if base_model is not None and base_feats:
        class _Wrap:
            def __init__(self, m, names):
                self.m, self.names = m, names

            def predict_proba(self, Xs):
                import numpy as np
                idx = [i for i, n in enumerate(top_rules)]
                arr = []
                for x in Xs:
                    # v2 里 NUM 的顺序是固定的，基线特征按名字取
                    d = dict(zip(NUM, x[: len(NUM)]))
                    d["log1p_sup"] = d["log_sup"]
                    d["prod_ha"] = d["prod_ha"]
                    d["src_ha"] = d["src_ha"]
                    row = []
                    for name in self.names:
                        if name.startswith("rule:"):
                            row.append(x[len(NUM) + top_rules.index(name[5:])]
                                       if name[5:] in top_rules else 0.0)
                        elif name == "log_sup":
                            row.append(d["log_sup"])
                        else:
                            row.append(d.get(name, 0.0))
                    arr.append(row)
                return np.asarray(self.m.predict_proba(np.asarray(arr, dtype="float32")))

        try:
            res.append(evaluate(_Wrap(base_model, base_feats), te, top_rules, "v1(base)"))
        except Exception as exc:  # 基线算不出来不影响主结果
            print("  [warn] 基线 v1 无法在新数据上重算：%s" % exc, flush=True)

    pickle.dump({
        "model": clf,
        "features": NUM + ["rule:" + r for r in top_rules],
        "top_rules": top_rules,
        "metrics": res,
        "n_train": len(tr),
        "n_test": len(te),
    }, io.open(a.model_out, "wb"))
    print("写出 %s（%.0f s）" % (a.model_out, time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

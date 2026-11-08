#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重排序器的稳健性：按反应类别做「类别不交叉」评估，并做特征消融。

- 类别映射：从 reports/paper/data/uspto50k_canon.jsonl 取 product→class（同一产物取首次出现的类别）。
- 两种划分：随机一半（同分布）/ 类别 1-5 训练、6-10 测试（类别不交叉）。
- 消融：去掉 rank 特征，看提升是否只来自「发射序本来就是对的那些」。

用法：
    python -I tools/train_ranker_robust.py --data reports/rank_dataset_20261107.jsonl \\
        --out reports/rank_experiment_robust_20261107.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
REACT_BASE = ["rank", "log_sup", "act", "eng", "ext", "cur", "byp", "prod_ha", "src_ha", "keep"]


def load_class_map() -> dict:
    m = {}
    p = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
    with p.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            prod = d.get("product") or ""
            cls = d.get("class")
            if prod and cls is not None and prod not in m:
                m[prod] = int(cls)
    return m


def featurise(rows, top_rules, drop_rank=False):
    out = []
    for r in rows:
        v = [
            float(r["rank"]),
            math.log1p(float(r["sup"])),
            float(r["act"]),
            float(r["eng"]),
            float(r["ext"]),
            float(r["cur"]),
            float(r["byp"]),
            float(r["prod_ha"]),
            float(r["src_ha"]),
            float(r["keep"]),
        ]
        if drop_rank:
            v[0] = 0.0
        for k in top_rules:
            v.append(1.0 if r["rule"] == k else 0.0)
        out.append(v)
    return out


def evaluate(groups):
    n = len(groups)
    top1 = top5 = hit_any = 0
    mrr = 0.0
    for items in groups.values():
        items = sorted(items, key=lambda t: t[1])
        labels = [lab for lab, _ in items]
        if 1 not in labels:
            continue
        hit_any += 1
        pos = labels.index(1) + 1
        if pos == 1:
            top1 += 1
        if pos <= 5:
            top5 += 1
        mrr += 1.0 / pos
    return {
        "n": n,
        "recall_any": round(hit_any / max(1, n), 4),
        "top1": round(top1 / max(1, n), 4),
        "top5": round(top5 / max(1, n), 4),
        "mrr": round(mrr / max(1, n), 4),
    }


def run_one(rows, top_rules, label, drop_rank=False):
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier

    tr = [r for r in rows if r["_tr"]]
    te = [r for r in rows if not r["_tr"]]
    Xtr = featurise(tr, top_rules, drop_rank)
    Xte = featurise(te, top_rules, drop_rank)
    ytr = [r["label"] for r in tr]
    clf = HistGradientBoostingClassifier(
        max_iter=120, learning_rate=0.1, early_stopping=True,
        validation_fraction=0.1, random_state=20261107)
    clf.fit(np.asarray(Xtr, dtype=float), np.asarray(ytr, dtype=int))
    proba = clf.predict_proba(np.asarray(Xte, dtype=float))[:, 1]

    g_learn, g_base = defaultdict(list), defaultdict(list)
    for r, p in zip(te, proba):
        g_learn[r["rid"]].append((r["label"], -float(p)))
        g_base[r["rid"]].append((r["label"], float(r["rank"])))
    base = evaluate(g_base)
    learn = evaluate(g_learn)
    print("  %-28s base top1=%.4f  learned top1=%.4f  top5=%.4f  mrr=%.4f  (n=%d)"
          % (label, base["top1"], learn["top1"], learn["top5"], learn["mrr"], base["n"]))
    return {"label": label, "baseline": base, "learned": learn,
            "delta_top1": round(learn["top1"] - base["top1"], 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "reports" / "rank_dataset_20261107.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "rank_experiment_robust_20261107.json"))
    ap.add_argument("--top-rules", type=int, default=20)
    a = ap.parse_args()

    from collections import Counter
    rows = [json.loads(l) for l in Path(a.data).open(encoding="utf-8")]
    cls_map = load_class_map()
    print("类别映射 %d 个产物" % len(cls_map))
    unknown = 0
    for r in rows:
        c = cls_map.get(r["want"])
        if c is None:
            unknown += 1
        r["_cls"] = c
    print("候选行 %d，找不到类别的 %d 行" % (len(rows), unknown))

    cnt = Counter(r["rule"] for r in rows)
    top_rules = [k for k, _ in cnt.most_common(a.top_rules)]

    results = []

    # ① 随机一半（与 train_ranker.py 同口径，用 split 字段）
    for r in rows:
        r["_tr"] = r["split"] == "train"
    results.append(run_one(rows, top_rules, "random-half"))

    # ② 类别不交叉：1-5 训练，6-10 测试
    for r in rows:
        c = r.get("_cls")
        r["_tr"] = (c is not None and c <= 5)
    sub = [r for r in rows if r.get("_cls") is not None]
    results.append(run_one(sub, top_rules, "class-disjoint(1-5 -> 6-10)"))

    # ③ 随机一半，但不给 rank 特征
    for r in rows:
        r["_tr"] = r["split"] == "train"
    results.append(run_one(rows, top_rules, "random-half, no rank feature", drop_rank=True))

    out = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "data": str(a.data),
        "n_rows": len(rows),
        "results": results,
        "caveat": "标签=候选是否等于真产物；训练不使用真产物做特征；随机半切分属同分布评估，"
                  "类别不交叉那一组才是泛化证据。",
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("写出 %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

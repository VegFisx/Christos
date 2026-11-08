#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""学习型重排序器：在候选集合内部按特征重排，评估 top-1 / top-5 / MRR。

训练/测试按**反应**哈希切分（同反应的候选不会跨侧），避免泄漏。

用法：
    python -I tools\\train_ranker.py --data reports/rank_dataset_20261107.jsonl \\
        --out reports/rank_experiment_20261107.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
# ★ 第129轮：去掉 "eng"（= Product.score）。生产基准路径不跑 scorer 时它恒为 0，
#   训练/推理口径不一致会让模型在真实 CLI 上掉点。只保留两条路径都能算出的特征。
NUM = ["rank", "log_sup", "act", "ext", "cur", "byp", "prod_ha", "src_ha", "keep"]


def load(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _load_curated_ids():
    try:
        d = json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))
        return {r.get("id") for r in (d.get("rules") or []) if r.get("id")}
    except Exception:
        return set()


def to_features(rows, top_rules):
    out = []
    for r in rows:
        v = [
            float(r["rank"]),
            math.log1p(float(r["sup"])),
            float(r["act"]),
            float(r["ext"]),
            float(r["cur"]),
            float(r["byp"]),
            float(r["prod_ha"]),
            float(r["src_ha"]),
            float(r["keep"]),
        ]
        rule = r["rule"]
        for k in top_rules:
            v.append(1.0 if rule == k else 0.0)
        out.append(v)
    return out


def metrics(groups, order_key):
    """groups: {rid: [(label, key), ...]}；order_key 越小越靠前。"""
    top1 = top5 = n = hit_any = 0
    mrr = 0.0
    ranks = []
    for rid, items in groups.items():
        n += 1
        items = sorted(items, key=order_key)
        labels = [lab for lab, _ in items]
        if 1 not in labels:
            continue
        hit_any += 1
        pos = labels.index(1) + 1
        ranks.append(pos)
        if pos == 1:
            top1 += 1
        if pos <= 5:
            top5 += 1
        mrr += 1.0 / pos
    return {
        "n_reactions": n,
        "n_with_hit": hit_any,
        "recall_any": round(hit_any / max(1, n), 4),
        "top1": round(top1 / max(1, n), 4),
        "top5": round(top5 / max(1, n), 4),
        "mrr": round(mrr / max(1, n), 4),
        "hit_rank_median": sorted(ranks)[len(ranks) // 2] if ranks else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "reports" / "rank_dataset_20261107.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "rank_experiment_20261107.json"))
    ap.add_argument("--top-rules", type=int, default=20)
    ap.add_argument("--max-iter", type=int, default=120)
    ap.add_argument("--model-out", default=str(ROOT / "reports" / "rank_model_20261107.pkl"))
    a = ap.parse_args()

    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier

    rows = load(Path(a.data))
    print("候选行 %d" % len(rows))

    cnt = Counter(r["rule"] for r in rows)
    top_rules = [k for k, _ in cnt.most_common(a.top_rules)]
    print("规则 top%d：%s" % (a.top_rules, ", ".join(top_rules[:8])))

    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    print("train 行 %d / test 行 %d" % (len(train), len(test)))

    Xtr = to_features(train, top_rules)
    ytr = [r["label"] for r in train]
    Xte = to_features(test, top_rules)

    clf = HistGradientBoostingClassifier(
        max_iter=a.max_iter, learning_rate=0.1, max_depth=None,
        early_stopping=True, validation_fraction=0.1, random_state=20261107,
    )
    clf.fit(np.asarray(Xtr, dtype=float), np.asarray(ytr, dtype=int))
    proba = clf.predict_proba(np.asarray(Xte, dtype=float))[:, 1]

    groups_learn = defaultdict(list)
    groups_base = defaultdict(list)
    for r, p in zip(test, proba):
        groups_learn[r["rid"]].append((r["label"], -float(p)))
        groups_base[r["rid"]].append((r["label"], float(r["rank"])))

    base = metrics(groups_base, order_key=lambda t: t[1])
    learn = metrics(groups_learn, order_key=lambda t: t[1])
    print("基线（发射序）：", base)
    print("学习型重排：  ", learn)

    n_test = len({r["rid"] for r in test})
    res = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "data": str(a.data),
        "n_rows": len(rows),
        "n_train_rows": len(train),
        "n_test_rows": len(test),
        "n_test_reactions": n_test,
        "top_rules": top_rules,
        "baseline_emission_order": base,
        "learned_rerank": learn,
        "delta": {
            k: round(learn[k] - base[k], 4)
            for k in ("top1", "top5", "mrr")
        },
        "model": "HistGradientBoostingClassifier(max_iter=%d)" % a.max_iter,
        "caveat": "训练与测试按反应哈希对半切分；特征只来自候选与模板，不含真产物；"
                  "同一 50k 数据集内部切分，属同分布评估。",
    }
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("写出 %s" % a.out)

    # 训练好的模型 + 特征顺序 + 规则表，供 core/rerank.py 在生产路径里加载
    import pickle
    model_path = Path(a.model_out)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    blob = {
        "model": clf,
        "features": list(NUM) + ["rule:%s" % r for r in top_rules],
        "top_rules": top_rules,
        "curated_ids": sorted(_load_curated_ids()),
        "meta": {
            "trained_at": res["generated_at"],
            "data": str(a.data),
            "n_train_rows": len(train),
            "n_test_rows": len(test),
            "baseline_top1": base["top1"],
            "learned_top1": learn["top1"],
            "caveat": res["caveat"],
        },
    }
    with model_path.open("wb") as f:
        pickle.dump(blob, f, protocol=4)
    print("写出 %s（%.1f KB）" % (model_path, model_path.stat().st_size / 1024.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

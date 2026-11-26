# -*- coding: utf-8 -*-
"""所有重排序模型的契约测试。

每个 reports/rank_model*.pkl 必须满足：
  A 能加载，且加载自检通过（特征名单长度 == 模型 n_features_in_）
  B 用生产特征函数能打出有限分数（无 NaN/Inf）
  C 重排只改顺序，不改候选集合
  D blend_hitrate > 0 的模型必须带模板统计

另做一次「坏模型」对照：故意截短特征名单，加载必须被拒绝（ok=False），
不能静默退回发射序。

用法：python tools\\test_model_contracts.py
"""
from __future__ import annotations

import pickle
import sys
import tempfile
import types
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

import rerank as RR  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print("  %s %s %s" % ("[ok] " if ok else "[FAIL]", name, detail))
    if not ok:
        fails.append(name)


def _prod(smi, tpl):
    return types.SimpleNamespace(
        smiles=smi, template_smarts=tpl, rule_id="r1",
        source_smiles="CCC", partner_smiles="", activation=1.0,
        is_byproduct=False, score=0.0)


def _cond():
    return types.SimpleNamespace(
        temperature=100.0, time_min=60.0, pH=7.0, pressure_atm=1.0,
        concentration_M=0.1, solvent="water", catalyst="", atmosphere="air")


def _eng():
    return types.SimpleNamespace(cond_table={}, curated_cond_table={},
                                 mined_top_cond_table={})


def main() -> int:
    models = sorted((ROOT / "reports").glob("rank_model*.pkl"))
    if not models:
        print("[FAIL] reports/rank_model*.pkl 一个都没有")
        return 1
    print("检查 %d 个模型" % len(models))

    for p in models:
        print("\n== %s" % p.name)
        r = RR.Reranker(str(p))
        check("加载 + 自检", r.ok)
        n_model = getattr(r.model, "n_features_in_", None)
        check("特征名单 == 模型维数",
              n_model is not None and len(r.features) == int(n_model),
              "%s vs %s" % (len(r.features), n_model))
        if not r.ok:
            continue
        prods = [_prod("CCO", "TPL_A"), _prod("CCN", "TPL_B"), _prod("CCCl", "TPL_A")]
        feats = r._features_of(prods, _eng(), _cond())
        check("特征行长度一致", all(len(x) == len(r.features) for x in feats))
        proba = r.model.predict_proba(feats)[:, 1]
        check("分数有限", bool(np.all(np.isfinite(proba))), str(proba.round(4).tolist()))
        out = r.reorder(list(prods), _eng(), _cond())
        check("重排只改顺序",
              sorted(x.smiles for x in out) == sorted(x.smiles for x in prods))
        if r.blend_hitrate > 0:
            check("blend 模型带模板统计", bool(r.tpl_stats),
                  "%d 个模板" % len(r.tpl_stats))

    # 坏模型对照：截短特征名单，必须被拒绝
    print("\n== 坏模型对照（截短特征名单）")
    base = ROOT / "reports" / "rank_model_v2.pkl"
    blob = pickle.load(base.open("rb"))
    bad = dict(blob)
    bad["features"] = list(blob["features"])[:-1]
    with tempfile.TemporaryDirectory() as td:
        bp = Path(td) / "rank_model_bad.pkl"
        pickle.dump(bad, bp.open("wb"))
        rb = RR.Reranker(str(bp))
        check("截短名单被拒绝", not rb.ok)

    print("\n失败 %d 项" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

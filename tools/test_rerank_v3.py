# -*- coding: utf-8 -*-
"""重排序 v3（模板先验特征）的守约测试。

检查：
  A 模型文件：特征列表 91 维、tpl_stats 非空、alpha/prior 合理
  B 生产公式：core/rerank.py 现算的 tpl_hitrate 与训练脚本同式（含未见模板取 prior）
  C 行长度：v3 91 维、v2 89 维，两种模型都能加载
  D 重排：只改顺序，不改候选集合
"""
from __future__ import annotations

import sys
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

import rerank as RR  # noqa: E402

V3 = ROOT / "reports" / "rank_model_v3.pkl"
V2 = ROOT / "reports" / "rank_model_v2.pkl"

fails = []


def check(name, ok, detail=""):
    print("  %s %s %s" % ("[ok] " if ok else "[FAIL]", name, detail))
    if not ok:
        fails.append(name)


def _prod(smi, tpl, rule="r1", src="CCC"):
    return types.SimpleNamespace(
        smiles=smi, template_smarts=tpl, rule_id=rule,
        source_smiles=src, partner_smiles="", activation=1.0,
        is_byproduct=False, score=0.0)


def _cond():
    return types.SimpleNamespace(
        temperature=100.0, time_min=60.0, pH=7.0, pressure_atm=1.0,
        concentration_M=0.1, solvent="water", catalyst="", atmosphere="air")


def _eng():
    return types.SimpleNamespace(cond_table={}, curated_cond_table={},
                                 mined_top_cond_table={})


def main() -> int:
    print("A 模型文件")
    r3 = RR.Reranker(str(V3))
    check("v3 可加载", r3.ok)
    check("v3 特征 61 维", len(r3.features) == 61, str(len(r3.features)))
    check("v3 tpl_stats 非空", len(r3.tpl_stats) > 1000, "%d 个模板" % len(r3.tpl_stats))
    check("v3 prior 在 (0,1)", 0.0 < r3.tpl_prior < 1.0, "%.4f" % r3.tpl_prior)
    check("特征名单含两个新列",
          "tpl_hitrate" in r3.features and "tpl_hitrate_n" in r3.features)
    import pickle as _pk
    _blob = _pk.load(open(V3, "rb"))
    check("训练带模板 dropout", 0.0 < float(_blob.get("tpl_dropout") or 0.0) < 1.0,
          "%.2f" % float(_blob.get("tpl_dropout") or 0.0))

    print("B 生产公式")
    seen = next(iter(r3.tpl_stats))
    pos, tot = r3.tpl_stats[seen]
    want_hr = (pos + r3.tpl_alpha * r3.tpl_prior) / (tot + r3.tpl_alpha)
    prods = [_prod("CCO", seen), _prod("CCN", "UNSEEN_TPL_XYZ")]
    feats = r3._features_of(prods, _eng(), _cond())
    check("两行长度 61", all(len(x) == 61 for x in feats))
    j_hr = r3.features.index("tpl_hitrate")
    j_n = r3.features.index("tpl_hitrate_n")
    check("见过的模板：命中率相同", abs(feats[0][j_hr] - want_hr) < 1e-12,
          "%.6f vs %.6f" % (feats[0][j_hr], want_hr))
    check("见过的模板：log1p(n) 相同",
          abs(feats[0][j_n] - __import__("math").log1p(tot)) < 1e-12)
    check("未见模板取 prior", abs(feats[1][j_hr] - r3.tpl_prior) < 1e-12,
          "%.6f" % feats[1][j_hr])
    check("未见模板 n=0", abs(feats[1][j_n]) < 1e-12)

    print("C 兼容 v2")
    r2 = RR.Reranker(str(V2))
    check("v2 可加载", r2.ok)
    check("v2 特征 59 维", len(r2.features) == 59, str(len(r2.features)))
    check("v2 无 tpl_stats", not r2.tpl_stats)
    f2 = r2._features_of(prods, _eng(), _cond())
    check("v2 行长度 59", all(len(x) == 59 for x in f2))

    print("D 重排只改顺序")
    prods = [_prod("CCO", seen), _prod("CCN", "UNSEEN_TPL_XYZ"), _prod("CCCl", seen)]
    out = r3.reorder(list(prods), _eng(), _cond())
    check("候选数不变", len(out) == 3)
    check("集合不变", sorted(p.smiles for p in out) == sorted(p.smiles for p in prods))

    print("\n失败 %d 项" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

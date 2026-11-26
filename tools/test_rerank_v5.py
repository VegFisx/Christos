# -*- coding: utf-8 -*-
"""重排序 v5（旧表分布 + 反应内模板候选数 + 命中率后处理）的守约测试。"""
from __future__ import annotations

import math
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

V5 = ROOT / "reports" / "rank_model_v5.pkl"
V4 = ROOT / "reports" / "rank_model_v4.pkl"

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
    print("A 模型文件")
    r5 = RR.Reranker(str(V5))
    check("v5 可加载", r5.ok)
    check("v5 特征 61 维", len(r5.features) == 61, str(len(r5.features)))
    check("含两个新特征", "tpl_in_rxn" in r5.features and "rank_frac_tpl" in r5.features)
    check("blend 已设", 0.0 < r5.blend_hitrate < 1.0, "%.2f" % r5.blend_hitrate)

    print("B 反应内模板候选数")
    prods = [_prod("CCO", "TPL_A"), _prod("CCN", "TPL_B"), _prod("CCCl", "TPL_A")]
    feats = r5._features_of(prods, _eng(), _cond())
    check("三行长度 61", all(len(x) == 61 for x in feats))
    j_n = r5.features.index("tpl_in_rxn")
    j_f = r5.features.index("rank_frac_tpl")
    check("TPL_A(2 个) 计数", abs(feats[0][j_n] - math.log1p(2)) < 1e-12,
          "%.4f" % feats[0][j_n])
    check("TPL_B(1 个) 计数", abs(feats[1][j_n] - math.log1p(1)) < 1e-12,
          "%.4f" % feats[1][j_n])
    check("TPL_A 内相对位置 0", abs(feats[0][j_f] - 0.0) < 1e-12)
    check("TPL_A 内相对位置 2/2", abs(feats[2][j_f] - 1.0) < 1e-12,
          "%.3f" % feats[2][j_f])

    print("C 重排只改顺序")
    out = r5.reorder(list(prods), _eng(), _cond())
    check("集合不变", sorted(p.smiles for p in out) == sorted(p.smiles for p in prods))

    print("D 向后兼容")
    r4 = RR.Reranker(str(V4))
    check("v4 仍可加载", r4.ok)
    check("v4 特征 59 维", len(r4.features) == 59, str(len(r4.features)))
    f4 = r4._features_of(prods, _eng(), _cond())
    check("v4 行长度 59", all(len(x) == 59 for x in f4))

    print("\n失败 %d 项" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""重排序 v4（v2 分数 + 模板命中率后处理混合）的守约测试。

  A 模型文件：59 维特征、tpl_stats 非空、blend=λ
  B 混合函数：λ=0 等于按模型分排；λ=1 等于按命中率排；0<λ<1 居中
  C 重排只改顺序，不改候选集合
  D v2 不启用混合（向后兼容）
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

V4 = ROOT / "reports" / "rank_model_v4.pkl"
V2 = ROOT / "reports" / "rank_model_v2.pkl"

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
    r4 = RR.Reranker(str(V4))
    check("v4 可加载", r4.ok)
    check("v4 特征 59 维", len(r4.features) == 59, str(len(r4.features)))
    check("v4 tpl_stats 非空", len(r4.tpl_stats) > 1000, "%d" % len(r4.tpl_stats))
    check("v4 blend=0.25", abs(r4.blend_hitrate - 0.25) < 1e-9,
          "%.3f" % r4.blend_hitrate)

    print("B 混合函数")
    # 三个命中率互不相同的模板：top0 最高、top1 居中、未见最低
    top = sorted(r4.tpl_stats, key=r4._hitrate_of, reverse=True)[:2]
    lo = "UNSEEN_TPL_XYZ"
    prods = [_prod("CCO", lo), _prod("CCN", top[0]), _prod("CCCl", top[1])]
    proba = [0.9, 0.1, 0.5]
    r4.blend_hitrate = 0.0
    check("λ=0 等于模型分序", r4._blend(prods, proba) == [1.0, 0.0, 0.5])
    r4.blend_hitrate = 1.0
    check("λ=1 等于命中率序", r4._blend(prods, proba) == [0.0, 1.0, 0.5])
    r4.blend_hitrate = 0.25
    sc = r4._blend(prods, proba)
    check("λ=0.25 公式正确", sc == [0.75, 0.25, 0.5],
          str([round(x, 3) for x in sc]))

    print("C 重排只改顺序")
    out = r4.reorder(list(prods), _eng(), _cond())
    check("数量不变", len(out) == 3)
    check("集合不变", sorted(p.smiles for p in out) == sorted(p.smiles for p in prods))
    r4.blend_hitrate = 1.0
    out1 = r4.reorder(list(prods), _eng(), _cond())
    check("λ=1 时高命中率模板排最前", out1[0].smiles == "CCN", out1[0].smiles)
    r4.blend_hitrate = 0.25

    print("D 向后兼容")
    r2 = RR.Reranker(str(V2))
    check("v2 可加载", r2.ok)
    check("v2 不启用混合", r2.blend_hitrate == 0.0, "%.3f" % r2.blend_hitrate)
    out2 = r2.reorder(list(prods), _eng(), _cond())
    check("v2 集合不变", sorted(p.smiles for p in out2) == sorted(p.smiles for p in prods))

    print("\n失败 %d 项" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

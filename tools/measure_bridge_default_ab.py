# -*- coding: utf-8 -*-
r"""同口径 A/B：TCMAI 桥（生产路径）在【K1 关闭】vs【K1 默认开】下的产物数与耗时。

为什么要这个脚本（口径先定死）：
  · 药材 = 甘草，成分上限 limit 固定（默认 60，与 tcmai_bridge.py --demo 的默认一致）
  · 引擎参数除 use_extra_templates 外完全一致（gate_conditions=True）
  · 两次跑的是同一个 predict_for_herb()，只换 bridge._ENGINE
  · 只读 tcm.db；不写 D:\TCMAI

跑法：
  & "D:\TCMAI\venv\Scripts\python.exe" tools\measure_bridge_default_ab.py 甘草 60
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "integration"))
sys.path.insert(0, str(STAGE / "core"))

import tcmai_bridge as bridge                      # noqa: E402
from smartreact_engine import SmartReactEngine     # noqa: E402

HERB = sys.argv[1] if len(sys.argv) > 1 else "甘草"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 60


def run(label: str, **kw):
    t0 = time.time()
    eng = SmartReactEngine(gate_conditions=True, verbose=False, **kw)
    t_init = time.time() - t0
    n_tpl = len(eng.extra_templates)
    bridge._ENGINE = eng          # get_engine() 是模块级单例，直接换掉
    t0 = time.time()
    res = bridge.predict_for_herb(HERB, limit=LIMIT)
    t_pred = time.time() - t0
    print(f"[{label}]")
    print(f"  note        : {eng.extra_template_note}")
    print(f"  自抽模板    : {n_tpl} 条   引擎构造 {t_init:.1f}s")
    print(f"  成分        : {res['compounds']}   预测产物: {res['n_products']}   "
          f"反应类型: {len(res['types'])}")
    for t, n in list(res["types"].items())[:8]:
        print(f"      {t:<32} {n}")
    print(f"  预测耗时    : {t_pred:.1f}s")
    print()
    return {"label": label, "n_tpl": n_tpl, "n_products": res["n_products"],
            "types": res["types"], "t_pred": t_pred, "t_init": t_init,
            "compounds": res["compounds"]}


print("=" * 92)
print(f"TCMAI 桥 A/B（只读）：{HERB} / limit={LIMIT}")
print("=" * 92)
print(f"桥的引擎构造点: integration/tcmai_bridge.py:71  get_engine()")
print()

off = run("K1 关闭（第十六轮之前的旧基线）", use_extra_templates=False)
on = run("K1 默认开（第十六轮之后）")

print("=" * 92)
print("对比")
print("=" * 92)
d = on["n_products"] - off["n_products"]
pct = (d / off["n_products"] * 100) if off["n_products"] else float("inf")
print(f"  产物数      : {off['n_products']}  ->  {on['n_products']}   "
      f"（{d:+d}，{pct:+.1f}%）")
print(f"  自抽模板贡献: {on['types'].get('mined_extra', 0)} 条 "
      f"（占新体系 {on['types'].get('mined_extra', 0) / on['n_products']:.1%}）")
print(f"  预测耗时    : {off['t_pred']:.1f}s  ->  {on['t_pred']:.1f}s   "
      f"（{on['t_pred'] / off['t_pred']:.2f}x）")
print(f"  反应类型数  : {len(off['types'])}  ->  {len(on['types'])}")
print()
print("  ★ 口径提醒：两组除 use_extra_templates 外完全一致，成分数相同 -> 可比。")

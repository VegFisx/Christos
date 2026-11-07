# -*- coding: utf-8 -*-
r"""确认 thermo（xTB ΔG）在当前环境是否真的生效，以及它会不会影响产物。

如果 thermo 生效：
  · 打分依赖 ΔG → ΔG 依赖时间预算 → 结果依赖机器负载
  · 这是第 26 轮 py hashseed 之后，第二处「环境依赖」
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

print("=" * 88)
print("① thermo_xtb 能不能导入 / xTB 二进制在不在")
print("=" * 88)
try:
    import thermo_xtb
    print("  ✓ import thermo_xtb 成功")
    print(f"    CACHE_DIR = {getattr(thermo_xtb, 'CACHE_DIR', '(无)')}")
    import inspect
    src = inspect.getsource(thermo_xtb)
    for kw in ("xtb", "XTB", "exe", "subprocess", "which"):
        for ln in src.splitlines():
            if kw in ln and ("=" in ln or "def " in ln) and not ln.strip().startswith("#"):
                s = ln.strip()
                if len(s) < 100 and any(x in s for x in ("PATH", "exe", "cmd", "which", "XTB")):
                    print(f"      {s[:92]}")
                break
except Exception as e:
    print(f"  ✗ 导入失败: {type(e).__name__}: {e}")

print()
print("=" * 88)
print("② Thermo 实例是否可用")
print("=" * 88)
from thermo import Thermo, ThermoStats
for enabled in (True, False):
    t = Thermo(enabled=enabled)
    print(f"  enabled={enabled}: available={t.available}  budget={t.budget_sec}s")

print()
print("=" * 88)
print("③ 打分时到底用没用 ΔG")
print("=" * 88)
import scorer as SC
import inspect
src = inspect.getsource(SC)
hits = [ln.strip() for ln in src.splitlines()
        if "thermo" in ln.lower() or "delta_g" in ln.lower() or "dg" in ln.lower()]
print(f"  scorer.py 里与 ΔG/thermo 相关的行：{len(hits)}")
for h in hits[:14]:
    print(f"      {h[:92]}")

print()
print("=" * 88)
print("④ 引擎实际统计：跑一小批，看 computed / budget_exhausted")
print("=" * 88)
from engine import Compound, get_mol, load_engine
import templates as T
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds
eng, rules, profs = load_engine()
print(f"  eng.thermo 存在: {getattr(eng, 'thermo', None) is not None}")
th = getattr(eng, "thermo", None)
if th is not None:
    print(f"  available={th.available}")
    s0 = dict(vars(th.stats))
    comps = []
    for h in ("甘草", "附子"):
        for r in find_compounds(h, limit=12):
            comps.append(dict(r))
    subs = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
            for c in comps if get_mol(c["smiles"])]
    cond = T.get_template("煎煮")
    ps = eng.step(subs, cond, 0.15, round_no=1)
    s1 = dict(vars(th.stats))
    print(f"  跑完 {len(ps)} 个产物后：")
    for k in s0:
        if s1.get(k, 0) != s0.get(k, 0):
            print(f"      {k}: {s0.get(k,0)} → {s1.get(k,0)}")
    if s1 == s0:
        print("      （统计无变化 —— thermo 没被调用）")

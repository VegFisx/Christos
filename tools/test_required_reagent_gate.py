# -*- coding: utf-8 -*-
r"""第十二轮：必需试剂判据的【校准 + 回归】。

三件事：
  1. 打印实测覆盖率表里每类的必需件（人要能看见判据建立在什么数字上）；
  2. 逐个场景看 cond_activation 判定（用户要的例子：Mitsunobu 缺 DEAD 就判零）；
  3. ★ 向后兼容回归 ★ 条件里一个试剂都不写时，37 类必须全部仍然放行（1.0）。
     理由：默认条件（煎煮水）不会写试剂，若这里不放行，整套默认预测会被清空。

用法: python test_required_reagent_gate.py
"""
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs",
           STAGE / "tools", Path(r"D:\TCMAI\src")):
    sys.path.insert(0, str(_p))

from model import Conditions  # noqa: E402
from smartreact_engine import REQUIRED_COV, REQUIRED_MIN_N, SmartReactEngine  # noqa: E402

PPh3 = "P(c1ccccc1)(c1ccccc1)c1ccccc1"
DEAD = "CCOC(=O)/N=N/C(=O)OCC"
DIAD = "CC(C)OC(=O)/N=N/C(=O)OC(C)C"
K2CO3 = "O=C([O-])[O-].[K+].[K+]"

eng = SmartReactEngine(gate_conditions=True)
print("=" * 96)
print("0. 覆盖率表是否载入")
print("=" * 96)
print(f"  载入类型数 {len(eng.reagent_coverage)}"
      f"（阈值：覆盖率>={REQUIRED_COV}，样本>={REQUIRED_MIN_N}）")
if not eng.reagent_coverage:
    print("  !! 覆盖率表不存在 -> 判据退化为旧的『降权 0.5』。"
          "先跑 tools/run_aux_reagent_coverage.py")

print()
print("=" * 96)
print("1. 实测必需件（按样本数排序，前 12 类）")
print("=" * 96)
for name in sorted(eng.reagent_coverage,
                   key=lambda k: -eng.reagent_coverage[k].get("n_reactions", 0))[:12]:
    e = eng.cond_table.get(name, {})
    units = eng.required_reagent_units(name, e)
    n = eng.reagent_coverage[name].get("n_reactions", 0)
    if not units:
        print(f"  {name[:28]:<30} n={n:<6} 无必需件（不参与判零）")
        continue
    desc = "; ".join(f"{u['name']}({u['coverage']:.0%}, {len(u['members'])}件)"
                     for u in units)
    print(f"  {name[:28]:<30} n={n:<6} 必需: {desc}")

print()
print("=" * 96)
print("2. 场景实测（用户要的例子）")
print("=" * 96)
CASES = [
    ("Mitsunobu 不给试剂", "mitsunobu", Conditions(solvent="thf", temperature=25)),
    ("Mitsunobu 只给 PPh3", "mitsunobu",
     Conditions(solvent="thf", temperature=25, reagents=(PPh3,))),
    ("Mitsunobu PPh3+DEAD", "mitsunobu",
     Conditions(solvent="thf", temperature=25, reagents=(PPh3, DEAD))),
    ("Mitsunobu PPh3+DIAD（等价物）", "mitsunobu",
     Conditions(solvent="thf", temperature=25, reagents=(PPh3, DIAD))),
    ("Mitsunobu 只给无关试剂", "mitsunobu",
     Conditions(solvent="thf", temperature=25, reagents=("CCO",))),
    ("Suzuki 不给碱", "suzuki", Conditions(solvent="dme", temperature=90)),
    ("Suzuki 给 K2CO3", "suzuki",
     Conditions(solvent="dme", temperature=90, reagents=(K2CO3,))),
    ("酰胺缩合 无缩合剂", "amide_coupling", Conditions(solvent="dmf", temperature=25)),
    ("酰胺缩合 HATU+HOBt", "amide_coupling",
     Conditions(solvent="dmf", temperature=25,
                reagents=("CN(C)C(=[N+](C)C)On1nnc2ccccc21", "O=Nn1nnc2ccccc21"))),
    ("Suzuki 给无关试剂", "suzuki",
     Conditions(solvent="dme", temperature=90, reagents=("CCO",))),
    ("还原胺化 只给 Et3N", "reductive_amination_aldehyde",
     Conditions(solvent="dcm", temperature=25, reagents=("CCN(CC)CC",))),
    ("还原胺化 给 NaBH3CN", "reductive_amination_aldehyde",
     Conditions(solvent="dcm", temperature=25, reagents=("[BH3-]C#N.[Na+]",))),
]
for label, rxn, cond in CASES:
    a, why = eng.cond_activation(rxn, cond)
    tag = "判零" if a == 0.0 else f"{a:.2f}"
    print(f"  {label:<30} {rxn:<16} {tag:<6} {why[:70]}")

print()
print("=" * 96)
print("3. ★ 向后兼容回归：一个试剂都不写，37 类必须全部放行 ★")
print("=" * 96)
bad = []
with_req = []
for name, e in eng.cond_table.items():
    t = e.get("temp_C") or {}
    sols = e.get("solvents") or []
    cond = Conditions(solvent=(sols[0] if sols else "water"),
                      temperature=float(t.get("default", 25.0)))
    a, why = eng.cond_activation(name, cond)
    if a != 1.0:
        bad.append((name, a, why))
    u = eng.required_reagent_units(name, e)
    if u:
        with_req.append((name, ", ".join(f"{x['name']}({x['coverage']:.0%},"
                                         f"{len(x['members'])}件)" for x in u)))
print(f"  37 类中不放行的: {len(bad)}")
for name, a, why in bad[:10]:
    print(f"    !! {name:<28} {a:.2f}  {why[:70]}")
print()
print(f"  有必需件、会参与判零的类: {len(with_req)}/{len(eng.cond_table)}")
for name, desc in with_req:
    print(f"    {name:<30} {desc}")
print()
print(f"结果：{'通过' if not bad else '失败'}（断言 {len(eng.cond_table)} 类）")
sys.exit(1 if bad else 0)

# -*- coding: utf-8 -*-
r"""E-4：辅助试剂门控实测。

三个场景（都以 mitsunobu 为例，它的 ORD 常用试剂 = PPh3 + DEAD）：
  A. 不给试剂        -> 不检查（向后兼容），分数应为 1.0
  B. 只给 PPh3       -> 命中 top-8 里的 triphenylphosphine -> 1.0
  C. 给一个无关试剂  -> 不在 top-8 -> 降权 0.5
再跑一遍真实底物，看条件里的试剂会不会改变产物清单。

用法: python test_reagent_gate.py
"""
import sys
import time
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
from smartreact_engine import SmartReactEngine  # noqa: E402

PPh3 = "P(c1ccccc1)(c1ccccc1)c1ccccc1"
DEAD = "CCOC(=O)/N=N/C(=O)OCC"

print("=" * 92)
print("① 逐个场景看 cond_activation 的判定")
print("=" * 92)
eng = SmartReactEngine(gate_conditions=True)
CASES = [
    ("不给试剂", Conditions(solvent="THF", temperature=25)),
    ("只给 PPh3", Conditions(solvent="THF", temperature=25, reagents=(PPh3,))),
    ("给 PPh3 + DEAD", Conditions(solvent="THF", temperature=25, reagents=(PPh3, DEAD))),
    ("给无关试剂(CCO)", Conditions(solvent="THF", temperature=25, reagents=("CCO",))),
]
for label, c in CASES:
    for rxn in ("mitsunobu", "suzuki", "amide_coupling"):
        a, why = eng.cond_activation(rxn, c)
        print(f"  {label:<18} {rxn:<16} 分数 {a:.2f}   {why[:78]}")
    print()

print("=" * 92)
print("② 真实底物：条件里的试剂会不会改变产物")
print("=" * 92)
try:
    from tcm_ro import open_db  # ★ 只读（AGENTS.md 四）
    from rdkit import Chem
    from engine import Compound
    subs = []
    with open_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name_en, smiles FROM compounds "
                    "WHERE smiles IS NOT NULL AND smiles != '' "
                    "AND mol_weight BETWEEN 150 AND 400 LIMIT 12")
        for nm, smi in cur.fetchall():
            m = Chem.MolFromSmiles(smi)
            if m is not None:
                subs.append((nm or "?", Chem.MolToSmiles(m)))
    print(f"  底物 {len(subs)} 个", flush=True)
    for label, c in (("煎煮100°C 无试剂", Conditions(solvent="water", temperature=100)),
                     ("煎煮100°C + PPh3", Conditions(solvent="water", temperature=100,
                                                     reagents=(PPh3,))),
                     ("室温THF + PPh3+DEAD", Conditions(solvent="organic", temperature=25,
                                                        reagents=(PPh3, DEAD)))):
        comps = [Compound(smiles=s, name=n, herb="test") for n, s in subs]
        eng.gate_stats = {}
        prods = eng.step(comps, c, round_no=1)
        types = sorted({p.rule_name for p in prods})
        print(f"  【{label}】产物 {len(prods):>4}  类型 {types}", flush=True)
except Exception as ex:
    print(f"   [warn] {type(ex).__name__}: {ex}")
print()
print("说明：无试剂时不检查是【有意为之】—— 向后兼容，")
print("      否则默认条件下所有需要试剂的反应都会被拦掉。")

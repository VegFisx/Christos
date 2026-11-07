# -*- coding: utf-8 -*-
r"""严格验证假设：6 条"未命中"是不是因为作者 example 里的叠氮写法不规范。

对比 期望产物 vs 枚举器产物 的：
  分子式 / 总电荷 / 自由基电子数 / InChI
如果分子式相同而电荷或自由基数不同 -> 是写法（价态）问题，不是规则问题。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

P = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
rows = []
for line in P.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
    f = line.split("\t")
    if len(f) == 5:
        rows.append(f)

TARGET_IDS = {"3118", "3119", "3120", "3121", "7833", "7834"}
enum = ReactionEnumerator()


def describe(smi):
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    return {
        "formula": rdMolDescriptors.CalcMolFormula(m),
        "charge": Chem.GetFormalCharge(m),
        "radicals": sum(a.GetNumRadicalElectrons() for a in m.GetAtoms()),
        "canon": Chem.MolToSmiles(m),
        "inchi": Chem.MolToInchi(m),
    }


same_formula = 0
same_charge = 0
total = 0

for rname, tid, example, smarts, cats in rows:
    if tid not in TARGET_IDS:
        continue
    lhs, rhs = example.split(">>", 1)
    ra, rb = [s for s in lhs.split(".") if s]
    try:
        res = enum.enumerate_pair(ra, rb)
    except Exception:
        continue
    produced = None
    for r in res:
        if r.reaction_name == rname and r.products:
            produced = list(r.products)[0]
            break
    if produced is None:
        continue

    e, p = describe(rhs), describe(produced)
    if not e or not p:
        continue
    total += 1
    sf = e["formula"] == p["formula"]
    sc = e["charge"] == p["charge"]
    same_formula += sf
    same_charge += sc

    print("=" * 88)
    print(f"[{rname}] id={tid}")
    print(f"  期望   : {rhs}")
    print(f"     式 {e['formula']:<22} 电荷 {e['charge']:>+2}  自由基 {e['radicals']}")
    print(f"  产出   : {produced}")
    print(f"     式 {p['formula']:<22} 电荷 {p['charge']:>+2}  自由基 {p['radicals']}")
    print(f"  分子式相同: {'✓' if sf else '✗'}    电荷相同: {'✓' if sc else '✗'}")
    print(f"  InChI 相同 : {'✓' if e['inchi'] == p['inchi'] else '✗'}")

print()
print("=" * 88)
print("结论")
print("=" * 88)
print(f"  可对比 {total} 条")
print(f"  分子式相同 {same_formula}/{total}")
print(f"  电荷相同   {same_charge}/{total}")
print()
print("  若'分子式相同但电荷不同'占多数 → 是作者 example 的叠氮价态写法问题，")
print("  而非 smartreact 规则失效。")

enum.close()

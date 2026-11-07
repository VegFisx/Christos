# -*- coding: utf-8 -*-
r"""给 SmartReact 的 37 种反应类型建【反应中心指纹】——完全数据驱动。

原理：reaction_template 是带原子映射的 SMARTS：
    [C;$(...):1][O:2].[N:3]... >> [*:2][n:3]1:...
两侧靠 :n 编号相连。所以可以直接从 SMARTS 算出：
    · 底物侧哪些映射原子之间有键
    · 产物侧哪些映射原子之间有键
    · 差集 = 成键 / 断键  -> 就是该模板的反应中心

不手写任何化学规则。
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdChemReactions  # noqa: E402

RDLogger.DisableLog("rdApp.*")

P = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
OUT = STAGE / "reports" / "reaction_center_fingerprints.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def is_carbonyl_c(a):
    if a.GetSymbol() != "C":
        return False
    for b in a.GetBonds():
        o = b.GetOtherAtom(a)
        if o.GetSymbol() in ("O", "N", "S") and b.GetBondTypeAsDouble() == 2.0:
            return True
    return False


def adesc(a):
    """原子环境描述（从图推导）。"""
    sym = a.GetSymbol()
    if sym == "N":
        if a.GetIsAromatic():
            return "唑N"
        if any(is_carbonyl_c(nb) for nb in a.GetNeighbors()):
            return "酰胺N"
        hn = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() == "H")
        return f"胺N({'NH2' if hn >= 2 else 'NH' if hn == 1 else 'N'})"
    if sym == "O":
        if a.GetIsAromatic():
            return "酚O/芳醚O"
        nc = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() == "C")
        return "醚/酯O" if nc >= 2 else "羟基O"
    s = sym
    if a.GetIsAromatic():
        s += "ar"
    elif a.IsInRing():
        s += "环"
    if is_carbonyl_c(a):
        s += "=O"
    het = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() not in ("C", "H"))
    if het:
        s += f"{1 if het == 1 else 2 if het == 2 else 3}杂"
    return s


def bonds_over_maps(mol):
    out = {}
    for b in mol.GetBonds():
        m1, m2 = b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            out[(min(m1, m2), max(m1, m2))] = True
    return out


def label(prod_mol, pair):
    a1 = next((a for a in prod_mol.GetAtoms() if a.GetAtomMapNum() == pair[0]), None)
    a2 = next((a for a in prod_mol.GetAtoms() if a.GetAtomMapNum() == pair[1]), None)
    if a1 is None or a2 is None:
        return None
    return " - ".join(sorted([adesc(a1), adesc(a2)]))


rows = []
for line in P.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
    f = line.split("\t")
    if len(f) == 5:
        rows.append(f)
print(f"模板 {len(rows)} 条\n")

type_formed = defaultdict(Counter)   # reaction_name -> Counter(成键标签)
type_broken = defaultdict(Counter)
n_ok = n_fail = 0
center_size = Counter()

for rname, tid, example, smarts, cats in rows:
    try:
        rxn = rdChemReactions.ReactionFromSmarts(smarts)
    except Exception:
        n_fail += 1
        continue
    if rxn is None or rxn.GetNumReactantTemplates() == 0 or rxn.GetNumProductTemplates() == 0:
        n_fail += 1
        continue
    n_ok += 1

    left = {}
    for i in range(rxn.GetNumReactantTemplates()):
        left.update(bonds_over_maps(rxn.GetReactantTemplate(i)))
    prod_mol = rxn.GetProductTemplate(0)
    right = bonds_over_maps(prod_mol)

    formed = set(right) - set(left)
    broken = set(left) - set(right)
    center_size[min(len(formed), 4)] += 1

    for pair in formed:
        lab = label(prod_mol, pair)
        if lab:
            type_formed[rname][lab] += 1
    for pair in broken:
        lab = label(prod_mol, pair) if pair[0] in {a.GetAtomMapNum() for a in prod_mol.GetAtoms()} else None
        if lab:
            type_broken[rname][lab] += 1

print(f"SMARTS 解析成功 {n_ok} / 失败 {n_fail}\n")
print("模板的反应中心规模（成键根数）:")
for k in sorted(center_size):
    print(f"   {k if k < 4 else '4+'} 根: {center_size[k]}")

print()
print("=" * 94)
print("★ 每种反应类型的反应中心指纹")
print("=" * 94)
for rname in sorted(type_formed, key=lambda r: -sum(type_formed[r].values())):
    tot = sum(type_formed[rname].values())
    print(f"\n  【{rname}】 成键事件 {tot}")
    for lab, v in type_formed[rname].most_common(4):
        print(f"       {v:>5}  {lab}")
    if type_broken[rname]:
        tb = type_broken[rname].most_common(2)
        print(f"       断键: " + ", ".join(f"{l}({v})" for l, v in tb))

# 反向索引：某类键 -> 哪些反应类型会形成它
rev = defaultdict(Counter)
for rname, c in type_formed.items():
    for lab, v in c.items():
        rev[lab][rname] += v

print()
print("=" * 94)
print("★ 反向索引：某种键 <- 哪些反应类型会形成")
print("=" * 94)
for lab in ["C=O2杂 - 酰胺N", "C=O3杂 - 酰胺N", "C=O1杂 - 酰胺N",
            "C1杂 - 胺N(N)", "Car1杂 - 唑N", "C1杂 - 醚/酯O",
            "Car - Car", "C=O1杂 - Car", "C=O2杂 - 羟基O"]:
    c = rev.get(lab)
    if not c:
        print(f"\n  {lab}: （没有模板形成这种键）")
        continue
    print(f"\n  {lab}:")
    for rn, v in c.most_common(6):
        print(f"       {v:>5}  {rn}")

OUT.write_text(json.dumps({
    "n_templates": len(rows), "parsed_ok": n_ok, "parsed_fail": n_fail,
    "type_formed": {k: dict(v) for k, v in type_formed.items()},
    "type_broken": {k: dict(v) for k, v in type_broken.items()},
    "reverse_index": {k: dict(v) for k, v in rev.items()},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n已存: {OUT}")

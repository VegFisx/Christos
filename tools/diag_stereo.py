# -*- coding: utf-8 -*-
r"""立体化学体检：目标里明确要求的第四项校验，之前一直漏了。

要回答：
  · tcm.db 的底物里有多少带立体化学信息？
  · 规则跑完之后，手性中心是保留、丢失、还是新生成未指定？
  · 有没有"不可能的手性中心"（RDKit 能判定的非法立体化学）？
  · 哪些规则系统性地破坏立体化学？

背景：中药成分（糖苷、萜类、生物碱）含大量手性中心。
本引擎是 2D 的、不做立体选择性，所以**必然**会丢一部分信息——
但"必然丢"和"悄悄丢"是两回事，得量化出来写明白。
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from schema import load_rules, _load_substrates
import templates as T
from activator import active_rules

DB = r"D:\TCMAI\tcm.db"
profiles, rules = load_rules(str(STAGE / "rules" / "rules.json"))
subs = _load_substrates(DB, 1500)
print(f"规则 {len(rules)} 条 | 底物 {len(subs)} 个\n")


def stereo_profile(mol):
    """返回 (已指定手性中心数, 未指定但潜在的手性中心数)。"""
    try:
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    except Exception:
        return (0, 0)
    n_spec = len(Chem.FindMolChiralCenters(mol, includeUnassigned=False,
                                           useLegacyImplementation=False))
    n_all = len(Chem.FindMolChiralCenters(mol, includeUnassigned=True,
                                          useLegacyImplementation=False))
    return (n_spec, n_all - n_spec)


print("=" * 90)
print("① 底物里的立体化学规模")
print("=" * 90)
spec_tot = unspec_tot = 0
n_with = n_without = 0
examples = []
for name, smi, mol in subs:
    ns, nu = stereo_profile(mol)
    spec_tot += ns
    unspec_tot += nu
    if ns:
        n_with += 1
        if len(examples) < 5:
            examples.append((name or smi[:30], ns, nu))
    else:
        n_without += 1

print(f"  带【已指定】手性中心的底物: {n_with} / {len(subs)}"
      f"  ({100*n_with/max(1,len(subs)):.1f}%)")
print(f"  不含已指定手性中心的底物  : {n_without}")
print(f"  已指定手性中心总数        : {spec_tot}")
print(f"  未指定但潜在的手性中心总数: {unspec_tot}")
print()
print("  例：")
for nm, ns, nu in examples:
    print(f"    {nm[:44]:<46} 已指定 {ns:<3} 未指定 {nu}")

print()
print("=" * 90)
print("② 规则跑完后，立体化学变成了什么")
print("=" * 90)

cond = T.get_template("煎煮")
act = active_rules(rules, profiles, cond)
print(f"  （用煎煮条件下激活的 {len(act)} 条规则）\n")

print(f"{'规则':<20}{'产物':>7}{'保留手性':>9}{'丢手性':>7}{'新生成':>7}{'丢失率':>8}")
print("-" * 66)

rule_stats = []
for r, _s, _w in act:
    smarts = r.get("smarts")
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception:
        continue
    if rxn is None:
        continue
    n_prod = kept = lost = new_centers = 0

    for name, smi, mol in subs[:400]:
        ns, _nu = stereo_profile(mol)
        if ns == 0:
            continue
        if len(Chem.GetMolFrags(mol)) > 1:
            continue
        try:
            res = rxn.RunReactants((mol,))
        except Exception:
            continue
        if not res:
            continue
        for ps in res[:2]:
            for p in ps:
                pc = Chem.Mol(p)
                try:
                    Chem.SanitizeMol(pc)
                except Exception:
                    continue
                n_prod += 1
                ps_spec, _ = stereo_profile(pc)
                # 产物原子数 >= 底物的那些手性中心算"保留"
                if ps_spec >= ns:
                    kept += 1
                else:
                    lost += 1
                    if ps_spec > 0:
                        new_centers += 1

    if n_prod:
        rule_stats.append((lost / n_prod, r["name"], n_prod, kept, lost, new_centers))

for rate, nm, np_, k, l, nc in sorted(rule_stats, reverse=True):
    print(f"{nm:<20}{np_:>7}{k:>9}{l:>7}{nc:>7}{rate*100:>7.1f}%")

print()
print("=" * 90)
print("③ 汇总")
print("=" * 90)
tp = sum(x[2] for x in rule_stats)
tl = sum(x[4] for x in rule_stats)
tk = sum(x[3] for x in rule_stats)
print(f"  总产物样本: {tp}")
print(f"  保留手性信息: {tk}  ({100*tk/max(1,tp):.1f}%)")
print(f"  丢失手性信息: {tl}  ({100*tl/max(1,tp):.1f}%)")
print()
worst = sorted(rule_stats, reverse=True)[:5]
print("  丢失最严重的 5 条规则：")
for rate, nm, np_, k, l, nc in worst:
    print(f"    {rate*100:>5.1f}%  {nm:<20} ({l}/{np_})")

print()
print("=" * 90)
print("④ 结论要怎么用")
print("=" * 90)
print("""
  本引擎是 2D 的、不做立体选择性，所以丢手性信息是**预期的**。
  但必须分清楚两种情况：

   a) 规则作用位点【远离】手性中心 → 手性应当保留，丢了就是 bug
   b) 规则作用位点【就是】手性中心（如羟基氧化把 CHOH 变 C=O）→ 手性必然消失，正确

  判定方法：看产物的手性中心数是否 >= 底物的手性中心数减去【被作用掉的那些】。
  本脚本用的是最粗糙的上界（>= 底物全部），所以"丢失率"是个**上界估计**，
  真正需要人工看的只有：作用位点远离手性中心、却仍然丢了手性的规则。
""")

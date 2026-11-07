# -*- coding: utf-8 -*-
r"""★ 重做未命中归因（用可信口径：原子映射定出的真反应物对）★

上一版（analyze_ord_misses.py）用 role=REACTANT 取底物，缺口被高估。
这版改用原子映射定出的真反应物对。

除了 A/B 分类，还利用原子映射给出【精确反应中心】——
按"形成的键"给缺失的化学命名，比官能团统计精确得多。

键的标注全部从分子图推导（元素/芳香性/邻接杂原子/是否羰基/是否成环），
不手写任何 SMARTS。

用法: python analyze_mapped_misses.py [抽样数]
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 2500
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
REPORTS = STAGE / "chemreact-staging" if False else STAGE / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)
OUT = REPORTS / "miss_attribution_mapped.json"


def split_rxn(cx):
    body = cx
    if "|" in cx:
        body = cx[:cx.index("|")]
    parts = [p for p in body.split(">") if p.strip()]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return None, None, None


def canon_nomap(smi):
    try:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)
    except Exception:
        return None


def bond_set(mol):
    out = set()
    for b in mol.GetBonds():
        m1, m2 = b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            out.add((min(m1, m2), max(m1, m2)))
    return out


# ---------- 原子/键标注（从图推导，非手写 SMARTS） ----------
def is_carbonyl_c(a):
    if a.GetSymbol() != "C":
        return False
    for b in a.GetBonds():
        o = b.GetOtherAtom(a)
        if o.GetSymbol() in ("O", "N", "S") and b.GetBondTypeAsDouble() == 2.0:
            return True
    return False


def adesc(a):
    s = a.GetSymbol()
    if a.GetIsAromatic():
        s += "ar"
    elif a.IsInRing():
        s += "环"
    if is_carbonyl_c(a):
        s += "=O"
    het = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() not in ("C", "H"))
    if het:
        s += f"{het}杂"
    # 氮的化学环境（关键：酰胺氮 vs 胺氮 vs 唑氮）
    if a.GetSymbol() == "N":
        if a.GetIsAromatic():
            s = "唑N"
        elif any(is_carbonyl_c(nb) for nb in a.GetNeighbors()):
            s = "酰胺N" if not a.GetIsAromatic() else s
        else:
            hn = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() == "H")
            s = f"胺N({'NH2' if hn >= 2 else 'NH' if hn == 1 else 'N'})"
    if a.GetSymbol() == "O":
        if is_carbonyl_c(a):
            pass
        nc = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() == "C")
        if a.GetIsAromatic():
            s = "酚O/芳醚O"
        elif nc >= 2:
            s = "醚/酯O"
        else:
            s = "羟基O"
    return s


con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE {N} ROWS"
).fetchall()
print(f"抽样 {len(rows)} 条\n")

enum = ReactionEnumerator()
stat = Counter()
formed_a = Counter()      # A 类缺失的成键
formed_b = Counter()      # B 类（模板触发了但产物错）的成键
broken_a = Counter()
a_by_nbonds = Counter()   # A 类：形成键数分布
formed_a1 = Counter()     # A 类且只成 1 根键
formed_a2 = Counter()     # A 类且成 2+ 根键
a_examples = []
a_multi_examples = []
seen = set()
t0 = time.time()

for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    try:
        rxn.ParseFromString(blob)
    except Exception:
        continue
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES), None)
    if cx is None:
        continue
    lhs, agents, rhs = split_rxn(cx)
    if not lhs or not rhs:
        continue

    pm_mapped = Chem.MolFromSmiles(rhs)
    if pm_mapped is None:
        continue
    prod_maps = {a.GetAtomMapNum() for a in pm_mapped.GetAtoms() if a.GetAtomMapNum() > 0}
    if not prod_maps:
        continue
    product = canon_nomap(rhs)
    if product is None:
        continue

    contributors = []
    left_bonds = set()
    for s in (x for x in lhs.split(".") if x):
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        maps = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
        if maps and len(maps & prod_maps) / len(maps) > 0.5:
            cs = canon_nomap(s)
            if cs:
                contributors.append(cs)
        left_bonds |= bond_set(m)

    if len(contributors) != 2:
        continue
    r1, r2 = sorted(contributors)
    if (r1, r2, product) in seen:
        continue
    seen.add((r1, r2, product))
    stat["可测"] += 1

    try:
        res = enum.enumerate_pair(r1, r2)
    except Exception:
        stat["枚举异常"] += 1
        continue

    got = set()
    for r in res:
        for p in r.products:
            cp = canon_nomap(p)
            if cp:
                got.add(cp)

    # 反应中心
    right_bonds = bond_set(pm_mapped)
    formed = right_bonds - left_bonds
    broken = left_bonds - right_bonds

    def label_bonds(bset):
        out = []
        for m1, m2 in bset:
            a1 = next((a for a in pm_mapped.GetAtoms() if a.GetAtomMapNum() == m1), None)
            a2 = next((a for a in pm_mapped.GetAtoms() if a.GetAtomMapNum() == m2), None)
            if a1 is None or a2 is None:
                continue
            d1, d2 = adesc(a1), adesc(a2)
            out.append(" - ".join(sorted([d1, d2])))
        return out

    if product in got:
        stat["命中"] += 1
        continue

    stat["未命中"] += 1
    nfired = len(res)
    if nfired == 0:
        stat["  └ A类: 无模板匹配"] += 1
        labs = label_bonds(formed)
        nb = len(labs)
        a_by_nbonds[min(nb, 4)] += 1
        for lab in labs:
            formed_a[lab] += 1
            if nb == 1:
                formed_a1[lab] += 1
            elif nb >= 2:
                formed_a2[lab] += 1
        for lab in label_bonds(broken):
            broken_a[lab] += 1
        if nb <= 1 and len(a_examples) < 25:
            a_examples.append({
                "reactants": [r1, r2], "product": product,
                "formed": labs, "broken": label_bonds(broken),
            })
        if nb >= 2 and len(a_multi_examples) < 10:
            a_multi_examples.append({
                "reactants": [r1, r2], "product": product, "formed": labs,
            })
    else:
        stat["  └ B类: 模板触发但产物错"] += 1
        for lab in label_bonds(formed):
            formed_b[lab] += 1

el = time.time() - t0
print(f"耗时 {el:.0f}s\n")

miss = stat["未命中"]
a = stat["  └ A类: 无模板匹配"]
b = stat["  └ B类: 模板触发但产物错"]

print("=" * 94)
print("★ 未命中构成（可信口径）")
print("=" * 94)
print(f"  可测     {stat['可测']}")
print(f"  命中     {stat['命中']}  ({stat['命中']/stat['可测']*100:.1f}%)")
print(f"  未命中   {miss}  ({miss/stat['可测']*100:.1f}%)")
if miss:
    print(f"     A 类（无模板匹配底物）  {a:>5}  ({a/miss*100:.1f}% of miss)")
    print(f"     B 类（匹配了但产物错）  {b:>5}  ({b/miss*100:.1f}% of miss)")

print()
print("=" * 94)
print("★ A 类缺失的化学：按【形成的键】命名（来自原子映射，非手写规则）")
print("=" * 94)
for lab, v in formed_a.most_common(25):
    print(f"      {v:>5}  {lab}")

print()
print("  同时【断掉的键】（前 12）:")
for lab, v in broken_a.most_common(12):
    print(f"      {v:>5}  {lab}")

print()
print("=" * 94)
print("B 类（模板触发但产物错）：形成的键（前 15）")
print("=" * 94)
for lab, v in formed_b.most_common(15):
    print(f"      {v:>5}  {lab}")

print()
print("=" * 94)
print("★★ 关键区分：A 类里，形成几根键？")
print("=" * 94)
tot_a = a
print(f"  A 类合计 {tot_a}")
for k in sorted(a_by_nbonds):
    n = a_by_nbonds[k]
    label = {0: "0 根（无成键：氧化还原/脱保护/重排）",
             1: "1 根（单步成键 -> 缺模板即可补）",
             2: "2 根（多步/环化 -> 单模板架构做不到）",
             3: "3 根（多步）", 4: "4+ 根（多步）"}.get(k, str(k))
    print(f"      {n:>5}  ({n/tot_a*100:5.1f}%)  {label}")

print()
print("  --- 只成 1 根键的 A 类：缺失的单步反应类型（前 15）---")
for lab, v in formed_a1.most_common(15):
    print(f"      {v:>5}  {lab}")

print()
print("  --- 成 2+ 根键的 A 类：多步/环化（前 15）---")
for lab, v in formed_a2.most_common(15):
    print(f"      {v:>5}  {lab}")

print()
print("  多步/环化实例:")
for e in a_multi_examples[:6]:
    print(f"      底物: {e['reactants']}")
    print(f"      产物: {e['product']}")
    print(f"      成键 {len(e['formed'])} 根: {e['formed']}")
    print()

print()
print("=" * 94)
print("A 类实例（只成 1 根键的，即真正缺模板的）")
print("=" * 94)
for e in a_examples[:10]:
    print(f"  底物: {e['reactants']}")
    print(f"  产物: {e['product']}")
    print(f"  成键: {e['formed']}   断键: {e['broken']}")
    print()

OUT.write_text(json.dumps({
    "sampled": len(rows), "stat": dict(stat),
    "a_by_nbonds": dict(a_by_nbonds),
    "formed_a": dict(formed_a), "broken_a": dict(broken_a),
    "formed_b": dict(formed_b),
    "formed_a1": dict(formed_a1), "formed_a2": dict(formed_a2),
    "a_examples": a_examples, "a_multi_examples": a_multi_examples,
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"明细已存: {OUT}")

enum.close()
con.close()

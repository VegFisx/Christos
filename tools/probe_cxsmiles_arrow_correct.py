# -*- coding: utf-8 -*-
r"""修正版：正确解析 ORD 的 CXSMILES 反应箭头。

RDKit 反应 SMILES 有两种写法：
  两段式:  底物>>产物
  三段式:  底物>试剂>产物     <-- 之前漏掉了这种（无 '>>'，但有单个 '>'）

按 '>' 拆并丢掉空段：
  2 段 -> (底物, 产物)
  3 段 -> (底物, 试剂, 产物)

重测：反应中心定位的可用率
"""
import sys
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 600


def split_rxn(cx):
    """拆成 (底物侧, 试剂侧, 产物侧)。CXSMILES 扩展块 |...| 单独剥出。"""
    ext = ""
    body = cx
    if "|" in cx:
        i = cx.index("|")
        body, ext = cx[:i], cx[i:]
    parts = [p for p in body.split(">") if p.strip()]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2], ext
    if len(parts) == 2:
        return parts[0], "", parts[1], ext
    return None, None, None, ext


def bond_set(mol):
    out = set()
    for b in mol.GetBonds():
        m1, m2 = b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            out.add((min(m1, m2), max(m1, m2)))
    return out


con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE {N} ROWS"
).fetchall()
print(f"抽样 {len(rows)} 条\n")

stat = Counter()
form = Counter()
n_contrib = Counter()
n_formed = Counter()
n_broken = Counter()
n_left = Counter()
n_agents = Counter()

for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    rxn.ParseFromString(blob)
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES), None)
    if cx is None:
        stat["无 CXSMILES"] += 1
        continue
    stat["有 CXSMILES"] += 1

    lhs, agents, rhs, ext = split_rxn(cx)
    if lhs is None:
        stat["无法拆分"] += 1
        continue
    form["三段式" if agents else "两段式"] += 1

    lcomps = [s for s in lhs.split(".") if s]
    acomp = [s for s in agents.split(".") if s] if agents else []
    n_left[min(len(lcomps), 8)] += 1
    n_agents[min(len(acomp), 5)] += 1

    pm = Chem.MolFromSmiles(rhs)
    if pm is None:
        stat["产物解析失败"] += 1
        continue
    prod_maps = {a.GetAtomMapNum() for a in pm.GetAtoms() if a.GetAtomMapNum() > 0}
    if not prod_maps:
        stat["产物无映射"] += 1
        continue
    stat["可用（有映射的完整反应）"] += 1

    contrib = 0
    left_bonds = set()
    for s in lcomps:
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        maps = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
        if maps and len(maps & prod_maps) / len(maps) > 0.5:
            contrib += 1
        left_bonds |= bond_set(m)
    n_contrib[min(contrib, 5)] += 1

    rb = bond_set(pm)
    n_formed[min(len(rb - left_bonds), 5)] += 1
    n_broken[min(len(left_bonds - rb), 5)] += 1

print("=" * 92)
print("① 可用性（修正后）")
print("=" * 92)
for k, v in stat.most_common():
    print(f"   {k:<32} {v:>5}  ({v/len(rows)*100:5.1f}%)")

print()
print("=" * 92)
print("② 箭头形式")
print("=" * 92)
for k, v in form.most_common():
    print(f"   {k:<12} {v:>5}  ({v/len(rows)*100:5.1f}%)")

print()
print("   底物侧组分数:")
for k in sorted(n_left):
    print(f"      {k if k < 8 else '8+'} 个: {n_left[k]}")
print("   试剂侧组分数:")
for k in sorted(n_agents):
    print(f"      {k if k < 5 else '5+'} 个: {n_agents[k]}")

usable = stat["可用（有映射的完整反应）"]
print()
print("=" * 92)
print("③ 反应中心定位")
print("=" * 92)
print("   ★【贡献原子到产物的组分数】分布（理想=2）:")
for k in sorted(n_contrib):
    print(f"      {k if k < 5 else '5+'} 个: {n_contrib[k]}")
good = n_contrib.get(2, 0)
print(f"\n   ★ 恰好 2 个贡献组分: {good}/{usable} = {good/usable*100 if usable else 0:.1f}%")
print("   成键条数分布:")
for k in sorted(n_formed):
    print(f"      {k if k < 5 else '5+'} 条: {n_formed[k]}")
print("   断键条数分布:")
for k in sorted(n_broken):
    print(f"      {k if k < 5 else '5+'} 条: {n_broken[k]}")

con.close()

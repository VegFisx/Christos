# -*- coding: utf-8 -*-
r"""量化：177 万条里有多少能拿来做"反应中心定位"。

上一步发现：有些 REACTION_CXSMILES 里没有 '>>'（疑似只有产物单边）。
必须先量化可用率，否则 P0.5 做不下去。

统计：
  · 有 '>>' 的比例
  · 有 '>>' 时，左侧组分数分布
  · 【贡献原子到产物的组分个数】分布  <- 理想应恰好 2 个
  · 成键/断键条数分布
"""
import sys
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402

RDLogger.DisableLog("rdApp.*")

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"

N = int(sys.argv[1]) if len(sys.argv) > 1 else 400

con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE {N} ROWS"
).fetchall()
print(f"抽样 {len(rows)} 条（来自 177 万条的文件）\n")


def bond_set(mol):
    out = set()
    for b in mol.GetBonds():
        m1, m2 = b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            out.add((min(m1, m2), max(m1, m2)))
    return out


stat = Counter()
n_left = Counter()
n_contrib = Counter()
n_formed = Counter()
n_broken = Counter()
contrib_examples = []

for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    rxn.ParseFromString(blob)
    cx = None
    for i in rxn.identifiers:
        if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES:
            cx = i.value
            break
    if cx is None:
        stat["无 CXSMILES"] += 1
        continue
    if ">>" not in cx:
        stat["★CXSMILES 无 '>>'（只有单边）"] += 1
        continue
    stat["有完整 '>>'"] += 1

    lhs, rhs = cx.split(">>", 1)
    if "|" in rhs:
        rhs = rhs.split("|", 1)[0]
    comps = [s for s in lhs.split(".") if s]
    n_left[len(comps)] += 1

    pm = Chem.MolFromSmiles(rhs)
    if pm is None:
        stat["产物解析失败"] += 1
        continue
    prod_maps = {a.GetAtomMapNum() for a in pm.GetAtoms() if a.GetAtomMapNum() > 0}
    if not prod_maps:
        stat["产物无原子映射"] += 1
        continue

    contrib = 0
    left_bonds = set()
    for s in comps:
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        maps = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
        if maps and len(maps & prod_maps) / len(maps) > 0.5:
            contrib += 1
        left_bonds |= bond_set(m)
    n_contrib[contrib] += 1

    right_bonds = bond_set(pm)
    n_formed[len(right_bonds - left_bonds)] += 1
    n_broken[len(left_bonds - right_bonds)] += 1

    if contrib == 2 and len(contrib_examples) < 5:
        contrib_examples.append((comps, contrib))

print("=" * 92)
print("① 可用性")
print("=" * 92)
tot_ok = stat["有完整 '>>'"]
for k, v in stat.most_common():
    print(f"   {k:<32} {v:>5}  ({v/len(rows)*100:5.1f}%)")

print()
print("=" * 92)
print("② 有 '>>' 的里面")
print("=" * 92)
print("   左侧组分数分布:")
for k in sorted(n_left):
    print(f"       {k} 个组分: {n_left[k]}")
print("\n   ★【贡献原子到产物的组分数】分布（理想=2）:")
for k in sorted(n_contrib):
    print(f"       {k} 个: {n_contrib[k]}")
print("\n   成键条数分布（前 6）:")
for k in sorted(n_formed)[:6]:
    print(f"       {k} 条: {n_formed[k]}")
print("\n   断键条数分布（前 6）:")
for k in sorted(n_broken)[:6]:
    print(f"       {k} 条: {n_broken[k]}")

good = sum(v for k, v in n_contrib.items() if k == 2)
print()
print(f"   ★ 恰好 2 个贡献组分（可直接定位反应物对）: {good} / {tot_ok} "
      f"= {good/tot_ok*100 if tot_ok else 0:.1f}%")

con.close()

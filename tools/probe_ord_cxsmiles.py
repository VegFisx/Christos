# -*- coding: utf-8 -*-
r"""探 ORD 的 REACTION_CXSMILES：能否解析出原子映射、定位"谁在反应"。

思路：
  带原子映射的反应 SMILES 里，每个原子有编号 :n。
  · 产物里出现的编号 -> 那些原子来自哪个底物组分 -> 该组分是【真反应物】
  · 产物里有、但底物中没有的键 -> 【成键】= 反应中心
  · 底物里有、产物中没有的键   -> 【断键】= 反应中心

先看 5 条，确认解析路径可行。
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
print(f"文件: {BIG.name} ({BIG.stat().st_size/1024**2:.1f} MB)")

con = duckdb.connect()
con.execute("SET memory_limit='1200MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') LIMIT 6").fetchall()

for k, (blob,) in enumerate(rows):
    rxn = reaction_pb2.Reaction()
    rxn.ParseFromString(blob)

    cx = None
    for i in rxn.identifiers:
        if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES:
            cx = i.value
            break
    print("=" * 92)
    print(f"【{k+1}】ReactionIdentifier 一览")
    for i in rxn.identifiers:
        tn = reaction_pb2.ReactionIdentifier.ReactionIdentifierType.Name(i.type)
        print(f"    {tn:<20} is_mapped={i.is_mapped}  len={len(i.value)}")
    if cx is None:
        print("   ✗ 没有 CXSMILES")
        continue

    print(f"    CXSMILES 长度 {len(cx)}")
    print(f"    开头 120: {cx[:120]}")
    print(f"    结尾 120: {cx[-120:]}")
    has_ext = "|" in cx
    print(f"    含 CXSMILES 扩展块 '|...|': {has_ext}")

    # 拆分
    if ">>" not in cx:
        print("   ✗ 没有 '>>'")
        continue
    lhs, rhs = cx.split(">>", 1)
    # CXSMILES 扩展块可能在最末尾，先把 '|...|' 剥掉
    ext = ""
    if "|" in rhs:
        rhs_main, _, rest = rhs.partition("|")
        ext = "|" + rest
        rhs = rhs_main
    comps = [s for s in lhs.split(".") if s]
    print(f"    左侧组分 {len(comps)} 个，扩展块: {ext!r}")

    # 解析各组分，取原子映射号
    comp_maps = []
    for s in comps:
        m = Chem.MolFromSmiles(s)
        if m is None:
            comp_maps.append((s, None))
            continue
        maps = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
        comp_maps.append((s, maps))

    pm = Chem.MolFromSmiles(rhs)
    if pm is None:
        print(f"   ✗ 产物解析失败: {rhs[:120]}")
        continue
    prod_maps = {a.GetAtomMapNum() for a in pm.GetAtoms() if a.GetAtomMapNum() > 0}
    print(f"    产物原子映射号 {len(prod_maps)} 个")

    print(f"    --- 各组分是否贡献原子到产物 ---")
    for s, maps in comp_maps:
        if maps is None:
            print(f"      [解析失败] {s[:70]}")
            continue
        shared = maps & prod_maps
        ratio = len(shared) / len(maps) if maps else 0
        tag = "★真反应物" if ratio > 0.5 else ("部分" if shared else "旁观(溶剂/试剂)")
        print(f"      {tag:<16} 贡献 {len(shared):>3}/{len(maps):<3} "
              f"({ratio*100:5.1f}%)  {s[:64]}")

    # 反应中心：成键/断键
    def bond_set(mol):
        out = set()
        for b in mol.GetBonds():
            a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
            m1, m2 = a1.GetAtomMapNum(), a2.GetAtomMapNum()
            if m1 and m2:
                out.add((min(m1, m2), max(m1, m2)))
        return out

    # 把左侧所有组分并成一个"底物侧"键集合
    left_bonds = set()
    for s, _ in comp_maps:
        m = Chem.MolFromSmiles(s)
        if m is not None:
            left_bonds |= bond_set(m)
    right_bonds = bond_set(pm)

    formed = right_bonds - left_bonds
    broken = left_bonds - right_bonds
    print(f"    --- 反应中心 ---")
    print(f"      成键 {len(formed)} 条, 断键 {len(broken)} 条")
    if formed:
        print(f"      成键样例: {sorted(formed)[:8]}")
    if broken:
        print(f"      断键样例: {sorted(broken)[:8]}")
    print()

con.close()

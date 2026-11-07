# -*- coding: utf-8 -*-
r"""跨全部 53 个 parquet 文件统计 ORD 到底给不给原子映射。

决定性问题：rxnmapper（2.5 GB GPU 折腾）到底需不需要？
  若 ORD 已有一部分自带原子映射 -> 可直接从那里抽模板，rxnmapper 降级为"补其余部分"

每个文件抽样，统计：
  · REACTION_SMILES / REACTION_CXSMILES 占比
  · is_mapped 标志
  · SMILES 文本里是否真含 ':' 原子映射
  · 反应物(Role=REACTANT)个数分布
"""
import sys
import time
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402

# --- 用描述符正确解析 reaction_role 枚举名 ---
_rf = reaction_pb2.Compound.DESCRIPTOR.fields_by_name["reaction_role"]
_role_enum = _rf.enum_type


def role_name(n):
    v = _role_enum.values_by_number.get(n)
    return v.name if v else f"<{n}>"


ORD = STAGE / "ord-data"
pq = sorted((ORD / "data").rglob("*.parquet"))

con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")

PER_FILE = 40
grand = Counter()
file_rows = []
n_reactants_dist = Counter()
role_dist = Counter()
t_start = time.time()

print(f"{'文件':<20} {'行数':>9} {'RSMILES':>8} {'CXSMILES':>9} {'is_mapped':>10} {'含:)':>7}")
print("-" * 78)

for p in pq:
    try:
        n_rows = con.execute(
            f"SELECT num_rows FROM parquet_file_metadata('{p.as_posix()}')").fetchone()[0]
    except Exception:
        n_rows = -1
    try:
        rows = con.execute(
            f"SELECT reaction FROM read_parquet('{p.as_posix()}') LIMIT {PER_FILE}").fetchall()
    except Exception as ex:
        print(f"{p.name[:18]:<20} 读取失败: {str(ex)[:40]}")
        continue

    c = Counter()
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction()
        rxn.ParseFromString(blob)
        c["n"] += 1
        for i in rxn.identifiers:
            tn = reaction_pb2.ReactionIdentifier.ReactionIdentifierType.Name(i.type)
            if tn == "REACTION_SMILES":
                c["RSMILES"] += 1
            elif tn == "REACTION_CXSMILES":
                c["CXSMILES"] += 1
                if ":" in i.value:
                    c["mapped_text"] += 1
            if i.is_mapped:
                c["is_mapped"] += 1
        # 反应物个数
        nreact = 0
        for key, inp in rxn.inputs.items():
            for comp in inp.components:
                role_dist[role_name(comp.reaction_role)] += 1
                if role_name(comp.reaction_role) == "REACTANT":
                    nreact += 1
        n_reactants_dist[nreact] += 1

    grand.update(c)
    print(f"{p.name[:18]:<20} {n_rows:>9,} {c['RSMILES']:>8} {c['CXSMILES']:>9} "
          f"{c['is_mapped']:>10} {c['mapped_text']:>7}")
    file_rows.append((p.name, n_rows, c))

print("-" * 78)
print(f"抽样合计 {grand['n']} 条反应")
print()
print("=" * 78)
print("汇总")
print("=" * 78)
print(f"  REACTION_SMILES   {grand['RSMILES']}")
print(f"  REACTION_CXSMILES {grand['CXSMILES']}")
print(f"    └ 其中文本含 ':' (真原子映射) {grand['mapped_text']}")
print(f"  is_mapped 标志置位 {grand['is_mapped']}")
print()
print("  反应物(REACTANT)个数分布:")
for k, v in sorted(n_reactants_dist.items()):
    print(f"      {k} 个反应物: {v} 条")
print()
print("  reaction_role 分布:")
for k, v in role_dist.most_common(10):
    print(f"      {k:<24} {v}")
print()
print(f"  总耗时 {time.time()-t_start:.1f}s")

# 哪些文件带映射 —— 这决定 rxnmapper 的必要性
mapped_files = [r for r in file_rows if r[2]["mapped_text"] > 0]
print()
print("=" * 78)
print(f"★ 带原子映射的文件 {len(mapped_files)}/{len(file_rows)} 个")
print("=" * 78)
for name, n_rows, c in sorted(mapped_files, key=lambda x: -x[1])[:15]:
    print(f"   {n_rows:>9,} 行  {name}  (抽样 {c['mapped_text']}/{c['n']} 带映射)")
if not mapped_files:
    print("   （抽样里一个都没有 —— 需要更大抽样或直接查那个大文件）")

con.close()

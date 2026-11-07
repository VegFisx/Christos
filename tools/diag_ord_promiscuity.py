# -*- coding: utf-8 -*-
r"""诊断 ORD 命中里的"乱枪打鸟"风险。

背景：ORD 覆盖率 42.4%，但命中榜第一是 B-H（硼烷），化学上可疑。
若某模板对一对底物吐出几十个产物，那"命中"很可能是巧合而非真实预测。

对每个命中，ReactionResult 自带该模板的产物数 -> 量化"特异度"：
  · 命中时该模板产出 1 个产物  -> 特异（强证据）
  · 命中时该模板产出很多产物    -> 可能是碰巧（弱证据）

另打印若干条 B-H 命中的真实例子，人工判断是否合理。
"""
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 600

_rf = reaction_pb2.Compound.DESCRIPTOR.fields_by_name["reaction_role"]
_role_enum = _rf.enum_type


def role_name(n):
    v = _role_enum.values_by_number.get(n)
    return v.name if v else f"<{n}>"


def canon(smi):
    try:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)
    except Exception:
        return None


ORD = STAGE / "ord-data"
pq = sorted((ORD / "data").rglob("*.parquet"))
con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")

plan = []
total_rows = 0
for p in pq:
    try:
        n = con.execute(
            f"SELECT num_rows FROM parquet_file_metadata('{p.as_posix()}')").fetchone()[0]
    except Exception:
        n = 0
    plan.append((p, n))
    total_rows += n

quota = [(p, max(15, round(TARGET * n / total_rows))) for p, n in plan if n > 40]

enum = ReactionEnumerator()

# 每个模板：命中次数、命中时产物数列表
per_tmpl = defaultdict(list)
bh_examples = []
n_test = n_hit = 0
t0 = time.time()

for p, k in quota:
    try:
        rows = con.execute(
            f"SELECT reaction_id, reaction FROM read_parquet('{p.as_posix()}') "
            f"USING SAMPLE {k} ROWS").fetchall()
    except Exception:
        continue
    for rid, blob in rows:
        rxn = reaction_pb2.Reaction()
        rxn.ParseFromString(blob)
        reactants = []
        for key, inp in rxn.inputs.items():
            for c in inp.components:
                if role_name(c.reaction_role) != "REACTANT":
                    continue
                smi = next((ci.value for ci in c.identifiers
                            if ci.type == reaction_pb2.CompoundIdentifier.SMILES), None)
                if smi is None:
                    smi = next((ci.value for ci in c.identifiers), None)
                if smi:
                    reactants.append(smi)
        products = []
        for oc in rxn.outcomes:
            for pr in oc.products:
                smi = next((ci.value for ci in pr.identifiers
                            if ci.type == reaction_pb2.CompoundIdentifier.SMILES), None)
                if smi is None:
                    smi = next((ci.value for ci in pr.identifiers), None)
                if smi:
                    products.append(smi)
        if len(reactants) != 2 or not products:
            continue
        exp = {canon(x) for x in products} - {None}
        if not exp:
            continue
        n_test += 1
        try:
            res = enum.enumerate_pair(reactants[0], reactants[1])
        except Exception:
            continue

        hit_this = False
        for r in res:
            prods = list(r.products)
            cps = {canon(x) for x in prods} - {None}
            if cps & exp:
                hit_this = True
                per_tmpl[r.reaction_name].append(len(prods))
                if r.reaction_name == "B-H" and len(bh_examples) < 6:
                    bh_examples.append({
                        "reaction_id": rid,
                        "reactants": reactants,
                        "expected": list(exp),
                        "n_products_this_tmpl": len(prods),
                        "products_sample": prods[:5],
                    })
        if hit_this:
            n_hit += 1

print(f"可测 {n_test} 条，命中 {n_hit} 条 ({n_hit/n_test*100:.1f}%)，"
      f"耗时 {time.time()-t0:.0f}s\n")

# ---------------- 特异度 ----------------
print("=" * 96)
print("各模板的'特异度'：命中时它吐了几个产物")
print("=" * 96)
print(f"{'模板':<32} {'命中':>5} {'中位产物':>8} {'均值':>7} {'仅1个产物%':>10}")
rows = []
for name, counts in per_tmpl.items():
    counts_sorted = sorted(counts)
    med = counts_sorted[len(counts_sorted) // 2]
    mean = sum(counts) / len(counts)
    one = sum(1 for c in counts if c == 1) / len(counts) * 100
    rows.append((len(counts), name, med, mean, one))
for hits, name, med, mean, one in sorted(rows, reverse=True)[:25]:
    flag = "  ← 可疑" if mean > 10 else ""
    print(f"{name:<32} {hits:>5} {med:>8} {mean:>7.1f} {one:>9.0f}%{flag}")

tot_hits = sum(len(v) for v in per_tmpl.values())
specific = sum(1 for v in per_tmpl.values() for c in v if c == 1)
print()
print(f"  命中事件合计 {tot_hits}，其中'该模板只吐 1 个产物'的占 "
      f"{specific/tot_hits*100:.1f}%")

# ---------------- B-H 的实例 ----------------
print()
print("=" * 96)
print("B-H 命中的真实例子（人工判断是否合理）")
print("=" * 96)
for e in bh_examples:
    print(f"  {e['reaction_id']}  该模板吐出 {e['n_products_this_tmpl']} 个产物")
    print(f"      底物: {e['reactants']}")
    print(f"      真实产物: {e['expected']}")
    print(f"      它吐的前 5 个: {e['products_sample']}")
    print()

enum.close()
con.close()

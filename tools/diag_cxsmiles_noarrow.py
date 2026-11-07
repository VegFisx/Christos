# -*- coding: utf-8 -*-
r"""诊断：那 79% 没有 '>>' 的 CXSMILES 到底是什么？

假设 A：它其实是【产物】单边（带原子映射）
假设 B：它其实是【底物】单边
假设 C：是别的东西

方法：把单边 SMILES 规范化（去掉原子映射号）后，
      跟 outcomes 里的产物 / inputs 里的各组分逐一比对。
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
_ci = reaction_pb2.CompoundIdentifier
_rf = reaction_pb2.Compound.DESCRIPTOR.fields_by_name["reaction_role"]
_re = _rf.enum_type

con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE 600 ROWS"
).fetchall()


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


def smi_of(c):
    v = next((x.value for x in c.identifiers if x.type == _ci.SMILES), None)
    return v if v is not None else next((x.value for x in c.identifiers), None)


stat = Counter()
detail = Counter()
examples = []
KEY_NOARROW = "noarrow"

for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    rxn.ParseFromString(blob)
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES), None)
    if cx is None or ">>" in cx:
        continue
    stat[KEY_NOARROW] += 1

    # 单边里可能有多个组分（用 '.' 分）
    if "|" in cx:
        cx = cx.split("|", 1)[0]
    parts = [s for s in cx.split(".") if s]
    part_canon = {canon(s) for s in parts} - {None}

    prods = {canon(smi_of(p)) for oc in rxn.outcomes for p in oc.products} - {None}
    reactants = {canon(smi_of(c)) for k, inp in rxn.inputs.items()
                 for c in inp.components
                 if _re.values_by_number.get(c.reaction_role) and
                 _re.values_by_number[c.reaction_role].name == "REACTANT"} - {None}

    hit_p = part_canon & prods
    hit_r = part_canon & reactants
    if hit_p and not hit_r:
        detail["= 产物（假设A 成立）"] += 1
    elif hit_r and not hit_p:
        detail["= 底物（假设B 成立）"] += 1
    elif hit_p and hit_r:
        detail["产物和底物都有匹配"] += 1
    else:
        detail["都不匹配"] += 1
        if len(examples) < 4:
            examples.append((parts, sorted(prods)[:2], sorted(reactants)[:3]))

    stat["  其中单边组分数=1"] += (len(parts) == 1)
    stat["  其中单边组分数>1"] += (len(parts) > 1)

print("=" * 92)
print("诊断：无 '>>' 的 CXSMILES 是什么")
print("=" * 92)
print(f"   无箭头记录 {stat[KEY_NOARROW]} 条")
print(f"      单边只有 1 个组分: {stat['  其中单边组分数=1']}")
print(f"      单边有多个组分:    {stat['  其中单边组分数>1']}")
print()
for k, v in detail.most_common():
    print(f"   {k:<28} {v:>5}")

if examples:
    print()
    print("   都不匹配的例子:")
    for parts, prods, reacs in examples:
        print(f"      单边: {[p[:70] for p in parts]}")
        print(f"      产物: {prods}")
        print(f"      底物: {reacs}")
        print()

con.close()
